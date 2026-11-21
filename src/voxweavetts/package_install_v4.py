"""Single-click installation of *only* Universal .vwmodel format v4.

The local picker supplies the paths authorized by the Install action. Each
archive is previewed and rehashed before installation to detect changes since
its preview.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from pathlib import Path

from .universal_model_v4 import V4PackageError, inspect_archive, install

_LOCK = threading.RLock()
_PLANS: dict[str, dict] = {}
_TTL_SECONDS = 900
_SELECTIONS: dict[str, tuple[float, dict[int, str]]] = {}
_SELECTION_IDLE_SECONDS = 3600


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def preview(choose_file=None) -> dict:
    from .model_file_picker import pick_model_file

    selected = (choose_file or pick_model_file)()
    if not selected:
        return {"cancelled": True}
    return _preview_file(selected)


def select_batch() -> dict:
    from .model_file_picker import pick_model_files

    selected = pick_model_files()
    if not selected:
        return {"cancelled": True}
    token = secrets.token_urlsafe(30)
    with _LOCK:
        now = time.monotonic()
        for key, (expires, _) in tuple(_SELECTIONS.items()):
            if expires <= now:
                del _SELECTIONS[key]
        if len(_SELECTIONS) >= 8:
            raise V4PackageError("another model package selection is pending")
        _SELECTIONS[token] = (now + _SELECTION_IDLE_SECONDS, dict(enumerate(selected)))
    return {
        "cancelled": False,
        "selection_token": token,
        "files": [Path(file).name for file in selected],
    }


def preview_selected(selection_token: str, index: int) -> dict:
    with _LOCK:
        now = time.monotonic()
        expires, remaining = _SELECTIONS.get(selection_token, (0, {}))
        if expires <= now:
            _SELECTIONS.pop(selection_token, None)
            raise V4PackageError("package selection expired; choose the files again")
        selected = remaining.pop(index, None)
        if selected is None:
            raise V4PackageError("package selection has no pending file at this index")
        if remaining:
            _SELECTIONS[selection_token] = (now + _SELECTION_IDLE_SECONDS, remaining)
        else:
            del _SELECTIONS[selection_token]
    return _preview_file(selected)


def _preview_file(selected: Path | str) -> dict:
    file = Path(selected).resolve(strict=True)
    if file.is_symlink() or not file.is_file():
        raise V4PackageError("choose a local .vwmodel v4 file")
    manifest = inspect_archive(file)
    token = secrets.token_urlsafe(30)
    record = {
        "path": file,
        "size": file.stat().st_size,
        "sha256": _sha256(file),
        "manifest": manifest,
        "created": time.monotonic(),
    }
    with _LOCK:
        for key, previous in tuple(_PLANS.items()):
            if time.monotonic() - previous["created"] > _TTL_SECONDS:
                _PLANS.pop(key, None)
        if len(_PLANS) >= 8:
            raise V4PackageError("another model installation preview is pending")
        _PLANS[token] = record
    rights = manifest["rights"]
    return {
        "cancelled": False,
        "token": token,
        "format_version": 4,
        "package": manifest["package"].copy(),
        "runtime": {
            "source": "offline-bundled-wheels",
            "platform": manifest["runtime"]["platform"],
            "python": manifest["runtime"]["python"],
        },
        "license": {
            "spdx": rights["spdx"],
            "url": rights["url"],
            "attribution": rights["attribution"],
            "review_status": rights.get("review_status", "declared"),
        },
        "source": {"url": rights["source"]},
        "contains_executable_plugin": True,
        "offline": True,
        "file_size": record["size"],
    }


def commit(token: str, *, accepted_rights: bool,
           acknowledged_noncommercial: bool = False) -> dict:
    # The Install button itself supplies accepted_rights=True. No extra
    # confirmation is required even for packages marked NC/review_required.
    if (not isinstance(token, str) or len(token) > 128
        or accepted_rights is not True
        or type(acknowledged_noncommercial) is not bool):
        raise V4PackageError("an explicit Install click is required")
    with _LOCK:
        record = _PLANS.pop(token, None)
    if record is None or time.monotonic() - record["created"] > _TTL_SECONDS:
        raise V4PackageError("package selection expired; choose the file again")
    file: Path = record["path"]
    if (not file.is_file() or file.is_symlink()
        or file.stat().st_size != record["size"]
        or _sha256(file) != record["sha256"]):
        raise V4PackageError("selected package changed; choose it again")
    if inspect_archive(file) != record["manifest"]:
        raise V4PackageError("selected package manifest changed")
    return install(file)
