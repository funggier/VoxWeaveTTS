"""Shared text pipeline: mode-normalized content -> pre-AI -> AI -> post-AI -> TTS.

Sender prefix is already formatted by its mode, and NEVER enters the AI or
shared rules. Source-facing display metadata remains separate from the plan.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from .processing import InputError, Rule, parse_rules, process_text, MAX_TEXT
from .ai_processing import DEFAULTS, process_ai, validate_settings


def process_pipeline(
    text: str,
    *,
    source: str = "manual",
    rules: list[dict[str, Any]] | list[Rule] | None = None,
    pronunciations: dict[str, str] | None = None,
    settings: dict[str, Any] | None = None,
    sender_prefix_text: str = "",
    model_call: Callable | None = None,
) -> dict[str, Any]:
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        raise InputError("text must be a string of at most 8000 characters")
    if not isinstance(sender_prefix_text, str) or len(sender_prefix_text) > 180:
        raise InputError("sender_prefix_text must be at most 180 characters")
    if re.search(r"[\u0000-\u001f\u007f]", sender_prefix_text):
        raise InputError("sender_prefix_text contains control characters")
    sender = sender_prefix_text.strip()
    parsed = (rules if rules is not None and all(isinstance(r, Rule) for r in rules)
              else parse_rules([] if rules is None else rules))
    pre = [rule for rule in parsed if rule.stage == "pre_ai"]
    post = [rule for rule in parsed if rule.stage == "post_ai"]
    pre_plan = process_text(text, rules=pre, source=source, pronunciations={})
    filtered = pre_plan["spoken_text"]
    config = validate_settings(DEFAULTS if settings is None else settings)
    ai = process_ai(filtered, config, model_call=model_call)
    processed = ai["text"]

    # Post-AI rules always execute, including when the AI is disabled, skips
    # translation or fails. Only content, NEVER the sender, passes here.
    post_plain = process_text(processed, rules=post, source=source, pronunciations={})
    plan = process_text(processed, rules=post, source=source,
                        pronunciations=pronunciations)

    mode = config["display_mode"] if config["enabled"] else "processed"
    # Never let the alternative original-display mode bypass a suppression
    # policy installed for the post-AI speech/subtitle plan.
    suppressed = any(r.mode in {"skip", "silence"} and r.applies_to(source) for r in post)
    display = plan["display_text"]
    if mode in {"original", "both"} and not suppressed:
        original_safe = pre_plan["display_text"]
        if mode == "original":
            display = original_safe
        elif original_safe != display:
            display = original_safe + "\n" + display
        if display != plan["display_text"]:
            # Display one complete alternative subtitle at the first speech
            # segment; keep existing audio/silence segments and their timing.
            first = next((seg for seg in plan["segments"] if seg["kind"] == "speech"), None)
            if first is not None:
                for seg in plan["segments"]:
                    seg["display_text"] = ""
                first["display_text"] = display
    if sender and plan["spoken_text"]:
        prefix = sender + " "
        # Sender is a separate plan segment; it has no global replacements or
        # pronunciation hints and is not translated by the AI.
        part = {"kind": "speech", "spoken_text": prefix, "display_text": prefix,
                "source_start": 0, "source_end": len(prefix), "silence_ms": 0}
        for segment in plan["segments"]:
            segment["source_start"] += len(prefix)
            segment["source_end"] += len(prefix)
        plan["segments"].insert(0, part)
        plan["spoken_text"] = prefix + plan["spoken_text"]
        display = prefix + display

    plan["display_text"] = display
    # Never expose intermediate raw inputs through public preview endpoints
    # when a later skip/silence policy might have hidden that content.
    safe_pre = None if suppressed else pre_plan["display_text"]
    safe_ai = None if suppressed else processed
    plan["processing"] = {
        "ai_status": ai["status"],
        "ai_applied": ai["applied"],
        "target_language": config["target_language"],
        "display_mode": mode,
        "original_text": safe_pre,
        "pre_ai_text": None if suppressed else filtered,
        "ai_result_text": safe_ai,
        "post_ai_text": post_plain["spoken_text"],
        "sender_prefix_text": sender,
        "display_limited_by_filter": suppressed and mode != "processed",
        **({"warning": ai["warning"]} if "warning" in ai else {}),
    }
    return plan
