"""End-to-end Kokoro CPU add-on verification with the embedded Portable runtime.

Run only with dist/VoxWeaveTTS/runtime/python/python.exe and the stage cwd.
Temporarily installs the official optional model into a disposable directory,
registers the model and generates a WAV. Never edits user-installed models.
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
if not (STAGE / "runtime" / "python" / "python.exe").is_file():
    raise SystemExit("Missing staged Windows Portable runtime")
if Path(sys.executable).resolve() != (STAGE / "runtime" / "python" / "python.exe").resolve():
    raise SystemExit("Use staged Portable Python runtime, not local .venv")
if Path.cwd().resolve() != STAGE.resolve():
    raise SystemExit("Run from the staged portable root")
from voxweavetts import speech
from voxweavetts.model_packages import (
    install_model_package, installed_packages, engine_id_for,
)
from voxweavetts.processing import process_text

archive = ROOT / "dist" / "ModelPackages" / "VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel"
temp_parent = STAGE / "cache" / "temp"
temp_parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="verify-kokoro-cpu-", dir=temp_parent) as temporary:
    base = Path(temporary) / "packages"
    manifest = install_model_package(archive, base=base)
    identifier = engine_id_for(manifest)
    with patch.object(speech, "installed_packages",
                      lambda: installed_packages(base=base)):
        speech.refresh_engine_registry()
        try:
            info = speech.get_engine_info(identifier)
            assert info.assets_ready and info.runtime_ready and info.language == "multi"
            assert len(info.voice_ids) == 18
            # Verify both English and Japanese in the embedded runtime.
            # Japanese must use Misaki (not eSpeak letter-name fallback).
            for voice_id, sample in (
                ("af_heart", "Hello, this is a portable multilingual speech test."),
                ("jf_nezumi", "多分殻ごと食ってるもんね"),
            ):
                wav, detail = speech.render_wav(
                    process_text(sample),
                    engine_id=identifier, voice_id=voice_id,
                    speed=1.0, seed=100,
                )
                with wave.open(io.BytesIO(wav), "rb") as sound:
                    assert sound.getnframes() > 2000
                    assert sound.getframerate() == 24000
                    print("KOKORO_PORTABLE_CPU_WAV_PASS", voice_id,
                          sound.getnframes(), detail["duration_ms"], flush=True)
        finally:
            speech.refresh_engine_registry()
print("KOKORO_OPTIONAL_PACKAGE_INSTALLED_AND_TEMP_CLEANED", flush=True)
