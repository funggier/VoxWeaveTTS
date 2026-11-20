"""VoxWeaveTTS v0.12.0 v4 Core-only ZIP release verification.

CRC, safe paths, zero model weights/runtimes, no private files, isolated
extraction, HTTP API, YouTube transport, and an offline separately-packaged
MIT demo Worker generating a tone (not actual TTS).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = os.getenv("VOXWEAVE_PORTABLE_VERSION", "0.12.0")
ARCHIVE = ROOT / "dist" / f"VoxWeaveTTS-v{VERSION}-portable.zip"
DEMO = ROOT / "dist" / f"VoxWeaveTTS-v{VERSION}-v4-demo-tone.vwmodel"

if not ARCHIVE.is_file() or not DEMO.is_file():
    raise SystemExit("Expected release-candidate core ZIP and demo package are missing")
with ARCHIVE.open("rb") as stream:
    digest = hashlib.file_digest(stream, "sha256").hexdigest()
print("PUBLIC_CORE_V4_ZIP_SHA256", digest, flush=True)

with zipfile.ZipFile(ARCHIVE) as zip_in:
    bad = zip_in.testzip()
    if bad:
        raise AssertionError("v4 Core ZIP failed CRC: " + bad)
    entries = zip_in.namelist()
    files = {name for name in entries if not name.endswith("/")}
    required = {
        "VoxWeaveTTS/VoxWeaveTTS.exe",
        "VoxWeaveTTS/runtime/python/python.exe",
        "VoxWeaveTTS/runtime/python/LICENSE.txt",
        "VoxWeaveTTS/runtime/tools/uv.exe",
        "VoxWeaveTTS/src/voxweavetts/universal_model_v4.py",
        "VoxWeaveTTS/src/voxweavetts/package_install_v4.py",
        "VoxWeaveTTS/examples/v4-demo-tone/plugin/worker.py",
        "VoxWeaveTTS/docs/UNIVERSAL_VWMODEL_V4_TH.md",
        "VoxWeaveTTS/THIRD_PARTY_NOTICES.txt",
        "VoxWeaveTTS/third_party_licenses/uv/LICENSE-MIT",
        "VoxWeaveTTS/third_party_licenses/uv/LICENSE-APACHE",
        "VoxWeaveTTS/third_party_licenses/uv/SOURCE.json",
        "VoxWeaveTTS/docs/RELEASE_NOTES_v0.12.0_TH.md",
    }
    if not required <= files:
        raise AssertionError("release ZIP missing Core files: "
                             + repr(sorted(required - files)))
    if any(".." in Path(name).parts or not name.startswith("VoxWeaveTTS/")
           for name in entries):
        raise AssertionError("release archive contains unsafe paths")
    if any(name.lower().endswith((".vwmodel", ".onnx", ".safetensors", ".pt",
                                  ".pth", ".npy")) for name in files):
        raise AssertionError("unapproved model, weight or QA binary in public Core")
    if any("/models/universal/v3/" in name
           or name.endswith(("/portable_runtime_v3.py", "/package_install_v3.py",
                             "/engine_worker_legacy.py")) for name in entries):
        raise AssertionError("legacy v3 components shipped")
    if any(x.startswith("VoxWeaveTTS/examples/") and not x.endswith("/")
           and not x.startswith(("VoxWeaveTTS/examples/v4-",
                                 "VoxWeaveTTS/examples/README_TH.md"))
           for x in entries):
        raise AssertionError("non-v4 example in public distribution")
    for secret_root in ("VoxWeaveTTS/cache/", "VoxWeaveTTS/logs/",
                        "VoxWeaveTTS/data/settings/", "VoxWeaveTTS/output/"):
        if any(item.startswith(secret_root) and not item.endswith("/")
               for item in entries):
            raise AssertionError("user-sensitive data leaked into ZIP: " + secret_root)
    site = "VoxWeaveTTS/runtime/python/Lib/site-packages/"
    dist_infos = sorted(name for name in entries
                        if name.startswith(site) and name.endswith(".dist-info/METADATA"))
    if len(dist_infos) != 4:
        raise AssertionError("Core ZIP included unapproved Python dependency")
    print("CORE_ONLY_ZIP_CONTENTS_PASS", len(files), flush=True)
    with tempfile.TemporaryDirectory(dir=ARCHIVE.parent,
                                     prefix="v4-core-release-extract-") as tmp:
        zip_in.extractall(tmp)
        stage = Path(tmp) / "VoxWeaveTTS"
        python = stage / "runtime/python/python.exe"
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": str(stage / "src"),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HF_HOME": str(stage / "cache/huggingface"),
            "TORCH_HOME": str(stage / "cache/torch"),
            "XDG_CACHE_HOME": str(stage / "cache"),
            "TEMP": str(stage / "cache/temp"),
            "TMP": str(stage / "cache/temp"),
            "UV_OFFLINE": "1",
        })
        (stage / "cache/temp").mkdir(parents=True, exist_ok=True)
        run = subprocess.run(
            [str(python), "-X", "utf8",
             str(ROOT / "scripts/verify_v4_core_only_stage.py"),
             "--stage", str(stage), "--demo-package", str(DEMO)],
            cwd=stage, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        print(run.stdout, flush=True)
        if run.returncode:
            raise AssertionError(run.stderr[-3000:] + run.stdout[-600:])
        payload = json.loads(run.stdout)
        assert payload["model_packages_bundled"] == 0
        assert payload["demo_v4_install_audio_uninstall"]
print("PUBLIC_V4_CORE_ZIP_EXTRACT_AND_PLUGIN_VERIFIED", flush=True)
