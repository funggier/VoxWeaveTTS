"""Conservative script-based language spans for optional mixed-language TTS.

Only identifiable scripts are inferred: Latin defaults to English, Cyrillic to
Russian. Han adjacent to Japanese kana in the same unbroken CJK word is
Japanese; isolated Han defaults to Chinese. This is not a language classifier.
Neutral punctuation and spaces stay with the preceding spoken span, avoiding
missing characters when voices change.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageSpan:
    language: str
    text: str
    start: int
    end: int


def _script(ch: str) -> str | None:
    cp = ord(ch)
    if 0x0E00 <= cp <= 0x0E7F:
        return "th"
    if (0x3040 <= cp <= 0x30FF or 0x31F0 <= cp <= 0x31FF
            or 0xFF66 <= cp <= 0xFF9F):
        return "ja"
    if (0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF
            or 0x3130 <= cp <= 0x318F):
        return "ko"
    if (0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF
            or 0xF900 <= cp <= 0xFAFF):
        return "han"
    if 0x0900 <= cp <= 0x097F:
        return "hi"
    if 0x0370 <= cp <= 0x03FF:
        return "el"
    if 0x0600 <= cp <= 0x06FF:
        return "ar"
    if 0x0400 <= cp <= 0x052F:
        return "ru"
    if ch.isalpha() and "LATIN" in unicodedata.name(ch, ""):
        return "en"
    return None


def split_language_spans(text: str) -> list[LanguageSpan]:
    """Preserve every code point in order, including punctuation/whitespace.

    No words are translated. One unconfigured language falls back to the
    caller's default engine; voice routing is a separate explicit choice.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text:
        return []
    kinds = [_script(ch) for ch in text]
    # A Han+kana word must be read as Japanese, e.g. 多分殻ごと食ってる.
    # Whitespace/punctuation separates words; do not globally turn Chinese
    # into Japanese merely because another word has kana elsewhere.
    i = 0
    while i < len(text):
        if kinds[i] not in ("han", "ja"):
            i += 1
            continue
        end = i + 1
        while end < len(text) and kinds[end] in ("han", "ja"):
            end += 1
        if "ja" in kinds[i:end]:
            kinds[i:end] = ["ja"] * (end - i)
        else:
            kinds[i:end] = ["zh"] * (end - i)
        i = end

    spans: list[LanguageSpan] = []
    active: str | None = None
    start = 0
    for index, kind in enumerate(kinds):
        if kind is None:
            continue
        if active is None:
            active = kind
        elif kind != active:
            spans.append(LanguageSpan(active, text[start:index], start, index))
            start = index
            active = kind
    if active is None:
        return [LanguageSpan("und", text, 0, len(text))]
    spans.append(LanguageSpan(active, text[start:], start, len(text)))
    return spans
