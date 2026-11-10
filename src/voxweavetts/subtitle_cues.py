"""Model-independent, explicitly ESTIMATED caption windows.

Only segment boundaries are grounded in generated WAV sample counts.
Within a speech segment, text is divided into grapheme-safe display windows;
the allocated timing is proportional to grapheme count, NOT forced alignment.
Do not call these word-aligned subtitles or claim phoneme timing.
"""
from __future__ import annotations

import unicodedata
from typing import Any

from .text_boundaries import natural_break_positions

MODE_SEGMENT = "segment"
MODE_ESTIMATED = "estimated"
MODE_ACTIVITY = "activity"
MODE_MANUAL = "manual"
MODES = frozenset({MODE_SEGMENT, MODE_ESTIMATED, MODE_ACTIVITY, MODE_MANUAL})


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
    """Split only at explicit *natural* text boundaries.

    Thai consonant/vowel runs cannot safely be divided into words based on
    Unicode grapheme count. When no whitespace/punctuation is available,
    leave the whole generated speech segment visible instead of guessing.
    Timing for the safe text groups remains estimated, NOT audio alignment.
    """
    result: list[dict[str, Any]] = []
    for part in segments:
        start, end = part["start_ms"], part["end_ms"]
        text = part["display_text"] if part["kind"] == "speech" else ""
        duration = end - start
        if not text or part["kind"] != "speech" or duration < 800:
            result.append({
                "start_ms": start, "end_ms": end,
                "kind": part["kind"], "display_text": text,
            })
            continue
        graphemes = _clusters(text)
        max_groups = min(12, len(graphemes) // 22, duration // 400)
        # Explicit separators only: no consonant/coda or Thai pre-vowel
        # can be sliced off by an estimated character-count window.
        options = natural_break_positions(text)
        if max_groups < 2 or not options:
            result.append({
                "start_ms": start, "end_ms": end,
                "kind": "speech", "display_text": text,
            })
            continue
        # Choose balanced explicit boundaries; discard tiny final cues.
        # Offsets are code points, never byte indices.
        cuts: list[int] = []
        prev = 0
        for group in range(1, max_groups):
            goal = round(len(text) * group / max_groups)
            available = [
                cut for cut in options
                if cut > prev
                and cut not in cuts
                and duration * (cut - prev) >= 400 * len(text)
                and duration * (len(text) - cut) >= 400 * len(text)
            ]
            if not available:
                break
            chosen = min(available, key=lambda cut: (abs(cut - goal), cut))
            cuts.append(chosen)
            prev = chosen
        boundaries = [0] + cuts + [len(text)]
        # Weight timings by real Unicode grapheme counts, never character
        # count alone. This is still an estimate of *speech* duration.
        total = len(graphemes)
        for first, last in zip(boundaries, boundaries[1:]):
            covered = len(_clusters(text[:first]))
            finished = len(_clusters(text[:last]))
            result.append({
                "start_ms": start + duration * covered // total,
                "end_ms": start + duration * finished // total,
                "kind": "speech", "display_text": text[first:last],
            })
    return result

def caption_for(
    segments: list[dict[str, Any]], position_ms: int, mode: str = MODE_SEGMENT,
    manual_cues: list[dict[str, Any]] | None = None,
) -> str:
    if mode not in MODES or type(position_ms) is not int or position_ms < 0:
        return ""
    if mode == MODE_MANUAL:
        for cue in manual_cues or []:
            if cue["start_ms"] <= position_ms < cue["end_ms"]:
                return cue["display_text"]
        # No fabricated words/timing when a portion is unannotated.
        return ""
    cues = estimated_cues(segments) if mode == MODE_ESTIMATED else segments
    for cue in cues:
        if cue["start_ms"] <= position_ms < cue["end_ms"]:
            if cue["kind"] != "speech":
                return ""
            if mode == MODE_ACTIVITY and "activity_intervals" in cue:
                # Empty list means analyzed speech segment had no audible
                # energy; do not show text over an all-silent waveform.
                if not any(interval["start_ms"] <= position_ms < interval["end_ms"]
                           for interval in cue["activity_intervals"]):
                    return ""
            return cue["display_text"]
    return ""