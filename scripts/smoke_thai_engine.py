"""Manual hardware smoke test: creates private sample WAV in output/."""
from __future__ import annotations

import math
import json
import sys
import wave
from array import array
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from voxweavetts.processing import process_text
from voxweavetts.speech import engine_info, render_wav

print("ENGINE", engine_info().as_dict(), flush=True)
plan = process_text(
    "สวัสดีครับ เขาเป็นอมตะ แต่คำต้องห้ามนั้นไม่อ่าน",
    rules=[{"match": "คำต้องห้าม", "mode": "silence", "silence_ms": 400, "display": "***"}],
    pronunciations={"อมตะ": "อะ มะ ตะ"},
)
audio, info = render_wav(plan, speed=1.0)
destination = root / "output" / "thai_m1_smoke.wav"
destination.parent.mkdir(exist_ok=True, parents=True)
destination.write_bytes(audio)
with wave.open(str(destination), "rb") as wav:
    nframes = wav.getnframes()
    frames = wav.readframes(nframes)
    samples = array("h")
    samples.frombytes(frames)
    rms = math.sqrt(sum(x * x for x in samples) / max(len(samples), 1))
    print(
        "WAV", str(destination),
        "RATE", wav.getframerate(),
        "FRAMES", nframes,
        "CHANNELS", wav.getnchannels(),
        "RMS", round(rms, 3),
        "BYTES", destination.stat().st_size,
        flush=True,
    )
print("TIMELINE", json.dumps(info, ensure_ascii=True), flush=True)
if rms < 20:
    raise RuntimeError("Synthesized audio is effectively silent")
if not any(s["kind"] == "silence" and s["end_ms"] - s["start_ms"] == 400
           for s in info["segments"]):
    raise RuntimeError("400ms silence was not preserved")
print("SMOKE_OK", flush=True)