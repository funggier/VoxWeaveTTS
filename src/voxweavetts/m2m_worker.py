"""Trusted offline M2M100 translation worker (UTF-8 JSON over private stdio).

This module does not execute package code, shell commands, prompts or tools.
Only installed, schema-checked safetensors model IDs are allowed.
"""
from __future__ import annotations

import json
import sys
from .m2m_runtime import PROTOCOL, MAX_LINE, MAX_TEXT


def process(message: object) -> dict:
    if not isinstance(message, dict) or set(message) != {
        "version", "request_id", "method", "text", "model",
        "source_language", "target_language",
    }:
        raise ValueError("invalid M2M100 IPC message")
    if (message["version"] != PROTOCOL or message["method"] != "translate"
        or type(message["request_id"]) is not int
        or not 0 < message["request_id"] <= 2**31
        or not isinstance(message["text"], str)
        or not 0 < len(message["text"].strip()) <= MAX_TEXT
        or "\0" in message["text"]):
        raise ValueError("invalid M2M100 IPC metadata")
    model = message["model"]
    if not isinstance(model, str) or len(model) > 100:
        raise ValueError("invalid M2M100 model ID")
    from .ai_processing import LANGUAGES
    source = message["source_language"]
    target = message["target_language"]
    if (source not in LANGUAGES or source in ("auto", "unspecified")
            or target not in LANGUAGES or target in ("auto", "unspecified")):
        raise ValueError("unsupported M2M100 source or target language")
    from .ai_engine_registry import M2M100Adapter
    output = M2M100Adapter().process(message["text"], {
        "operation": "translate", "model": model,
        "source_language": source, "target_language": target,
    }, [], inline_worker=True)
    return {"version": PROTOCOL, "request_id": message["request_id"],
            "ok": True, "text": output}


def main() -> None:
    # Binary buffered reading allows a strict physical byte bound.
    while True:
        line = sys.stdin.buffer.readline(MAX_LINE + 1)
        if not line:
            break
        if len(line) > MAX_LINE or not line.endswith(b"\n"):
            break
        request_id = None
        try:
            request = json.loads(line.decode("utf-8"))
            if isinstance(request, dict) and type(request.get("request_id")) is int:
                request_id = request["request_id"]
            reply = process(request)
        except (OSError, ValueError, RuntimeError, ImportError, KeyError,
                TypeError, MemoryError) as exc:
            # Return only allowlisted, non-sensitive error codes. Never echo
            # chat text, model paths, exception stack traces or credentials.
            memory_error = (isinstance(exc, MemoryError)
                            or isinstance(exc, OSError) and (
                                getattr(exc, "winerror", None) == 1455
                                or "1455" in str(exc)
                                or "paging file is too small" in str(exc).lower()))
            reply = {"version": PROTOCOL, "request_id": request_id,
                     "ok": False, "error": ("resource_exhausted"
                                           if memory_error else "inference_failed")}
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
