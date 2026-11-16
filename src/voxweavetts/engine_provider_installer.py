"""One-click setup for trusted engine providers in separate, portable-local venvs.

Model .vwmodel metadata cannot supply install commands/dependencies. Installation
recipes are part of the trusted app code and always target runtime/engine-envs.
"""
from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

from .engine_provider_catalog import Provider, ROOT, all_providers

_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}
INSTALL_TIMEOUT = 900


class InstallError(RuntimeError):
    pass


def ready(provider: Provider, *, root: Path = ROOT) -> bool:
    folder = provider.python_path(root).parent.parent
    marker = folder / ".voxweave-ready.json"
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
        valid = (provider.python_path(root).is_file()
                 and state.get("provider") == provider.id
                 and state.get("backend") == provider.backend
                 and state.get("protocol") == 1)
        if provider.plugin_path is not None:
            approval = provider.plugin_path / "approved.json"
            valid = valid and state.get("approval_hash") == hashlib.sha256(
                approval.read_bytes()).hexdigest()
        return valid
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def _execute(command: list[str], *, root: Path, log: Any) -> None:
    # No shell, no user/model-supplied executable paths or pip arguments.
    result = subprocess.run(
        command, cwd=str(root), stdout=log, stderr=subprocess.STDOUT,
        timeout=INSTALL_TIMEOUT, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise InstallError("provider environment installation failed; see logs/engine-workers")


def install(provider_id: str, *, root: Path = ROOT) -> Path:
    """Synchronous install, intentionally used by background jobs / CLI."""
    profile = all_providers(root).get(provider_id)
    if profile is None:
        raise InstallError("unknown or untrusted engine provider")
    root = Path(root)
    uv = shutil.which("uv")
    if not uv:
        raise InstallError("uv is not installed")
    main_python = (root / ".venv" / "Scripts" / "python.exe")
    if not main_python.is_file():
        main_python = root / "runtime" / "python" / "python.exe"
    if not main_python.is_file():
        # Developer fallback; never create venv inside the system Python.
        main_python = Path(sys.executable)
    if not main_python.is_file():
        raise InstallError("no Python interpreter available for worker")
    requirements = profile.requirements_path(root)
    if not requirements.is_file():
        raise InstallError("trusted provider requirements missing")
    runtime = profile.python_path(root).parent.parent
    runtime.parent.mkdir(parents=True, exist_ok=True)
    log_dir = root / "logs" / "engine-workers"
    log_dir.mkdir(parents=True, exist_ok=True)
    marker = runtime / ".voxweave-ready.json"
    # A partial previous environment is never advertised as ready.
    marker.unlink(missing_ok=True)
    with (log_dir / ("install-" + profile.id + ".log")).open("a", encoding="utf-8") as log:
        if not profile.python_path(root).is_file():
            _execute([uv, "venv", str(runtime), "--python", str(main_python)],
                     root=root, log=log)
        _execute([uv, "pip", "install", "--python", str(profile.python_path(root)),
                  "--link-mode", "copy", "-r", str(requirements)],
                 root=root, log=log)
        _execute([uv, "pip", "check", "--python", str(profile.python_path(root))],
                 root=root, log=log)
    approved_hash = (hashlib.sha256((profile.plugin_path / "approved.json").read_bytes()).hexdigest()
                     if profile.plugin_path is not None else None)
    marker.write_text(json.dumps({
        "provider": profile.id, "backend": profile.backend, "protocol": 1,
        "completed_at": int(time.time()), "approval_hash": approved_hash,
    }, indent=2) + "\n", encoding="utf-8")
    return runtime


def install_async(provider_id: str, *, root: Path = ROOT) -> dict[str, Any]:
    if provider_id not in all_providers(root):
        raise InstallError("unknown engine provider")
    with _LOCK:
        current = _JOBS.get(provider_id)
        if current and current["state"] == "installing":
            return dict(current)
        if ready(all_providers(root)[provider_id], root=root):
            status = {"id": provider_id, "state": "ready", "error": None}
            _JOBS[provider_id] = status
            return dict(status)
        state = {"id": provider_id, "state": "installing", "error": None}
        _JOBS[provider_id] = state

    def run() -> None:
        try:
            install(provider_id, root=root)
            state_name, error = "ready", None
        except (InstallError, OSError, subprocess.TimeoutExpired) as exc:
            state_name, error = "failed", str(exc)
        with _LOCK:
            _JOBS[provider_id] = {
                "id": provider_id, "state": state_name, "error": error,
            }

    threading.Thread(target=run, name="install-tts-provider-" + provider_id,
                     daemon=True).start()
    return dict(state)


def status(provider_id: str) -> dict[str, Any]:
    profile = all_providers().get(provider_id)
    if profile is None:
        raise InstallError("unknown engine provider")
    with _LOCK:
        task = dict(_JOBS.get(provider_id, {}))
    if task.get("state") != "installing":
        if ready(profile):
            return {"id": provider_id, "state": "ready", "error": None}
        return task or {"id": provider_id, "state": "not_installed", "error": None}
    return task


def catalog_status() -> list[dict[str, Any]]:
    from .engine_provider_catalog import provider_status
    return [{**entry, **{"install": status(entry["id"])}}
            for entry in provider_status()]


def main() -> None:
    import argparse
    from .engine_provider_catalog import approve_provider_folder
    parser = argparse.ArgumentParser(
        description="Install isolated TTS provider dependencies without altering the main venv")
    parser.add_argument("operation", choices=("install", "approve-install"))
    parser.add_argument("provider_id")
    parser.add_argument("--trust-executable-code", action="store_true")
    args = parser.parse_args()
    if args.operation == "approve-install":
        if not args.trust_executable_code:
            parser.error("approve-install requires --trust-executable-code")
        provider_path = ROOT / "extensions" / "engine-providers" / args.provider_id
        approved = approve_provider_folder(provider_path, trust_code=True)
        print("Approved engine provider", approved.id, flush=True)
    print("Installing", args.provider_id, flush=True)
    installed = install(args.provider_id)
    print("Runtime ready:", installed, flush=True)


if __name__ == "__main__":
    main()
