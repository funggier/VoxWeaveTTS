"""Portable per-workspace model/voice/DSP preferences and global play policy.

Only future synthesis requests read a changed workspace setting; in-flight and
currently-playing speech jobs retain the voice parameters captured at enqueue.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .processing import InputError
from .speech import get_engine_info, validate_speech_request, validate_seed, DEFAULT_SEED
from .voice_controls import validate_controls

ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = ROOT / "data" / "settings" / "mode-voices.json"
VOICE_MODES = frozenset(("studio", "reader", "queue", "live", "youtube_browser", "tiktok", "tiktok_browser",
                         "discord", "discord_client"))
AUDIO_POLICIES = frozenset(("serial", "overlap"))
SENDER_MODES = frozenset(("live", "youtube_browser", "tiktok", "tiktok_browser",
                          "discord", "discord_client"))
SPEECH_FORMAT_KEYS = frozenset(("separator", "gift_separator", "read_comments",
                               "read_gifts", "read_levels", "read_ranks",
                               "read_badges", "read_gift_count", "read_name_emojis"))
SPEECH_FORMAT_BOOL_KEYS = SPEECH_FORMAT_KEYS - {"separator", "gift_separator"}
DEFAULT_SPEECH_FORMAT = {
    "separator": "พิมพ์ว่า", "gift_separator": "ส่งของขวัญ",
    "read_comments": True, "read_gifts": False,
    "read_levels": False, "read_ranks": False, "read_badges": False,
    "read_gift_count": True, "read_name_emojis": False,
}


def validate_speech_format(raw: Any) -> dict[str, Any]:
    if (not isinstance(raw, dict) or set(raw) != SPEECH_FORMAT_KEYS
        or any(type(raw[key]) is not bool for key in SPEECH_FORMAT_BOOL_KEYS)
        or any(not isinstance(raw[key], str) or len(raw[key]) > 60
               or any(ord(char) < 32 or ord(char) == 127 for char in raw[key])
               for key in ("separator", "gift_separator"))):
        raise InputError("invalid sender speech format")
    return dict(raw)

_LOCK = threading.RLock()


def validate_voice_profile(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not {"engine_id","voice_id","speed","voice_controls"} <= set(raw) or set(raw) - {"engine_id","voice_id","speed","voice_controls","seed"}:
        raise InputError("invalid workspace voice settings")
    engine_id = raw["engine_id"]
    info = get_engine_info(engine_id)
    voice_id = raw["voice_id"]
    speed = raw["speed"]
    validate_speech_request({"segments": []}, speed, voice_id, info.id)
    controls = validate_controls(raw["voice_controls"])
    return {
        "engine_id": engine_id, "voice_id": voice_id,
        "speed": float(speed), "voice_controls": controls,
        "seed": validate_seed(raw.get("seed", DEFAULT_SEED)),
    }


def load_workspace_settings(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    with _LOCK:
        if not path.is_file():
            return {"revision": 0, "policy": "serial", "modes": {}, "sender_names": {}, "speech_formats": {}}
        try:
            if path.stat().st_size > 48_000:
                raise InputError("workspace settings file too large")
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise InputError("invalid workspace voice settings file") from exc
        if (not isinstance(doc, dict) or not {"revision", "policy", "modes"} <= set(doc)
            or set(doc) - {"revision", "policy", "modes", "sender_names", "speech_formats"}
            or type(doc["revision"]) is not int or doc["revision"] < 0
            or doc["policy"] not in AUDIO_POLICIES or not isinstance(doc["modes"], dict)
            or not set(doc["modes"]) <= VOICE_MODES):
            raise InputError("invalid saved workspace settings")
        sender_names = doc.get("sender_names", {})
        if (not isinstance(sender_names, dict) or not set(sender_names) <= SENDER_MODES
            or any(type(value) is not bool for value in sender_names.values())):
            raise InputError("invalid saved sender-name settings")
        formats = doc.get("speech_formats", {})
        if (not isinstance(formats, dict)
            or not set(formats) <= SENDER_MODES):
            raise InputError("invalid saved speech format settings")
        migrated_formats = {}
        for name, config in formats.items():
            if not isinstance(config, dict) or set(config) - SPEECH_FORMAT_KEYS:
                raise InputError("invalid saved speech format settings")
            # A newly introduced switch must not invalidate an older portable
            # configuration. Validate all supplied values, fill missing keys
            # with conservative defaults, and preserve each source separately.
            migrated_formats[name] = validate_speech_format({
                **DEFAULT_SPEECH_FORMAT, **config,
            })
        return {**doc, "sender_names": dict(sender_names),
                "speech_formats": migrated_formats}


def save_workspace_settings(data: dict[str, Any], path: Path = SETTINGS_PATH) -> dict[str, Any]:
    if not isinstance(data, dict) or set(data) != {"expected_revision", "mode", "settings"}:
        raise InputError("invalid workspace voice update")
    revision = data["expected_revision"]
    if type(revision) is not int or revision < 0:
        raise InputError("invalid workspace settings revision")
    mode = data["mode"]
    if not isinstance(mode, str) or (mode not in ("__policy__", "__sender__", "__speech_format__") and mode not in VOICE_MODES):
        raise InputError("unknown voice workspace")
    if mode == "__policy__":
        value = data["settings"]
        if value not in AUDIO_POLICIES:
            raise InputError("unsupported audio playback policy")
    elif mode == "__sender__":
        value = data["settings"]
        if (not isinstance(value, dict) or set(value) != {"source_mode", "enabled"}
            or not isinstance(value["source_mode"], str)
            or value["source_mode"] not in SENDER_MODES
            or type(value["enabled"]) is not bool):
            raise InputError("invalid sender-name preference")
    elif mode == "__speech_format__":
        value = data["settings"]
        if (not isinstance(value, dict) or set(value) != {"source_mode", "format"}
            or not isinstance(value["source_mode"], str)
            or value["source_mode"] not in SENDER_MODES):
            raise InputError("invalid source speech format update")
        value = {"source_mode": value["source_mode"],
                 "format": validate_speech_format(value["format"])}
    else:
        value = validate_voice_profile(data["settings"])
    with _LOCK:
        current = load_workspace_settings(path)
        if revision != current["revision"]:
            raise ValueError("workspace voice settings changed in another tab")
        next_doc = {
            "revision": revision + 1, "policy": current["policy"],
            "modes": dict(current["modes"]),
            "sender_names": dict(current["sender_names"]),
            "speech_formats": dict(current["speech_formats"]),
        }
        if mode == "__policy__":
            next_doc["policy"] = value
        elif mode == "__sender__":
            next_doc["sender_names"][value["source_mode"]] = value["enabled"]
        elif mode == "__speech_format__":
            next_doc["speech_formats"][value["source_mode"]] = value["format"]
        else:
            next_doc["modes"][mode] = value
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n",
                dir=path.parent, prefix=".mode-voices-", suffix=".tmp", delete=False,
            ) as out:
                tmp = Path(out.name)
                json.dump(next_doc, out, indent=2, ensure_ascii=False)
                out.write("\n")
            os.replace(tmp, path)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
        return next_doc
