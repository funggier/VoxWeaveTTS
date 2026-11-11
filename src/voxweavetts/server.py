"""Loopback-only text, Engine Registry, WAV preview and job queue HTTP API."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .processing import InputError, process_text
from .document_reader import prepare_document, MAX_DOCUMENT_REQUEST_BYTES
from .speech import (
    ENGINE_ID,
    EngineUnavailable,
    SpeechFailure,
    engine_info,
    list_engine_info,
    get_engine_info,
    DEFAULT_SEED,
    render_wav,
    validate_seed,
    validate_speech_request,
)
from .voice_controls import control_schema
from .presets import load_presets, save_preset
from .text_settings import load_all as load_text_settings, load_section as load_text_section, save_section as save_text_section, SettingsConflict
from .reading_progress import load_position, save_position, clear_position, ProgressConflict
from .playback_state import PlaybackState, PlaybackConflict, StreamFull
from .mode_state import ModeState, ModeConflict, MODES
from .source_manager import SourceManager
from .manual_alignment import timing_metrics
from .engine_contract import ADAPTER_API_VERSION
from .voice_controls import validate_controls
from .speech_coordinator import (
    SpeechCoordinator, QueueFull, JobMissing, JobNotReady, AlignmentConflict, EVENT_SCHEMA_VERSION,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_REQUEST_BYTES = 65_536
SYNTHESIS_SETTINGS = PROJECT_ROOT / "data" / "settings" / "synthesis.json"
GLOBAL_VOICE_SETTINGS = PROJECT_ROOT / "data" / "settings" / "global-voice.json"
_SETTINGS_LOCK = threading.RLock()
_COORDINATOR_LOCK = threading.Lock()
_COORDINATOR: SpeechCoordinator | None = None
_PLAYBACK_STATE = PlaybackState()
_MODE_LOCK = threading.Lock()
_SOURCE_LOCK = threading.Lock()


def _load_json(relative: str, default: Any) -> Any:
    path = PROJECT_ROOT / relative
    if not path.exists():
        return default
    if path.stat().st_size > MAX_REQUEST_BYTES:
        raise InputError(f"local {relative} file is too large")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"invalid local {relative} JSON: {exc}") from exc


def _read_seed() -> int:
    with _SETTINGS_LOCK:
        path = SYNTHESIS_SETTINGS
        if not path.exists():
            return DEFAULT_SEED
        if path.stat().st_size > 4096:
            raise InputError("synthesis settings file is too large")
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InputError("invalid synthesis settings file") from exc
        if not isinstance(document, dict):
            raise InputError("synthesis settings must be an object")
        return validate_seed(document.get("seed", DEFAULT_SEED))


def _save_seed(seed: int) -> None:
    """Keep seed preferences with the portable project, not browser storage."""
    seed = validate_seed(seed)
    with _SETTINGS_LOCK:
        path = SYNTHESIS_SETTINGS
        path.parent.mkdir(exist_ok=True, parents=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, prefix=".synthesis-",
                suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump({"seed": seed}, stream)
                stream.write("\n")
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def _read_global_voice() -> dict[str, Any]:
    """Global default Engine/Voice/DSP shared by all workspaces."""
    with _SETTINGS_LOCK:
        if not GLOBAL_VOICE_SETTINGS.exists():
            return {"revision": 0, "settings": None}
        try:
            if GLOBAL_VOICE_SETTINGS.stat().st_size > 4096:
                raise InputError("global voice settings file is too large")
            document = json.loads(GLOBAL_VOICE_SETTINGS.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise InputError("invalid global voice settings") from exc
        if not isinstance(document, dict) or type(document.get("revision")) is not int:
            raise InputError("invalid global voice settings structure")
        return document


def _save_global_voice(data: dict[str, Any]) -> dict[str, Any]:
    expected = data.get("expected_revision")
    if type(expected) is not int or expected < 0:
        raise InputError("expected_revision must be a nonnegative integer")
    engine_id = data.get("engine_id")
    info = get_engine_info(engine_id)
    voice_id = data.get("voice_id")
    speed = data.get("speed")
    # Validate model/voice compatibility and all shared DSP options; readiness
    # is not required to keep a preset for a temporarily uninstalled engine.
    validate_speech_request({"segments": []}, speed, voice_id, engine_id)
    controls = validate_controls(data.get("voice_controls"))
    settings = {
        "engine_id": engine_id, "voice_id": voice_id,
        "speed": float(speed), "voice_controls": controls,
    }
    with _SETTINGS_LOCK:
        current = _read_global_voice()
        if expected != current["revision"]:
            raise SettingsConflict("global voice settings were updated in another tab")
        result = {"revision": expected + 1, "settings": settings}
        path = GLOBAL_VOICE_SETTINGS
        path.parent.mkdir(exist_ok=True, parents=True)
        temp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=".global-voice-", suffix=".tmp", delete=False,
            ) as stream:
                temp = Path(stream.name)
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temp, path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        return result


def _coordinator_default() -> SpeechCoordinator:
    global _COORDINATOR
    with _COORDINATOR_LOCK:
        if _COORDINATOR is None:
            _COORDINATOR = SpeechCoordinator(render_wav)
        return _COORDINATOR


class Handler(BaseHTTPRequestHandler):
    server_version = "VoxWeaveTTS/0.3"

    def _coordinator(self) -> SpeechCoordinator:
        # Tests can inject an isolated fake renderer into their HTTP server.
        return getattr(self.server, "speech_coordinator", None) or _coordinator_default()

    def _playback_state(self) -> PlaybackState:
        # Isolate the live overlay state when testing multiple HTTP servers.
        return getattr(self.server, "playback_state", None) or _PLAYBACK_STATE

    def _mode_state(self) -> ModeState:
        # A separate ownership state per local HTTP server, including tests.
        with _MODE_LOCK:
            mode = getattr(self.server, "mode_state", None)
            if mode is None:
                mode = ModeState()
                self.server.mode_state = mode
            return mode

    def _source_manager(self) -> SourceManager:
        with _SOURCE_LOCK:
            source = getattr(self.server, "source_manager", None)
            if source is None:
                source = SourceManager()
                self.server.source_manager = source
            return source

    @staticmethod
    def _job_route(route: str) -> tuple[str, str] | None:
        parts = route.split("/")
        if (len(parts) in (4, 5) and parts[:3] == ["", "v1", "jobs"]
            and len(parts[3]) == 32
            and all(ch in "0123456789abcdef" for ch in parts[3])):
            suffix = parts[4] if len(parts) == 5 else ""
            if suffix in ("", "audio", "events", "cancel", "alignment"):
                return parts[3], suffix
        return None

    def _speech_params(self, data: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        central = _read_global_voice()["settings"] or {}
        engine_id = data.get("engine_id", central.get("engine_id", ENGINE_ID))
        info = get_engine_info(engine_id)
        default_voice = central.get("voice_id") if central.get("engine_id") == engine_id else info.voice_id
        voice_id = data.get("voice_id", default_voice)
        speed = data.get("speed", central.get("speed", 1.0))
        validate_speech_request(plan, speed, voice_id, engine_id)
        controls = validate_controls(
            data.get("voice_controls", central.get("voice_controls"))
        )
        seed = validate_seed(data.get("seed", _read_seed()))
        if not (info.assets_ready and info.runtime_ready):
            raise EngineUnavailable("selected Thai voice model is not installed or runtime is missing")
        return {
            "engine_id": engine_id, "voice_id": voice_id, "speed": speed,
            "voice_controls": controls, "seed": seed,
        }

    def _headers(self, status: int, content_type: str, length: int,
                 extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def send_json(self, status: int, body: Any) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(payload))
        self.wfile.write(payload)

    def reject_unread_post(self, status: int, body: Any) -> None:
        """Finish a small local request before returning an early HTTP error.

        Windows can abort an HTTP/1.0 connection before the caller receives
        its 403/415 response when the handler closes a socket with an unread
        POST body. Bound and time-limit the discard; never accept huge input.
        """
        length = self.headers.get("Content-Length", "")
        if length.isdecimal() and 0 < int(length) <= MAX_REQUEST_BYTES:
            previous_timeout = self.connection.gettimeout()
            try:
                self.connection.settimeout(1.0)
                self.rfile.read(int(length))
            except (OSError, TimeoutError):
                pass
            finally:
                self.connection.settimeout(previous_timeout)
        self.send_json(status, body)

    def _subtitle_mode(self) -> str:
        parameters = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
        values = parameters.get("mode", ["segment"])
        if len(values) != 1 or values[0] not in {"segment", "estimated", "activity", "manual"}:
            raise InputError("subtitle mode must be segment, estimated, activity or manual")
        return values[0]

    def _stream_modes(self) -> None:
        """Push every active-workspace change without exposing owner tokens."""
        state = self._mode_state()
        try:
            state.subscribe()
        except ModeConflict:
            self.send_json(429, {"error": "too many local mode watchers"})
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-transform")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

            def publish(snapshot: dict[str, Any]) -> None:
                payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
                self.wfile.write((
                    "id: " + str(snapshot["revision"]) + "\n"
                    + "event: workspace\n"
                    + "data: " + payload + "\n\n"
                ).encode("utf-8"))
                self.wfile.flush()

            snap = state.snapshot()
            publish(snap)
            revision = snap["revision"]
            deadline = time.monotonic() + 20.0
            heartbeat = time.monotonic()
            while time.monotonic() < deadline:
                updated = state.watch(revision, timeout=0.5)
                if updated is not None:
                    publish(updated)
                    revision = updated["revision"]
                    heartbeat = time.monotonic()
                elif time.monotonic() - heartbeat >= 6:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    heartbeat = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass
        finally:
            state.unsubscribe()

    def _stream_playback(self) -> None:
        """Short-lived SSE snapshot stream; reconnect requires no replay log.

        No per-client queue and no speech audio/body retention. Bound streams,
        reuse playback revisions, and close idle sockets after 20 seconds.
        """
        state = self._playback_state()
        mode = self._subtitle_mode()
        try:
            state.subscribe()
        except StreamFull:
            self.send_json(429, {"error": "too many local subtitle viewers"})
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-transform")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

            def publish(snapshot: dict[str, Any]) -> None:
                payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
                packet = (
                    "id: " + str(snapshot["revision"]) + "\n"
                    + "event: playback\n"
                    + "data: " + payload + "\n\n"
                ).encode("utf-8")
                self.wfile.write(packet)
                self.wfile.flush()

            snapshot = state.snapshot(mode)
            publish(snapshot)
            revision = snapshot["revision"]
            deadline = time.monotonic() + 20.0
            keepalive = time.monotonic()
            while time.monotonic() < deadline:
                update = state.watch(revision, timeout=0.5, mode=mode)
                if update is not None:
                    publish(update)
                    revision = update["revision"]
                    keepalive = time.monotonic()
                elif time.monotonic() - keepalive >= 6:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    keepalive = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            # Browsers/OBS routinely disconnect when scenes or tabs change.
            pass
        finally:
            state.unsubscribe()

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        try:
            if route in {"/", "/index.html", "/overlay", "/overlay.html", "/playback_clock.js", "/manual_alignment.js", "/waveform_editor.js", "/mode_workspace.js", "/mode_inputs.js", "/source_feed.js"}:
                name = ("source_feed.js" if route == "/source_feed.js" else
                        "mode_inputs.js" if route == "/mode_inputs.js" else
                        "mode_workspace.js" if route == "/mode_workspace.js" else
                        "waveform_editor.js" if route == "/waveform_editor.js" else
                        "manual_alignment.js" if route == "/manual_alignment.js" else
                        "playback_clock.js" if route == "/playback_clock.js"
                        else "overlay.html" if route in {"/overlay", "/overlay.html"}
                        else "index.html")
                payload = (PROJECT_ROOT / "web" / name).read_bytes()
                content_type = ("text/javascript; charset=utf-8"
                                if name.endswith(".js") else "text/html; charset=utf-8")
                self._headers(200, content_type, len(payload))
                self.wfile.write(payload)
            elif route == "/v1/status":
                info = engine_info()
                self.send_json(200, {
                    "app": "VoxWeaveTTS",
                    "version": __version__,
                    "adapter_api_version": ADAPTER_API_VERSION,
                    "event_schema_version": EVENT_SCHEMA_VERSION,
                    "foundation": False,
                    "capabilities": {
                        "text_filter": True,
                        "document_preview": True,
                        "document_queue_chunks": True,
                        "document_resume_metadata": True,
                        "document_read_ahead_playback": False,
                        "engine_registry": True,
                        "audio_preparation_queue": True,
                        "queue_events": True,
                        "audio_playback_clock": False,
                        "pronunciation_hints": True,
                        "persistent_text_settings": True,
                        "tts_audio": any(e.assets_ready and e.runtime_ready for e in list_engine_info()),
                        "reproducible_seed": info.assets_ready and info.runtime_ready,
                        "voice_cloning": False,
                        "websocket_streaming": False,
                        "live_connectors": True,
                        "youtube_live_polling": True,
                        "discord_bot_rest_polling": True,
                        "discord_client_rpc_channel_selection": True,
                        "discord_client_rpc_account_verified": False,
                        "live_credentials_persisted": False,
                        "exclusive_workspace_modes": True,
                        "workspace_mode_sse": True,
                        "shared_voice_settings": True,
                        "persistent_global_voice_defaults": True,
                        "live_discord_simulation": True,
                        "subtitle_overlay": True,
                        "browser_media_clock_reporting": True,
                        "overlay_poll_interval_ms": 1000,
                        "subtitle_sse": True,
                        "estimated_subtitle_windows": True,
                        "audio_activity_subtitles": True,
                        "audio_activity_provider": "builtin-pcm16-energy-v1",
                        "word_level_alignment": False,
                        "manual_alignment": True,
                        "manual_alignment_storage": "speech_job_memory_only",
                        "portable_executable": False,
                    },
                })
            elif route == "/v1/sources/status":
                params = parse_qs(urlsplit(self.path).query)
                mode = params.get("mode", [""])[0]
                self.send_json(200, self._source_manager().status(mode))
            elif route == "/v1/modes/state":
                self.send_json(200, self._mode_state().snapshot())
            elif route == "/v1/modes/stream":
                self._stream_modes()
            elif route == "/v1/playback/state":
                self.send_json(200, self._playback_state().snapshot(self._subtitle_mode()))
            elif route == "/v1/playback/stream":
                self._stream_playback()
            elif route == "/v1/jobs":
                self.send_json(200, {"schema_version": EVENT_SCHEMA_VERSION,
                                     "jobs": self._coordinator().list()})
            elif self._job_route(route):
                job_id, action = self._job_route(route)
                try:
                    if action in ("", "alignment"):
                        self.send_json(200, self._coordinator().get(job_id))
                    elif action == "events":
                        self.send_json(200, {
                            "schema_version": EVENT_SCHEMA_VERSION,
                            "speech_id": job_id,
                            "events": self._coordinator().events(job_id),
                        })
                    elif action == "audio":
                        wav = self._coordinator().audio(job_id)
                        self._headers(200, "audio/wav", len(wav), {
                            "X-VoxWeaveTTS-Speech-Id": job_id,
                        })
                        self.wfile.write(wav)
                    else:
                        self.send_json(404, {"error": "not found"})
                except JobMissing:
                    self.send_json(404, {"error": "speech job not found"})
                except JobNotReady:
                    self.send_json(409, {"error": "speech audio is not ready"})
            elif route == "/v1/settings/global-voice":
                self.send_json(200, _read_global_voice())
            elif route == "/v1/settings/synthesis":
                self.send_json(200, {"seed": _read_seed()})
            elif route == "/v1/engines":
                self.send_json(200, {
                    "engines": [item.as_dict() for item in list_engine_info()],
                    "control_schema": control_schema(),
                })
            elif route == "/v1/voices":
                self.send_json(200, {
                    "voices": [
                        {"id": item.voice_id, "engine_id": item.id,
                         "language": item.language, "voice_cloning": False,
                         "ready": item.assets_ready and item.runtime_ready}
                        for item in list_engine_info()
                    ]
                })
            elif route == "/v1/presets":
                self.send_json(200, {"presets": load_presets()})
            elif route == "/v1/settings/text":
                self.send_json(200, load_text_settings())
            elif route == "/v1/reading/progress":
                params = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                values = params.get("document_id", [])
                if len(values) != 1:
                    raise InputError("exactly one document_id is required")
                self.send_json(200, load_position(values[0]))
            elif route == "/v1/rules":
                self.send_json(200, load_text_section("rules")["value"])
            elif route == "/v1/pronunciations":
                self.send_json(200, load_text_section("pronunciations")["value"])
            else:
                self.send_json(404, {"error": "not found"})
        except (OSError, InputError) as exc:
            self.send_json(400, {"error": str(exc)})

    def _read_json(self, max_bytes: int = MAX_REQUEST_BYTES) -> dict[str, Any]:
        length_text = self.headers.get("Content-Length", "")
        if (not length_text.isdecimal() or not 0 < int(length_text) <= max_bytes):
            raise InputError(f"invalid or excessive Content-Length (max {max_bytes})")
        data = json.loads(self.rfile.read(int(length_text)).decode("utf-8"))
        if not isinstance(data, dict):
            raise InputError("request must be a JSON object")
        return data

    def _text_plan(self, data: dict[str, Any]) -> dict[str, Any]:
        rules = data.get("rules")
        if rules is None:
            rules = load_text_section("rules")["value"]
        dictionary = data.get("pronunciations")
        if dictionary is None:
            dictionary = load_text_section("pronunciations")["value"]
        return process_text(
            text=data.get("text"),
            rules=rules,
            pronunciations=dictionary,
            source=data.get("source", "manual"),
        )

    def do_POST(self) -> None:
        route = urlsplit(self.path).path
        job_route = self._job_route(route)
        if job_route is not None and job_route[1] == "cancel":
            if self.headers.get("X-VoxWeaveTTS-Intent") != "cancel-speech-job":
                self.reject_unread_post(403, {"error": "missing cancel intent"})
                return
            try:
                self.send_json(200, self._coordinator().cancel(job_route[0]))
            except JobMissing:
                self.send_json(404, {"error": "speech job not found"})
            return
        if route == "/v1/alignment/evaluate":
            if self.headers.get("X-VoxWeaveTTS-Intent") != "evaluate-manual-alignment":
                self.reject_unread_post(403, {"error": "missing alignment evaluation intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "evaluation requires application/json"})
                return
            try:
                data = self._read_json()
                self.send_json(200, timing_metrics(data.get("candidate"), data.get("reference")))
            except (InputError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if job_route is not None and job_route[1] == "alignment":
            if self.headers.get("X-VoxWeaveTTS-Intent") != "save-manual-alignment":
                self.reject_unread_post(403, {"error": "missing manual alignment intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "alignment requires application/json"})
                return
            try:
                data = self._read_json()
                self.send_json(200, self._coordinator().set_manual_alignment(
                    job_route[0], data.get("cues"), data.get("expected_revision")
                ))
            except JobMissing:
                self.send_json(404, {"error": "speech job not found"})
            except JobNotReady:
                self.send_json(409, {"error": "speech job is not ready"})
            except AlignmentConflict as exc:
                self.send_json(409, {"error": str(exc)})
            except (InputError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if route in {"/v1/sources/start", "/v1/sources/stop", "/v1/sources/drain"}:
            intent = {
                "/v1/sources/start": "start-live-source",
                "/v1/sources/stop": "stop-live-source",
                "/v1/sources/drain": "drain-live-source",
            }[route]
            if self.headers.get("X-VoxWeaveTTS-Intent") != intent:
                self.reject_unread_post(403, {"error": "missing source operation intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "source operation requires JSON"})
                return
            try:
                data = self._read_json()
                if not isinstance(data, dict):
                    raise InputError("source operation requires JSON object")
                sources = self._source_manager()
                if route.endswith("/start"):
                    result = sources.start(data, self._mode_state())
                elif route.endswith("/stop"):
                    result = sources.stop(data, self._mode_state())
                else:
                    result = sources.drain(data, self._mode_state())
                self.send_json(200, result)
            except ModeConflict as exc:
                self.send_json(409, {"error": str(exc)})
            except (InputError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if route == "/v1/settings/global-voice":
            if self.headers.get("X-VoxWeaveTTS-Intent") != "save-global-voice":
                self.reject_unread_post(403, {"error": "missing global voice settings intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "global voice settings require JSON"})
                return
            try:
                data = self._read_json()
                self.send_json(200, _save_global_voice(data))
            except SettingsConflict as exc:
                self.send_json(409, {"error": str(exc)})
            except (InputError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if route == "/v1/modes/activate":
            if self.headers.get("X-VoxWeaveTTS-Intent") != "activate-mode":
                self.reject_unread_post(403, {"error": "missing mode activation intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "mode activation requires application/json"})
                return
            try:
                data = self._read_json()
                activated = self._mode_state().activate(
                    data.get("mode"), self._playback_state()
                )
                # A mode change revokes any prior Live/Discord reader and
                # drops source messages not yet reviewed by the current owner.
                self._source_manager().stop_all()
                self.send_json(200, activated)
            except (InputError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if route == "/v1/playback/event":
            if self.headers.get("X-VoxWeaveTTS-Intent") != "report-playback":
                self.reject_unread_post(403, {"error": "missing playback intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "playback event requires application/json"})
                return
            try:
                data = self._read_json()
                ready_job = None
                PlaybackState._validate_event(data)
                if data.get("event") == "start":
                    ready_job = self._coordinator().get(data["speech_id"])
                result = self._mode_state().report(data, ready_job, self._playback_state())
                self.send_json(200, result)
            except JobMissing:
                self.send_json(404, {"error": "speech job not found"})
            except (PlaybackConflict, ModeConflict) as exc:
                self.send_json(409, {"error": str(exc)})
            except (InputError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if route == "/v1/documents/preview":
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "document preview requires application/json"})
                return
            try:
                data = self._read_json(MAX_DOCUMENT_REQUEST_BYTES)
                self.send_json(200, prepare_document(
                    data.get("text"), data.get("format"),
                    title=data.get("title", ""),
                    chunk_chars=data.get("chunk_chars", 350),
                    page_index=data.get("page_index", 0),
                    page_size=data.get("page_size", 15),
                ))
            except (InputError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if route == "/v1/jobs":
            if self.headers.get("X-VoxWeaveTTS-Intent") != "queue-speech":
                self.reject_unread_post(403, {"error": "missing queue intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "speech job requires application/json"})
                return
            try:
                data = self._read_json()
                plan = self._text_plan(data)
                params = self._speech_params(data, plan)
                job = self._coordinator().submit(
                    plan, engine_id=params["engine_id"], voice_id=params["voice_id"],
                    render_args=params,
                    source_message_id=data.get("source_message_id"),
                )
                self.send_json(202 if job["state"] not in {"ready", "failed"} else 200, job)
            except (InputError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
            except EngineUnavailable as exc:
                self.send_json(503, {"error": str(exc)})
            except QueueFull:
                self.send_json(429, {"error": "speech queue is full"})
            return
        if route in {"/v1/reading/progress", "/v1/reading/progress/clear"}:
            clearing = route.endswith("/clear")
            intent = "clear-reading-progress" if clearing else "save-reading-progress"
            if self.headers.get("X-VoxWeaveTTS-Intent") != intent:
                self.reject_unread_post(403, {"error": "missing reading progress update intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "reading progress must be application/json"})
                return
            try:
                body = self._read_json()
                if clearing:
                    result = clear_position(
                        body.get("document_id"), body.get("expected_revision"))
                else:
                    result = save_position(
                        body.get("document_id"),
                        chunk_chars=body.get("chunk_chars"),
                        chunk_total=body.get("chunk_total"),
                        next_chunk=body.get("next_chunk"),
                        expected_revision=body.get("expected_revision"),
                    )
                self.send_json(200, result)
            except ProgressConflict as exc:
                self.send_json(409, {"error": str(exc)})
            except (InputError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if route == "/v1/settings/text":
            if self.headers.get("X-VoxWeaveTTS-Intent") != "save-text-settings":
                self.reject_unread_post(403, {"error": "missing text settings update intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "text settings must be application/json"})
                return
            try:
                data = self._read_json()
                value = save_text_section(
                    data.get("section"), data.get("value"),
                    data.get("expected_revision"),
                )
                self.send_json(200, {"section": data["section"], **value})
            except SettingsConflict as exc:
                self.send_json(409, {"error": str(exc)})
            except (InputError, UnicodeDecodeError, json.JSONDecodeError, OSError, ValueError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if route == "/v1/settings/synthesis":
            if self.headers.get("X-VoxWeaveTTS-Intent") != "save-synthesis-settings":
                self.reject_unread_post(403, {"error": "missing settings update intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "settings must be application/json"})
                return
            try:
                data = self._read_json()
                seed = validate_seed(data.get("seed"))
                _save_seed(seed)
                self.send_json(200, {"seed": seed})
            except (InputError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if route == "/v1/presets":
            if self.headers.get("X-VoxWeaveTTS-Intent") != "save-voice-preset":
                self.reject_unread_post(403, {"error": "missing preset update intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.reject_unread_post(415, {"error": "preset must be application/json"})
                return
            try:
                result = save_preset(self._read_json())
                self.send_json(200, {"preset": result})
            except (InputError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if route not in {"/v1/text/process", "/v1/speech"}:
            self.send_json(404, {"error": "not found"})
            return
        try:
            data = self._read_json()
            plan = self._text_plan(data)
            if route == "/v1/text/process":
                self.send_json(200, plan)
                return
            wav, info = render_wav(plan, **self._speech_params(data, plan))
            headers = {
                "X-VoxWeaveTTS-Engine": info["engine_id"],
                "X-VoxWeaveTTS-Duration-Ms": str(info["duration_ms"]),
            }
            if info["seed"] is not None:
                headers["X-VoxWeaveTTS-Seed"] = str(info["seed"])
            self._headers(200, "audio/wav", len(wav), headers)
            self.wfile.write(wav)
        except (InputError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except EngineUnavailable as exc:
            self.send_json(503, {"error": str(exc)})
        except (SpeechFailure, OSError):
            self.send_json(502, {"error": "speech engine failed; check local diagnostics"})
        except Exception:
            # Third-party models may embed the original text in errors.
            # Never return a raw traceback or echo filtered text to an API client.
            self.send_json(502, {"error": "speech engine encountered an unexpected error"})

    def log_message(self, format: str, *args: Any) -> None:
        if os.environ.get("VOXWEAVETTS_HTTP_LOG") == "1":
            super().log_message(format, *args)


def serve(port: int = 8765) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("port must be 1..65535")
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"VoxWeaveTTS v{__version__} at http://127.0.0.1:{port}/",
              flush=True)
        info = engine_info()
        print(
            "Thai CPU speech available:"
            f" {info.assets_ready and info.runtime_ready}"
            " (voice cloning unavailable; live connectors require user credentials)",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping VoxWeaveTTS.")
        finally:
            global _COORDINATOR
            getattr(server, "source_manager", None) and server.source_manager.stop_all()
            with _COORDINATOR_LOCK:
                if _COORDINATOR is not None:
                    _COORDINATOR.close()
                    _COORDINATOR = None