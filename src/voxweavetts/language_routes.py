"""Portable voice routing by language, independent from translation settings.

Routes use trusted engine IDs and voice IDs from the active Engine Registry.
Automatic detection is script-level only. Latin-script languages other than
English must be selected explicitly or provided by the translation target.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import unicodedata
from pathlib import Path
from typing import Any

from .processing import InputError

PATH = Path(__file__).resolve().parents[2] / "data" / "settings" / "language-voices.json"
LANGUAGES = {
    "th": "ไทย", "en": "English", "ja": "日本語", "zh": "中文",
    "ko": "한국어", "es": "Español", "fr": "Français",
    "hi": "हिन्दी", "it": "Italiano", "pt": "Português",
    "de": "Deutsch", "ru": "Русский",
}
_LOCK = threading.RLock()


def _default() -> dict[str, Any]:
    return {"revision": 0, "enabled": False, "routes": {}}


def load_routes(path: Path = PATH) -> dict[str, Any]:
    with _LOCK:
        if not path.is_file():
            return _default()
        try:
            if path.stat().st_size > 16_384:
                raise ValueError("large language routing file")
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if (not isinstance(value, dict) or set(value) != {"revision", "enabled", "routes"}
                    or type(value["revision"]) is not int or value["revision"] < 0
                    or type(value["enabled"]) is not bool
                    or not isinstance(value["routes"], dict)
                    or not set(value["routes"]) <= set(LANGUAGES)
                    or any(not isinstance(route, dict)
                           or set(route) != {"engine_id", "voice_id"}
                           or any(not isinstance(v, str) or not 1 <= len(v) <= 100
                                  for v in route.values())
                           for route in value["routes"].values())):
                raise ValueError("invalid language routes")
        except (OSError, ValueError, TypeError) as exc:
            raise InputError("invalid saved language routing settings") from exc
        return value


def voice_languages(engine_id: str, voice_id: str) -> set[str]:
    from .speech import get_engine_info
    info = get_engine_info(engine_id)
    if voice_id not in info.voice_ids:
        raise InputError("unknown voice ID in language route")
    if info.language == "multi":
        from .kokoro_engine import LANGUAGE_CODES
        language = LANGUAGE_CODES.get(voice_id[0], "")
        return {language} if language else set()
    return {info.language}


def save_routes(request: Any, path: Path = PATH) -> dict[str, Any]:
    if (not isinstance(request, dict)
            or set(request) != {"expected_revision", "enabled", "routes"}
            or type(request["expected_revision"]) is not int
            or request["expected_revision"] < 0
            or type(request["enabled"]) is not bool
            or not isinstance(request["routes"], dict)
            or not set(request["routes"]) <= set(LANGUAGES)):
        raise InputError("invalid language routing update")
    validated = {}
    for language, route in request["routes"].items():
        if (not isinstance(route, dict) or set(route) != {"engine_id", "voice_id"}
                or not all(isinstance(v, str) for v in route.values())):
            raise InputError("invalid language route")
        if language not in voice_languages(route["engine_id"], route["voice_id"]):
            raise InputError("selected model/voice cannot speak this language")
        validated[language] = dict(route)
    with _LOCK:
        current = load_routes(path)
        if current["revision"] != request["expected_revision"]:
            raise ValueError("language routes changed in another tab")
        value = {"revision": current["revision"] + 1,
                 "enabled": request["enabled"], "routes": validated}
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
              "hi": 0, "ru": 0, "en": 0}
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
        elif 0x0400 <= cp <= 0x052F:
            counts["ru"] += 2
        elif "LATIN" in unicodedata.name(ch, "") and ch.isalpha():
            counts["en"] += 1
    if counts["ja"] and counts["zh"]:
        counts["ja"] += counts["zh"]
    winner = max(counts, key=counts.get)
    return winner if counts[winner] else "und"


def choose_route(text: str, *, language: str | None = None,
                 path: Path = PATH) -> tuple[str, dict[str, str] | None]:
    if language is not None and not isinstance(language, str):
        raise InputError("invalid speech language")
    snapshot = load_routes(path)
    lang = language if language and language != "auto" else detect_language(text)
    if lang not in LANGUAGES and lang != "und":
        raise InputError("unsupported speech language")
    route = snapshot["routes"].get(lang) if snapshot["enabled"] else None
    return lang, route
