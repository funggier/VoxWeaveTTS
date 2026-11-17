"""Reference TTS Worker Protocol v1 SDK for reviewed external providers.

This module is deliberately standard-library-only and does not load models.
A third-party provider supplies its own synthesize callback and runs in a
separate approved worker environment; never auto-import it from .vwmodel.
Stdout is reserved for bounded JSON Lines responses; diagnostics go to stderr.
"""
from __future__ import annotations

import base64
import json
import math
import re
import sys
from dataclasses import dataclass
from typing import BinaryIO, Callable, Iterable

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 64 * 1024
MAX_TEXT_CHARS = 5000
MAX_PCM_BYTES = 32_000_000
_VOICE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
_ENGINE_ID = re.compile(r"[a-z][a-z0-9_-]{2,95}\Z")


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class SynthesisRequest:
    text: str
    voice_id: str
    speed: float
    seed: int
    engine_id: str | None = None


def parse_request(raw: object, *, voices: frozenset[str],
                  engines: frozenset[str]) -> tuple[int, SynthesisRequest]:
    if (not isinstance(raw, dict)
        or set(raw) - {"version", "request_id", "method", "text", "voice_id",
                       "speed", "seed", "engine_id"}
        or raw.get("version") != PROTOCOL_VERSION
        or raw.get("method") != "synthesize"
        or type(raw.get("request_id")) is not int
        or raw["request_id"] < 1 or raw["request_id"] > 2**53 - 1
        or not isinstance(raw.get("text"), str)
        or not 0 < len(raw["text"]) <= MAX_TEXT_CHARS
        or not isinstance(raw.get("voice_id"), str)
        or raw["voice_id"] not in voices
        or type(raw.get("speed")) not in (int, float)
        or not math.isfinite(raw["speed"])
        or not 0.6 <= raw["speed"] <= 5.0
        or type(raw.get("seed")) is not int
        or not 0 <= raw["seed"] < 2**31):
        raise ProtocolError("malformed or out-of-bounds TTS request")
    engine = raw.get("engine_id")
    if (engine is not None and
        (not isinstance(engine, str) or engine not in engines)):
        raise ProtocolError("unregistered engine identifier")
    return (raw["request_id"], SynthesisRequest(
        raw["text"], raw["voice_id"], float(raw["speed"]), raw["seed"], engine))


def serve(synthesize: Callable[[SynthesisRequest], bytes], *,
          sample_rate: int, voice_ids: Iterable[str],
          engine_ids: Iterable[str] = (),
          input_stream: BinaryIO | None = None,
          output_stream: BinaryIO | None = None) -> None:
    """Handle sequential local IPC without running untrusted text as commands."""
    if not callable(synthesize):
        raise ValueError("synthesize must be a callable")
    if type(sample_rate) is not int or not 8000 <= sample_rate <= 96000:
        raise ValueError("sample rate outside worker protocol limits")
    voices = frozenset(voice_ids)
    engines = frozenset(engine_ids)
    if (not voices or len(voices) > 64 or
        any(not isinstance(x, str) or not _VOICE_ID.fullmatch(x) for x in voices)
        or any(not isinstance(x, str) or not _ENGINE_ID.fullmatch(x) for x in engines)):
        raise ValueError("invalid trusted worker voice/engine definitions")
    reader = input_stream if input_stream is not None else sys.stdin.buffer
    writer = output_stream if output_stream is not None else sys.stdout.buffer
    while True:
        line = reader.readline(MAX_REQUEST_BYTES + 1)
        if not line:
            break
        # Consume a newline-free oversized request in bounded chunks. Never
        # reinterpret its remaining bytes as an independent request.
        oversized = len(line) > MAX_REQUEST_BYTES or not line.endswith(b"\n")
        if oversized:
            while line and not line.endswith(b"\n"):
                line = reader.readline(MAX_REQUEST_BYTES + 1)
        request_id = None
        try:
            if oversized:
                raise ProtocolError("request line is too long")
            raw = json.loads(line.decode("utf-8"))
            if isinstance(raw, dict) and type(raw.get("request_id")) is int:
                request_id = raw["request_id"]
            request_id, request = parse_request(raw, voices=voices, engines=engines)
            result = synthesize(request)
            if (not isinstance(result, bytes) or not result
                or len(result) > MAX_PCM_BYTES or len(result) % 2):
                raise ProtocolError("callback returned invalid PCM16 data")
            response = {"version": PROTOCOL_VERSION,
                        "request_id": request_id, "ok": True,
                        "sample_rate": sample_rate,
                        "pcm16_b64": base64.b64encode(result).decode("ascii")}
        except MemoryError:
            response = {"version": PROTOCOL_VERSION,
                        "request_id": request_id, "ok": False,
                        "error": "resource_exhausted"}
        except Exception:
            # Never expose provider exceptions, incoming text, paths or traces.
            response = {"version": PROTOCOL_VERSION,
                        "request_id": request_id, "ok": False,
                        "error": "synthesis_failure"}
        writer.write(json.dumps(response, ensure_ascii=False,
                                separators=(",", ":")).encode("utf-8") + b"\n")
        writer.flush()
