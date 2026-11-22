"""Server-owned computer playback and source-to-speech dispatch.

Web and desktop interfaces only invoke the local HTTP API. This worker is owned
by the server process, not by an open browser or Tk window.
"""
from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from .processing import InputError
from .audio_devices import (WindowsDeviceOutput, available_outputs,
                            DEFAULT_AUDIO_SETTINGS, validate_audio_settings)
from .live_audio import LiveAudioHub

RUNTIME_MODES = ("browser", "computer")
OUTPUT_DEFAULT = "default"
OUTPUT_LIVE = "live"
SOURCE_NAMES = {
    "live": "youtube-live",
    "youtube_browser": "youtube-live-browser",
    "tiktok_browser": "tiktok-live-extension",
    "discord": "discord",
    "discord_client": "discord",
}
CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "settings" / "runtime-control.json"


def read_mode(path: Path = CONFIG_PATH) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["mode"] if data["mode"] in RUNTIME_MODES else "browser"
    except (OSError, ValueError, KeyError, TypeError):
        return "browser"


def read_output(path: Path = CONFIG_PATH) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        output = data.get("output", OUTPUT_DEFAULT)
        return output if isinstance(output, str) and output else OUTPUT_DEFAULT
    except (OSError, ValueError, TypeError):
        return OUTPUT_DEFAULT


def read_audio_settings(path: Path = CONFIG_PATH) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return validate_audio_settings(data.get("audio_settings", DEFAULT_AUDIO_SETTINGS))
    except (OSError, ValueError, KeyError, TypeError):
        return dict(DEFAULT_AUDIO_SETTINGS)


