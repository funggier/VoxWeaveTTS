"""Hardware QA: prove same Thai text+seed yields byte-identical WAV output.

Run: set PYTHONPATH=src && .venv\Scripts\python.exe scripts\test_seed_reproducibility.py
Samples in output/seed-tests/ are private QA artifacts, NOT runtime clip sources.
"""
from __future__ import annotations

import hashlib
import json
import sys
import wave
from io import BytesIO
from pathlib import Path

from voxweavetts.processing import process_text
from voxweavetts.speech import render_wav

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "seed-tests"
OUTPUT.mkdir(parents=True, exist_ok=True)

text = "ฮ่า ฮ่า ฮ่า"
plan = process_text(text)
checksums = {}
result = []
for seed in (100, 101, 100, 100):
    wav_bytes, meta = render_wav(plan, seed=seed, speed=1.0)
    sha = hashlib.sha256(wav_bytes).hexdigest()
    with wave.open(BytesIO(wav_bytes), "rb") as reader:
        assert reader.getframerate() == 24000
        assert reader.getnchannels() == 1
        assert reader.getnframes() > 0
    result.append({"seed": seed, "sha256": sha, "duration_ms": meta["duration_ms"]})
    if seed == 100:
        if 100 in checksums:
            assert checksums[100] == sha, "Nondeterministic audio for fixed seed"
        else:
            checksums[100] = sha
    destination = OUTPUT / f"tha-ha-seed-{seed}.wav"
    if not destination.exists():
        destination.write_bytes(wav_bytes)

print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
print("FIXED_SEED_REPRODUCIBLE", flush=True)
