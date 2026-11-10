"""Model-independent, explicitly ESTIMATED caption windows.

Only segment boundaries are grounded in generated WAV sample counts.
Within a speech segment, text is divided into grapheme-safe display windows;
the allocated timing is proportional to grapheme count, NOT forced alignment.
Do not call these word-aligned subtitles or claim phoneme timing.
"""
from __future__ import annotations

import unicodedata
from typing import Any

MODE_SEGMENT = "segment"
MODE_ESTIMATED = "estimated"
MODES = frozenset({MODE_SEGMENT, MODE_ESTIMATED})


def _clusters(value: str) -> list[str]:
    result: list[str] = []
    regional_run = 0
    for char in value:
        code = ord(char)
        regional = 0x1F1E6 <= code <= 0x1F1FF
        join = (
            unicodedata.combining(char) != 0
            or unicodedata.category(char) in ("Mn", "Mc", "Me")
            or char == "\u200d"
            or 0xFE00 <= code <= 0xFE0F
            or 0xE0100 <= code <= 0xE01EF
            or 0x1F3FB <= code <= 0x1F3FF
            or (result and result[-1].endswith("\u200d"))
            or (regional and regional_run % 2 == 1)
        )
        if join and result:
            result[-1] += char
        else:
            result.append(char)
        regional_run = regional_run + 1 if regional else 0
    return result


def estimated_cues(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a bounded, grapheme-safe, estimated cue list, preserving silence.

    A synthetic window never crosses a real generated segment boundary.
    """
    result: list[dict[str, Any]] = []
    for part in segments:
        start = part["start_ms"]
        end = part["end_ms"]
        text = part["display_text"] if part["kind"] == "speech" else ""
        if not text or part["kind"] != "speech" or end - start < 600:
            result.append({
                "start_ms": start, "end_ms": end,
                "kind": part["kind"], "display_text": text,
            })
            continue
        graphemes = _clusters(text)
        # No more than 12 blocks, and each predicted block gets >= 400 ms.
        total = min(12, len(graphemes) // 22, (end - start) // 400)
        if total < 2:
            result.append({
                "start_ms": start, "end_ms": end,
                "kind": part["kind"], "display_text": text,
            })
            continue
        n = len(graphemes)
        # Proportional character-count windows; Thai text needs a real
        # aligner to determine where spoken-word boundaries actually fall.
        for i in range(total):
            first = (i * n) // total
            last = ((i + 1) * n) // total
            result.append({
                "start_ms": start + (i * (end - start)) // total,
                "end_ms": start + ((i + 1) * (end - start)) // total,
                "kind": "speech",
                "display_text": "".join(graphemes[first:last]),
            })
    return result


def caption_for(
    segments: list[dict[str, Any]], position_ms: int, mode: str = MODE_SEGMENT,
) -> str:
    if mode not in MODES or type(position_ms) is not int or position_ms < 0:
        return ""
    cues = estimated_cues(segments) if mode == MODE_ESTIMATED else segments
    for cue in cues:
        if cue["start_ms"] <= position_ms < cue["end_ms"]:
            return cue["display_text"] if cue["kind"] == "speech" else ""
    return ""