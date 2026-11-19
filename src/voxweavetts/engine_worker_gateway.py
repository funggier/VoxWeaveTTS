"""Versioned local IPC gateway for TTS engines with independent Python runtimes.

Only application-owned, explicitly registered worker definitions can execute.
Each worker is a persistent child process; no model package can supply executable
code or override the executable path. Stdout carries line-delimited JSON only.
"""
from __future__ import annotations

import atexit
import base64
import binascii
import json
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .engine_provider_catalog import PROVIDERS, provider_for_backend

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_VERSION = 1
MAX_PCM_BYTES = 32_000_000
REQUEST_TIMEOUT = 120.0
MAX_RESPONSE_LINE = 46_000_000


class WorkerError(RuntimeError):
    """A worker is unavailable or failed without exposing private input."""


class WorkerResourceError(WorkerError):
    """The isolated worker reported insufficient memory for inference."""


@dataclass(frozen=True)
class WorkerSpec:
    backend: str
    python_dir: str
    sample_rate: int
    worker_script: str | None = None

    def python_path(self, *, root: Path = ROOT) -> Path:
        folder = root / "runtime" / "engine-envs" / self.python_dir
        return folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


# Provider recipes are curated by the application, never by a .vwmodel archive.
WORKERS = {p.backend: WorkerSpec(p.backend, p.runtime_dir, p.sample_rate)
           for p in PROVIDERS.values()}


