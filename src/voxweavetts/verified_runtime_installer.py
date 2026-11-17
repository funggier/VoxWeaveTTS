"""Explicit user-approved, offline and hash-pinned runtime installation.

Uses trusted application recipe/lock only. Wheel data never selects commands,
paths, executable modules, network endpoints or the target environment.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

from .engine_provider_catalog import PROVIDERS, ROOT
from .engine_provider_installer import _execute
from .managed_runtime_pool import (atomic_install, atomic_rebuild,
                                    inspect_environment, pin_fields)
from .offline_wheelhouse import (WheelhouseError, _safe_id, _digest,
                                 _lock_path, _recipe, verified_wheels)

IMPORT_CHECKS: dict[str, str] = {
    "pythaitts": "import pythaitts, onnxruntime, numpy, pythainlp",
    "vachana": "import vachanatts, ssg, onnxruntime, numpy, pythainlp",
    "kokoro": "import kokoro_onnx, numpy, misaki, onnxruntime",
    "sherpa": "import sherpa_onnx, numpy",
    "m2m100": "import torch, transformers, sentencepiece, safetensors, numpy",
}
PYTHON_NAME = "Scripts/python.exe" if os.name == "nt" else "bin/python"


class VerifiedInstallError(RuntimeError):
    pass


def _base_python(root: Path) -> Path:
    for candidate in (root / ".venv" / "Scripts" / "python.exe",
                      root / "runtime" / "python" / "python.exe",
                      Path(sys.executable)):
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    raise VerifiedInstallError("Python 3.11 base interpreter is missing")


def _environment(root: Path, runtime_id: str) -> tuple[Path, str, dict]:
    if runtime_id not in IMPORT_CHECKS:
        raise VerifiedInstallError("runtime not approved for verified wheel installation")
    if runtime_id == "m2m100":
        return (root / "runtime" / "ai-envs" / "m2m100",
                ".voxweave-ai-ready.json",
                {"runtime": "m2m100", "protocol": 1})
    profile = PROVIDERS[runtime_id]
    return (profile.python_path(root).parent.parent, ".voxweave-ready.json",
            {"provider": profile.id, "backend": profile.backend,
             "protocol": 1, "approval_hash": None,
             "completed_at": int(time.time())})


def install_verified(runtime_id: str, *, root: Path = ROOT) -> Path:
    """Install missing runtime, or repair non-ready runtime with exact wheels.

    Caller must verify the user's explicit intent and current runtime recipe
    fingerprint. This synchronous method is also suitable for local CLI tests.
    """
    root = Path(root)
    runtime_id = _safe_id(runtime_id)
    folder, marker, identity = _environment(root, runtime_id)
    recipe_hash = _digest(_recipe(root, runtime_id))
    uv = shutil.which("uv")
    if not uv:
        raise VerifiedInstallError("uv is required to create a verified runtime")
    base_python = _base_python(root)
    folder.parent.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink() or folder.parent.is_symlink():
        raise VerifiedInstallError("runtime folder is redirected")
    from .runtime_registry import inventory
    item = next((x for x in inventory(root) if x["id"] == runtime_id), None)
    if item is None or item["ready"]:
        raise VerifiedInstallError("runtime is already ready or not allowlisted")
    if item["installed"] and not item["repair_required"]:
        raise VerifiedInstallError("existing runtime requires a distinct repair diagnosis")
    # Refuse an unmanaged, damaged or redirected existing venv. A repair must
    # not delete an arbitrary folder by merely occupying a known runtime name.
    if folder.exists():
        existing_marker = folder / marker
        try:
            previous = json.loads(existing_marker.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise VerifiedInstallError("existing runtime is not safely managed") from exc
        if any(previous.get(k) != v for k, v in identity.items()
               if k not in ("completed_at", "approval_hash")):
            raise VerifiedInstallError("runtime owner/protocol marker mismatch")
    log_dir = root / "logs" / ("ai-runtime" if runtime_id == "m2m100"
                                else "engine-workers")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / ("install-verified-" + runtime_id + ".log")
    with verified_wheels(root, runtime_id) as (wheels, lock_file):
        # All wheel bytes are copied and pinned before *any* venv operations.
        def build(stage: Path) -> None:
            stage_python = stage / PYTHON_NAME
            with log_path.open("a", encoding="utf-8") as log:
                _execute([uv, "venv", "--offline", str(stage), "--python",
                          str(base_python)], root=root, log=log)
                _execute([uv, "pip", "install", "--offline", "--no-index",
                          "--no-cache", "--only-binary", ":all:",
                          "--require-hashes", "--python", str(stage_python),
                          "--find-links", str(wheels), "-r", str(lock_file)],
                         root=root, log=log)
                _execute([uv, "pip", "check", "--offline",
                          "--python", str(stage_python)], root=root, log=log)
            (stage / marker).write_text(json.dumps({
                **identity, **pin_fields(root, recipe_hash),
                "wheelhouse_lock_sha256": _digest(_lock_path(root, runtime_id)),
            }, indent=2) + "\n", encoding="utf-8")

        def verify(stage: Path) -> bool:
            result = inspect_environment(
                root=root, folder=stage, python=stage / PYTHON_NAME,
                marker=stage / marker, expected_recipe_hash=recipe_hash)
            return result["ready"] and result["location_pinned"]

        def verify_final(final: Path) -> bool:
            if not verify(final):
                return False
            with log_path.open("a", encoding="utf-8") as log:
                # Run the *final path* Python and import trusted dependencies.
                # Failure rolls back the entire install/repair.
                _execute([str(final / PYTHON_NAME), "-c",
                          IMPORT_CHECKS[runtime_id]], root=root, log=log)
                _execute([uv, "pip", "check", "--offline",
                          "--python", str(final / PYTHON_NAME)], root=root,
                         log=log)
            return True

        def quiesce() -> None:
            if root.resolve() != ROOT.resolve():
                return
            if runtime_id == "m2m100":
                from .m2m_runtime import reset
                reset()
            else:
                from .engine_worker_gateway import gateway
                gateway().reset(PROVIDERS[runtime_id].backend)
        if folder.exists():
            atomic_rebuild(root=root, folder=folder, build=build, verify=verify,
                           quiesce=quiesce, verify_activated=verify_final)
        else:
            atomic_install(root=root, folder=folder, build=build, verify=verify,
                           verify_activated=verify_final)
    return folder
