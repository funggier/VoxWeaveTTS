"""End-to-end optional model pack verification with the *published v0.4.2* runtime.

Run from project root (Windows) using the extracted Portable staging runtime:
    $env:PYTHONPATH = "$PWD\dist\VoxWeaveTTS\src"
    & .\dist\VoxWeaveTTS\runtime\python\python.exe -X utf8 scripts\verify_portable_model_packages.py

Temporarily extracts packages under the Portable staging cache and cleans them
up. Does not modify actual user model directories or stable GitHub Release.
"""
from __future__ import annotations

import io
import sys
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/"dist"/"VoxWeaveTTS"
if not (STAGE/"runtime"/"python"/"python.exe").is_file():
    raise SystemExit("Missing portable runtime staging directory")
if (Path(sys.executable).resolve() !=
        (STAGE/"runtime"/"python"/"python.exe").resolve()):
    raise SystemExit("Use only the embedded portable runtime to run this verification")

from voxweavetts import speech  # noqa: E402
from voxweavetts.model_packages import (  # noqa: E402
    install_model_package,installed_packages,engine_id_for,
)
from voxweavetts.processing import process_text  # noqa: E402

temp_root=STAGE/"cache"/"temp"
temp_root.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix="model-pack-compat-",dir=temp_root) as temp:
    base=Path(temp)/"packages"
    archives=[
        ROOT/"dist"/"ModelPackages"/"VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel",
        ROOT/"dist"/"ModelPackages"/"VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel",
    ]
    manifests=[install_model_package(archive,base=base) for archive in archives]
    with patch.object(speech,"installed_packages",
                      lambda:installed_packages(base=base)):
        speech.refresh_engine_registry()
        try:
            for manifest in manifests:
                engine_id=engine_id_for(manifest)
                info=speech.get_engine_info(engine_id)
                if not info.assets_ready or not info.runtime_ready:
                    raise RuntimeError("portable runtime cannot load " + engine_id)
                wav,metadata=speech.render_wav(
                    process_text("สวัสดีครับ ทดสอบเสียงภาษาไทย"),
                    engine_id=engine_id,voice_id=info.voice_id,
                    speed=1.0,seed=100,
                )
                with wave.open(io.BytesIO(wav),"rb") as stream:
                    assert stream.getnframes()>1000
                    assert stream.getframerate()==info.sample_rate
                    print("PORTABLE_MODEL_WAV_OK",engine_id,
                          info.voice_id,stream.getnframes(),
                          stream.getframerate(),flush=True)
        finally:
            speech.refresh_engine_registry()
print("PORTABLE_OPTIONAL_MODEL_PACKS_COMPATIBLE_AND_TEMP_CLEANED",flush=True)
