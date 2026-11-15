"""Structured, non-prompt translation pipeline for M2M100.

Only each segment's natural-language text is sent to the model. Source/target
language, segmentation, boundaries and validation remain in application code.
This cannot change the learned translation quality of the M2M100 checkpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable

from .processing import MAX_TEXT
from .translation_protocol import validate_translation

# Keep input well below the 512-token source tokenizer limit. Characters are
# not tokens: the adapter must still check actual tokenizer lengths.
MAX_SEGMENT_CHARS = 180
MAX_SEGMENTS = 48
_SENTENCE_BOUNDARY = frozenset(".!?。！？؟\n")
_SCRIPT_HAN = re.compile(r"[\u3400-\u9fff]")
_SCRIPT_KANA = re.compile(r"[\u3040-\u30ff]")
_SCRIPT_HANGUL = re.compile(r"[\u1100-\u11ff\uac00-\ud7af]")
_SCRIPT_THAI = re.compile(r"[\u0e01-\u0e5b]")
_SCRIPT_DEVANAGARI = re.compile(r"[\u0900-\u097f]")
_SCRIPT_CYRILLIC = re.compile(r"[\u0400-\u052f]")
_SCRIPT_LATIN = re.compile(r"[A-Za-zÀ-ÿ]")


@dataclass(frozen=True)
class M2MTranslationPlan:
    """Application metadata; never serialized as input to M2M100."""
    source_language: str
    target_language: str
    segments: tuple[str, ...]


def infer_source_language(text: str) -> str:
    """Best-effort script hint, not a semantic language classifier.

    Han-only strings are ambiguous between Chinese/Japanese. A fallback is
    safer than treating Japanese Kanji as Chinese. Latin defaults to English
    for backwards compatibility; select explicit source for Latin languages.
    """
    if _SCRIPT_KANA.search(text):
        return "ja"
    if _SCRIPT_HANGUL.search(text):
        return "ko"
    if _SCRIPT_THAI.search(text):
        return "th"
    if _SCRIPT_DEVANAGARI.search(text):
        return "hi"
    if _SCRIPT_CYRILLIC.search(text):
        return "ru"
    if _SCRIPT_HAN.search(text):
        raise ValueError("Han-only text is ambiguous (Chinese/Japanese); choose the source language")
    if _SCRIPT_LATIN.search(text):
        return "en"
    raise ValueError("source language unknown; select it explicitly for M2M100")


def ambiguous_han_source(text: str) -> bool:
    return bool(_SCRIPT_HAN.search(text) and not _SCRIPT_KANA.search(text)
                and not _SCRIPT_HANGUL.search(text) and not _SCRIPT_THAI.search(text)
                and not _SCRIPT_DEVANAGARI.search(text) and not _SCRIPT_CYRILLIC.search(text))


def split_preserving_text(text: str, *,
                          limit: int = MAX_SEGMENT_CHARS,
                          max_segments: int = MAX_SEGMENTS) -> tuple[str, ...]:
    """Split long input at sentences/whitespace; never discard punctuation.

    The exact source is reconstructible from the parts. If splitting is
    infeasible within a bounded number of model calls, fail rather than
    truncate a portion of the text.
    """
    if not isinstance(text, str) or not text or len(text) > MAX_TEXT:
        raise ValueError("invalid M2M100 input length")
    if not 32 <= limit <= 512 or not 1 <= max_segments <= 64:
        raise ValueError("invalid M2M100 segment bounds")
    result: list[str] = []
    rest = text
    while len(rest) > limit:
        window = rest[:limit + 1]
        lower = max(16, limit // 3)
        boundaries = [i + 1 for i, c in enumerate(window[:limit])
                      if c in _SENTENCE_BOUNDARY and i + 1 >= lower]
        if boundaries:
            cut = boundaries[-1]
        else:
            spaces = [m.end() for m in re.finditer(r"\s+", window[:limit])
                      if m.end() >= lower]
            cut = spaces[-1] if spaces else limit
        result.append(rest[:cut])
        rest = rest[cut:]
        if len(result) >= max_segments:
            raise ValueError("too many M2M100 translation segments")
    if rest:
        result.append(rest)
    if len(result) > max_segments or "".join(result) != text:
        raise ValueError("M2M100 segment planning failed")
    return tuple(result)


def plan_translation(text: str, source_language: str,
                     target_language: str) -> M2MTranslationPlan:
    if not isinstance(source_language, str) or not isinstance(target_language, str):
        raise ValueError("invalid M2M100 language codes")
    from .ai_processing import LANGUAGES
    source = (infer_source_language(text) if source_language == "auto"
              else source_language)
    if source not in LANGUAGES or target_language not in LANGUAGES:
        raise ValueError("M2M100 requires supported source and target languages")
    return M2MTranslationPlan(source, target_language, split_preserving_text(text))


def translate_structured(text: str, settings: dict[str, Any],
                         model_call: Callable[[str, dict[str, Any],
                                               list[dict[str, str]]], str],
                         context: list[dict[str, str]]) -> str:
    """Translate bounded segments and join in source order.

    Strings sent to M2M100 contain only natural-language input; metadata is
    passed separately through the adapter settings. No prompt/JSON is given
    to a non-instruction-following translation model.
    """
    plan = plan_translation(text, settings["source_language"],
                            settings["target_language"])
    if plan.source_language == plan.target_language:
        return text
    chosen = {**settings, "source_language": plan.source_language}
    out: list[str] = []
    for segment in plan.segments:
        body = segment.strip()
        if not body:
            out.append(segment)
            continue
        left_len = len(segment) - len(segment.lstrip())
        right_len = len(segment) - len(segment.rstrip())
        translated = model_call(body, chosen, context)
        translated = validate_translation(
            body, translated, plan.target_language,
            bypass_content_checks=settings.get("translation_bypass_validation", False))
        out.append(segment[:left_len] + translated
                   + (segment[len(segment) - right_len:] if right_len else ""))
        if sum(len(item) for item in out) > MAX_TEXT:
            raise ValueError("M2M100 combined translation is excessive")
    return "".join(out)
