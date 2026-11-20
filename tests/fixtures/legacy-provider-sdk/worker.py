"""Example external TTS Worker Protocol v1 adapter; synthetic tone, NOT speech.

The SDK handles JSON Lines framing, strict request validation, PCM16 checks,
error sanitation and bounds. Replace synthesize() with model-specific inference.
Incoming chat/document text is data, never a Python instruction.
"""
from __future__ import annotations

import math
import struct

from voxweavetts.tts_provider_sdk import SynthesisRequest, serve

SAMPLE_RATE = 24000


def synthesize(request: SynthesisRequest) -> bytes:
    """Synthetic test tone. Real adapters should return their own PCM16 mono."""
    frames = min(SAMPLE_RATE // 2,
                 SAMPLE_RATE // 10 + len(request.text) * 100)
    return b"".join(struct.pack(
        "<h", round(800 * math.sin(i * math.tau * 440 / SAMPLE_RATE)))
        for i in range(frames))


if __name__ == "__main__":
    serve(synthesize, sample_rate=SAMPLE_RATE,
          voice_ids=("demo",), engine_ids=("minimal-demo-v1",))
