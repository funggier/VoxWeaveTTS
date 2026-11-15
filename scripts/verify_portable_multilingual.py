"""Test two optional CPU model add-ons with the embedded portable Python.

Does not alter user-installed voices or settings. Run with:
  cd dist/VoxWeaveTTS
  runtime/python/python.exe -c "import runpy,sys;sys.path.insert(0,'src');runpy.run_path('../../scripts/verify_portable_multilingual.py',run_name='__main__')"
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
if Path(sys.executable).resolve() != (STAGE / "runtime" / "python" / "python.exe").resolve():
    raise SystemExit("run with packaged Python runtime")
if Path.cwd().resolve() != STAGE.resolve():
    raise SystemExit("run from the Portable stage directory")
from voxweavetts import speech
from voxweavetts.model_packages import install_model_package, installed_packages, engine_id_for
from voxweavetts.processing import process_text
from voxweavetts.ai_pipeline import process_pipeline
from voxweavetts.ai_processing import DEFAULTS

NAMES = (
    ("VoxWeaveTTS-MeloTTS-Chinese-ONNX-v1.0.0.vwmodel",
     "zh_melo", "你好，欢迎来到我们的直播间。", 44100),
    ("VoxWeaveTTS-Supertonic3-31Languages-INT8-v1.0.0.vwmodel",
     "ko_s0", "안녕하세요. 오늘 날씨가 좋아요.", 44100),
)
with tempfile.TemporaryDirectory(prefix="verify-multilingual-", dir=STAGE / "cache" / "temp") as temp:
    packages = Path(temp) / "models"
    manifests = []
    for filename, _, _, _ in NAMES:
        manifests.append(install_model_package(ROOT / "dist" / "ModelPackages" / filename,
                                               base=packages))
    with patch.object(speech, "installed_packages",
                      lambda: installed_packages(base=packages)):
        speech.refresh_engine_registry()
        try:
            for manifest, (_, voice, sample, rate) in zip(manifests, NAMES):
                engine_id = engine_id_for(manifest)
                info = speech.get_engine_info(engine_id)
                assert info.runtime_ready and info.assets_ready, engine_id
                assert voice in info.voice_ids, voice
                wav, details = speech.render_wav(process_text(sample),
                                                  engine_id=engine_id,
                                                  voice_id=voice, speed=1)
                with wave.open(io.BytesIO(wav), "rb") as audio:
                    assert audio.getnchannels() == 1
                    assert audio.getframerate() == rate
                    assert audio.getnframes() > 5000
                    print("PORTABLE_MULTILINGUAL_WAV_PASS", voice,
                          audio.getnframes(), details["duration_ms"], flush=True)
                if voice == "zh_melo":
                    # Regression: AI translation keeps the digits, while the
                    # configured legacy post-AI rule says 555 -> Thai laugh.
                    # TTS must use a Chinese laughter token after translation.
                    source = "ชายหนุ่มกลายเป็นอมตะ และพูดคำต้องห้าม ก่อนหัวเราะ 555"
                    chinese = "年轻人获得了永生，说出了禁忌之词，然后笑了 555"
                    plan = process_pipeline(
                        source,
                        rules=[{"match":"555", "match_mode":"five_run", "mode":"replace",
                                "spoken":"ฮ่า ฮ่า ฮ่า"}],
                        settings={**DEFAULTS, "enabled": True, "engine": "ollama",
                                  "operation": "translate", "target_language": "zh",
                                  "translation_mode": "whole_message"},
                        model_call=lambda *_: chinese,
                    )
                    assert "哈哈哈" in plan["spoken_text"]
                    assert "ฮ่า" not in plan["spoken_text"]
                    wav, _ = speech.render_wav(
                        plan, engine_id=engine_id, voice_id=voice, speed=1.0, seed=100)
                    with wave.open(io.BytesIO(wav), "rb") as audio:
                        assert audio.getframerate() == rate and audio.getnframes() > 5000
                        print("PORTABLE_CHINESE_LAUGH_555_PASS", audio.getnframes(), flush=True)
        finally:
            speech.refresh_engine_registry()
print("PORTABLE_MULTILINGUAL_MODELS_TEMP_CLEANED", flush=True)