def persist_mode(mode: str, path: Path = CONFIG_PATH, *, output: str | None = None,
                 audio_settings: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".runtime-",
            suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump({
                "mode": mode, "output": output or read_output(path),
                "audio_settings": validate_audio_settings(
                    audio_settings if audio_settings is not None
                    else read_audio_settings(path)
                ),
            }, stream)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class WindowsWaveOutput:
    """Playback through the machine's default Windows audio device.

    Audio is stored only in the portable cache while playing. Progress uses
    monotonic elapsed time, not the device's hardware clock, and is labelled
    accordingly in the playback API.
    """

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or CONFIG_PATH.parents[2] / "cache" / "temp"

    def play(self, wav: bytes, duration_ms: int, stop: threading.Event,
             progress: Callable[[int], None]) -> bool:
        if os.name != "nt":
            raise OSError("computer playback requires Windows")
        import winsound
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav", prefix="local-output-", dir=self.cache_dir,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(wav)
            winsound.PlaySound(str(temporary),
                               winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            started = time.monotonic()
            while not stop.wait(0.10):
                elapsed = int((time.monotonic() - started) * 1000)
                progress(min(elapsed, duration_ms))
                if elapsed >= duration_ms:
                    break
            interrupted = stop.is_set()
            if interrupted:
                winsound.PlaySound(None, 0)
            else:
                progress(duration_ms)
            return not interrupted
        finally:
            # Avoid leaving WAV copies of private chat in the portable cache.
            if temporary:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


class ComputerRuntime:
    """Single computer-output worker; HTTP clients cannot own its lifetime."""

    def __init__(self, *, port: int, coordinator: Any, source_manager: Any,
                 playback_state: Any, mode_path: Path = CONFIG_PATH,
                 output: Any = None, initial_mode: str | None = None,
                 host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self.coordinator = coordinator
        self.sources = source_manager
        self.playback = playback_state
        self.mode_path = mode_path
        self.output = output or WindowsDeviceOutput()
        self.audio_hub = LiveAudioHub()
        self._output_id = read_output(mode_path)
        self._audio_settings = read_audio_settings(mode_path)
        self._mode = initial_mode if initial_mode in RUNTIME_MODES else read_mode(mode_path)
        self._lock = threading.RLock()
        self._changed = threading.Event()
        self._shutdown = threading.Event()
        self._stop_audio = threading.Event()
        self._seen: set[str] = set()
        self._pending_messages: deque[tuple[str, dict[str, Any]]] = deque()
        self._active_id: str | None = None
        self._active_workspace: str | None = None
        self._last_completed: str | None = None
        self._last_audio: tuple[bytes, dict[str, Any]] | None = None
        self._replays: deque[tuple[bytes, dict[str, Any]]] = deque()
        self._last_error = ""
        self._completed = 0
        self._failed = 0
        self._revision = 0
        self._thread: threading.Thread | None = None
        self._job_limit_cache = 8
        self._job_limit_refreshed = 0.0

    def start(self) -> None:
        with self._lock:
            if self._thread:
                return
            self._thread = threading.Thread(
                target=self._run, daemon=True, name="voxweavetts-computer-runtime"
            )
            self._thread.start()

    def mode(self) -> str:
        with self._lock:
            return self._mode

    def configure(self, mode: Any) -> dict[str, Any]:
        if type(mode) is not str or mode not in RUNTIME_MODES:
            raise InputError("mode must be browser or computer")
        with self._lock:
            if mode != self._mode:
                persist_mode(mode, self.mode_path, output=self._output_id,
                             audio_settings=self._audio_settings)
                if mode == "computer":
                    self._seen.update(j.get("speech_id") for j in self.coordinator.list())
                self._mode = mode
                self._revision += 1
                if mode == "browser":
                    self._stop_audio.set()
                self._changed.set()
        return self.snapshot()

    def configure_output(self, output: Any) -> dict[str, Any]:
        if type(output) is not str or not 1 <= len(output) <= 256:
            raise InputError("invalid output target")
        choices = {device["id"] for device in available_outputs()}
        choices.add(OUTPUT_LIVE)
        if output not in choices:
            raise InputError("output device is not available")
        with self._lock:
            if output != self._output_id:
                persist_mode(self._mode, self.mode_path, output=output,
                             audio_settings=self._audio_settings)
                self._output_id = output
                self._stop_audio.set()
                self._revision += 1
                self._changed.set()
        return self.snapshot()

    def configure_audio(self, settings: Any) -> dict[str, Any]:
        try:
            options = validate_audio_settings(settings)
        except ValueError as exc:
            raise InputError(str(exc)) from exc
        with self._lock:
            if options != self._audio_settings:
                persist_mode(self._mode, self.mode_path, output=self._output_id,
                             audio_settings=options)
                self._audio_settings = options
                self._revision += 1
                self._changed.set()
        return self.snapshot()

    def replay_latest(self) -> dict[str, Any]:
        with self._lock:
            if self._mode != "computer":
                raise ValueError("computer runtime is not enabled")
            if self._last_audio is None:
                raise ValueError("no completed audio is available")
            if len(self._replays) >= 3:
                raise ValueError("replay queue is full")
            self._replays.append(self._last_audio)
            # Replay is an API command; interrupt the current output and start
            # the new playback from the beginning, in the selected destination.
            self._stop_audio.set()
            self._revision += 1
            self._changed.set()
        return {"accepted": True, "queued_replays": len(self._replays)}

    def stop_audio(self) -> dict[str, Any]:
        with self._lock:
            self._stop_audio.set()
            self._changed.set()
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self._mode,
                "output": self._output_id,
                "audio_settings": dict(self._audio_settings),
                "actual_audio_format": (
                    dict(self.output.last_format)
                    if isinstance(self.output, WindowsDeviceOutput)
                    and self.output.last_format is not None else None
                ),
                "available_outputs": available_outputs() + [
                    {"id": OUTPUT_LIVE, "label": "Live broadcast to browser", "api": "network"}],
                "listeners": self.audio_hub.count,
                "worker_running": self._thread is not None and self._thread.is_alive(),
                "audio_state": "playing" if self._active_id else "idle",
                "active_speech_id": self._active_id,
                "active_workspace": self._active_workspace,
                "pending_source_messages": len(self._pending_messages),
                "job_states": self.job_counts(),
                "max_outstanding_jobs": self.max_outstanding_jobs(),
                "last_completed_speech_id": self._last_completed,
                "completed": self._completed,
                "failed": self._failed,
                "last_error": self._last_error,
                "revision": self._revision,
                "clock_basis": "computer_monotonic_estimate",
                "sources": {name: self.sources.status(name)
                            for name in SOURCE_NAMES},
            }

    def max_outstanding_jobs(self) -> int:
        """Bound computer Live admissions to saved prepare/ready queue limits."""
        now = time.monotonic()
        if now - self._job_limit_refreshed >= 3.0:
            try:
                from .source_queue_settings import load_settings
                records = load_settings()["modes"]
                capacities = [
                    records[mode]["settings"]["prepare_queue_limit"]
                    + records[mode]["settings"]["ready_audio_queue_limit"]
                    for mode in SOURCE_NAMES if mode in records
                ]
                self._job_limit_cache = max(6, min(48, max(capacities, default=8)))
            except (OSError, ValueError, KeyError, TypeError):
                self._job_limit_cache = 8
            self._job_limit_refreshed = now
        return self._job_limit_cache

    def job_counts(self) -> dict[str, int]:
        counts = {key: 0 for key in (
            "preparing", "prepared", "queued", "rendering", "ready",
            "failed", "skipped", "cancelled",
        )}
        for job in self.coordinator.list():
            name = job.get("state")
            if name in counts:
                if name != "ready" or job.get("speech_id") not in self._seen:
                    counts[name] += 1
        return counts

    def outstanding_jobs(self) -> int:
        counts = self.job_counts()
        return sum(counts[key] for key in
                   ("preparing", "prepared", "queued", "rendering", "ready"))

    def shutdown(self) -> None:
        self._shutdown.set()
        self._stop_audio.set()
        self._changed.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=3.0)

    def _enqueue_via_api(self, mode: str, msg: dict[str, Any]) -> bool:
        """Use exactly the same speech API/pipeline as desktop and web."""
        message_id = str(msg.get("message_id", ""))
        from .mode_voice_settings import (
            DEFAULT_SPEECH_FORMAT, load_workspace_settings,
        )
        import re
        preferences = load_workspace_settings()
        options = {
            **DEFAULT_SPEECH_FORMAT,
            **preferences.get("speech_formats", {}).get(mode, {}),
        }
        # Core must obey the same saved per-mode voice and source formatting
        # as the web controller. New browser windows are not an input to this.
        if msg.get("kind") == "gift" or not options["read_comments"]:
            return True
        def say_emojis(text: str) -> str:
            words = options.get("emoji_dictionary", {}) if options["read_emojis"] else {}
            if not words:
                return text
            pattern = re.compile("|".join(re.escape(key)
                                  for key in sorted(words, key=len, reverse=True)))
            return pattern.sub(lambda match: words[match.group(0)], text)
        content = say_emojis(msg["text"])
        sender_prefix_text = ""
        author = msg.get("author", "") if preferences.get("sender_names", {}).get(mode, False) else ""
        if author:
            author = " ".join(author.split())[:80]
            if mode in ("live", "youtube_browser") and not options["read_name_at"]:
                author = author.lstrip("@").strip()
            if author:
                prefix = options["sender_prefix"]
                name = (prefix + " " if prefix and not author.startswith(prefix) else "") + say_emojis(author)
                sender_prefix_text = " ".join(
                    part for part in (name, options["separator"]) if part
                )
        data = {
            "text": " ".join(part for part in (sender_prefix_text, content) if part),
            "content_text": content,
            "sender_prefix_text": sender_prefix_text,
            "source": SOURCE_NAMES[mode],
            "mode": mode,
            "source_message_id": message_id[:128] or None,
            "hold_for_render": True,
        }
        voice = preferences.get("modes", {}).get(mode)
        if voice:
            data.update(voice)
        request = Request(
            f"http://{self.host}:{self.port}/v1/jobs",
            data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-VoxWeaveTTS-Intent": "queue-speech",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=12) as response:
                status = response.status
            return status in (200, 202)
        except HTTPError as exc:
            if exc.code == 429 or exc.code >= 500:
                return False
            # A permanently invalid job must not block every later message.
            with self._lock:
                self._failed += 1
                self._last_error = "A source message could not be queued"
            return True
        except (URLError, TimeoutError, OSError):
            return False

    def _drain_sources(self) -> None:
        # Backpressure at the source boundary: no silent message deletion.
        headroom = self.max_outstanding_jobs() - self.outstanding_jobs()
        if headroom <= 0:
            return
        if len(self._pending_messages) < headroom:
            for mode, msg in self.sources.take_for_runtime(
                limit=min(4, headroom - len(self._pending_messages))
            ):
                self._pending_messages.append((mode, msg))
        for _ in range(min(headroom, len(self._pending_messages))):
            mode, msg = self._pending_messages[0]
            if not self._enqueue_via_api(mode, msg):
                break
            self._pending_messages.popleft()

    def _play_job(self, job: dict[str, Any]) -> None:
        speech_id = job["speech_id"]
        workspace = job.get("source") or "studio"
        # The source is not always a UI workspace (e.g. youtube-live).
        workspace = {
            "youtube-live": "live", "youtube-live-browser": "youtube_browser",
            "tiktok-live-extension": "tiktok_browser",
        }.get(workspace, workspace)
        if workspace not in {"studio", "queue", "reader", "live",
                            "youtube_browser", "tiktok_browser", "discord",
                            "discord_client", "tiktok"}:
            workspace = "studio"
        wav = self.coordinator.audio(speech_id)
        self._play_audio(wav, job, workspace)

    def _play_audio(self, wav: bytes, job: dict[str, Any], workspace: str) -> None:
        speech_id = job["speech_id"]
        duration_ms = job["audio"]["duration_ms"]
        session_id = uuid4().hex
        sequence = 0
        def report(event: str, position: int) -> None:
            nonlocal sequence
            sequence += 1
            try:
                self.playback.report({
                    "session_id": session_id, "speech_id": speech_id,
                    "event": event, "position_ms": position,
                    "sequence": sequence,
                }, ready_job=job if event == "start" else None,
                   workspace=workspace, clock_basis="computer_monotonic_estimate")
            except Exception:
                # Audio must not stop because an optional overlay failed.
                pass
        with self._lock:
            self._active_id = speech_id
            self._active_workspace = workspace
            self._revision += 1
            self._stop_audio.clear()
        report("start", 0)
        try:
            with self._lock:
                target = self._output_id
            if target == OUTPUT_LIVE:
                finished = self.audio_hub.broadcast(
                    wav, self._stop_audio, lambda position: report("progress", position)
                )
            else:
                if isinstance(self.output, WindowsDeviceOutput):
                    finished = self.output.play(
                        wav, duration_ms, self._stop_audio,
                        lambda position: report("progress", position), target,
                        settings=dict(self._audio_settings),
                    )
                else:
                    finished = self.output.play(
                        wav, duration_ms, self._stop_audio,
                        lambda position: report("progress", position), target
                    )
            report("ended" if finished else "stopped",
                   duration_ms if finished else 0)
            with self._lock:
                if finished:
                    self._completed += 1
                    self._last_completed = speech_id
                    self._last_audio = (wav, job)
        except Exception as exc:
            report("stopped", 0)
            # Show the device-format failure without ever exposing raw chat.
            detail = str(exc).replace("\r", " ").replace("\n", " ")[:190]
            with self._lock:
                self._failed += 1
                self._last_error = (
                    "Audio output error: " + type(exc).__name__
                    + (": " + detail if detail else "")
                )
        finally:
            with self._lock:
                self._active_id = None
                self._active_workspace = None
                self._revision += 1

    def _run(self) -> None:
        while not self._shutdown.is_set():
            if self.mode() == "computer":
                try:
                    self._drain_sources()
                    if self._replays:
                        with self._lock:
                            if self._replays:
                                wav, job = self._replays.popleft()
                            else:
                                wav, job = None, None
                        if wav is not None and job is not None:
                            workspace = {
                                "youtube-live":"live",
                                "youtube-live-browser":"youtube_browser",
                                "tiktok-live-extension":"tiktok_browser",
                            }.get(job.get("source"), job.get("source") or "studio")
                            self._play_audio(wav, job, workspace)
                            continue
                    for job in self.coordinator.list():
                        job_id = job.get("speech_id")
                        if not job_id or job_id in self._seen:
                            continue
                        state = job.get("state")
                        if state == "prepared":
                            # Stage one FIFO speech at a time; no WAV burst.
                            try:
                                self.coordinator.start_render(job_id)
                            except Exception:
                                pass
                            break
                        elif state == "ready":
                            self._seen.add(job_id)
                            self._play_job(job)
                            break
                        elif state in {"failed", "skipped", "cancelled"}:
                            self._seen.add(job_id)
                        elif state in {"preparing", "queued", "rendering"}:
                            # Preserve FIFO even if a newer AI job finishes first.
                            break
                    # Bound tracking to the in-memory job collection.
                    if len(self._seen) > 1000:
                        known = {j.get("speech_id") for j in self.coordinator.list()}
                        self._seen.intersection_update(known)
                except Exception:
                    with self._lock:
                        self._last_error = "Computer runtime worker encountered an error"
                        self._failed += 1
            self._changed.wait(0.25)
            self._changed.clear()
