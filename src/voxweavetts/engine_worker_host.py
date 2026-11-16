"""Trusted child entry point for the versioned local TTS worker gateway.

Only this process imports model-specific ML dependencies. Stdout is reserved
strictly for machine-readable protocol replies. Untrusted chat is input data.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import redirect_stdout
import json
import math
import sys
from typing import Any

from .engine_provider_catalog import provider_for_backend
from .engine_worker_gateway import MAX_PCM_BYTES, PROTOCOL_VERSION, WORKERS


class WorkerInputError(ValueError):
    pass


def _validate_request(request: Any) -> tuple[int, str, str, float, int, str | None]:
    required = {"version", "request_id", "method", "text", "voice_id", "speed", "seed"}
    if (not isinstance(request, dict) or not required <= set(request)
        or set(request) - required not in (set(), {"engine_id"})):
        raise WorkerInputError("invalid schema")
    if request["version"] != PROTOCOL_VERSION or request["method"] != "synthesize":
        raise WorkerInputError("unsupported protocol")
    identity = request["request_id"]
    if type(identity) is not int or identity < 1:
        raise WorkerInputError("invalid request ID")
    txt, voice, speed, seed = (
        request["text"], request["voice_id"], request["speed"], request["seed"]
    )
    if not isinstance(txt, str) or not 0 < len(txt) <= 5000 or not txt.strip():
        raise WorkerInputError("invalid text")
    if not isinstance(voice, str) or not 0 < len(voice) <= 80:
        raise WorkerInputError("invalid voice")
    if type(speed) not in (int, float) or not math.isfinite(speed) or not 0.1 <= speed <= 5:
        raise WorkerInputError("invalid speed")
    if type(seed) is not int or not 0 <= seed <= 2_147_483_647:
        raise WorkerInputError("invalid seed")
    engine_id = request.get("engine_id")
    if engine_id is not None and (not isinstance(engine_id, str)
                                  or not 0 < len(engine_id) <= 96):
        raise WorkerInputError("invalid engine_id")
    return identity, txt, voice, float(speed), seed, engine_id


def _create_backend(name: str):
    # Explicit trust boundary: never import modules named by a model manifest
    # or by input received from stdin.
    profile = provider_for_backend(name)
    if profile is None:
        raise WorkerInputError("backend is not registered")
    if profile.driver == "wayu":
        from .engine_worker_wayu import WayuBackend
        return WayuBackend()
    if profile.driver == "legacy":
        from .engine_worker_legacy import LegacyBackend
        return LegacyBackend(profile)
    raise WorkerInputError("untrusted provider driver")


def serve(backend: str, *, reader: Any = None, writer: Any = None) -> None:
    if backend not in WORKERS:
        raise WorkerInputError("unknown backend")
    reader = sys.stdin if reader is None else reader
    writer = sys.stdout if writer is None else writer
    with redirect_stdout(sys.stderr):
        engine = _create_backend(backend)
    for line in reader:
        request_id: int | None = None
        try:
            if len(line) > 20_000:
                raise WorkerInputError("input too large")
            message = json.loads(line)
            if isinstance(message, dict) and type(message.get("request_id")) is int:
                request_id = message["request_id"]
            request_id, text, voice, speed, seed, engine_id = _validate_request(message)
            with redirect_stdout(sys.stderr):
                if engine_id is None:
                    pcm = engine.synthesize(text, voice_id=voice, speed=speed, seed=seed)
                else:
                    pcm = engine.synthesize(text, voice_id=voice, speed=speed,
                                            seed=seed, engine_id=engine_id)
            if not isinstance(pcm, bytes) or not pcm or len(pcm) > MAX_PCM_BYTES or len(pcm) % 2:
                raise WorkerInputError("invalid model output")
            response = {
                "version": PROTOCOL_VERSION,
                "request_id": request_id,
                "ok": True,
                "sample_rate": engine.sample_rate,
                "pcm16_b64": base64.b64encode(pcm).decode("ascii"),
            }
        except Exception as exc:
            # Never return exception details or the sensitive input text.
            print("TTS worker error:", type(exc).__name__, file=sys.stderr)
            response = {
                "version": PROTOCOL_VERSION,
                "request_id": request_id,
                "ok": False,
                "error": "synthesis_failure",
            }
        writer.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n")
        writer.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=tuple(WORKERS), required=True)
    args = parser.parse_args()
    serve(args.backend)


if __name__ == "__main__":
    main()
