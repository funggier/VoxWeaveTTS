"""Structured response contract for trusted user-configured custom AI processing.

Instructions are stored in application settings. Incoming external chat is
untrusted data which may be classified, translated, summarized or answered,
but never grants permission to change instructions or invoke tools.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .processing import MAX_TEXT


CUSTOM_FORMAT: dict[str, Any] = {
    "type": "object",
    "properties": {"result": {"type": "string"}},
    "required": ["result"],
    "additionalProperties": False,
}

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class CustomContractError(ValueError):
    """A model's response does not satisfy the saved custom-task contract."""


def parse_structured_custom(raw: Any) -> str:
    """Extract only the text to speak; never pass model metadata to TTS."""
    if not isinstance(raw, str) or len(raw) > MAX_TEXT + 2048:
        raise CustomContractError("invalid structured custom response")
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise CustomContractError("model returned non-JSON custom response") from exc
    if not isinstance(value, dict) or set(value) != {"result"}:
        raise CustomContractError("custom response must contain only result")
    result = value["result"]
    if not isinstance(result, str):
        raise CustomContractError("custom result must be text")
    result = result.strip()
    if not result or len(result) > MAX_TEXT or _CONTROL.search(result):
        raise CustomContractError("custom result was empty, excessive or contained controls")
    return result
