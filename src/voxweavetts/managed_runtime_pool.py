"""Read-only health checks for application-managed Python worker environments.

The model archive never controls executable paths or commands.  In particular,
a Windows venv copied to a different drive must not be assumed runnable merely
because Scripts/python.exe and a ready marker are present.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
from collections.abc import Callable
from pathlib import Path

MAX_CONFIG_BYTES = 8192
MAX_MARKER_BYTES = 16384
_ABI = re.compile(r"^3\.\d+$")


def _same_location(a: str, b: Path) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(
        os.path.normpath(str(b.resolve())))


def _config(folder: Path) -> dict[str, str] | None:
    config = folder / "pyvenv.cfg"
    if not config.is_file() or config.is_symlink():
        return None
    if config.stat().st_size > MAX_CONFIG_BYTES:
        raise ValueError("oversized pyvenv.cfg")
    result: dict[str, str] = {}
    for line in config.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            result[key.strip().lower()] = value.strip()
    return result


def _abi(config: dict[str, str]) -> str | None:
    raw = config.get("version_info", config.get("version", ""))
    match = re.match(r"^(3\.\d+)(?:\.|\s|$)", raw)
    return match.group(1) if match else None


def inspect_environment(*, root: Path, folder: Path, python: Path,
                        marker: Path, expected_abi: str = "3.11",
                        expected_recipe_hash: str | None = None) -> dict:
    """Return a bounded, non-executing health report for one managed venv.

    Older markers are supported but explicitly reported as unpinned. The
    installer pins new markers to the absolute installation root and recipe.
    No diagnostics delete files, launch Python, or use package-supplied paths.
    """
    root = Path(root)
    folder = Path(folder)
    python = Path(python)
    marker = Path(marker)
    def result(state: str, *, pinned: bool = False, abi: str | None = None) -> dict:
        return {"state": state, "ready": state in ("ready", "legacy-unpinned"),
                "location_pinned": pinned, "python_abi": abi,
                "repair_required": state in (
                    "relocated", "recipe-changed", "python-abi-mismatch",
                    "base-python-missing", "incomplete")}

    if not folder.exists():
        return result("not-installed")
    if (not folder.is_dir() or folder.is_symlink()
        or not folder.resolve().is_relative_to(root.resolve())
        or folder.parent.is_symlink()):
        return result("unsafe-environment")
    if not python.is_file() or python.is_symlink():
        return result("incomplete")
    try:
        if (not marker.is_file() or marker.is_symlink()
            or marker.stat().st_size > MAX_MARKER_BYTES):
            return result("incomplete")
        state = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            return result("incomplete")
        pinned = state.get("installed_root")
        if pinned is not None:
            if not isinstance(pinned, str) or not os.path.isabs(pinned):
                return result("incomplete")
            if not _same_location(pinned, root):
                return result("relocated", pinned=True)
        pinned_bool = pinned is not None
        if (expected_recipe_hash is not None and "recipe_hash" in state
            and state["recipe_hash"] != expected_recipe_hash):
            return result("recipe-changed", pinned=pinned_bool)
        config = _config(folder)
        if config is None:
            return result("incomplete" if pinned_bool else "legacy-unpinned",
                          pinned=pinned_bool)
        abi = _abi(config)
        if abi != expected_abi:
            return result("python-abi-mismatch", pinned=pinned_bool, abi=abi)
        home = config.get("home")
        if home and os.path.isabs(home) and not Path(home).is_dir():
            return result("base-python-missing", pinned=pinned_bool, abi=abi)
        return result("ready" if pinned_bool else "legacy-unpinned",
                      pinned=pinned_bool, abi=abi)
    except (OSError, UnicodeError, ValueError, TypeError):
        return result("incomplete")


def pin_fields(root: Path, recipe_hash: str) -> dict[str, str]:
    """Trusted installer writes these only after successful dependency checks."""
    if not re.fullmatch(r"[0-9a-f]{64}", recipe_hash):
        raise ValueError("invalid trusted recipe digest")
    return {"installed_root": str(Path(root).resolve()),
            "recipe_hash": recipe_hash}


class RuntimeRebuildError(RuntimeError):
    """An explicit, trusted runtime rebuild was refused or failed."""


def atomic_rebuild(*, root: Path, folder: Path, build: Callable[[Path], None],
                   verify: Callable[[Path], bool],
                   quiesce: Callable[[], None] | None = None) -> None:
    """Rebuild into a sibling, verify, then replace only the managed venv.

    Never touch models, settings or caches; never follow a redirected runtime
    path. On staging or activation failure the previous environment is kept.
    The caller must have separately authorized this runtime ID and recipe.
    """
    root = Path(root)
    folder = Path(folder)
    try:
        relative = folder.relative_to(root)
    except ValueError as exc:
        raise RuntimeRebuildError("runtime must remain within the application") from exc
    if (len(relative.parts) != 3 or relative.parts[0] != "runtime"
        or relative.parts[1] not in ("engine-envs", "ai-envs")
        or not re.fullmatch(r"[a-z][a-z0-9-]{1,39}", relative.parts[2])
        or (relative.parts[1] == "ai-envs" and relative.parts[2] != "m2m100")
        or folder.is_symlink() or folder.parent.is_symlink()
        or folder.parent.parent.is_symlink()
        or not folder.is_dir()
        or folder.resolve().parent != folder.parent.resolve()):
        raise RuntimeRebuildError("unmanaged or unsafe runtime directory")
    token = secrets.token_hex(8)
    stage = folder.with_name("." + folder.name + ".stage-" + token)
    backup = folder.with_name("." + folder.name + ".backup-" + token)
    moved_old = False
    activated = False
    try:
        build(stage)
        if (not stage.is_dir() or stage.is_symlink()
            or stage.resolve().parent != folder.parent.resolve()
            or not verify(stage)):
            raise RuntimeRebuildError("rebuilt runtime failed verification")
        # Wait until the trusted worker is quiescent before changing launchers.
        if quiesce is not None:
            quiesce()
        folder.rename(backup)
        moved_old = True
        stage.rename(folder)
        activated = True
    except Exception:
        if moved_old and not activated:
            backup.rename(folder)
        raise
    finally:
        if stage.exists() and not stage.is_symlink():
            shutil.rmtree(stage)
    # Only disposable app-owned venv contents, not model data, are removed.
    # If cleanup is blocked (e.g. Windows file lock), leave the old folder
    # available for manual recovery rather than disturbing the new runtime.
    try:
        shutil.rmtree(backup)
    except OSError:
        pass
