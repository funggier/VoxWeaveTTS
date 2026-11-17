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
from .managed_runtime_pool import inspect_environment, pin_fields

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
        if not valid:
            return False
        recipe = provider.requirements_path(root)
        recipe_hash = hashlib.sha256(recipe.read_bytes()).hexdigest() if recipe.is_file() else None
        return inspect_environment(
            root=Path(root), folder=folder, python=provider.python_path(root),
            marker=marker, expected_recipe_hash=recipe_hash)["ready"]
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def _execute(command: list[str], *, root: Path, log: Any) -> None:
    # No shell, no user/model-supplied executable paths or pip arguments.
    # Keep all uv / model download caches inside this portable installation.
    # Browser-triggered installs do not go through Install-EngineProvider.ps1,
    # so setting environment only in the CLI wrapper is insufficient.
    cache = Path(root) / "cache"
    temp = cache / "temp"
    for path in (cache / "uv", cache / "huggingface", cache / "torch", temp):
        path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "UV_CACHE_DIR": str(cache / "uv"),
        "UV_LINK_MODE": "copy",
        "HF_HOME": str(cache / "huggingface"),
        "TORCH_HOME": str(cache / "torch"),
        "XDG_CACHE_HOME": str(cache),
        "TEMP": str(temp),
        "TMP": str(temp),
    })
    result = subprocess.run(
        command, cwd=str(root), stdout=log, stderr=subprocess.STDOUT,
        timeout=INSTALL_TIMEOUT, check=False, env=env,
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
    from .runtime_tools import find_uv
    uv = find_uv(root)
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
    if marker.is_file():
        health = inspect_environment(
            root=root, folder=runtime, python=profile.python_path(root),
            marker=marker, expected_recipe_hash=hashlib.sha256(requirements.read_bytes()).hexdigest())
        if health["repair_required"]:
            raise InstallError("existing runtime requires explicit offline repair; normal install refused")
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
        **pin_fields(root, hashlib.sha256(requirements.read_bytes()).hexdigest()),
    }, indent=2) + "\n", encoding="utf-8")
    return runtime


def repair(provider_id: str, *, root: Path = ROOT) -> Path:
    """Explicit offline, transactional rebuild of one trusted TTS worker venv."""
    from .managed_runtime_pool import atomic_rebuild
    profile = all_providers(root).get(provider_id)
    if profile is None:
        raise InstallError("unknown or unapproved engine provider")
    root = Path(root)
    requirements = profile.requirements_path(root)
    if not requirements.is_file() or requirements.is_symlink():
        raise InstallError("trusted provider requirements missing")
    from .runtime_tools import find_uv
    uv = find_uv(root)
    if not uv:
        raise InstallError("uv is unavailable; repair cannot proceed offline")
    base_python = root / ".venv" / "Scripts" / "python.exe"
    if not base_python.is_file():
        base_python = root / "runtime" / "python" / "python.exe"
    if not base_python.is_file():
        base_python = Path(sys.executable)
    if not base_python.is_file():
        raise InstallError("Python 3.11 base runtime is missing")
    folder = profile.python_path(root).parent.parent
    marker = folder / ".voxweave-ready.json"
    try:
        old = json.loads(marker.read_text(encoding="utf-8"))
        if (old.get("provider") != profile.id
            or old.get("backend") != profile.backend or old.get("protocol") != 1):
            raise InstallError("not an application-managed provider runtime")
    except (OSError, ValueError, AttributeError) as exc:
        raise InstallError("provider runtime marker is missing or invalid") from exc
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    approved_hash = (hashlib.sha256((profile.plugin_path / "approved.json").read_bytes()).hexdigest()
                     if profile.plugin_path is not None else None)
    log_dir = root / "logs" / "engine-workers"
    log_dir.mkdir(parents=True, exist_ok=True)
    def build(stage: Path) -> None:
        staged_python = stage / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        with (log_dir / ("repair-" + profile.id + ".log")).open("a", encoding="utf-8") as log:
            _execute([uv, "venv", "--offline", str(stage), "--python", str(base_python)],
                     root=root, log=log)
            _execute([uv, "pip", "install", "--offline", "--python", str(staged_python),
                      "--link-mode", "copy", "-r", str(requirements)], root=root, log=log)
            _execute([uv, "pip", "check", "--offline", "--python", str(staged_python)],
                     root=root, log=log)
        (stage / ".voxweave-ready.json").write_text(json.dumps({
            "provider": profile.id, "backend": profile.backend, "protocol": 1,
            "completed_at": int(time.time()), "approval_hash": approved_hash,
            **pin_fields(root, digest),
        }, indent=2) + "\n", encoding="utf-8")
    def verify(stage: Path) -> bool:
        report = inspect_environment(
            root=root, folder=stage,
            python=stage / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
            marker=stage / ".voxweave-ready.json", expected_recipe_hash=digest)
        return report["ready"] and report["location_pinned"]
    def quiesce() -> None:
        if root.resolve() == ROOT.resolve():
            from .engine_worker_gateway import gateway
            gateway().reset(profile.backend)
    def verify_final(final: Path) -> bool:
        if not verify(final):
            return False
        final_python = final / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        with (log_dir / ("repair-" + profile.id + ".log")).open("a", encoding="utf-8") as log:
            # Ensure the activated path actually launches and its dependencies
            # remain coherent. Stage-path-only checks are insufficient after
            # moving Windows virtual environments to their final folder.
            _execute([str(final_python), "-c",
                      "import sys; from pathlib import Path; "
                      "assert Path(sys.prefix).resolve() == Path(sys.argv[1]).resolve()",
                      str(final)], root=root, log=log)
            _execute([uv, "pip", "check", "--offline", "--python",
                      str(final_python)], root=root, log=log)
        return True

    atomic_rebuild(root=root, folder=folder, build=build,
                   verify=verify, quiesce=quiesce,
                   verify_activated=verify_final)
    return folder


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
        if profile.python_path(ROOT).parent.parent.is_dir():
            recipe = profile.requirements_path(ROOT)
            digest = hashlib.sha256(recipe.read_bytes()).hexdigest() if recipe.is_file() else None
            info = inspect_environment(root=ROOT, folder=profile.python_path(ROOT).parent.parent,
                python=profile.python_path(ROOT),
                marker=profile.python_path(ROOT).parent.parent / ".voxweave-ready.json",
                expected_recipe_hash=digest)
            if info["repair_required"]:
                return {"id": provider_id, "state": "repair_required",
                        "error": info["state"]}
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
