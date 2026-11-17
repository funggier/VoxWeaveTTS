"""Install and use optional M2M100 in its own portable-local Python runtime.

The .vwmodel is data-only. It never supplies commands, import paths or code.
A trusted, pinned runtime recipe is installed only after explicit user action.
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
_JOBS: dict[str, Any] = {"state": "not_installed", "error": None}


class M2MRuntimeError(RuntimeError):
    pass


def python_path(root: Path = ROOT) -> Path:
    base = Path(root) / "runtime" / "ai-envs" / RUNTIME_NAME
    return base / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _recipe_hash(root: Path) -> str:
    recipe = Path(root) / REQUIREMENTS
    with recipe.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def ready(root: Path = ROOT) -> bool:
    root = Path(root)
    try:
        state = json.loads((python_path(root).parent.parent / MARKER).read_text(encoding="utf-8"))
        return bool(python_path(root).is_file()
                    and state == {"runtime": RUNTIME_NAME, "protocol": PROTOCOL,
                                  "recipe_hash": _recipe_hash(root)})
    except (OSError, ValueError, TypeError):
        return False


def _execute(command: list[str], *, root: Path, log: Any) -> None:
    from .engine_provider_installer import _execute as execute_provider
    execute_provider(command, root=root, log=log)


def install(root: Path = ROOT) -> Path:
    """Install fixed application-owned deps. No .vwmodel can choose packages."""
    root = Path(root)
    uv = shutil.which("uv")
    if not uv:
        raise M2MRuntimeError("uv is required to install M2M100 runtime")
    recipe = root / REQUIREMENTS
    if not recipe.is_file():
        raise M2MRuntimeError("M2M100 trusted dependency recipe is missing")
    base_python = root / ".venv" / "Scripts" / "python.exe"
    if not base_python.is_file():
        base_python = root / "runtime" / "python" / "python.exe"
    if not base_python.is_file():
        base_python = Path(sys.executable)
    if not base_python.is_file():
        raise M2MRuntimeError("Python 3.11 runtime is unavailable")
    worker_python = python_path(root)
    folder = worker_python.parent.parent
    folder.parent.mkdir(parents=True, exist_ok=True)
    marker = folder / MARKER
    marker.unlink(missing_ok=True)
    log_dir = root / "logs" / "ai-runtime"
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        with (log_dir / "install-m2m100.log").open("a", encoding="utf-8") as log:
            if not worker_python.is_file():
                _execute([uv, "venv", str(folder), "--python", str(base_python)],
                         root=root, log=log)
            _execute([uv, "pip", "install", "--python", str(worker_python),
                      "--link-mode", "copy", "-r", str(recipe)], root=root, log=log)
            _execute([uv, "pip", "check", "--python", str(worker_python)],
                     root=root, log=log)
            _execute([str(worker_python), "-c",
                      "import torch, transformers, sentencepiece, safetensors"],
                     root=root, log=log)
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        raise M2MRuntimeError("M2M100 runtime installation failed; see logs/ai-runtime/install-m2m100.log") from exc
    state = {"runtime": RUNTIME_NAME, "protocol": PROTOCOL,
             "recipe_hash": _recipe_hash(root)}
    temporary = folder / (MARKER + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(marker)
    return folder


def install_async(root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    with _LOCK:
        if _JOBS["state"] == "installing":
            return dict(_JOBS)
        if ready(root):
            _JOBS.update(state="ready", error=None)
            return dict(_JOBS)
        _JOBS.update(state="installing", error=None)

    def work() -> None:
        try:
            install(root)
            status = {"state": "ready", "error": None}
        except M2MRuntimeError as exc:
            status = {"state": "failed", "error": str(exc)}
        with _LOCK:
            _JOBS.update(status)
    threading.Thread(target=work, name="install-ai-m2m100", daemon=True).start()
    return {"state": "installing", "error": None}


def status(root: Path = ROOT) -> dict[str, Any]:
    with _LOCK:
        job = dict(_JOBS)
    if job["state"] == "installing":
        return job
    if ready(root):
        return {"state": "ready", "error": None}
    return job if job["state"] == "failed" else {"state": "not_installed", "error": None}


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
        if memory is not None and (memory.commit_available < 4 * 1024**3
                                   or memory.physical_available < 2 * 1024**3):
            raise M2MRuntimeError(
                "M2M100 requires more available Windows RAM/commit. "
                "Close unneeded applications or increase the Windows paging "
                "file; Ollama and other processes were not stopped.")
        logs = self.root / "logs" / "ai-runtime"
        logs.mkdir(parents=True, exist_ok=True)
        self._log = (logs / "m2m100-worker.log").open("a", encoding="utf-8")
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": str(self.root / "src"),
            "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1", "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HOME": str(self.root / "cache" / "huggingface"),
            "TORCH_HOME": str(self.root / "cache" / "torch"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
        })
        try:
            proc = subprocess.Popen(
                [str(python_path(self.root)), "-u", "-m", "voxweavetts.m2m_worker"],
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
            if proc.poll() is None:
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
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            for stream in (proc.stdin, proc.stdout):
                if stream is not None:
                    stream.close()
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


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Install optional isolated M2M100 runtime")
    parser.add_argument("operation", choices=("install", "status"))
    args = parser.parse_args()
    if args.operation == "status":
        print(json.dumps(status(), ensure_ascii=False), flush=True)
        return
    folder = install()
    print("M2M100 isolated runtime installed:", folder, flush=True)


if __name__ == "__main__":
    main()
