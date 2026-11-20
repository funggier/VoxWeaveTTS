"""Single-click installation of *only* Universal .vwmodel format v4.

The user selects the file and clicks Install once; that action is acceptance
of its declared rights and its executable worker. No online license check,
second dialog, or arbitrary caller-supplied paths. The archive is rehashed
immediately before installation to catch changes since selection.
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


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def preview(choose_file=None) -> dict:
    from .model_file_picker import pick_model_file

    selected = (choose_file or pick_model_file)()
    if not selected:
        return {"cancelled": True}
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
