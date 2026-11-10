"""Deterministic, dependency-free, Thai-friendly text filtering foundation.

Only text planning is implemented here. Audio generation/playback remains separate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

MAX_TEXT = 8_000
MAX_RULES = 128
MAX_SILENCE_MS = 10_000
# Predefined, bounded pattern; it is not arbitrary user-supplied regex.
# Exclude digit sequences within larger numbers and decimal/grouped numbers.
_FIVE_RUN = re.compile(r'(?<!\d)(?<!\d[.,])5{3,}(?!\d)(?![.,]\d)')


class InputError(ValueError):
    """Invalid caller-supplied filter or pronunciation configuration."""


def _text(value: Any, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise InputError(f"{field} must be a string")
    if len(value) > max_length:
        raise InputError(f"{field} must be at most {max_length} characters")
    return value


@dataclass(frozen=True)
class Rule:
    match: str
    mode: str
    spoken: str | None = None
    display: str | None = None
    silence_ms: int = 0
    sources: tuple[str, ...] = ()
    match_mode: str = "literal"

    @classmethod
    def parse(cls, raw: Any) -> "Rule":
        if not isinstance(raw, Mapping):
            raise InputError("each rule must be an object")
        match_mode = raw.get("match_mode", "literal")
        if match_mode not in {"literal", "five_run"}:
            raise InputError("match_mode must be literal or five_run")
        match = _text(raw.get("match", "555" if match_mode == "five_run" else None), "match", 200)
        if not match:
            raise InputError("match cannot be empty")
        if match_mode == "five_run" and match != "555":
            raise InputError("five_run requires match=555")
        mode = raw.get("mode", "replace")
        if mode not in {"replace", "skip", "silence"}:
            raise InputError("mode must be replace, skip, or silence")
        spoken = raw.get("spoken")
        if spoken is not None:
            spoken = _text(spoken, "spoken", 500)
        display = raw.get("display")
        if display is not None:
            display = _text(display, "display", 500)
        duration = raw.get("silence_ms", 400 if mode == "silence" else 0)
        if type(duration) is not int or not 0 <= duration <= MAX_SILENCE_MS:
            raise InputError("silence_ms must be an integer from 0 to 10000")
        sources = raw.get("sources", [])
        if not isinstance(sources, list) or len(sources) > 32 or not all(
            isinstance(v, str) and 0 < len(v) <= 64 for v in sources
        ):
            raise InputError("sources must be a list of non-empty short strings")
        return cls(match, mode, spoken, display, duration, tuple(sources), match_mode)

    def applies_to(self, source: str) -> bool:
        return not self.sources or source in self.sources

    def find(self, text: str, position: int) -> tuple[int, str] | None:
        if self.match_mode == "five_run":
            result = _FIVE_RUN.search(text, position)
            return (result.start(), result.group()) if result else None
        index = text.find(self.match, position)
        return (index, self.match) if index >= 0 else None


def parse_rules(raw: Any) -> list[Rule]:
    if not isinstance(raw, list) or len(raw) > MAX_RULES:
        raise InputError("rules must be a list containing at most 128 rules")
    return [Rule.parse(rule) for rule in raw]


def parse_pronunciations(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict) or len(raw) > 512:
        raise InputError("pronunciations must be a map with at most 512 entries")
    result: dict[str, str] = {}
    for key, value in raw.items():
        key = _text(key, "pronunciation key", 200)
        value = _text(value, "pronunciation value", 500)
        if not key or not value:
            raise InputError("pronunciation keys and values cannot be empty")
        result[key] = value
    return result


def apply_pronunciations(text: str, dictionary: Mapping[str, str]) -> str:
    """Longest literal match in one pass; replacements cannot cascade."""
    if not dictionary:
        return text
    keys = sorted(dictionary, key=len, reverse=True)
    out: list[str] = []
    index = 0
    while index < len(text):
        found = next((key for key in keys if text.startswith(key, index)), None)
        if found is None:
            out.append(text[index])
            index += 1
        else:
            out.append(dictionary[found])
            index += len(found)
    return "".join(out)


def process_text(
    text: str,
    rules: list[dict[str, Any]] | list[Rule] | None = None,
    pronunciations: dict[str, str] | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    """Create a speech plan and a separately masked subtitle string."""
    text = _text(text, "text", MAX_TEXT)
    source = _text(source, "source", 64)
    if not source:
        raise InputError("source cannot be empty")
    rules = [] if rules is None else rules
    active = (
        rules if all(isinstance(rule, Rule) for rule in rules) else parse_rules(rules)
    )
    active = [rule for rule in active if rule.applies_to(source)]
    pronunciations = parse_pronunciations(
        {} if pronunciations is None else pronunciations
    )

    segments: list[dict[str, Any]] = []

    def add_segment(kind: str, spoken: str, display: str, start: int,
                    end: int, silence_ms: int = 0) -> None:
        segments.append({
            "kind": kind,
            "spoken_text": spoken,
            "display_text": display,
            "source_start": start,
            "source_end": end,
            "silence_ms": silence_ms,
        })

    position = 0
    while position < len(text):
        candidate: tuple[int, int, int, Rule, str] | None = None
        for priority, rule in enumerate(active):
            result = rule.find(text, position)
            if result is None:
                continue
            index, matched = result
            rank = (index, -len(matched), priority, rule, matched)
            if candidate is None or rank[:3] < candidate[:3]:
                candidate = rank

        if candidate is None:
            original = text[position:]
            add_segment("speech", apply_pronunciations(original, pronunciations),
                        original, position, len(text))
            break
        index, _neg_length, _priority, rule, matched = candidate
        if index > position:
            original = text[position:index]
            add_segment("speech", apply_pronunciations(original, pronunciations),
                        original, position, index)
        end = index + len(matched)
        if rule.mode == "replace":
            spoken = matched if rule.spoken is None else rule.spoken
            display = matched if rule.display is None else rule.display
            add_segment("speech", apply_pronunciations(spoken, pronunciations),
                        display, index, end)
        elif rule.mode == "silence":
            add_segment("silence", "", "***" if rule.display is None else rule.display,
                        index, end, rule.silence_ms)
        else:
            add_segment("skip", "", "***" if rule.display is None else rule.display,
                        index, end)
        position = end

    return {
        "source": source,
        "display_text": "".join(seg["display_text"] for seg in segments),
        "spoken_text": "".join(seg["spoken_text"] for seg in segments),
        "segments": segments,
    }