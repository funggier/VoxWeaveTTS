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
VOICE_MODES = frozenset(("studio", "reader", "queue", "live", "tiktok",
                         "discord", "discord_client"))
AUDIO_POLICIES = frozenset(("serial", "overlap"))
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
            return {"revision": 0, "policy": "serial", "modes": {}}
        try:
            if path.stat().st_size > 48_000:
                raise InputError("workspace settings file too large")
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise InputError("invalid workspace voice settings file") from exc
        if (not isinstance(doc, dict) or set(doc) != {"revision", "policy", "modes"}
            or type(doc["revision"]) is not int or doc["revision"] < 0
            or doc["policy"] not in AUDIO_POLICIES or not isinstance(doc["modes"], dict)
            or not set(doc["modes"]) <= VOICE_MODES):
            raise InputError("invalid saved workspace settings")
        # Do not reject saved profiles solely because the model was removed.
        return doc


def save_workspace_settings(data: dict[str, Any], path: Path = SETTINGS_PATH) -> dict[str, Any]:
    if not isinstance(data, dict) or set(data) != {"expected_revision", "mode", "settings"}:
        raise InputError("invalid workspace voice update")
    revision = data["expected_revision"]
    if type(revision) is not int or revision < 0:
        raise InputError("invalid workspace settings revision")
    mode = data["mode"]
    if mode != "__policy__" and mode not in VOICE_MODES:
        raise InputError("unknown voice workspace")
    if mode == "__policy__":
        value = data["settings"]
        if value not in AUDIO_POLICIES:
            raise InputError("unsupported audio playback policy")
    else:
        value = validate_voice_profile(data["settings"])
    with _LOCK:
        current = load_workspace_settings(path)
        if revision != current["revision"]:
            raise ValueError("workspace voice settings changed in another tab")
        next_doc = {
            "revision": revision + 1, "policy": current["policy"],
            "modes": dict(current["modes"]),
        }
        if mode == "__policy__":
            next_doc["policy"] = value
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
