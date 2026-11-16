"""Verify opt-in mixed-language WAV using ONLY the packaged Windows Python.

Run from dist/VoxWeaveTTS (without changing user settings/models):
  runtime/python/python.exe -c "import sys,runpy;sys.path.insert(0,'src');runpy.run_path('../../scripts/verify_portable_mixed_language.py',run_name='__main__')"
"""
from __future__ import annotations

import io
import sys
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "dist" / "VoxWeaveTTS"
if (Path(sys.executable).resolve()
        != (STAGE / "runtime" / "python" / "python.exe").resolve()):
    raise SystemExit("use the embedded Portable Python")
if Path.cwd().resolve() != STAGE.resolve():
    raise SystemExit("run from the staged Portable directory")

from voxweavetts import speech
from voxweavetts.model_packages import (
    install_model_package, installed_packages, engine_id_for,
)
from voxweavetts.processing import process_text

archives = {
    "en": ("VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel", "bf_emma"),
    "zh": ("VoxWeaveTTS-MeloTTS-Chinese-ONNX-v1.0.0.vwmodel", "zh_melo"),
    "ko": ("VoxWeaveTTS-Supertonic3-31Languages-INT8-v1.0.0.vwmodel", "ko_s0"),
}
temp = STAGE / "cache" / "temp"
temp.mkdir(exist_ok=True, parents=True)
with tempfile.TemporaryDirectory(prefix="verify-mixed-voice-", dir=temp) as folder:
    base = Path(folder) / "packages"
    routes = {"th": {"engine_id": "makham-paradee-cpu", "voice_id": "paradee_thai"}}
    for lang, (filename, voice_id) in archives.items():
        manifest = install_model_package(ROOT / "dist" / "ModelPackages" / filename,
                                         base=base)
        routes[lang] = {"engine_id": engine_id_for(manifest), "voice_id": voice_id}

    with patch.object(speech, "installed_packages",
                      lambda: installed_packages(base=base)):
        speech.refresh_engine_registry()
        try:
            for sample, expected, rate in (
                ("ผมอยากทำComputer ผม ให้มันลื่นกว่านี้ lol",
                 ("th", "en"), 24000),
                ("สวัสดี 你好 안녕하세요 Hello",
                 ("th", "zh", "ko", "en"), 44100),
            ):
                plan = process_text(sample)
                wav, metadata = speech.render_wav(
                    plan, engine_id="makham-paradee-cpu",
                    voice_id="paradee_thai", seed=100,
                    language_voice_routes=routes,
                )
                with wave.open(io.BytesIO(wav), "rb") as f:
                    assert f.getnchannels() == 1 and f.getsampwidth() == 2
                    assert f.getframerate() == rate and f.getnframes() > 2000
                    print("PORTABLE_MIXED_WAV_PASS", expected,
                          "rate", rate, "frames", f.getnframes(), flush=True)
                languages = tuple(item["language"]
                                  for item in metadata["voices_used"])
                assert languages == expected, (languages, expected)
                assert metadata["segments"][0]["display_text"] == sample
                assert metadata["mixed_language"]
        finally:
            speech.refresh_engine_registry()
print("PORTABLE_MIXED_MODEL_PACKAGES_TEMP_CLEANED", flush=True)
