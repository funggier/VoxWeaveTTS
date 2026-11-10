"""Private, versioned, model-independent Rules/Pronunciations persistence.

Uses existing portable data paths. Writes are validated, atomic, and guarded by
an optimistic revision to protect simultaneous browser tabs. No user-provided
paths, executable rules, arbitrary regular expressions, or cloud dependencies.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .processing import InputError, parse_pronunciations, parse_rules

ROOT = Path(__file__).resolve().parents[2]
RULES_FILE = ROOT / "data" / "filters" / "rules.json"
PRONUNCIATIONS_FILE = ROOT / "data" / "dictionaries" / "pronunciations.json"
MAX_FILE_BYTES = 65_536
_SETTINGS_LOCK = threading.RLock()
_ALLOWED = frozenset(("rules", "pronunciations"))


class SettingsConflict(Exception):
    """Configuration changed since the client's last read."""


def _path(section: str) -> Path:
    if section not in _ALLOWED:
        raise InputError("unknown text settings section")
    return RULES_FILE if section == "rules" else PRONUNCIATIONS_FILE


def _validate(section: str, value: Any) -> Any:
    # Existing Rule.parse uses a bounded predefined five_run mode; never eval.
    if section == "rules":
        parse_rules(value)
    elif section == "pronunciations":
        parse_pronunciations(value)
    else:
        raise InputError("unknown text settings section")
    return value


def _reject_json_constant(token: str) -> None:
    raise ValueError(f"non-standard JSON number: {token}")


def _read(section: str) -> tuple[Any, bool]:
    path = _path(section)
    if not path.is_file():
        return ([] if section == "rules" else {}), False
    if path.stat().st_size > MAX_FILE_BYTES:
        raise InputError(f"saved {section} file exceeds {MAX_FILE_BYTES} bytes")
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8-sig"),
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise InputError(f"saved {section} JSON is invalid") from exc
    # Backward compatibility with legacy wrapped rules files.
    if section == "rules" and isinstance(raw, dict) and "rules" in raw:
        raw = raw["rules"]
    return _validate(section, raw), True


def _revision(value: Any) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_section(section: str) -> dict[str, Any]:
    with _SETTINGS_LOCK:
        value, saved = _read(section)
        return {"value": value, "saved": saved, "revision": _revision(value)}


def load_all() -> dict[str, Any]:
    with _SETTINGS_LOCK:
        rules, rules_saved = _read("rules")
        pronunciations, pron_saved = _read("pronunciations")
        return {
            "schema_version": 1,
            "rules": rules,
            "pronunciations": pronunciations,
            "revisions": {
                "rules": _revision(rules),
                "pronunciations": _revision(pronunciations),
            },
            "saved": {"rules": rules_saved, "pronunciations": pron_saved},
        }


def save_section(section: str, value: Any, expected_revision: Any) -> dict[str, Any]:
    _path(section)  # validate section before accessing its value
    if not isinstance(expected_revision, str) or len(expected_revision) != 64 or any(
        c not in "0123456789abcdef" for c in expected_revision
    ):
        raise InputError("expected_revision must be the 64-character version from GET")
    _validate(section, value)
    encoded = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
               + "\n").encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise InputError(f"{section} JSON exceeds {MAX_FILE_BYTES} bytes")
    with _SETTINGS_LOCK:
        current, _ = _read(section)
        if _revision(current) != expected_revision:
            raise SettingsConflict("settings changed in another tab or on disk; reload before saving")
        target = _path(section)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, prefix=".text-setting-",
                suffix=".tmp", delete=False
            ) as handle:
                temporary = Path(handle.name)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return {"value": value, "saved": True, "revision": _revision(value)}