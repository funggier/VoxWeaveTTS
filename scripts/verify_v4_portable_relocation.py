"""Windows QA: install a real v4 TTS, MOVE the entire Portable, speak and uninstall.

Operate exclusively on two explicitly specified, separate, disposable directories
inside dist/. Never move the live application or change a global service/port.
This test does not require network access and refuses to overwrite the destination.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voxweavetts.universal_model_v4 import (
    inspect_archive, install, installed_packages, ready, remove, runtime_dir,
    engine_id, backend_id, fingerprint, worker_command,
)

ENGINE = "fastthaig2p-thai-som"
VOICE = "thai_som"

SPEECH = r'''
import io, json, wave
from voxweavetts.universal_model_v4 import installed_packages, engine_id, ready, backend_id, worker_command
from voxweavetts.speech import render_wav
from voxweavetts.processing import process_text
from voxweavetts.engine_worker_gateway import gateway
from pathlib import Path
root = Path.cwd()
items = installed_packages(root)
ids = {m["package"]["id"] for m, _ in items}
assert {"makham-paradee", "fastthaig2p-thai-som"} <= ids, ids
m = next(m for m, _ in items if m["package"]["id"] == "fastthaig2p-thai-som")
assert ready(root, m)
cmd = worker_command(root, m)
assert all(str(root) in part for part in (cmd[0], cmd[-1]))
try:
    audio, meta = render_wav(
        process_text("สวัสดีครับ ทดสอบการย้ายโปรแกรมไปยังโฟลเดอร์ใหม่"),
        engine_id=engine_id(m), voice_id="thai_som", speed=1.0, seed=100
    )
    with wave.open(io.BytesIO(audio), "rb") as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        assert wav.getframerate() == 24000 and wav.getnframes() > 1000
        result = {"root": str(root), "engine_id": engine_id(m),
                  "rate": wav.getframerate(), "frames": wav.getnframes(),
                  "wav_bytes": len(audio), "runtime_ready": ready(root, m),
                  "portable_python": str(cmd[0]), "bundled_only": True}
    print("RELOCATION_V4_WAV " + json.dumps(result, ensure_ascii=False), flush=True)
finally:
    gateway().reset(backend_id(m))
'''


def isolated_root(path: Path) -> Path:
    path = path.resolve()
    dist = (ROOT / "dist").resolve()
    if (not path.is_relative_to(dist) or "validation" not in path.name.lower()
        or path == dist or path.is_symlink()):
        raise ValueError("use separate explicit disposable validation roots inside dist/")
    return path


def speech(root: Path) -> dict:
    embedded = root / "runtime" / "python" / "python.exe"
    if not embedded.is_file():
        raise AssertionError("embedded Python is missing after relocation")
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(root / "src"), "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HF_HOME": str(root / "cache" / "huggingface"),
        "TORCH_HOME": str(root / "cache" / "torch"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "TEMP": str(root / "cache" / "temp"),
        "TMP": str(root / "cache" / "temp"),
        "PIP_NO_INDEX": "1", "UV_OFFLINE": "1",
    })
    (root / "cache" / "temp").mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(embedded), "-X", "utf8", "-c", SPEECH],
        cwd=root, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError("relocation v4 inference failed: "
                           + result.stderr[-1600:] + result.stdout[-500:])
    lines = [x.removeprefix("RELOCATION_V4_WAV ") for x in result.stdout.splitlines()
             if x.startswith("RELOCATION_V4_WAV ")]
    if len(lines) != 1:
        raise AssertionError("v4 relocation test did not emit one WAV result")
    return json.loads(lines[0])


def verify(source: Path, destination: Path, archive: Path) -> dict:
    source, destination = isolated_root(source), isolated_root(destination)
    if source == destination or not source.is_dir() or destination.exists():
        raise ValueError("relocation requires a pre-existing disposable source and a new destination")
    m = inspect_archive(archive)
    if m["package"]["id"] != ENGINE or m["package"]["kind"] != "tts":
        raise ValueError("wrong v4 FastThai QA archive")
    if [p["package"]["id"] for p, _ in installed_packages(source)] != ["makham-paradee"]:
        raise ValueError("source must contain only the v4 MakHam default")
    install(archive, root=source)
    installed = next(x for x, _ in installed_packages(source) if x["package"]["id"] == ENGINE)
    old_env = runtime_dir(source, installed)
    if not old_env.is_dir() or not ready(source, installed):
        raise AssertionError("v4 model runtime not ready before relocation")
    before = speech(source)
    source.rename(destination)
    if source.exists() or not destination.is_dir():
        raise AssertionError("Portable was not moved successfully")
    moved = next(x for x, _ in installed_packages(destination) if x["package"]["id"] == ENGINE)
    if not ready(destination, moved) or not runtime_dir(destination, moved).is_dir():
        raise AssertionError("isolated environment not portable")
    after = speech(destination)
    if after["rate"] != before["rate"] or after["engine_id"] != before["engine_id"]:
        raise AssertionError("v4 model changed identity after relocation")
    if not remove(ENGINE, installed["package"]["version"], root=destination):
        raise AssertionError("v4 uninstall did not work after relocation")
    remaining = installed_packages(destination)
    if len(remaining) != 1 or remaining[0][0]["package"]["id"] != "makham-paradee":
        raise AssertionError("optional TTS package remained after relocation uninstall")
    # V4 intentionally deduplicates offline runtimes by wheel fingerprint.
    # A model uninstall must preserve its environment if default MakHam uses it.
    shared_runtime = any(fingerprint(other) == fingerprint(moved)
                         for other, _ in remaining)
    if runtime_dir(destination, moved).exists() != shared_runtime:
        raise AssertionError("v4 shared runtime retention/removal violated")
    return {
        "test": "voxweavetts.v4-only-portable-relocation",
        "moved": True,
        "source": str(source), "destination": str(destination),
        "old_path_referenced": False, "runtime_relocated": True,
        "before_frames": before["frames"], "after_frames": after["frames"],
        "wav_rate": after["rate"], "uninstall_after_move": True,
        "shared_runtime_retained": shared_runtime,
        "default_makham_retained": True,
        "public_release_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--archive", type=Path, default=ROOT / "dist" /
                        "ModelPackagesV4-QA" /
                        "VoxWeaveTTS-fastthaig2p-thai-som-0.3.0-UNRELEASED-QA-format-v4.vwmodel")
    args = parser.parse_args()
    print(json.dumps(verify(args.source, args.destination, args.archive),
                     ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
