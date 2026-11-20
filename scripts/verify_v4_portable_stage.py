"""Smoke test v4-only Portable without touching running service ports.

Uses the staged package and its own embedded Python; opens an ephemeral
loopback HTTP port and synthesizes actual MakHam Thai PCM/WAV.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import threading
import wave
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen


def verify(stage: Path) -> dict:
    stage = stage.resolve()
    if not (stage / "runtime/python/python.exe").is_file():
        raise AssertionError("no portable Python")
    if not (stage / "runtime/tools/uv.exe").is_file():
        raise AssertionError("no offline installer")
    if (stage / "models/universal/v3").exists():
        raise AssertionError("v3 model tree is still in the Portable")
    forbidden = ("universal_model_packages.py", "portable_runtime_v3.py",
                 "package_install_v3.py", "engine_worker_legacy.py",
                 "makham_package.py", "engine_worker_wayu.py")
    if any((stage / "src/voxweavetts" / name).exists() for name in forbidden):
        raise AssertionError("v3 code was bundled into v4")
    sys.path.insert(0, str(stage / "src"))
    from voxweavetts.universal_model_v4 import installed_packages, ready, engine_id
    from voxweavetts.speech import get_engine_info, render_wav
    from voxweavetts.processing import process_text
    from voxweavetts.server import Handler
    models = installed_packages(stage)
    if len(models) != 1 or models[0][0]["package"]["id"] != "makham-paradee":
        raise AssertionError("wrong v4-only default model")
    manifest = models[0][0]
    if not ready(stage, manifest):
        raise AssertionError("v4 default model not runtime-ready")
    eid = engine_id(manifest)
    info = get_engine_info(eid)
    if not info.runtime_ready or not info.assets_ready:
        raise AssertionError("v4 voice absent from registry")
    pcm_wav, timeline = render_wav(
        process_text("สวัสดีครับ วันนี้ทดสอบ VoxWeaveTTS v4"),
        engine_id=eid, voice_id="paradee_thai", speed=1.0, seed=100)
    with wave.open(io.BytesIO(pcm_wav), "rb") as f:
        rate, frames = f.getframerate(), f.getnframes()
    if rate != 24000 or frames < 1000:
        raise AssertionError("invalid v4 MakHam WAV")
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    results = {}
    try:
        origin = "http://127.0.0.1:" + str(http.server_port)
        for path in ("/v1/status", "/v1/engines",
                     "/v1/model-packages", "/v1/ai/packages"):
            with urlopen(origin + path, timeout=6) as response:
                data = json.load(response)
            if not isinstance(data, dict):
                raise AssertionError("invalid v4 API response")
            results[path] = data
    finally:
        http.shutdown()
        http.server_close()
        thread.join(3)
    packages = results["/v1/model-packages"]["packages"]
    if len(packages) != 1 or packages[0]["format_version"] != 4:
        raise AssertionError("model package API advertised non-v4 models")
    return {
        "format": "voxweavetts.v4-only-portable-smoke",
        "engine_id": eid, "sample_rate": rate,
        "pcm_frames": frames, "wav_bytes": len(pcm_wav),
        "http_endpoints": sorted(results),
        "model_package_format": packages[0]["format_version"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.stage), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
