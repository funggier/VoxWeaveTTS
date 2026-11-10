"""Engine-neutral, user-timed subtitle cues and deterministic timing evaluation.

Manual alignment is not machine forced alignment. The caller provides
selection offsets into *public display text* and media timestamps; no arbitrary
text is accepted. The aligned cue text is sliced from the already-filtered
speech timeline. Cues remain in-memory with their speech job by default.
"""
from __future__ import annotations

import unicodedata
from typing import Any

from .processing import InputError

MAX_CUES = 128


def _valid_boundary(text: str, offset: int) -> bool:
    if offset in (0, len(text)):
        return True
    right = text[offset]
    left = text[offset - 1]
    code = ord(right)
    if (unicodedata.combining(right)
            or unicodedata.category(right) in ("Mn", "Mc", "Me")
            or right == "\u200d" or left == "\u200d"
            or 0xFE00 <= code <= 0xFE0F
            or 0xE0100 <= code <= 0xE01EF
            or 0x1F3FB <= code <= 0x1F3FF):
        return False
    # Keep both regional indicators forming a flag together.
    if 0x1F1E6 <= ord(left) <= 0x1F1FF and 0x1F1E6 <= code <= 0x1F1FF:
        preceding = 0
        k = offset - 1
        while k >= 0 and 0x1F1E6 <= ord(text[k]) <= 0x1F1FF:
            preceding += 1
            k -= 1
        return preceding % 2 == 0
    return True


def validate_manual_cues(
    segments: list[dict[str, Any]], cues: Any,
) -> list[dict[str, Any]]:
    """Validate ordered, non-overlapping timecodes with public text offsets.

    A cue never crosses the segment that generated it, nor enters a
    silence/masked/skip segment. Duration must come from a ready WAV job.
    """
    if not isinstance(cues, list) or len(cues) > MAX_CUES:
        raise InputError(f"manual alignment accepts at most {MAX_CUES} cues")
    if not isinstance(segments, list) or len(segments) > 512:
        raise InputError("invalid generated audio timeline")
    safe = []
    previous_time = 0
    previous_positions: dict[int, int] = {}
    for item in cues:
        keys = {"segment_index", "start_offset", "end_offset", "start_ms", "end_ms"}
        if (not isinstance(item, dict)
                or set(item) not in (keys, keys | {"display_text"})):
            raise InputError("manual cue has invalid fields")
        index = item["segment_index"]
        if type(index) is not int or not 0 <= index < len(segments):
            raise InputError("manual cue segment_index out of range")
        segment = segments[index]
        if segment.get("kind") != "speech":
            raise InputError("manual cues may only refer to speech segments")
        text = segment.get("display_text")
        start_off, end_off = item["start_offset"], item["end_offset"]
        start_ms, end_ms = item["start_ms"], item["end_ms"]
        if (not isinstance(text, str)
            or type(start_off) is not int or type(end_off) is not int
            or not 0 <= start_off < end_off <= len(text)
            or not _valid_boundary(text, start_off)
            or not _valid_boundary(text, end_off)):
            raise InputError("manual cue text range splits Unicode or exceeds display text")
        if "display_text" in item and item["display_text"] != text[start_off:end_off]:
            raise InputError("manual cue display_text does not match filtered source")
        if not text[start_off:end_off].strip():
            raise InputError("manual cue must contain visible display text")
        if (type(start_ms) is not int or type(end_ms) is not int
            or not segment["start_ms"] <= start_ms < end_ms <= segment["end_ms"]
            or start_ms < previous_time):
            raise InputError("manual cue time range overlaps or exceeds its speech segment")
        if start_off < previous_positions.get(index, 0):
            raise InputError("manual cue text ranges overlap or reverse")
        previous_time = end_ms
        previous_positions[index] = end_off
        safe.append({
            "segment_index": index,
            "start_offset": start_off, "end_offset": end_off,
            "start_ms": start_ms, "end_ms": end_ms,
            "display_text": text[start_off:end_off],
        })
    return safe


def timing_metrics(candidate: Any, reference: Any) -> dict[str, Any]:
    """Compare exact cue identities (segment + text offsets) without guesses.

    Partial coverage is reported, never silently matched to an unrelated word.
    Human-reviewed reference data is required for meaningful error metrics.
    """
    def keyed(items: Any) -> dict[tuple[int, int, int], tuple[int, int]]:
        if not isinstance(items, list) or len(items) > MAX_CUES:
            raise InputError("invalid evaluation cues")
        seen = {}
        for item in items:
            if not isinstance(item, dict):
                raise InputError("invalid evaluation cue")
            keys = ("segment_index", "start_offset", "end_offset", "start_ms", "end_ms")
            if any(type(item.get(k)) is not int or item[k] < 0 for k in keys):
                raise InputError("invalid evaluation cue timing")
            if not item["start_offset"] < item["end_offset"] or not item["start_ms"] < item["end_ms"]:
                raise InputError("invalid cue interval")
            key = (item["segment_index"], item["start_offset"], item["end_offset"])
            if key in seen:
                raise InputError("duplicate evaluation cue")
            seen[key] = (item["start_ms"], item["end_ms"])
        return seen

    a, b = keyed(candidate), keyed(reference)
    matched = a.keys() & b.keys()
    errors = [
        abs(x-y)
        for key in matched
        for x, y in zip(a[key], b[key])
    ]
    return {
        "candidate_cues": len(a), "reference_cues": len(b),
        "matched_cues": len(matched),
        "reference_coverage_percent": (
            round(100.0 * len(matched)/len(b), 2) if b else None
        ),
        "mean_absolute_boundary_error_ms": (
            round(sum(errors)/len(errors), 2) if errors else None
        ),
        "max_absolute_boundary_error_ms": max(errors) if errors else None,
        "boundaries_within_100ms_percent": (
            round(100.0 * sum(e <= 100 for e in errors)/len(errors), 2)
            if errors else None
        ),
        "timing_basis": "comparison_to_user_verified_reference",
    }