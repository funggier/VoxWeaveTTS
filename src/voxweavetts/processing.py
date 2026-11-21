"""Deterministic, dependency-free, Thai-friendly text filtering foundation.

Only text planning is implemented here. Audio generation/playback remains separate.
"""
from __future__ import annotations

import re
from functools import lru_cache
from dataclasses import dataclass
from typing import Any, Mapping

MAX_TEXT = 8_000
MAX_RULES = 128
MAX_SILENCE_MS = 10_000
# Predefined, bounded pattern; it is not arbitrary user-supplied regex.
# Exclude digit sequences within larger numbers and decimal/grouped numbers.
_FIVE_RUN = re.compile(r'(?<!\d)(?<!\d[.,])5{3,}(?!\d)(?![.,]\d)')


@lru_cache(maxsize=256)
def _repeat_pattern(unit: str, minimum: int) -> re.Pattern[str]:
    """A bounded literal *unit* run, never arbitrary user regex.

    Digits must not be interpreted as laughter inside decimal/grouped values.
    Latin sequences must be whole tokens, not suffixes of normal English
    words or domains. For Thai and Unicode emoji units, allow adjacent prose.
    """
    escaped = re.escape(unit)
    repeated = rf"(?:{escaped}){{{minimum},}}"
    if len(unit) == 1 and unit.isdecimal():
        return re.compile(r"(?<!\d)(?<!\d[.,])" + repeated
                          + r"(?!\d)(?![.,]\d)")
    if unit.isascii() and any(ch.isalpha() for ch in unit):
        return re.compile(r"(?<![A-Za-z0-9_])" + repeated
                          + r"(?![A-Za-z0-9_.])")
    return re.compile(repeated)


@lru_cache(maxsize=256)
def _phrase_pattern(phrase: str, minimum: int) -> re.Pattern[str]:
    """Find complete, whitespace-separated repetitions of one literal phrase."""
    literal = re.escape(phrase)
    return re.compile(r"(?<!\w)" + literal +
                      rf"(?:\s+{literal}){{{minimum - 1},}}" + r"(?!\w)")