class WorkerSession:
    """Synchronous requests over a persistent process, with bounded wait/restart."""

    def __init__(self, spec: WorkerSpec, *, root: Path = ROOT,
                 timeout: float = REQUEST_TIMEOUT,
                 runtime_manifest: dict | None = None) -> None:
        self.spec = spec
        self.root = Path(root)
        self.timeout = timeout
        self.runtime_manifest = runtime_manifest
        self._lock = threading.RLock()
        self._process: subprocess.Popen[str] | None = None
        self._lines: queue.Queue[str | None] = queue.Queue(maxsize=4)
        self._log: Any = None
        self._sequence = 0
        self.last_used = 0.0

    def running(self) -> bool:
        process = self._process
        return process is not None and process.poll() is None

    def reclaim_if_idle(self) -> bool:
        """Only unload a successfully loaded model under memory pressure.

        Never terminate a worker while it holds the synthesis lock.
        """
        if not self._lock.acquire(blocking=False):
            return False
        try:
            if not self.running():
                return False
            self._stop()
            return True
        finally:
            self._lock.release()

    def _reader(self, process: subprocess.Popen[str],
                output: queue.Queue[str | None]) -> None:
        try:
            assert process.stdout is not None
            while True:
                # readline(limit) prevents an untrusted/buggy external worker
                # from allocating arbitrary RAM with a newline-free response.
                line = process.stdout.readline(MAX_RESPONSE_LINE + 1)
                if not line:
                    break
                valid_line = (len(line) <= MAX_RESPONSE_LINE and line.endswith("\n"))
                try:
                    output.put_nowait(line if valid_line else "")
                except queue.Full:
                    break
                if not valid_line:
                    break
        finally:
            try:
                output.put_nowait(None)
            except queue.Full:
                pass

    def _start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        self._stop()
        if self.runtime_manifest is not None:
            from .portable_runtime_v3 import run_command
            try:
                command = run_command(
                    self.root, self.runtime_manifest,
                    "voxweavetts.engine_worker_host",
                    ["--backend", self.spec.backend])
            except Exception as exc:
                raise WorkerError("verified v3 runtime is unavailable") from exc
            python = Path(command[0])
        else:
            python = self.spec.python_path(root=self.root)
            if not python.is_file():
                raise WorkerError(f"isolated runtime missing: {self.spec.python_dir}")
            command = ([str(python), "-u", str(self.spec.worker_script)]
                       if self.spec.worker_script else
                       [str(python), "-u", "-m", "voxweavetts.engine_worker_host",
                        "--backend", self.spec.backend])
        log_dir = self.root / "logs" / "engine-workers"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log = (log_dir / (self.spec.backend + ".log")).open("a", encoding="utf-8")
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": str(self.root / "src"),
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HOME": str(self.root / "cache" / "huggingface"),
            "TORCH_HOME": str(self.root / "cache" / "torch"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "PIP_NO_INDEX": "1",
        })
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = subprocess.Popen(
                command,
                cwd=str(self.root), env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=self._log, text=True, encoding="utf-8",
                errors="replace", bufsize=1, creationflags=flags,
            )
        except OSError as exc:
            self._log.close()
            self._log = None
            raise WorkerError("could not start isolated TTS worker") from exc
        self._process = process
        from .process_ownership import register_process
        register_process("worker-launcher", pid=process.pid, root=self.root)
        self._lines = queue.Queue(maxsize=4)
        threading.Thread(
            target=self._reader, args=(process, self._lines),
            name="tts-worker-reader-" + self.spec.backend, daemon=True,
        ).start()

    def synthesize(self, *, text: str, voice_id: str, speed: float,
                   seed: int, engine_id: str | None = None) -> bytes:
        if not isinstance(text, str) or not text.strip() or len(text) > 5000:
            raise WorkerError("invalid worker text")
        with self._lock:
            self.last_used = time.monotonic()
            self._start()
            self._sequence += 1
            request_id = self._sequence
            request = {
                "version": PROTOCOL_VERSION, "request_id": request_id,
                "method": "synthesize", "text": text, "voice_id": voice_id,
                "speed": float(speed), "seed": int(seed),
            }
            if engine_id is not None:
                request["engine_id"] = engine_id
            try:
                assert self._process is not None and self._process.stdin is not None
                self._process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                self._process.stdin.flush()
                response_line = self._lines.get(timeout=self.timeout)
                if response_line is None:
                    raise WorkerError("TTS worker exited before replying")
                if not response_line or len(response_line) > MAX_RESPONSE_LINE:
                    raise WorkerError("TTS worker output exceeds limit")
                reply = json.loads(response_line)
                if (not isinstance(reply, dict)
                    or reply.get("version") != PROTOCOL_VERSION
                    or reply.get("request_id") != request_id):
                    raise WorkerError("TTS worker protocol mismatch")
                if reply.get("ok") is not True:
                    if reply.get("error") == "resource_exhausted":
                        raise WorkerResourceError("TTS worker ran out of available system memory")
                    raise WorkerError("TTS worker failed to synthesize")
                if reply.get("sample_rate") != self.spec.sample_rate:
                    raise WorkerError("TTS worker returned wrong sample rate")
                raw = reply.get("pcm16_b64")
                if not isinstance(raw, str) or len(raw) > (MAX_PCM_BYTES * 4 // 3 + 16):
                    raise WorkerError("TTS worker returned oversized PCM")
                pcm = base64.b64decode(raw, validate=True)
                if not pcm or len(pcm) > MAX_PCM_BYTES or len(pcm) % 2:
                    raise WorkerError("TTS worker returned invalid PCM")
                return pcm
            except (WorkerError, queue.Empty, OSError, BrokenPipeError,
                    ValueError, TypeError, binascii.Error, EOFError) as exc:
                self._stop()
                if isinstance(exc, queue.Empty):
                    raise WorkerError("TTS worker timed out") from exc
                if isinstance(exc, WorkerError):
                    raise
                raise WorkerError("TTS worker IPC failure") from exc

    def _stop(self) -> None:
        process = self._process
        self._process = None
        if process is not None:
            if process.poll() is None:
                if os.name == "nt":
                    # Windows venv Python launchers can create a second, real
                    # Python process. Killing only the launcher leaks weights.
                    try:
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            check=False, timeout=8,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        )
                    except (OSError, subprocess.TimeoutExpired):
                        process.kill()
                else:
                    process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    stream.close()
        if self._log is not None:
            self._log.close()
            self._log = None

    def close(self) -> None:
        with self._lock:
            self._stop()


