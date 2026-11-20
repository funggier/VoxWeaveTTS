"""Real v4 Core-only Portable smoke without opening the user's service ports.

Checks clean installation (no model weights), minimal third-party dependencies,
offline .vwmodel v4 demo-plugin installation, actual PCM/WAV worker execution
and uninstall. Demo-generated sound is not real TTS.
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


def verify(stage: Path, demo: Path | None = None, sapi: Path | None = None) -> dict:
    stage = stage.resolve(strict=True)
    assert (stage / "VoxWeaveTTS.exe").is_file()
    assert (stage / "runtime/python/python.exe").is_file()
    assert (stage / "runtime/tools/uv.exe").is_file()
    assert not (stage / "models/universal/v3").exists()
    assert not list(stage.rglob("*.vwmodel")), "public Core must contain no TTS model archives"
    assert (stage / "THIRD_PARTY_NOTICES.txt").is_file()
    forbidden = [
        "universal_model_packages.py", "portable_runtime_v3.py",
        "package_install_v3.py", "engine_worker_legacy.py",
    ]
    assert all(not (stage / "src/voxweavetts" / x).exists() for x in forbidden)
    site = stage / "runtime/python/Lib/site-packages"
    dist_info = sorted(p.name for p in site.glob("*.dist-info"))
    assert len(dist_info) == 4, "unreviewed Python dependency leaked into public Core"
    assert all(any(p.startswith(needle + "-") for needle in
                   ("grpcio", "protobuf", "packaging", "typing_extensions"))
               for p in dist_info)
    assert not any((site / x).exists() for x in (
        "torch", "numpy", "scipy", "onnxruntime", "vachanatts", "gensim", "soundfile",
        "phonemizer", "pythaitts", "kokoro", "sherpa_onnx"
    ))
    sys.path.insert(0, str(stage / "src"))
    from voxweavetts.universal_model_v4 import (
        installed_packages, inspect_archive, install, remove, engine_id, backend_id
    )
    from voxweavetts.speech import engine_info, refresh_engine_registry
    from voxweavetts.server import Handler
    from voxweavetts.youtube_stream import _wire_types
    import grpc
    from google import protobuf
    from packaging.version import Version
    assert Version("4.0") > Version("3.0")
    assert grpc.__version__ and protobuf.__version__
    assert len(_wire_types()) == 2
    assert not installed_packages(stage)
    default = engine_info()
    assert not default.assets_ready and not default.runtime_ready
    assert default.voice_id == "paradee_thai"

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    responses = {}
    try:
        origin = "http://127.0.0.1:" + str(server.server_port)
        for path in ("/v1/status", "/v1/engines", "/v1/model-packages",
                     "/v1/ai/packages"):
            with urlopen(origin + path, timeout=5) as response:
                data = json.load(response)
            assert isinstance(data, dict)
            responses[path] = data
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    assert responses["/v1/model-packages"]["packages"] == []
    result = {
        "format": "voxweavetts.v4-core-only-release-smoke",
        "platform": "Windows Portable v4",
        "model_packages_bundled": 0,
        "third_party_python_distributions": dist_info,
        "http_endpoints": sorted(responses),
        "grpc_and_protobuf_ready": True,
        "offline": True,
    }

    if demo:
        manifest = inspect_archive(demo)
        assert manifest["package"]["id"] == "demo-tone-plugin"
        assert manifest["runtime"]["wheels"] == []
        assert manifest["rights"]["spdx"] == "MIT"
        installed = install(demo, root=stage)
        assert installed["format_version"] == 4
        refresh_engine_registry()
        from voxweavetts.speech import render_wav
        from voxweavetts.processing import process_text
        from voxweavetts.engine_worker_gateway import gateway
        m = next(m for m, _ in installed_packages(stage)
                 if m["package"]["id"] == "demo-tone-plugin")
        try:
            audio, _ = render_wav(
                process_text("VoxWeave v4 test tone, not spoken words"),
                engine_id=engine_id(m), voice_id="demo_tone", speed=1.0, seed=100)
            with wave.open(io.BytesIO(audio)) as wav:
                assert wav.getframerate() == 16000
                assert wav.getnframes() > 2000
                result["demo_tone_frames"] = wav.getnframes()
        finally:
            gateway().reset(backend_id(m))
        assert remove("demo-tone-plugin", m["package"]["version"], root=stage)
        refresh_engine_registry()
        assert not installed_packages(stage)
        result["demo_v4_install_audio_uninstall"] = True
        result["demo_is_not_speech"] = True
    if sapi:
        # A first-party voice bridge, no model weights: real spoken English
        # via whatever licensed desktop SAPI voices exist on this Windows host.
        from voxweavetts.universal_model_v4 import installed_packages as list_installed
        from voxweavetts.engine_worker_gateway import gateway
        from voxweavetts.speech import render_wav, refresh_engine_registry
        from voxweavetts.processing import process_text
        m = inspect_archive(sapi)
        assert m["package"]["id"] == "windows-sapi-desktop"
        assert m["runtime"]["wheels"] == []
        assert m["rights"]["spdx"] == "MIT"
        installed = install(sapi, root=stage)
        assert installed["format_version"] == 4
        refresh_engine_registry()
        try:
            speech, _ = render_wav(
                process_text("Hello from Windows SAPI speech synthesis"),
                engine_id=engine_id(m), voice_id="system_default",
                speed=1.0, seed=11
            )
            with wave.open(io.BytesIO(speech)) as pcm:
                assert pcm.getnchannels() == 1
                assert pcm.getsampwidth() == 2
                assert pcm.getframerate() == 16000
                assert pcm.getnframes() > 10000
                result["sapi_speech_frames"] = pcm.getnframes()
        finally:
            gateway().reset(backend_id(m))
            assert remove("windows-sapi-desktop", m["package"]["version"], root=stage)
            refresh_engine_registry()
        assert not list_installed(stage)
        result["sapi_real_speech_install_uninstall"] = True
        result["sapi_host_voice_dependency"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--demo-package", type=Path, default=None)
    parser.add_argument("--sapi-package", type=Path, default=None)
    args = parser.parse_args()
    print(json.dumps(verify(args.stage, args.demo_package, args.sapi_package),
                     ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
