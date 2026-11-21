"""Safe, portable, per-source queue/display preferences.

This is intentionally separate from credentials and source profiles. Saving
queue knobs never persists Discord secrets, YouTube API keys or channel tokens.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .processing import InputError

ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = ROOT / "data" / "settings" / "source-queues.json"
SOURCE_MODES = ("live", "youtube_browser", "tiktok", "tiktok_browser",
                "discord", "discord_client")
DEFAULTS = {
    "blocked_words": "",
    "max_chars": 240,
    "auto_read": True,
    "read_history_limit": 20,
    "random_queue_enabled": False,
    "random_queue_threshold": 20,
    "random_queue_keep": 5,
    "continue_on_tts_error": False,
    "force_autoplay": False,  # opt-in skip blocked WAV and attempt next LIVE item
    "prepare_ahead": False,  # opt-in parallel AI/TTS while previous WAV plays
    "prepare_queue_limit": 3,
    "ready_audio_queue_limit": 2,
    "speech_job_timeout_minutes": 4,  # per-source, legacy default
}
_LOCK = threading.RLock()
_MAX_FILE_SIZE = 96_000  # six modes may each contain 2,000 Thai filter chars


class SettingsConflict(RuntimeError):
    """Another tab changed this mode after the caller loaded it."""


def validate_settings(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != set(DEFAULTS):
        raise InputError("invalid source queue settings")
    blocked = raw["blocked_words"]
    if (not isinstance(blocked, str) or len(blocked) > 2000
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in blocked)):
        raise InputError("invalid blocked words")
    for key in ("auto_read", "random_queue_enabled", "continue_on_tts_error",
                "force_autoplay", "prepare_ahead"):
        if type(raw[key]) is not bool:
            raise InputError("invalid queue switch")
    for key, low, high in (
        ("max_chars", 20, 8000),
        ("read_history_limit", 0, 100),
        ("random_queue_threshold", 2, 100000),
        ("random_queue_keep", 1, 99999),
        ("prepare_queue_limit", 1, 100),
        ("ready_audio_queue_limit", 1, 20),
        ("speech_job_timeout_minutes", 1, 60),
    ):
        value = raw[key]
        if type(value) is not int or not low <= value <= high:
            raise InputError("invalid queue setting: " + key)
    if raw["random_queue_keep"] >= raw["random_queue_threshold"]:
        raise InputError("random queue keep must be lower than its threshold")
    return dict(raw)


def _empty() -> dict[str, Any]:
    return {"schema_version": 1,
            "modes": {mode: {"revision": 0, "settings": dict(DEFAULTS)}
                      for mode in SOURCE_MODES}}


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _empty()
    if path.is_symlink() or path.stat().st_size > _MAX_FILE_SIZE:
        raise InputError("invalid source queue settings file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or set(data) != {"schema_version", "modes"}
            or data["schema_version"] != 1 or not isinstance(data["modes"], dict)
            or set(data["modes"]) != set(SOURCE_MODES)):
            raise ValueError("invalid queue settings structure")
        for mode in SOURCE_MODES:
            record = data["modes"][mode]
            if (not isinstance(record, dict)
                or set(record) != {"revision", "settings"}
                or type(record["revision"]) is not int
                or not 0 <= record["revision"] <= 1000000000):
                raise ValueError("invalid queue settings revision")
            # Two independently added opt-in switches: migrate any subset
            # of these missing keys, while rejecting unexpected keys.
            stored = record["settings"]
            new_switches = {"continue_on_tts_error", "force_autoplay", "prepare_ahead",
                            "prepare_queue_limit", "ready_audio_queue_limit",
                            "speech_job_timeout_minutes"}
            if (isinstance(stored, dict)
                and set(DEFAULTS) - new_switches <= set(stored) <= set(DEFAULTS)):
                record["settings"] = {**stored, **{key: DEFAULTS[key] for key in
                    new_switches - set(stored)}}
            validate_settings(record["settings"])
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, InputError) as exc:
        raise InputError("invalid stored source queue settings") from exc
    return data


def load_settings(*, path: Path = SETTINGS_FILE) -> dict[str, Any]:
    with _LOCK:
        return _read(Path(path))


def save_settings(payload: Any, *, path: Path = SETTINGS_FILE) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {
        "mode", "expected_revision", "settings"
    }:
        raise InputError("invalid source queue update")
    mode = payload["mode"]
    if not isinstance(mode, str) or mode not in SOURCE_MODES:
        raise InputError("invalid source mode")
    expected = payload["expected_revision"]
    if type(expected) is not int or not 0 <= expected <= 1000000000:
        raise InputError("invalid expected queue revision")
    settings = validate_settings(payload["settings"])
    path = Path(path)
    with _LOCK:
        current = _read(path)
        previous = current["modes"][mode]["revision"]
        if expected != previous:
            raise SettingsConflict("source queue settings changed in another tab")
        if previous >= 1000000000:
            raise InputError("revision limit reached")
        current["modes"][mode] = {"revision": previous + 1, "settings": settings}
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise InputError("source queue settings file may not be a symlink")
        staged: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=path.parent, prefix=".source-queue-",
                suffix=".json", delete=False
            ) as output:
                staged = output.name
                json.dump(current, output, ensure_ascii=False, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(staged, path)
        finally:
            if staged is not None and os.path.exists(staged):
                os.unlink(staged)
        return current
