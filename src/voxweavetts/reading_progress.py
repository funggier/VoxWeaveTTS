"""Private, engine-independent, resumable TXT/Markdown reading positions.

Only a content hash and chunk counters are persisted. Never save text, titles,
paths, voice data or narration audio here. All writes are bounded and atomic.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any

from .processing import InputError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROGRESS_FILE = PROJECT_ROOT / "data" / "reading" / "positions.json"
MAX_RECORDS = 128
MAX_FILE_BYTES = 48_000
_LOCK = threading.RLock()


class ProgressConflict(Exception):
    """Another browser tab changed the position since the last read."""


def _document_id(value: Any) -> str:
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise InputError("document_id must be a lowercase SHA-256 hex string")
    return value


def _revision(record: dict[str, Any] | None) -> str:
    canonical = json.dumps(
        record, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "chunk_chars", "chunk_total", "next_chunk", "updated_at"
    }:
        raise InputError("invalid local reading progress fields")
    for field, low, high in (("chunk_chars", 100, 450),
                             ("chunk_total", 1, 2500),
                             ("next_chunk", 0, 2500)):
        x = value[field]
        if type(x) is not int or not low <= x <= high:
            raise InputError(f"invalid local progress {field}")
    if value["next_chunk"] > value["chunk_total"]:
        raise InputError("progress position exceeds document chunks")
    if (not isinstance(value["updated_at"], str)
            or not 1 <= len(value["updated_at"]) <= 40):
        raise InputError("invalid local progress timestamp")
    return value


def _read() -> dict[str, dict[str, Any]]:
    path = PROGRESS_FILE
    if not path.exists():
        return {}
    if path.stat().st_size > MAX_FILE_BYTES:
        raise InputError("reading progress file too large")
    try:
        data = json.loads(
            path.read_text(encoding="utf-8-sig"),
            parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)),
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise InputError("saved reading progress JSON is invalid") from exc
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or not isinstance(data.get("documents"), dict)
            or set(data) != {"schema_version", "documents"}
            or len(data["documents"]) > MAX_RECORDS):
        raise InputError("saved reading progress has invalid schema")
    for key, record in data["documents"].items():
        _document_id(key)
        _validate_record(record)
    return data["documents"]


def _atomic_write(items: dict[str, dict[str, Any]]) -> None:
    path = PROGRESS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps({"schema_version": 1, "documents": items},
                   ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    if len(payload) > MAX_FILE_BYTES:
        raise InputError("reading progress storage limit reached")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=".reading-progress-",
            suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_position(document_id: Any) -> dict[str, Any]:
    key = _document_id(document_id)
    with _LOCK:
        record = _read().get(key)
        return {
            "schema_version": 1,
            "document_id": key,
            "progress": dict(record) if record else None,
            "revision": _revision(record),
        }


def save_position(
    document_id: Any, *, chunk_chars: Any, chunk_total: Any,
    next_chunk: Any, expected_revision: Any,
) -> dict[str, Any]:
    key = _document_id(document_id)
    if (not isinstance(expected_revision, str) or len(expected_revision) != 64
            or any(c not in "0123456789abcdef" for c in expected_revision)):
        raise InputError("expected_revision must be the current 64-character version")
    candidate = {
        "chunk_chars": chunk_chars, "chunk_total": chunk_total,
        "next_chunk": next_chunk,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _validate_record(candidate)
    with _LOCK:
        documents = _read()
        current = documents.get(key)
        if _revision(current) != expected_revision:
            raise ProgressConflict("reading position was changed in another tab; reload before saving")
        if key not in documents and len(documents) >= MAX_RECORDS:
            raise InputError("reading progress is full; clear an old position first")
        documents[key] = candidate
        _atomic_write(documents)
        return {
            "schema_version": 1, "document_id": key,
            "progress": dict(candidate), "revision": _revision(candidate),
        }


def clear_position(document_id: Any, expected_revision: Any) -> dict[str, Any]:
    key = _document_id(document_id)
    if (not isinstance(expected_revision, str) or len(expected_revision) != 64
            or any(c not in "0123456789abcdef" for c in expected_revision)):
        raise InputError("expected_revision must be the current 64-character version")
    with _LOCK:
        documents = _read()
        current = documents.get(key)
        if _revision(current) != expected_revision:
            raise ProgressConflict("reading position was changed in another tab; reload before clearing")
        documents.pop(key, None)
        _atomic_write(documents)
        return {
            "schema_version": 1, "document_id": key,
            "progress": None, "revision": _revision(None),
        }
