"""Integration QA: real v4 model archive install → inference → uninstall.

This executable test works only against an explicitly designated *disposable*
Portable QA directory. It never touches the user's running local server. The
model archives are private/UNRELEASED until redistribution rights are cleared.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import wave
from pathlib import Path

DEFAULT_PACKAGES = Path(__file__).resolve().parents[1] / "dist" / "ModelPackagesV4-QA"
VOICES = {
    "makham-paradee": ("paradee_thai", "สวัสดีครับ"),
    "fastthaig2p-thai-som": ("thai_som", "สวัสดีครับ"),
    "melo-chinese-onnx": ("zh_melo", "你好朋友"),
    "supertonic3-multilingual-int8": ("en_s0", "Hello, welcome."),
    "kokoro-multilingual-int8": ("af_heart", "Hello, welcome."),
    "vachana-thai-four-voices": ("th_f_1", "สวัสดีครับ"),
    "wayu-paxa-edge-nc": ("f_young_warm", "สวัสดีครับ"),
}


def test_one(root: Path, path: Path) -> dict:
    from voxweavetts.universal_model_v4 import (
        install, remove, for_engine, inspect_archive, engine_id, backend_id
    )
    from voxweavetts.speech import refresh_engine_registry, get_engine_info, render_wav
    from voxweavetts.processing import process_text
    from voxweavetts.engine_worker_gateway import gateway

    m = inspect_archive(path)
    model_id = m["package"]["id"]
    version = m["package"]["version"]
    eid = engine_id(m)
    assert for_engine(eid, root) is None, "QA package already installed; use clean stage"
    result = {}
    try:
        print("V4_QA_INSTALL_START", model_id, flush=True)
        result = install(path, root=root)
        assert result["format_version"] == 4
        print("V4_QA_INSTALL_OK", model_id, flush=True)
        if m["package"]["kind"] == "translation":
            from voxweavetts.m2m_runtime import TranslationWorkerSession
            session = TranslationWorkerSession(root=root, timeout=150)
            try:
                for src, dst, text in [
                    ("en", "th", "Good morning."),
                    ("th", "en", "ขอบคุณครับ"),
                ]:
                    output = session.translate(text, {
                        "model": model_id + "@" + version,
                        "source_language": src, "target_language": dst,
                    })
                    assert isinstance(output, str) and len(output.strip()) >= 2
                    print("V4_QA_REAL_TRANSLATION", model_id, src, dst, repr(output), flush=True)
                return {"model": model_id, "kind": "translation", "passed": True}
            finally:
                session.close()
        refresh_engine_registry()
        info = get_engine_info(eid)
        assert info.assets_ready and info.runtime_ready
        choice, text = VOICES[model_id]
        pcm_wav, _timeline = render_wav(
            process_text(text), engine_id=eid, voice_id=choice, seed=100, speed=1.0)
        with wave.open(io.BytesIO(pcm_wav)) as wave_in:
            rate, frames = wave_in.getframerate(), wave_in.getnframes()
        assert rate == m["engine"]["sample_rate"] and frames > 500
        print("V4_QA_REAL_WAV_PASS", model_id, choice, rate, frames, flush=True)
        if model_id == "kokoro-multilingual-int8":
            japanese, _ = render_wav(
                process_text("こんにちは。日本語をテストしています。"),
                engine_id=eid, voice_id="jf_nezumi", seed=100, speed=1.0)
            with wave.open(io.BytesIO(japanese)) as reader:
                ja_rate, ja_frames = reader.getframerate(), reader.getnframes()
            assert ja_rate == 24000 and ja_frames > 500
            print("V4_QA_REAL_JAPANESE_WAV_PASS", model_id, ja_rate, ja_frames, flush=True)
        return {"model": model_id, "kind": "tts", "passed": True,
                "sample_rate": rate, "frames": frames}
    finally:
        if m["package"]["kind"] == "tts":
            gateway().reset(backend_id(m))
        else:
            from voxweavetts.m2m_runtime import reset
            reset()
        if for_engine(eid, root) is not None:
            removed = remove(model_id, version, root=root)
            print("V4_QA_UNINSTALLED", model_id, removed, flush=True)
        refresh_engine_registry()
        assert for_engine(eid, root) is None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--packages", type=Path, default=DEFAULT_PACKAGES)
    parser.add_argument("--models", nargs="+", required=True)
    args = parser.parse_args()
    stage = args.stage.resolve()
    if (not (stage / "runtime/python/python.exe").is_file()
        or "validation" not in stage.name.lower()
        or not (stage / "src/voxweavetts/universal_model_v4.py").is_file()):
        raise RuntimeError("v4 QA requires an explicit isolated Portable validation stage")
    sys.path.insert(0, str(stage / "src"))
    reports = []
    for model in args.models:
        files = list(args.packages.glob("VoxWeaveTTS-" + model + "-*-UNRELEASED-QA-format-v4.vwmodel"))
        if len(files) != 1:
            raise RuntimeError("expected one exact QA archive for " + model)
        reports.append(test_one(stage, files[0]))
    print("V4_QA_MODELS_PASS", json.dumps(reports, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
