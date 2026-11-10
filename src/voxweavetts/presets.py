"""Portable, private Voice Studio presets; no tokens/audio/model data stored."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from .processing import InputError
from .speech import DEFAULT_SEED, get_engine_info, validate_seed
from .voice_controls import validate_controls

ROOT = Path(__file__).resolve().parents[2]
PRESETS_FILE = ROOT / "data" / "presets" / "voice-presets.json"
_LOCK = threading.Lock()
_NAME = re.compile(r"[\w \-\u0e00-\u0e7f]{1,50}\Z", re.UNICODE)


def validate_preset(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise InputError("preset must be a JSON object")
    name = raw.get("name")
    if not isinstance(name, str) or not _NAME.fullmatch(name) or not name.strip():
        raise InputError("preset name must be 1–50 characters without special paths")
    engine_id = raw.get("engine_id")
    info = get_engine_info(engine_id)
    voice_id = raw.get("voice_id", info.voice_id)
    if voice_id != info.voice_id:
        raise InputError("preset voice_id is not supported by engine")
    speed = raw.get("speed", 1.0)
    if type(speed) not in (int, float) or not 0.6 <= speed <= 1.5:
        raise InputError("preset speed must be 0.6–1.5")
    seed = validate_seed(raw.get("seed", DEFAULT_SEED))
    controls = validate_controls(raw.get("voice_controls"))
    return {
        "name": name.strip(),
        "engine_id": engine_id,
        "voice_id": voice_id,
        "speed": float(speed),
        "seed": seed,
        "voice_controls": controls,
    }


def load_presets() -> list[dict[str, Any]]:
    with _LOCK:
        if not PRESETS_FILE.exists():
            return []
        if PRESETS_FILE.stat().st_size > 40_000:
            raise InputError("voice preset file is too large")
        try:
            parsed = json.loads(PRESETS_FILE.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InputError("voice preset JSON is invalid") from exc
        if not isinstance(parsed, list) or len(parsed) > 32:
            raise InputError("voice preset list must contain at most 32 items")
        return [validate_preset(item) for item in parsed]


def save_preset(raw: Any) -> dict[str, Any]:
    preset = validate_preset(raw)
    with _LOCK:
        # Read in the same lock, without nesting the read function lock.
        if PRESETS_FILE.exists():
            if PRESETS_FILE.stat().st_size > 40_000:
                raise InputError("voice preset file is too large")
            try:
                records = json.loads(PRESETS_FILE.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                raise InputError("voice preset JSON is invalid") from exc
            if not isinstance(records, list) or len(records) > 32:
                raise InputError("voice preset list is invalid")
            records = [validate_preset(row) for row in records]
        else:
            records = []
        records = [r for r in records if r["name"] != preset["name"]]
        records.append(preset)
        if len(records) > 32:
            raise InputError("maximum 32 presets")
        PRESETS_FILE.parent.mkdir(exist_ok=True, parents=True)
        target: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", delete=False, dir=PRESETS_FILE.parent,
                prefix=".presets-", suffix=".tmp",
            ) as handle:
                target = Path(handle.name)
                json.dump(records, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(target, PRESETS_FILE)
        finally:
            if target is not None:
                target.unlink(missing_ok=True)
    return preset
