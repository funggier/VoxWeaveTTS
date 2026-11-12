"""Portable, per-file Voice Presets in the app's own presets/ directory.

Every JSON preset is data-only. No model weights, credentials or executable code.
Legacy data/presets/voice-presets.json is read as a migration fallback.
"""
from __future__ import annotations

import hashlib
import json
import math
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
PRESETS_DIR = ROOT / "presets"
PRESETS_FILE = ROOT / "data" / "presets" / "voice-presets.json"
_LOCK = threading.RLock()
_NAME = re.compile(r"[\w \-\u0e00-\u0e7f]{1,50}\Z", re.UNICODE)
MAX_PRESETS = 64
MAX_FILE_BYTES = 16_384


def validate_preset(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise InputError("preset must be a JSON object")
    name = raw.get("name")
    if not isinstance(name, str) or not _NAME.fullmatch(name) or not name.strip():
        raise InputError("preset name must be 1–50 characters without special paths")
    engine_id = raw.get("engine_id")
    info = get_engine_info(engine_id)
    voice_id = raw.get("voice_id", info.voice_id)
    if voice_id not in info.voice_ids:
        raise InputError("preset voice_id is not supported by engine")
    speed = raw.get("speed", 1.0)
    if type(speed) not in (int, float) or not math.isfinite(speed) or not 0.6 <= speed <= 5.0:
        raise InputError("preset speed must be 0.6–5.0")
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


def _filename(name: str) -> str:
    # The user-facing name never becomes an arbitrary filesystem path. The
    # digest prevents Unicode/Windows reserved-name and case collisions.
    return "voice-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:24] + ".json"


def _load_unlocked() -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    if PRESETS_FILE.is_file():
        if PRESETS_FILE.stat().st_size > 40_000:
            raise InputError("legacy voice preset file is too large")
        try:
            parsed = json.loads(PRESETS_FILE.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise InputError("legacy voice preset JSON is invalid") from exc
        if not isinstance(parsed, list) or len(parsed) > MAX_PRESETS:
            raise InputError("invalid legacy voice presets")
        for item in parsed:
            valid = validate_preset(item)
            found[valid["name"]] = valid
    if PRESETS_DIR.is_dir():
        files = [file for file in PRESETS_DIR.iterdir()
                 if file.suffix.lower() == ".json" and file.is_file() and not file.is_symlink()]
        if len(files) > MAX_PRESETS:
            raise InputError("too many voice preset JSON files")
        # Filenames can be user-defined. Canonical saved names always take
        # precedence over a manually dropped same-name JSON.
        for file in sorted(files, key=lambda file: file.name):
            if file.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                doc = json.loads(file.read_text(encoding="utf-8-sig"))
                valid = validate_preset(doc)
            except (OSError, ValueError, TypeError):
                continue  # A broken user file must not hide every good preset.
            found[valid["name"]] = valid
        for file in sorted(files, key=lambda file: file.name):
            if file.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                doc = json.loads(file.read_text(encoding="utf-8-sig"))
                valid = validate_preset(doc)
            except (OSError, ValueError, TypeError):
                continue
            if file.name == _filename(valid["name"]):
                found[valid["name"]] = valid
    return [found[name] for name in sorted(found, key=str.casefold)]


def load_presets() -> list[dict[str, Any]]:
    # Each request re-scans the directory. Manually copied JSON files appear
    # on the next dropdown refresh without restarting VoxWeaveTTS.
    with _LOCK:
        return _load_unlocked()


def save_preset(raw: Any) -> dict[str, Any]:
    preset = validate_preset(raw)
    with _LOCK:
        existing = _load_unlocked()
        if len(existing) >= MAX_PRESETS and preset["name"] not in {r["name"] for r in existing}:
            raise InputError("maximum 64 voice presets")
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        target = PRESETS_DIR / _filename(preset["name"])
        temp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", delete=False, dir=PRESETS_DIR,
                prefix=".voice-", suffix=".tmp",
            ) as handle:
                temp = Path(handle.name)
                json.dump(preset, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(temp, target)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
    return preset
