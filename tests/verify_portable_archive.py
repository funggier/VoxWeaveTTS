"""V4-only Portable ZIP gate: inspect, extract and synthesize Thai speech.

This verifier runs only for a locally built v4 ZIP. It never downloads models
or assumes any v3 package/runtime. No fixed service ports are opened.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION=os.getenv("VOXWEAVE_PORTABLE_VERSION","0.12.0-dev0")
ZIP=ROOT/"dist"/f"VoxWeaveTTS-v{VERSION}-portable.zip"
if not ZIP.is_file():
    raise SystemExit("Expected v4-only release candidate ZIP not found: "+str(ZIP))
with ZIP.open("rb") as file:
    digest=hashlib.file_digest(file,"sha256").hexdigest()
print("V4_ZIP_SHA256",digest,flush=True)
with zipfile.ZipFile(ZIP) as archive:
    bad=archive.testzip()
    if bad is not None:
        raise AssertionError("CRC validation failed: "+bad)
    names=archive.namelist()
    items=set(names)
    required={
        "VoxWeaveTTS/VoxWeaveTTS.exe",
        "VoxWeaveTTS/runtime/python/python.exe",
        "VoxWeaveTTS/runtime/tools/uv.exe",
        "VoxWeaveTTS/src/voxweavetts/universal_model_v4.py",
        "VoxWeaveTTS/src/voxweavetts/package_install_v4.py",
        "VoxWeaveTTS/models/universal/v4/tts/makham-paradee/1.0.0/manifest.json",
        "VoxWeaveTTS/models/recovery-packages/VoxWeaveTTS-MakHam-v4.vwmodel",
        "VoxWeaveTTS/examples/v4-model-plugin/plugin/worker.py",
        "VoxWeaveTTS/THIRD_PARTY_NOTICES.txt",
    }
    if not required <= items:
        raise AssertionError("v4 ZIP missing required files: "+repr(sorted(required-items)))
    if any(".." in Path(x).parts or not x.startswith("VoxWeaveTTS/")
           for x in names):
        raise AssertionError("unsafe release ZIP member")
    if any(("/models/universal/v3/" in x
            or x.endswith(("/portable_runtime_v3.py",
                           "/package_install_v3.py",
                           "/universal_model_packages.py",
                           "/engine_worker_legacy.py"))
            for x in names)):
        raise AssertionError("v3 source or model accidentally shipped")
    if any(x.startswith("VoxWeaveTTS/examples/") and not x.endswith("/")
           and not x.startswith(("VoxWeaveTTS/examples/v4-",
                                 "VoxWeaveTTS/examples/README_TH.md"))
           for x in names):
        raise AssertionError("non-v4 example in Portable")
    for prefix in ("VoxWeaveTTS/cache/", "VoxWeaveTTS/logs/",
                   "VoxWeaveTTS/data/settings/","VoxWeaveTTS/output/"):
        if any(n.startswith(prefix) and not n.endswith("/") for n in names):
            raise AssertionError("private user data in ZIP: "+prefix)
    print("V4_ZIP_CONTENTS_PASS",len(names),flush=True)

    with tempfile.TemporaryDirectory(dir=ZIP.parent,prefix="v4-extract-smoke-") as tmp:
        archive.extractall(tmp)
        stage=Path(tmp)/"VoxWeaveTTS"
        python=stage/"runtime/python/python.exe"
        env=os.environ.copy()
        env.update({
            "PYTHONPATH":str(stage/"src"),
            "PYTHONNOUSERSITE":"1",
            "PYTHONDONTWRITEBYTECODE":"1",
            "HF_HOME":str(stage/"cache/huggingface"),
            "TORCH_HOME":str(stage/"cache/torch"),
            "XDG_CACHE_HOME":str(stage/"cache"),
            "TEMP":str(stage/"cache/temp"),"TMP":str(stage/"cache/temp"),
        })
        (stage/"cache/temp").mkdir(parents=True,exist_ok=True)
        result=subprocess.run([
            str(python),"-X","utf8",
            str(ROOT/"scripts/verify_v4_portable_stage.py"),
            "--stage",str(stage),
        ],cwd=stage,env=env,text=True,capture_output=True,
           encoding="utf-8",errors="replace",timeout=90)
        print(result.stdout,flush=True)
        if result.returncode!=0:
            raise AssertionError(result.stderr[-1500:])
print("V4_PORTABLE_ARCHIVE_VERIFIED",flush=True)
