"""Example external engine Worker Protocol v1, deliberately NOT a TTS model.

Replace the waveform generator with an actual model-specific inference call
inside this provider's own Python environment. Keep protocol/error framing.
"""
import base64
import json
import math
import struct
import sys

RATE = 24000
MAX_TEXT = 5000

for line in sys.stdin:
    request_id = None
    try:
        request = json.loads(line)
        if not isinstance(request, dict):
            raise ValueError("invalid request")
        request_id = request.get("request_id")
        if (request.get("version") != 1 or request.get("method") != "synthesize"
            or type(request_id) is not int or request_id < 1
            or not isinstance(request.get("text"), str)
            or not 0 < len(request["text"]) <= MAX_TEXT
            or request.get("voice_id") != "demo"):
            raise ValueError("invalid protocol")
        # Demo only: emit a short tone, not actual speech. All text is data.
        frames = min(RATE // 2, RATE // 10 + len(request["text"]) * 100)
        raw = b"".join(struct.pack("<h", round(800 * math.sin(i * math.tau * 440 / RATE)))
                       for i in range(frames))
        result = {"version": 1, "request_id": request_id, "ok": True,
                  "sample_rate": RATE,
                  "pcm16_b64": base64.b64encode(raw).decode("ascii")}
    except Exception:
        result = {"version": 1, "request_id": request_id,
                  "ok": False, "error": "synthesis_failure"}
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
    sys.stdout.flush()
