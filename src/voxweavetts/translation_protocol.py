"""Small-model translation contract: structured JSON and conservative validation.

This file never executes user-supplied input. In particular, a model's claim
that its output is a translation is not taken as proof of the target language
or of question preservation.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .processing import MAX_TEXT

# Keep this as small as possible for 1–2B parameter models. The server still
# parses and validates the content independently of Ollama's schema decoder.
TRANSLATION_FORMAT: dict[str, Any] = {
    "type": "object",
    "properties": {"translation": {"type": "string"}},
    "required": ["translation"],
    "additionalProperties": False,
}

_TARGET_SCRIPTS = {
    "th": re.compile(r"[\u0e01-\u0e5b]"),
    "en": re.compile(r"[A-Za-z]"),
    "ja": re.compile(r"[\u3040-\u30ff\u3400-\u9fff]"),
    "zh": re.compile(r"[\u3400-\u9fff]"),
    "ko": re.compile(r"[\u1100-\u11ff\uac00-\ud7af]"),
    "hi": re.compile(r"[\u0900-\u097f]"),
    "ru": re.compile(r"[\u0400-\u052f]"),
    "es": re.compile(r"[A-Za-zÀ-ÿ]"),
    "fr": re.compile(r"[A-Za-zÀ-ÿ]"),
    "it": re.compile(r"[A-Za-zÀ-ÿ]"),
    "pt": re.compile(r"[A-Za-zÀ-ÿ]"),
    "de": re.compile(r"[A-Za-zÀ-ÿ]"),
}
_LETTERS = re.compile(r"[A-Za-zÀ-ÿ\u0e01-\u0e5b\u0900-\u097f\u0400-\u052f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\u0980-\u09ff]")
_QUESTION_MARKS = ("?", "？", "¿")
_QUESTION_CUES = {
    "th": re.compile(
        r"ไหม|มั้ย|หรือ|อะไร|ใคร|ทำไม|อย่างไร|ยังไง|ที่ไหน|เมื่อไหร่|"
        r"เมื่อไร|กี่|เท่าไหร่|เท่าไร|ไหน|เหรอ|หรอ|รึ|ใช่ไหม"
    ),
    "en": re.compile(
        r"\b(who|what|when|where|why|how|do|does|did|is|are|can|"
        r"could|would|should|will|have|has)\b", re.IGNORECASE
    ),
    "ja": re.compile(r"か|何|誰|どこ|いつ|どう|なぜ|ですか"),
    "zh": re.compile(r"吗|麼|么|呢|什么|誰|谁|哪|为什么|怎|如何|几"),
    "ko": re.compile(r"까|나요|습니까|어요|아요|무엇|누구|어디|왜|언제"),
}
_LANGUAGE_LABEL = re.compile(
    r"Chinese|Japanese|English|Korean|Thai|Hindi|French|Spanish|"
    r"German|Russian|Italian|Portuguese|จีน|ญี่ปุ่น|อังกฤษ|เกาหลี|"
    r"ไทย|ฮินดี|ฝรั่งเศส|สเปน|เยอรมัน|รัสเซีย|อิตาลี|โปรตุเกส",
    re.IGNORECASE,
)
_LABEL_SEPARATORS = re.compile(r"[\s,，、;；/|.。:：\-—]+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class TranslationContractError(ValueError):
    """An LLM response could not safely be used as translation text."""


def _language_label_loop(original: str, translated: str) -> bool:
    # A literal source list of languages is valid translation data.
    if _LANGUAGE_LABEL.search(original):
        return False
    labels = list(_LANGUAGE_LABEL.finditer(translated))
    if len(labels) < 3:
        return False
    leftover = _LANGUAGE_LABEL.sub("", translated)
    return not _LABEL_SEPARATORS.sub("", leftover)


def _translation_question_lost(original: str, translated: str, target: str) -> bool:
    if not any(mark in original for mark in _QUESTION_MARKS):
        return False
    if any(mark in translated for mark in _QUESTION_MARKS):
        return False
    cue = _QUESTION_CUES.get(target)
    # For script families without robust question markers, do not reject
    # punctuation-free natural translations.
    return cue is not None and not cue.search(translated)


def validate_target_language(translated: str, target: str) -> None:
    # Avoid mistakenly reading Bengali/Hindi/Chinese when Thai was selected.
    # Cannot distinguish languages sharing Latin or Han scripts; separate
    # semantic checks or more capable models are needed for those.
    expected = _TARGET_SCRIPTS.get(target)
    if (expected is not None and not expected.search(translated)
            and _LETTERS.search(translated)):
        raise TranslationContractError("model output does not use the selected target language script")


def validate_translation(original: str, translated: str, target: str,
                         *, bypass_content_checks: bool = False) -> str:
    if not isinstance(translated, str):
        raise TranslationContractError("translation must be text")
    translated = translated.strip()
    if not translated or len(translated) > MAX_TEXT or _CONTROL.search(translated):
        raise TranslationContractError("translation output was empty, excessive or contained controls")
    # User may disable semantic/script heuristics for limited-capability models.
    # Shape, text length, and control-character safeguards always remain.
    if bypass_content_checks:
        return translated
    if _language_label_loop(original, translated):
        raise TranslationContractError("model returned repeated language names, not a translation")
    validate_target_language(translated, target)
    if _translation_question_lost(original, translated, target):
        raise TranslationContractError("model answered a question or lost question meaning")
    return translated


def parse_structured_translation(raw: Any, original: str, target: str,
                                 *, bypass_content_checks: bool = False) -> str:
    if not isinstance(raw, str) or len(raw) > MAX_TEXT + 2_048:
        raise TranslationContractError("invalid structured translation response")
    try:
        output = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise TranslationContractError("model returned non-JSON translation") from exc
    if not isinstance(output, dict) or set(output) != {"translation"}:
        raise TranslationContractError("model returned commentary or an unexpected JSON shape")
    return validate_translation(original, output["translation"], target,
                                bypass_content_checks=bypass_content_checks)
