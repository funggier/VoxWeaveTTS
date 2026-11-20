"""One-click, same-origin local installation of v4 and existing v3 .vwmodel files.

Selecting a package and clicking Install accepts its declared rights and,
for v4, explicitly trusts its executable worker code. There is no further
dialog, online license request or invisible execution before the Install click.
The local archive is hashed at selection and again immediately before commit.
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


def _inspect(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as archive:
            info = json.loads(archive.read("manifest.json"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, UnicodeError) as exc:
        raise UniversalPackageError("invalid local model package manifest") from exc
    if isinstance(info, dict) and info.get("format_version") == 4:
        from .universal_model_v4 import inspect_archive as inspect_v4
        return inspect_v4(path)
    return inspect_archive(path)


def _rights(path: Path, manifest: dict) -> dict:
    if manifest["format_version"] == 4:
        license_info = manifest["rights"]
        return {
            "license": {
                "spdx": license_info["spdx"], "url": license_info["url"],
                "attribution": license_info["attribution"],
                "review_status": license_info.get("review_status", "declared"),
            },
            "source": {"url": license_info["source"]},
        }
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
    return rights


def preview(choose_file=None) -> dict:
    from .model_file_picker import pick_model_file
    selected = (choose_file or pick_model_file)()
    if not selected:
        return {"cancelled": True}
    path = Path(selected).resolve()
    manifest = _inspect(path)
    rights = _rights(path, manifest)
    size = path.stat().st_size
    digest = _hash(path)
    token = secrets.token_urlsafe(30)
    with _LOCK:
        expired = [key for key, data in _PLANS.items()
                   if time.monotonic() - data["created"] > _TTL]
        for key in expired:
            _PLANS.pop(key, None)
        if len(_PLANS) >= 8:
            raise UniversalPackageError("another model installation preview is pending")
        _PLANS[token] = {"path": path, "digest": digest, "size": size,
                         "created": time.monotonic(), "manifest": manifest}
    return {
        "cancelled": False, "token": token,
        "format_version": manifest["format_version"],
        "package": {**manifest["package"]},
        "runtime": {"source": manifest["runtime"].get("source", "bundled-wheels"),
                    "platform": manifest["runtime"]["platform"]},
        "license": rights["license"], "source": rights["source"],
        "offline": True, "file_size": size,
        "contains_executable_plugin": manifest["format_version"] == 4,
    }


def commit(token: str, *, accepted_rights: bool,
           acknowledged_noncommercial: bool = False) -> dict:
    if (not isinstance(token, str) or len(token) > 128
        or accepted_rights is not True
        or type(acknowledged_noncommercial) is not bool):
        raise UniversalPackageError("an explicit Install click is required")
    with _LOCK:
        record = _PLANS.pop(token, None)
    if record is None or time.monotonic() - record["created"] > _TTL:
        raise UniversalPackageError("package selection expired; choose the file again")
    old = record["manifest"]
    if (old["format_version"] == 3
        and old["runtime"]["source"] not in ("core-bundled", "bundled-wheels")):
        raise UniversalPackageError("offline self-contained package required")
    file = record["path"]
    if (not file.is_file() or file.is_symlink()
        or file.stat().st_size != record["size"]
        or _hash(file) != record["digest"]):
        raise UniversalPackageError("selected package changed; choose it again")
    manifest = _inspect(file)
    if manifest != old:
        raise UniversalPackageError("selected package manifest changed")
    if manifest["format_version"] == 4:
        from .universal_model_v4 import install
        return install(file)
    license_id = _rights(file, manifest)["license"]["spdx"].upper()
    if ("BY-NC" in license_id or "NONCOMMERCIAL" in license_id) and not acknowledged_noncommercial:
        raise UniversalPackageError("noncommercial restriction not acknowledged")
    return install_model_package(file)
