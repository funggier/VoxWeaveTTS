"""Release-gate: verify ZIP contents, extract independently and test Thai WAV via HTTP."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
archive = repo / "dist" / "VoxWeaveTTS-v0.4.1-portable.zip"
assert archive.is_file(), "no release ZIP"
sha = hashlib.sha256(archive.read_bytes()).hexdigest().upper()
print("ZIP_SHA256", sha, flush=True)
print("ZIP_MB", round(archive.stat().st_size / 1024**2, 1), flush=True)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None, "corrupted entry"
    files = [name.replace("\\", "/") for name in z.namelist()]
    assert all(n.startswith("VoxWeaveTTS/") and ".." not in n.split("/") for n in files)
    assert "VoxWeaveTTS/VoxWeaveTTS.exe" in files
    assert "VoxWeaveTTS/runtime/python/python.exe" in files
    assert "VoxWeaveTTS/LICENSE" in files
    assert "VoxWeaveTTS/THIRD_PARTY_NOTICES.txt" in files
    assert "VoxWeaveTTS/models/makham-paradee/paradee_thai_int8.onnx" in files
    user_directories = ("data/", "voices/", "cache/", "output/", "logs/")
    assert not any(
        name.startswith("VoxWeaveTTS/" + directory) and not name.endswith("/")
        for directory in user_directories for name in files
    ), "private user directory contents included"
    assert not any(
        name.startswith("VoxWeaveTTS/models/fastthaig2p/") and not name.endswith("/")
        for name in files
    ), "unreviewed Fast model included"
    voice_models = [name for name in files if name.endswith((".onnx", ".npy", ".wav", ".mp3", ".safetensors"))]
    assert voice_models == ["VoxWeaveTTS/models/makham-paradee/paradee_thai_int8.onnx"], voice_models
    print("ZIP_CONTENTS_PASS", len(files), "entries; only approved model", flush=True)

    with tempfile.TemporaryDirectory(dir=archive.parent, prefix="vox-portable-extract-") as temp:
        z.extractall(temp)
        root = Path(temp) / "VoxWeaveTTS"
        python = root / "runtime" / "python" / "python.exe"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root / "src")
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["HF_HOME"] = str(root / "cache" / "huggingface")
        env["TORCH_HOME"] = str(root / "cache" / "torch")
        env["XDG_CACHE_HOME"] = str(root / "cache")
        env["TEMP"] = str(root / "cache" / "temp")
        env["TMP"] = str(root / "cache" / "temp")
        (root / "cache" / "temp").mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [str(python), str(repo / "tests" / "smoke_portable_release.py")],
            cwd=root, env=env, capture_output=True, text=True, timeout=45,
            encoding="utf-8", errors="replace",
        )
        print(result.stdout, flush=True)
        assert result.returncode == 0, result.stderr

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        proc = subprocess.Popen(
            [str(python), "-m", "voxweavetts", "--port", str(port)],
            cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            ready = False
            for attempt in range(55):
                if proc.poll() is not None:
                    raise AssertionError("portable server stopped unexpectedly")
                try:
                    with urllib.request.urlopen(base + "/v1/status", timeout=1) as response:
                        state = json.load(response)
                    if state["version"] == "0.4.1":
                        ready = True
                        break
                except (OSError, ValueError):
                    time.sleep(.2)
            assert ready, "packaged API did not become ready"
            body = json.dumps({
                "text": "สวัสดีค่ะ ทดสอบเสียง",
                "engine_id": "makham-paradee-cpu",
                "voice_id": "paradee_thai",
            }, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(
                base + "/v1/speech", data=body,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(request, timeout=35) as response:
                wav = response.read()
            assert wav.startswith(b"RIFF") and len(wav) > 10000, len(wav)
            print("PORTABLE_HTTP_THAI_SPEECH_PASS", len(wav), "WAV bytes", flush=True)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

print("PORTABLE_ARCHIVE_VERIFIED", flush=True)
