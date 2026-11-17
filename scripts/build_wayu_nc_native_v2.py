"""Build the optional Wayu NC native-v2 model from previously pinned local files.

Never downloads, imports Wayu inference, unpickles weights, or writes to a live
model folder. Retains CC BY-NC 4.0 attribution and upstream acceptable use.
Legal attribution/acceptable-use notices are tracked in docs/third-party.
No v1 archive or v1 model package code is required to build this format.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from voxweavetts.personal_wayu_engine import VOICES
from voxweavetts.universal_model_packages import (
    make_package, validate_manifest, _validate_assets,
)
from voxweavetts.wayu_native_trust import (
    PINNED_ASSETS, SOURCE_URL, SOURCE_REVISION, LICENSE_SPDX,
    PACKAGE_ID, PACKAGE_VERSION,
)

OUTPUT = (ROOT / "dist" / "ModelPackagesV2" /
          "VoxWeaveTTS-Wayu-Paxa-Edge-Thai-English-12Voices-NC-v1.0.0-format-v2.vwmodel")
SOURCE = ROOT / "models" / "personal" / "wayu-paxa-tts-edge"
NOTICE_DIR = ROOT / "docs" / "third-party" / "wayu-nc"
NOTICES = ("legal/license.txt", "legal/attribution.md", "legal/acceptable-use.txt")


def checksum(file: Path) -> str:
    h = hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build(*, source: Path = SOURCE, output: Path = OUTPUT,
          notices: Path = NOTICE_DIR) -> Path:
    source, output, notices = Path(source), Path(output), Path(notices)
    if output.exists() or output.is_symlink():
        raise ValueError("refusing overwrite of existing Wayu NC v2 archive")
    if not notices.is_dir():
        raise ValueError("first-party Wayu NC legal notice directory is missing")
    # Check every dangerous serialized file against first-party, reviewed
    # upstream pins BEFORE exposing it to any ML inference library.
    for name, expected in PINNED_ASSETS.items():
        file = source / name
        if (not file.is_file() or file.is_symlink()
            or checksum(file) != expected):
            raise ValueError("Wayu NC pinned upstream asset missing or modified: " + name)
    staging_parent = ROOT / "cache" / "temp"
    staging_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wayu-v2-stage-", dir=staging_parent) as temporary:
        stage = Path(temporary)
        for name in PINNED_ASSETS:
            original = source / name
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(original, target)
            except OSError:
                shutil.copy2(original, target)
        (stage / "README.md").write_bytes((source / "README.md").read_bytes())
        for name in NOTICES:
            original = notices / Path(name).name
            if (not original.is_file() or original.is_symlink()
                or original.stat().st_size > 100_000):
                raise ValueError("missing/unsafe Wayu NC legal notice: " + name)
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
        rights = {
            "license": {
                "spdx": LICENSE_SPDX,
                "url": "https://creativecommons.org/licenses/by-nc/4.0/",
                "attribution": (
                    "Wayu Research — Wayu Paxa TTS Edge (12 original Thai/English voices). "
                    "Kunat Pipatanakul, Potsawee Manakul, Warit Sirichotedumrong, "
                    "Sittipong Sripaisarnmongkol, Pakorn Nathong, "
                    "Phatrasek Jirabovonvisut. Original weight/voice files unmodified; "
                    "repackaged as VoxWeaveTTS native .vwmodel v2. "
                    "CC BY-NC 4.0: NonCommercial ONLY, with attribution and "
                    "upstream acceptable-use limitations."
                ),
                "review_status": "hold",
            },
            "source": {"url": SOURCE_URL, "revision": SOURCE_REVISION},
        }
        legal_json = stage / "legal" / "rights.json"
        legal_json.write_text(
            json.dumps(rights, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        all_model_files = sorted(
            [*PINNED_ASSETS, "README.md", *NOTICES],
            key=lambda x: x.casefold(),
        )
        assets_file = stage / "manifest-assets.json"
        assets_file.write_text(
            json.dumps({"paths": all_model_files}, indent=2) + "\n",
            encoding="utf-8",
        )
        declared = sorted([*all_model_files, "manifest-assets.json",
                           "legal/rights.json"], key=str.casefold)
        files = []
        for name in declared:
            file = stage / name
            files.append({"path": name, "size": file.stat().st_size,
                          "sha256": checksum(file)})
        manifest = {
            "format": "voxweavetts.model-package",
            "format_version": 2,
            "package": {
                "id": PACKAGE_ID, "version": PACKAGE_VERSION, "kind": "tts",
                "title": "Wayu Paxa Edge — Thai / English — 12 voices",
                "languages": ["th", "en"],
            },
            "adapter": {"id": "wayu-nc-v1", "api_version": 1, "trust": "builtin"},
            "runtime": {
                "id": "wayu-nc", "kind": "python-venv", "python": "3.11",
                "platform": "windows-x64", "accelerator": "cpu",
                "source": "reuse-only", "install_policy": "reuse-only",
                "lockfile": None,
            },
            "assets": "manifest-assets.json",
            "rights": "legal/rights.json",
            "files": files,
            "capabilities": {
                "language": "th", "sample_rate": 24000,
                "voices": [
                    {"id": voice, "label": label, "asset": "voices/" + voice + ".pt"}
                    for voice, label in VOICES
                ],
            },
        }
        validate_manifest(manifest)
        _validate_assets(stage, manifest)
        return make_package(stage, manifest, output)


if __name__ == "__main__":
    result = build()
    print("Native v2 CC BY-NC archive:", result, flush=True)
    print("SHA256:", checksum(result), flush=True)
