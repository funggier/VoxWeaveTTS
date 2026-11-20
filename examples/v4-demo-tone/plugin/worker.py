"""Demonstration v4 engine: generates a deterministic tone, NOT speech.

Real TTS plugins replace the generate_pcm16 implementation while retaining
the JSONL protocol. No network, dependencies or package-side installer.
"""
import argparse
import base64
import json
import math
import struct
import sys


def synthesize(request):
    if (request.get("method") != "synthesize" or request.get("version") != 1
        or request.get("voice_id") != "demo_tone"):
        raise ValueError("unsupported demo request")
    text = request.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > 5000:
        raise ValueError("invalid input")
    frequency = 330 + (sum(map(ord, text)) % 300)
    speed = max(0.6, min(float(request.get("speed", 1)), 5))
    rate = 16000
    frames = min(16000, int(8000 / speed) + len(text) * 120)
    pcm = bytearray()
    for n in range(frames):
        env = min(1.0, n / 400, (frames - n) / 400)
        sample = int(5000 * env * math.sin(2 * math.pi * frequency * n / rate))
        pcm.extend(struct.pack("<h", sample))
    return {"version": 1, "request_id": request["request_id"],
            "ok": True, "sample_rate": rate,
            "pcm16_b64": base64.b64encode(pcm).decode("ascii")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    _ = parser.parse_args()
    for line in sys.stdin:
        request_id = None
        try:
            if len(line) > 20000:
                raise ValueError("oversized request")
            request = json.loads(line)
            request_id = request.get("request_id")
            result = synthesize(request)
        except Exception:
            result = {"version": 1, "request_id": request_id,
                      "ok": False, "error": "synthesis_failure"}
        sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
