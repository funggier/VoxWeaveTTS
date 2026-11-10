"""Conservative text boundary helpers for Thai TTS narration and captions.

Python stdlib cannot perform dictionary-based Thai word segmentation. We
therefore split at explicit whitespace/punctuation first, NEVER at an
arbitrary position in a continuous Thai word run for estimated captions.
Document chunks have a hard request-size limit and may require a documented
best-effort Unicode-safe fallback for exceptionally long unbroken runs.
"""
from __future__ import annotations

import unicodedata

THAI_LEADING_VOWELS = frozenset("เแโใไ")
# Explicit natural separators, not guesses at unspaced Thai word boundaries.
SENTENCE_ENDS = frozenset(".!?。！？;；ฯ…")
SOFT_PUNCTUATION = frozenset(",，:：")


def unsafe_unicode_boundary(text: str, index: int) -> bool:
    """No cut inside common Unicode grapheme sequences or after a Thai pre-vowel."""
    if index <= 0 or index >= len(text):
        return False
    previous, following = text[index - 1], text[index]
    code = ord(following)
    if (previous in THAI_LEADING_VOWELS
        or unicodedata.combining(following)
        or unicodedata.category(following) in ("Mn", "Mc", "Me")
        or following == "\u200d" or previous == "\u200d"
        or 0xFE00 <= code <= 0xFE0F
        or 0xE0100 <= code <= 0xE01EF
        or 0x1F3FB <= code <= 0x1F3FF):
        return True
    if 0x1F1E6 <= ord(previous) <= 0x1F1FF and 0x1F1E6 <= code <= 0x1F1FF:
        count = 0
        k = index - 1
        while k >= 0 and 0x1F1E6 <= ord(text[k]) <= 0x1F1FF:
            count += 1
            k -= 1
        return count % 2 == 1
    return False


def natural_break_positions(text: str) -> list[int]:
    """Return no-guess cut locations after explicit separators only.

    A Thai run without whitespace/punctuation has no such positions.
    """
    cuts = []
    for index in range(1, len(text)):
        left, right = text[index - 1], text[index]
        if unsafe_unicode_boundary(text, index):
            continue
        if left.isspace():
            cuts.append(index)
        elif left in SENTENCE_ENDS:
            if right not in SENTENCE_ENDS and right not in SOFT_PUNCTUATION and right not in "\"\u201d\u2019)]}" and not (left == "." and right.isdigit()):
                cuts.append(index)
        elif left in SOFT_PUNCTUATION:
            if not (left in ".," and right.isdigit()):
                cuts.append(index)
    return cuts


def thai_leading_vowel_fallbacks(text: str, start: int, end: int) -> list[int]:
    """Best-effort hard-limit fallback: cut *before* a Thai preposed vowel.

    This is a syllable onset hint, NOT a dictionary-proven word boundary.
    """
    return [
        i for i in range(max(1, start), min(len(text), end + 1))
        if text[i] in THAI_LEADING_VOWELS
        and not unsafe_unicode_boundary(text, i)
    ]