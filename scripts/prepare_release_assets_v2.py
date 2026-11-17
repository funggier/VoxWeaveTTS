#!/usr/bin/env python3
"""Curate public v0.10.0 release assets; never touch user settings or model caches.

V2 model packages are already built in dist/ModelPackagesV2. This script checks
archive manifests & hashes, stages separately labeled offline wheelhouse ZIPs
from first-party lock files and writes SHA256SUMS for reproducibility. Do not
publish while tests or publisher/license reviews are unfinished.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from voxweavetts.offline_wheelhouse import trusted_lock, verified_wheels
from voxweavetts.universal_model_packages import inspect_archive

VERSION = "0.10.0"
OUTPUT = ROOT / "dist" / "ReleaseV2"
PACKAGES = ROOT / "dist" / "ModelPackagesV2"
RUNTIMES = ("sherpa", "pythaitts", "m2m100")


def digest(file: Path) -> str:
    checksum = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def build_wheel_zip(runtime_id: str, destination: Path) -> None:
    lock = trusted_lock(ROOT, runtime_id)
    with verified_wheels(ROOT, runtime_id) as (snapshot, _):
        # Only hash-verified wheels from trusted, app-owned lock may be exported.
        with zipfile.ZipFile(destination, "w", allowZip64=True) as archive:
            for row in lock["wheels"]:
                source = snapshot / row["filename"]
                arc = "runtime/wheelhouse/" + runtime_id + "/" + row["filename"]
                archive.write(source, arc, compress_type=zipfile.ZIP_STORED)
            archive.write(ROOT / "scripts" / "wheelhouse-locks" /
                          (runtime_id + ".json"),
                          "scripts/wheelhouse-locks/" + runtime_id + ".json",
                          compress_type=zipfile.ZIP_DEFLATED)
            archive.write(ROOT / "docs" / "WHEELHOUSE_LICENSE_REVIEW_TH.md",
                          "docs/WHEELHOUSE_LICENSE_REVIEW_TH.md",
                          compress_type=zipfile.ZIP_DEFLATED)
            message = (
                "VoxWeaveTTS v0.10.0 | OFFLINE VERIFIED WHEELHOUSE\n"
                f"Runtime: {runtime_id} | Python: 3.11 | Windows: win_amd64\n"
                "Extract at the root of the corresponding Portable folder.\n"
                "Installs ONLY after user approval and SHA-256 verification.\n"
                "Wheel files have their own upstream license terms.\n"
                "Read docs/WHEELHOUSE_LICENSE_REVIEW_TH.md before redistribution;\n"
                "technical hash verification is not a license clearance.\n"
                "No pretrained TTS/translation model weights are included.\n"
            )
            archive.writestr("README-WHEELHOUSE.txt", message,
                             compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(destination) as archive:
            assert archive.testzip() is None
    print("WHEELHOUSE", destination.name, destination.stat().st_size, flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage-only", action="store_true",
                   help="validate and create wheelhouses; do not check portable zip")
    args = p.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if not args.stage_only and not (ROOT / "dist" /
                                    f"VoxWeaveTTS-v{VERSION}-portable.zip").is_file():
        raise RuntimeError("Portable native-v2 ZIP must exist first")
    for runtime_id in RUNTIMES:
        archive = OUTPUT / (
            f"VoxWeaveTTS-{runtime_id}-win_amd64-py311-wheelhouse.zip")
        if archive.exists():
            raise RuntimeError("Refusing to overwrite existing release asset: " + archive.name)
        build_wheel_zip(runtime_id, archive)
    listing = (PACKAGES / "SHA256SUMS.txt").read_text(encoding="utf-8")
    expected = {}
    for line in listing.splitlines():
        if not line.strip():
            continue
        sha, name = line.split(maxsplit=1)
        if name in expected or "/" in name or "\\" in name:
            raise RuntimeError("invalid model package SHA256SUMS")
        expected[name] = sha
    if len(expected) != 7:
        raise RuntimeError("release requires the 7 native Universal v2 packages")
    for name, sha in sorted(expected.items()):
        file = PACKAGES / name
        if not name.endswith("-format-v2.vwmodel") or not file.is_file():
            raise RuntimeError("missing native v2 model archive: " + name)
        metadata = inspect_archive(file)
        if metadata.get("format_version") != 2:
            raise RuntimeError("non-v2 model archive: " + name)
        actual = digest(file)
        if actual != sha:
            raise RuntimeError("model release archive SHA-256 mismatch: " + name)
        print("MODEL_ARCHIVE", name, file.stat().st_size, metadata["package"]["id"],flush=True)
    print("ALL MODEL ARCHIVES MATCH RELEASE SHA256SUMS", flush=True)
    if args.stage_only:
        return
    all_assets = sorted(OUTPUT.glob("*.zip"))
    all_assets += [ROOT / "dist" / f"VoxWeaveTTS-v{VERSION}-portable.zip"]
    all_assets += sorted(PACKAGES.glob("*.vwmodel"))
    all_assets += sorted(OUTPUT.glob("*.txt"))
    manifest = OUTPUT / f"SHA256SUMS-v{VERSION}.txt"
    manifest.write_text("".join(digest(x) + "  " + x.name + "\n"
                                for x in sorted(all_assets, key=lambda p: p.name)),
                        encoding="utf-8")
    print("Release checksums", manifest, "ASSETS", len(all_assets), flush=True)


if __name__ == "__main__":
    main()
