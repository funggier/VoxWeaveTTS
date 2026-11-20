"""Portable voice routing by language, independent from translation settings.

Routes use trusted engine IDs and voice IDs from the active Engine Registry.
Automatic detection is script-level only. Latin-script languages other than
English must be selected explicitly or provided by the translation target.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import unicodedata
from pathlib import Path
from typing import Any

from .processing import InputError
from .voice_controls import validate_controls
from .speech import validate_seed

PATH = Path(__file__).resolve().parents[2] / "data" / "settings" / "language-voices.json"
LANGUAGES = {
    "th": "ไทย", "en": "English", "ja": "日本語", "zh": "中文",
    "ko": "한국어", "es": "Español", "fr": "Français",
    "hi": "हिन्दी", "it": "Italiano", "pt": "Português",
    "de": "Deutsch", "ru": "Русский",
    "ar": "العربية", "bg": "Български", "hr": "Hrvatski",
    "cs": "Čeština", "da": "Dansk", "nl": "Nederlands",
    "et": "Eesti", "fi": "Suomi", "el": "Ελληνικά",
    "hu": "Magyar", "id": "Bahasa Indonesia", "lv": "Latviešu",
    "lt": "Lietuvių", "pl": "Polski", "ro": "Română",
    "sk": "Slovenčina", "sl": "Slovenščina", "sv": "Svenska",
    "tr": "Türkçe", "uk": "Українська", "vi": "Tiếng Việt",
}
_LOCK = threading.RLock()
_ROUTE_KEYS = frozenset({"engine_id", "voice_id", "speed", "voice_controls", "seed"})


def _validate_route_shape(route: Any) -> dict[str, Any]:
    """Validate a language voice profile without requiring installed model assets."""
    if (not isinstance(route, dict)
            or not {"engine_id", "voice_id"} <= set(route)
            or set(route) - _ROUTE_KEYS
            or any(not isinstance(route[name], str) or not 1 <= len(route[name]) <= 100
                   for name in ("engine_id", "voice_id"))):
        raise InputError("invalid language voice assignment")
    profile = {"engine_id": route["engine_id"], "voice_id": route["voice_id"]}
    if "speed" in route:
        speed = route["speed"]
        if (type(speed) not in (int, float) or not math.isfinite(speed)
                or not 0.6 <= speed <= 5.0):
            raise InputError("language voice speed must be 0.60–5.00")
        profile["speed"] = float(speed)
    if "voice_controls" in route:
        profile["voice_controls"] = validate_controls(route["voice_controls"])
    if "seed" in route:
        profile["seed"] = validate_seed(route["seed"])
    return profile


def _default() -> dict[str, Any]:
    return {"revision": 0, "routes": {}}


def load_routes(path: Path = PATH) -> dict[str, Any]:
    with _LOCK:
        if not path.is_file():
            return _default()
        try:
            if path.stat().st_size > 16_384:
                raise ValueError("large language routing file")
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if (not isinstance(value, dict) or set(value) not in (
                    {"revision", "routes"}, {"revision", "enabled", "routes"})
                    or type(value["revision"]) is not int or value["revision"] < 0
                    or ("enabled" in value and type(value["enabled"]) is not bool)
                    or not isinstance(value["routes"], dict)
                    or not set(value["routes"]) <= set(LANGUAGES)):
                raise ValueError("invalid language routes")
            value["routes"] = {code: _validate_route_shape(route)
                               for code, route in value["routes"].items()}
        except (OSError, ValueError, TypeError) as exc:
            raise InputError("invalid saved language routing settings") from exc
        # Ignore the obsolete global switch; each speech workspace now owns its own toggle.
        return {"revision": value["revision"], "routes": value["routes"]}


def voice_languages(engine_id: str, voice_id: str) -> set[str]:
    from .speech import get_engine_info
    info = get_engine_info(engine_id)
    if voice_id not in info.voice_ids:
        raise InputError("unknown voice ID in language route")
    if info.voice_language_map:
        code = info.voice_language_map.get(voice_id)
        return {code} if code else set()
    if info.supported_languages:
        return set(info.supported_languages)
    if info.language == "multi":
        # v4 packages advertise languages through the protocol, not by a
        # model-specific code table baked into VoxWeave Core.
        return set(info.supported_languages)
    return {info.language}


def save_routes(request: Any, path: Path = PATH) -> dict[str, Any]:
    if (not isinstance(request, dict)
            or set(request) != {"expected_revision", "routes"}
            or type(request["expected_revision"]) is not int
            or request["expected_revision"] < 0
            or not isinstance(request["routes"], dict)
            or not set(request["routes"]) <= set(LANGUAGES)):
        raise InputError("invalid language routing update")
    validated = {}
    for language, route in request["routes"].items():
        profile = _validate_route_shape(route)
        if language not in voice_languages(profile["engine_id"], profile["voice_id"]):
            raise InputError("selected model/voice cannot speak this language")
        validated[language] = profile
    with _LOCK:
        current = load_routes(path)
        if current["revision"] != request["expected_revision"]:
            raise ValueError("language routes changed in another tab")
        value = {"revision": current["revision"] + 1, "routes": validated}
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n",
                dir=path.parent, prefix=".language-voices-", suffix=".tmp",
                delete=False) as stream:
                tmp = Path(stream.name)
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(tmp, path)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
        return value


def detect_language(text: str) -> str:
    """Unicode-script heuristic; intentionally does not pretend to identify
    French/Spanish/Italian/Portuguese from their shared Latin script."""
    counts = {"th": 0, "ja": 0, "ko": 0, "zh": 0,
              "hi": 0, "ru": 0, "el": 0, "ar": 0, "en": 0}
    for ch in text:
        cp = ord(ch)
        if 0x0E00 <= cp <= 0x0E7F:
            counts["th"] += 1
        elif 0x3040 <= cp <= 0x30FF:
            counts["ja"] += 3
        elif 0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF:
            counts["ko"] += 2
        elif 0x4E00 <= cp <= 0x9FFF:
            counts["zh"] += 1
        elif 0x0900 <= cp <= 0x097F:
            counts["hi"] += 2
        elif 0x0370 <= cp <= 0x03FF:
            counts["el"] += 2
        elif 0x0600 <= cp <= 0x06FF:
            counts["ar"] += 2
        elif 0x0400 <= cp <= 0x052F:
            counts["ru"] += 2
        elif "LATIN" in unicodedata.name(ch, "") and ch.isalpha():
            counts["en"] += 1
    if counts["ja"] and counts["zh"]:
        counts["ja"] += counts["zh"]
    # Latin text often comes from a sender name or a fixed phrase such as
    # "writes:" in live-chat speech. Do not let that metadata override a
    # recognizable non-Latin script (e.g. "LongEnglishName: じゃない"), or the
    # English Kokoro voice will spell Japanese characters as letter names.
    # Explicit language choices still take precedence in choose_route().
    scripts = {code: amount for code, amount in counts.items() if code != "en"}
    if any(scripts.values()):
        return max(scripts, key=scripts.get)
    return "en" if counts["en"] else "und"


def choose_route(text: str, *, language: str | None = None,
                 path: Path = PATH) -> tuple[str, dict[str, str] | None]:
    if language is not None and not isinstance(language, str):
        raise InputError("invalid speech language")
    snapshot = load_routes(path)
    lang = language if language and language != "auto" else detect_language(text)
    if lang not in LANGUAGES and lang != "und":
        raise InputError("unsupported speech language")
    route = snapshot["routes"].get(lang)
    return lang, route
