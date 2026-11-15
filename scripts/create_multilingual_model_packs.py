"""Create reproducible data-only Chinese and 31-language .vwmodel add-ons.

Requires upstream archives safely extracted under cache/downloads/expanded/.
No model is downloaded or embedded in the application source. Distribution
must retain MIT and OpenRAIL-M notices and respect model-specific restrictions.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from voxweavetts.model_packages import make_package, FORMAT, FORMAT_VERSION
from voxweavetts.sherpa_voice_engine import SUPER_FILES, SUPER_VOICES, MELO_FILES

OUT = ROOT / "dist" / "ModelPackages"
BASE = ROOT / "cache" / "downloads" / "expanded"


def digest(path: Path) -> dict:
    with path.open("rb") as file:
        checksum = hashlib.file_digest(file, "sha256").hexdigest()
    return {"path": path.as_posix(), "size": path.stat().st_size, "sha256": checksum}


def files_for(base: Path, names: list[str]) -> list[dict]:
    files = []
    for name in names:
        source = base / name
        with source.open("rb") as file:
            sha = hashlib.file_digest(file, "sha256").hexdigest()
        files.append({"path": name, "size": source.stat().st_size, "sha256": sha})
    return files


def build_supertonic() -> Path:
    stage = BASE / "sherpa-onnx-supertonic-3-tts-int8-2026-05-11"
    legal = stage / "legal"
    if not (legal / "license.txt").is_file():
        raise FileNotFoundError("Download official OpenRAIL-M license into " + str(legal / "license.txt"))
    shutil.copyfile(stage / "LICENSE", legal / "conversion-license.txt")
    (legal / "attribution.md").write_text(
        "Supertonic 3 model: Copyright (c) 2026 Supertone Inc.\\n"
        "Model license: BigScience OpenRAIL-M, including use restrictions.\\n"
        "https://huggingface.co/Supertone/supertonic-3\\n"
        "ONNX INT8 conversion and sherpa-onnx runtime: k2-fsa/sherpa-onnx, Apache-2.0.\\n"
        "https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models\\n"
        "Voice/data rights are not independently audited. Do not mark as commercial-cleared.\\n",
        encoding="utf-8",
    )
    names = list(SUPER_FILES) + [
        "legal/license.txt", "legal/conversion-license.txt", "legal/attribution.md"
    ]
    manifest = {
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "package_id": "supertonic3-multilingual-int8", "version": "1.0.0",
        "title": "Supertonic 3 INT8 — 31 languages (including Korean)",
        "engine_adapter": "sherpa-supertonic-v1", "language": "multi",
        "sample_rate": 44_100,
        "voices": [{"id": v, "label": label, "asset": "voice.bin"}
                   for v, label in SUPER_VOICES],
        "files": files_for(stage, names),
        "license": {
            "spdx": "OpenRAIL-M",
            "url": "https://huggingface.co/Supertone/supertonic-3/blob/main/LICENSE",
            "attribution": "Copyright 2026 Supertone Inc. OpenRAIL-M model license with use-based restrictions; upstream k2-fsa ONNX conversion and separate notices enclosed.",
            "review_status": "review_required",
        },
        "source": {
            "url": "https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models",
            "revision": "sherpa-onnx-supertonic-3-tts-int8-2026-05-11",
        },
        "dependencies": ["sherpa-onnx==2.0.1"],
    }
    target = OUT / "VoxWeaveTTS-Supertonic3-31Languages-INT8-v1.0.0.vwmodel"
    return make_package(stage, manifest, target)


def build_chinese() -> Path:
    stage = BASE / "vits-melo-tts-zh_en"
    legal = stage / "legal"
    legal.mkdir(exist_ok=True)
    shutil.copyfile(stage / "LICENSE", legal / "license.txt")
    (legal / "attribution.md").write_text(
        "MeloTTS Chinese model by MyShell.ai, under MIT (license enclosed).\\n"
        "Upstream: https://huggingface.co/myshell-ai/MeloTTS-Chinese\\n"
        "Converted to ONNX for sherpa-onnx by k2-fsa; source https://github.com/k2-fsa/sherpa-onnx.\\n"
        "Model-card license alone does not certify all training/voice rights.\\n",
        encoding="utf-8",
    )
    names = list(MELO_FILES) + ["legal/license.txt", "legal/attribution.md"]
    manifest = {
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "package_id": "melo-chinese-onnx", "version": "1.0.0",
        "title": "MeloTTS Chinese / English ONNX — Mandarin voice",
        "engine_adapter": "sherpa-melo-zh-v1", "language": "zh",
        "sample_rate": 44_100,
        "voices": [{"id": "zh_melo", "label": "Mandarin (Melo)", "asset": "model.onnx"}],
        "files": files_for(stage, names),
        "license": {
            "spdx": "MIT",
            "url": "https://huggingface.co/myshell-ai/MeloTTS-Chinese",
            "attribution": "MyShell.ai MeloTTS Chinese (MIT model card), converted by k2-fsa/sherpa-onnx. Source license and attribution enclosed; training-rights review pending.",
            "review_status": "review_required",
        },
        "source": {
            "url": "https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models",
            "revision": "vits-melo-tts-zh_en (converted from MyShell.ai MeloTTS Chinese)",
        },
        "dependencies": ["sherpa-onnx==2.0.1"],
    }
    target = OUT / "VoxWeaveTTS-MeloTTS-Chinese-ONNX-v1.0.0.vwmodel"
    return make_package(stage, manifest, target)


if __name__ == "__main__":
    for archive in (build_supertonic(), build_chinese()):
        with archive.open("rb") as file:
            sha = hashlib.file_digest(file, "sha256").hexdigest()
        print("MODEL_PACKAGE", archive, archive.stat().st_size, sha, flush=True)
