"""Two-step, same-origin native-file consent for .vwmodel v3 installs.

The browser never sends arbitrary paths, commands, dependency URLs or hooks.
The selected local archive is hashed before preview and rehashed at commit;
every install is offline and requires explicit per-file rights confirmation.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
import zipfile
from pathlib import Path

from .universal_model_packages import (
    UniversalPackageError, inspect_archive, install_model_package,
)

_PLANS: dict[str, dict] = {}
_LOCK = threading.RLock()
_TTL = 900


def _hash(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def preview(choose_file=None) -> dict:
    from .model_file_picker import pick_model_file
    selected = (choose_file or pick_model_file)()
    if not selected:
        return {"cancelled": True}
    path = Path(selected).resolve()
    manifest = inspect_archive(path)
    rights_name = manifest["rights"]
    expected = next(r["sha256"] for r in manifest["files"]
                    if r["path"] == rights_name)
    with zipfile.ZipFile(path) as archive:
        raw = archive.read(rights_name)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise UniversalPackageError("tampered rights metadata")
    rights = json.loads(raw.decode("utf-8"))
    if (not isinstance(rights, dict) or set(rights) != {"license", "source"}):
        raise UniversalPackageError("missing verified rights metadata")
    if not rights["license"]["spdx"] or not rights["license"]["attribution"]:
        raise UniversalPackageError("missing rights and attribution")
    size = path.stat().st_size
    digest = _hash(path)
    token = secrets.token_urlsafe(30)
    with _LOCK:
        expired = [key for key, data in _PLANS.items()
                   if time.monotonic() - data["created"] > _TTL]
        for key in expired:
            _PLANS.pop(key, None)
        # Bound server-side pending handles. No persistent saved file paths.
        if len(_PLANS) >= 8:
            raise UniversalPackageError("another model installation preview is pending")
        _PLANS[token] = {"path": path, "digest": digest, "size": size,
                         "created": time.monotonic(), "manifest": manifest}
    return {
        "cancelled": False, "token": token,
        "package": {**manifest["package"]},
        "runtime": {"source": manifest["runtime"]["source"],
                    "platform": manifest["runtime"]["platform"]},
        "license": rights["license"], "source": rights["source"],
        "offline": True, "file_size": size,
    }


def commit(token: str, *, accepted_rights: bool,
           acknowledged_noncommercial: bool = False) -> dict:
    if (not isinstance(token, str) or len(token) > 128
        or accepted_rights is not True
        or type(acknowledged_noncommercial) is not bool):
        raise UniversalPackageError("explicit package license consent is required")
    with _LOCK:
        record = _PLANS.pop(token, None)
    if record is None or time.monotonic() - record["created"] > _TTL:
        raise UniversalPackageError("package selection expired; choose the file again")
    if record["manifest"]["runtime"]["source"] not in ("core-bundled", "bundled-wheels"):
        raise UniversalPackageError("offline self-contained package required")
    file = record["path"]
    if (not file.is_file() or file.is_symlink()
        or file.stat().st_size != record["size"]
        or _hash(file) != record["digest"]):
        raise UniversalPackageError("selected package changed; choose it again")
    manifest = inspect_archive(file)
    if manifest != record["manifest"]:
        raise UniversalPackageError("selected package manifest changed")
    with zipfile.ZipFile(file) as archive:
        rights = json.loads(archive.read(manifest["rights"]))
    license_id = rights["license"]["spdx"].upper()
    if ("BY-NC" in license_id or "NONCOMMERCIAL" in license_id) and not acknowledged_noncommercial:
        raise UniversalPackageError("noncommercial-only use requires separate acknowledgment")
    return install_model_package(file)