class EngineWorkerGateway:
    """Stable broker interface; future TTS backends register their own WorkerSpec."""

    def __init__(self, *, root: Path = ROOT,
                 specs: dict[str, WorkerSpec] | None = None,
                 timeout: float = REQUEST_TIMEOUT) -> None:
        self.root = Path(root)
        self._allow_custom_specs = specs is not None
        self.specs = dict(WORKERS if specs is None else specs)
        self.timeout = timeout
        self._sessions: dict[str, WorkerSession] = {}
        self._lock = threading.RLock()

    def _resolve_spec(self, backend: str) -> WorkerSpec | None:
        if backend not in self.specs:
            profile = provider_for_backend(backend, root=self.root)
            if profile is not None:
                self.specs[backend] = WorkerSpec(
                    profile.backend, profile.runtime_dir, profile.sample_rate,
                    str(profile.external_worker) if profile.external_worker else None)
        return self.specs.get(backend)

    def available(self, backend: str) -> bool:
        spec = self._resolve_spec(backend)
        if spec is None:
            return False
        profile = provider_for_backend(backend, root=self.root)
        if profile is None:
            return (self._allow_custom_specs
                    and spec.python_path(root=self.root).is_file())
        from .universal_model_packages import runtime_for_provider
        return runtime_for_provider(profile.id, root=self.root) is not None

    def _reclaim_idle_for_memory(self, exclude_backend: str) -> int:
        """Keep loaded models cached unless Windows reports low memory.

        Idle workers are reclaimed oldest-first; current/busy workers are never
        interrupted. No timer and no eviction when memory is sufficient.
        """
        from .worker_memory_budget import memory_headroom
        status = memory_headroom()
        if status is None or not status.critical:
            return 0
        with self._lock:
            candidates = sorted(
                (session for name, session in self._sessions.items()
                 if name != exclude_backend),
                key=lambda session: session.last_used,
            )
        released = 0
        for session in candidates:
            status = memory_headroom()
            if status is None or not status.critical:
                break
            if session.reclaim_if_idle():
                released += 1
        return released

    def synthesize(self, backend: str, *, text: str, voice_id: str,
                   speed: float, seed: int, engine_id: str | None = None) -> bytes:
        spec = self._resolve_spec(backend)
        if spec is None or not self.available(backend):
            raise WorkerError("unregistered or unavailable worker backend")
        profile = provider_for_backend(backend, root=self.root)
        manifest = None
        key = backend
        if profile is not None:
            from .universal_model_packages import runtime_for_provider
            from .portable_runtime_v3 import fingerprint
            manifest = runtime_for_provider(profile.id, root=self.root,
                                            engine_id=engine_id)
            if manifest is None:
                raise WorkerError("selected v3 model runtime is unavailable")
            key = backend + "|" + fingerprint(manifest)
        with self._lock:
            if key not in self._sessions:
                self._sessions[key] = WorkerSession(
                    spec, root=self.root, timeout=self.timeout,
                    runtime_manifest=manifest)
            session = self._sessions[key]
        # Loading an additional model is the only proactive eviction point.
        # Reusing an already loaded, successful model never unloads it.
        if not session.running():
            self._reclaim_idle_for_memory(key)
        try:
            return session.synthesize(text=text, voice_id=voice_id,
                                      speed=speed, seed=seed, engine_id=engine_id)
        except WorkerError:
            # A pressure-driven failure can be recoverable after reclaiming an
            # idle model. Never loop forever or retry a non-memory model error.
            from .worker_memory_budget import memory_headroom
            pressure = memory_headroom()
            released = (self._reclaim_idle_for_memory(key)
                        if pressure is not None and pressure.critical else 0)
            if not released:
                raise
            return session.synthesize(text=text, voice_id=voice_id,
                                      speed=speed, seed=seed, engine_id=engine_id)

    def reset(self, backend: str) -> None:
        """Recycle a provider after packages were installed or removed."""
        with self._lock:
            names = [name for name in self._sessions
                     if name == backend or name.startswith(backend + "|")]
            sessions = [self._sessions.pop(name) for name in names]
        for session in sessions:
            session.close()

    def close(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()


_gateway = EngineWorkerGateway()
atexit.register(_gateway.close)


def gateway() -> EngineWorkerGateway:
    return _gateway
