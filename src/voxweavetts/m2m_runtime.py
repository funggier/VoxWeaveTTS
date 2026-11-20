"""Offline-only M2M100 translation worker via Universal .vwmodel v4.

The model and dependencies install solely through Universal .vwmodel v4.
No separate installer, repair mechanism or online dependencies.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_NAME = "m2m100"
REQUIREMENTS = "scripts/ai-dependencies/m2m100.txt"
MARKER = ".voxweave-ai-ready.json"
PROTOCOL = 1
MAX_LINE = 65536
MAX_TEXT = 5000
WORKER_TIMEOUT = 180.0
_LOCK = threading.RLock()


class M2MRuntimeError(RuntimeError):
    pass


def ready(root: Path = ROOT) -> bool:
    """M2M100 is ready only with an installed offline v4 translation runtime."""
    from .universal_model_v4 import installed_packages, ready as v4_ready
    return any(m["package"]["kind"] == "translation"
               and m["package"]["id"] == "m2m100-418m"
               and v4_ready(root, m) for m, _ in installed_packages(root))


class TranslationWorkerSession:
    """Reuse one loaded 418M model. All IO is bounded and serialized."""

    def __init__(self, root: Path = ROOT, timeout: float = WORKER_TIMEOUT) -> None:
        self.root = Path(root)
        self.timeout = timeout
        self._lock = threading.RLock()
        self._process: subprocess.Popen[str] | None = None
        self._output: queue.Queue[str | None] = queue.Queue(maxsize=4)
        self._log: Any = None
        self._serial = 0

    def _read(self, proc: subprocess.Popen[str],
              output: queue.Queue[str | None]) -> None:
        try:
            assert proc.stdout is not None
            while True:
                line = proc.stdout.readline(MAX_LINE + 1)
                if not line:
                    break
                valid = len(line) <= MAX_LINE and line.endswith("\n")
                try:
                    output.put_nowait(line if valid else "")
                except queue.Full:
                    break
                if not valid:
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
        if not ready(self.root):
            raise M2MRuntimeError("isolated M2M100 runtime is not installed")
        # A 418M float32 checkpoint needs several GiB of commit headroom
        # beyond its on-disk size. Windows otherwise raises OSError 1455.
        # Never unload Ollama, change the user's pagefile or stop unrelated
        # apps in an attempt to free memory.
        from .worker_memory_budget import memory_headroom
        memory = memory_headroom()
        if memory is not None and (memory.commit_available < 6 * 1024**3
                                   or memory.physical_available < 2 * 1024**3):
            raise M2MRuntimeError(
                "M2M100 requires more available Windows RAM/commit. "
                "Close unneeded applications or increase the Windows paging "
                "file; Ollama and other processes were not stopped.")
        logs = self.root / "logs" / "ai-runtime"
        logs.mkdir(parents=True, exist_ok=True)
        # Do not open a Windows-locked log until the v4 worker has been verified.
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": str(self.root / "src"),
            "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1", "PYTHONNOUSERSITE": "1",
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            # Only the isolated CPU translation process is thread-capped.
            # Do not change Core, Ollama, TTS workers or user's system env.
            "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2",
            "TOKENIZERS_PARALLELISM": "false",
            "HF_HOME": str(self.root / "cache" / "huggingface"),
            "TORCH_HOME": str(self.root / "cache" / "torch"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
        })
        from .universal_model_v4 import (
            installed_packages as v4_installed, ready as v4_ready,
            worker_command as v4_command,
        )
        v4_model = next((m for m, _ in v4_installed(self.root)
                         if m["package"]["kind"] == "translation"
                         and m["package"]["id"] == "m2m100-418m"
                         and v4_ready(self.root, m)), None)
        if v4_model is None:
            raise M2MRuntimeError("verified offline M2M100 v4 package is missing")
        command = v4_command(self.root, v4_model)
        self._log = (logs / "m2m100-worker.log").open("a", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                command,
                cwd=str(self.root), env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            self._log.close()
            self._log = None
            raise M2MRuntimeError("could not start M2M100 runtime") from exc
        self._process = proc
        from .process_ownership import register_process
        register_process("worker-launcher", pid=proc.pid, root=self.root)
        self._output = queue.Queue(maxsize=4)
        threading.Thread(target=self._read, args=(proc, self._output),
                         name="m2m100-worker-reader", daemon=True).start()

    def translate(self, text: str, settings: dict[str, Any]) -> str:
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise M2MRuntimeError("invalid M2M100 input length")
        with self._lock:
            self._start()
            self._serial += 1
            request_id = self._serial
            request = {
                "version": PROTOCOL, "request_id": request_id, "method": "translate",
                "text": text, "model": settings["model"],
                "source_language": settings["source_language"],
                "target_language": settings["target_language"],
            }
            try:
                assert self._process is not None and self._process.stdin is not None
                self._process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                self._process.stdin.flush()
                line = self._output.get(timeout=self.timeout)
                if not line or len(line) > MAX_LINE:
                    raise M2MRuntimeError("M2M100 worker exited or returned invalid output")
                response = json.loads(line)
                if not (isinstance(response, dict)
                        and response.get("version") == PROTOCOL
                        and response.get("request_id") == request_id):
                    raise M2MRuntimeError("M2M100 worker protocol mismatch")
                if response.get("ok") is not True:
                    if response.get("error") == "resource_exhausted":
                        raise M2MRuntimeError(
                            "M2M100 cannot load weights: Windows paging file "
                            "or available memory is too small (OSError 1455)")
                    raise M2MRuntimeError("M2M100 worker translation failed")
                output = response.get("text")
                if not isinstance(output, str) or not output.strip() or len(output) > MAX_TEXT:
                    raise M2MRuntimeError("M2M100 worker returned invalid text")
                return output
            except (M2MRuntimeError, queue.Empty, OSError, ValueError, TypeError) as exc:
                self._stop()
                if isinstance(exc, queue.Empty):
                    raise M2MRuntimeError("M2M100 worker timed out") from exc
                if isinstance(exc, M2MRuntimeError):
                    raise
                raise M2MRuntimeError("M2M100 worker IPC failed") from exc

    def _stop(self) -> None:
        proc = self._process
        self._process = None
        if proc is not None:
            # Close the private JSONL input first. The worker treats EOF as
            # a graceful shutdown, allowing Python/Transformers to release
            # safetensors file handles before a moved Portable is cleaned up.
            # Forced termination is reserved for stalled/failed workers.
            stdin = proc.stdin
            if stdin is not None and not stdin.closed:
                try:
                    stdin.close()
                except OSError:
                    pass
            try:
                if proc.poll() is None:
                    proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    try:
                        subprocess.run(
                            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            check=False, timeout=8,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    except (OSError, subprocess.TimeoutExpired):
                        proc.kill()
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            finally:
                if proc.stdout is not None:
                    proc.stdout.close()
                if stdin is not None and not stdin.closed:
                    stdin.close()
        if self._log is not None:
            self._log.close()
            self._log = None

    def close(self) -> None:
        with self._lock:
            self._stop()


_SESSION = TranslationWorkerSession()
atexit.register(_SESSION.close)


def translate(text: str, settings: dict[str, Any]) -> str:
    return _SESSION.translate(text, settings)


def reset() -> None:
    _SESSION.close()
