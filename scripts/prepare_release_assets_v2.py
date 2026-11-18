#!/usr/bin/env python3
"""Curate native-v2 release assets; never touch user settings or model caches.

V2 model packages are already built in dist/ModelPackagesV2. This script checks
archive manifests & hashes, stages the three previously reviewed offline
wheelhouse ZIPs, source/docs/extension ZIPs and writes SHA256SUMS. Do not
publish while tests or publisher/license reviews are unfinished.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from voxweavetts import __version__
from voxweavetts.offline_wheelhouse import trusted_lock, verified_wheels
from voxweavetts.universal_model_packages import inspect_archive

VERSION = __version__
OUTPUT = ROOT / "dist" / ("ReleaseV2_" + VERSION.replace(".", ""))
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
                f"VoxWeaveTTS v{VERSION} | OFFLINE VERIFIED WHEELHOUSE\n"
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


def stage_supplemental_archives() -> None:
    """Archive only Git-tracked release files; never include developer caches.

    Source is exported from HEAD, so the source archive and model notes refer
    to one reproducible commit. Do not run with uncommitted source changes.
    """
    state = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    if state.stdout.strip():
        raise RuntimeError("commit all source changes before staging release archives")
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT,
        capture_output=True, check=True,
    )
    tracked = [Path(x.decode("utf-8")) for x in result.stdout.split(b"\0") if x]
    sources = {
        f"VoxWeaveTTS-TikTok-Extension-v{VERSION}.zip": [
            x for x in tracked if x.as_posix().startswith("extensions/tiktok-live-connector/")
        ],
        f"VoxWeaveTTS-v{VERSION}-docs.zip": [
            x for x in tracked if x.parts[0] == "docs"
            or x.as_posix() in ("LICENSE", "README.md", "README_TH.md")
        ],
    }
    for name, entries in sources.items():
        if not entries:
            raise RuntimeError("missing tracked inputs for " + name)
        archive_path = OUTPUT / name
        if archive_path.exists():
            raise RuntimeError("refusing to overwrite release asset: " + name)
        with zipfile.ZipFile(archive_path, "x", allowZip64=True) as archive:
            for rel in sorted(entries, key=lambda p: p.as_posix()):
                file = ROOT / rel
                if not file.is_file() or file.is_symlink():
                    raise RuntimeError("invalid tracked release file: " + rel.as_posix())
                key = rel.as_posix()
                if name.startswith("VoxWeaveTTS-TikTok"):
                    key = key[len("extensions/"):]
                archive.write(file, key, compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(archive_path) as check:
            assert check.testzip() is None
        print("SUPPLEMENT", archive_path.name, archive_path.stat().st_size, flush=True)

    source = OUTPUT / f"VoxWeaveTTS-v{VERSION}-source.zip"
    if source.exists():
        raise RuntimeError("refusing to overwrite source archive")
    subprocess.run(
        ["git", "archive", "--format=zip", f"--output={source}", "HEAD"],
        cwd=ROOT, check=True,
    )
    with zipfile.ZipFile(source) as check:
        assert check.testzip() is None
        ver = check.read("src/voxweavetts/__init__.py").decode("utf-8")
        if f'__version__ = "{VERSION}"' not in ver:
            raise RuntimeError("git HEAD does not match requested release version")
    print("SOURCE_ARCHIVE", source.name, source.stat().st_size, flush=True)


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
    if len(expected) != 8:
        raise RuntimeError("release requires the 8 native Universal v2 packages")
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
    stage_supplemental_archives()
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
