"""Portable release smoke: run with bundled Python, cwd=extracted package root."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen

root = Path.cwd()
assert (root / "VoxWeaveTTS.exe").is_file()
assert Path(sys.executable).resolve().is_relative_to(root), sys.executable
assert (root / "runtime" / "python" / "LICENSE.txt").exists()
assert (root / "THIRD_PARTY_NOTICES.txt").exists()
assert not list((root / "models" / "fastthaig2p").glob("*.onnx"))
assert not (root / "data" / "settings" / "global-voice.json").exists()
assert not (root / "voices").joinpath("recording.wav").exists()

from voxweavetts.speech import list_engine_info, render_wav
from voxweavetts.processing import process_text

engines = {e.id: e for e in list_engine_info()}
for info in engines.values():
    print("PORTABLE_ENGINE", info.id, info.assets_ready, info.runtime_ready)
assert engines["makham-paradee-cpu"].assets_ready
assert engines["makham-paradee-cpu"].runtime_ready
assert not engines["fastthaig2p-cpu"].assets_ready

wav, details = render_wav(
    process_text("\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35\u0e04\u0e48\u0e30 \u0e17\u0e14\u0e2a\u0e2d\u0e1a\u0e40\u0e2a\u0e35\u0e22\u0e07"),
    engine_id="makham-paradee-cpu", voice_id="paradee_thai",
)
assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
assert len(wav) > 10000, len(wav)
assert details["duration_ms"] > 100
print("PORTABLE_THAI_WAV_PASS",len(wav),details["duration_ms"])