# These are spoken laugh approximations, NOT language translation. Only the
# known legacy Thai 555 rule is localized; arbitrary user replacements remain
# exactly as specified unless spoken_by_language explicitly overrides them.
_FIVE_LAUGH = {
    "zh": "哈哈哈", "ja": "ははは", "ko": "하하하", "en": "ha ha ha",
    "hi": "हा हा हा", "ru": "ха ха ха", "uk": "ха ха ха",
    "bg": "ха ха ха", "ar": "ها ها ها", "el": "χα χα χα",
}
_THAI_FIVE_LAUGHS = frozenset({"ฮ่า ฮ่า ฮ่า", "ฮ่าฮ่าฮ่า", "ฮ่าๆ", "ฮ่า ฮ่า"})


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
    stage: str = "post_ai"
    spoken_by_language: tuple[tuple[str, str], ...] = ()
    min_repeats: int = 0

    @classmethod
    def parse(cls, raw: Any) -> "Rule":
        if not isinstance(raw, Mapping):
            raise InputError("each rule must be an object")
        match_mode = raw.get("match_mode", "literal")
        if match_mode not in {"literal", "five_run", "repeat_run", "phrase_run"}:
            raise InputError("match_mode must be literal, five_run, repeat_run or phrase_run")
        match = _text(raw.get("match", "555" if match_mode == "five_run" else None), "match", 200)
        if not match:
            raise InputError("match cannot be empty")
        if match_mode == "five_run" and match != "555":
            raise InputError("five_run requires match=555")
        minimum = 0
        if match_mode in {"repeat_run", "phrase_run"}:
            if (match_mode == "repeat_run" and
                (len(match) > 16 or any(ch.isspace() or ord(ch) < 32 for ch in match))):
                raise InputError("repeat_run match must be one non-whitespace unit of up to 16 characters")
            if match_mode == "phrase_run" and (len(match) > 100 or
                match != match.strip() or any(ord(ch) < 32 for ch in match)):
                raise InputError("phrase_run match must be a trimmed phrase of at most 100 characters")
            minimum = raw.get("min_repeats")
            if type(minimum) is not int or not 2 <= minimum <= 1000:
                raise InputError("min_repeats must be an integer from 2 to 1000")
        elif "min_repeats" in raw:
            raise InputError("min_repeats is only allowed for repeated match modes")
        mode = raw.get("mode", "replace")
        if mode not in {"replace", "skip", "silence"}:
            raise InputError("mode must be replace, skip, or silence")
        stage = raw.get("stage", "post_ai")
        if stage not in {"pre_ai", "post_ai"}:
            raise InputError("stage must be pre_ai or post_ai")
        if stage == "pre_ai" and mode == "silence":
            raise InputError("silence cannot be preserved through AI; use post_ai for silence")
        spoken = raw.get("spoken")
        if spoken is not None:
            spoken = _text(spoken, "spoken", 500)
        localized = raw.get("spoken_by_language", {})
        if (not isinstance(localized, Mapping) or len(localized) > 48
                or any(not isinstance(lang, str) or not re.fullmatch(r"[a-z]{2}", lang)
                       for lang in localized)):
            raise InputError("spoken_by_language must map 2-letter language codes")
        spoken_by_language = tuple(
            (lang, _text(translation, "localized spoken", 500))
            for lang, translation in localized.items()
        )
        if (mode != "replace" or stage != "post_ai") and spoken_by_language:
            raise InputError("localized spoken text is only valid for post-AI replacement")
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
        return cls(match, mode, spoken, display, duration, tuple(sources),
                   match_mode, stage, spoken_by_language, minimum)

    def applies_to(self, source: str) -> bool:
        return not self.sources or source in self.sources

    def find(self, text: str, position: int) -> tuple[int, str] | None:
        if self.match_mode == "five_run":
            result = _FIVE_RUN.search(text, position)
            return (result.start(), result.group()) if result else None
        if self.match_mode == "repeat_run":
            result = _repeat_pattern(self.match, self.min_repeats).search(text, position)
            return (result.start(), result.group()) if result else None
        if self.match_mode == "phrase_run":
            result = _phrase_pattern(self.match, self.min_repeats).search(text, position)
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
    language: str | None = None,
) -> dict[str, Any]:
    """Create a speech plan and a separately masked subtitle string."""
    text = _text(text, "text", MAX_TEXT)
    source = _text(source, "source", 64)
    if not source:
        raise InputError("source cannot be empty")
    if language is not None and (not isinstance(language, str)
                                 or not re.fullmatch(r"[a-z]{2}", language)):
        raise InputError("invalid speech replacement language")
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
        candidate: tuple[int, int, int, int, Rule, str] | None = None
        for priority, rule in enumerate(active):
            result = rule.find(text, position)
            if result is None:
                continue
            index, matched = result
            # Compare earliest position, longest *whole run*, then highest
            # minimum threshold. A 7+ rule overrides 5+/3+ even when it
            # was added later in the JSON list; literal legacy ties stay FIFO.
            specificity = -rule.min_repeats if rule.match_mode in {"repeat_run", "phrase_run"} else 0
            rank = (index, -len(matched), specificity, priority, rule, matched)
            if candidate is None or rank[:4] < candidate[:4]:
                candidate = rank

        if candidate is None:
            original = text[position:]
            add_segment("speech", apply_pronunciations(original, pronunciations),
                        original, position, len(text))
            break
        index, _neg_length, _specificity, _priority, rule, matched = candidate
        if index > position:
            original = text[position:index]
            add_segment("speech", apply_pronunciations(original, pronunciations),
                        original, position, index)
        end = index + len(matched)
        if rule.mode == "replace":
            # For phrase_run, default spoken is the phrase ONCE. The original
            # (possibly long) repeated phrase remains in display/subtitles.
            spoken = (rule.match if rule.match_mode == "phrase_run" else matched
                      ) if rule.spoken is None else rule.spoken
            if language:
                overrides = dict(rule.spoken_by_language)
                if language in overrides:
                    spoken = overrides[language]
                elif (rule.stage == "post_ai" and rule.match_mode == "five_run"
                      and spoken in _THAI_FIVE_LAUGHS and language != "th"):
                    spoken = _FIVE_LAUGH.get(language, "ha ha ha")
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