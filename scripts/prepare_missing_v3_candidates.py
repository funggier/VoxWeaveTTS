"""Prepare *private, unpublishable* v3 candidates for the three legacy TTS models.

Safety contract:
- Read original v1/v2 archives as data, verify every indexed original SHA-256.
- Preserve model notices, exact source revision and runtime's rights HOLD.
- Bundle candidate wheels only for LOCAL EVALUATION, never promote hashes to the
  trusted application lock, and never publish candidates to dist/ModelPackagesV3.
- Missing wheel closure => report a blocker, not a fabricated 'complete' model.
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
from packaging.utils import parse_wheel_filename
from voxweavetts.provider_rights import review
from voxweavetts.universal_model_packages import _path, inspect_archive

SOURCE = ROOT / "dist" / "ModelPackages"
OUTPUT = ROOT / "cache" / "v3-unreleased-candidates"
MODELS = {
    "kokoro-multilingual-int8": {
        "archive": "VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel",
        "wheel_dir": "phasec-kokoro-candidate",
        "languages": ["en", "es", "fr", "hi", "it", "ja", "pt"],
        "runtime": "kokoro",
    },
    "vachana-thai-four-voices": {
        "archive": "VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel",
        "wheel_dir": "phasec-vachana-candidate",
        "languages": ["th"],
        "runtime": "vachana",
    },
    "wayu-paxa-edge-nc": {
        "archive": "VoxWeaveTTS-Wayu-Paxa-Edge-Thai-English-12Voices-NC-v1.0.0.vwmodel",
        "wheel_dir": None,
        "languages": ["th", "en"],
        "runtime": "wayu-nc",
    },
}


def digest(stream) -> str:
    sha = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        sha.update(block)
    return sha.hexdigest()


def prepared_original(model_id: str, folder: Path) -> dict:
    spec = MODELS[model_id]
    archive_path = SOURCE / spec["archive"]
    with zipfile.ZipFile(archive_path) as archive:
        original = json.loads(archive.read("manifest.json"))
        if (original["package_id"] != model_id
            or original["version"] != "1.0.0"
            or not original.get("files")
            or not original.get("license")
            or not original.get("source")):
            raise ValueError("legacy archive identity and provenance mismatch")
        # Re-create only enumerated archive assets, with streaming digest checks.
        for row in original["files"]:
            name = _path(row["path"])
            dest = folder / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as inp, dest.open("wb") as out:
                sha = hashlib.sha256()
                for block in iter(lambda: inp.read(1024 * 1024), b""):
                    out.write(block)
                    sha.update(block)
            if (dest.stat().st_size != row["size"]
                or sha.hexdigest() != row["sha256"]):
                raise ValueError("legacy asset differs from original pin: " + name)
    rights = {
        "license": {**original["license"], "review_status": "hold"},
        "source": original["source"],
    }
    legal = folder / "legal"
    legal.mkdir(parents=True, exist_ok=True)
    (legal / "rights.json").write_text(
        json.dumps(rights, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return original


def wheel_bundle(model_id: str, folder: Path) -> dict | None:
    source_name = MODELS[model_id]["wheel_dir"]
    if source_name is None:
        return None
    source = ROOT / "cache" / "temp" / source_name
    wheels = sorted(source.glob("*.whl"))
    if not wheels:
        return None
    dest = folder / "runtime" / "wheels"
    dest.mkdir(parents=True, exist_ok=True)
    installed = []
    requirements = {}
    for file in wheels:
        name, version, _build, tags = parse_wheel_filename(file.name)
        if not any(str(tag).endswith("-win_amd64") or str(tag).endswith("-any") for tag in tags):
            raise ValueError("unexpected candidate wheel platform: " + file.name)
        normalized = str(name).replace("_", "-")
        key = normalized.casefold()
        if key in requirements and requirements[key] != str(version):
            raise ValueError("ambiguous wheel version for " + normalized)
        requirements[key] = str(version)
        target = dest / file.name
        shutil.copyfile(file, target)
        with target.open("rb") as stream:
            target_sha = digest(stream)
        with file.open("rb") as stream:
            source_sha = digest(stream)
        if target_sha != source_sha:
            raise ValueError("candidate wheel changed during staging")
        installed.append({"path": "runtime/wheels/" + file.name, "sha256": target_sha})
    lock = {"requirements": [{"name": name, "version": version}
                              for name, version in sorted(requirements.items())],
            "wheels": installed}
    path = folder / "runtime" / "locks" / "approved.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return lock


def prepare_one(model_id: str, *, make_draft: bool = False) -> dict:
    spec = MODELS[model_id]
    rights = review(spec["runtime"])
    assert rights["publication_state"] == "hold"
    result = {
        "model": model_id, "runtime": spec["runtime"],
        "legacy_archive": spec["archive"],
        "rights_state": rights["publication_state"],
        "blockers": list(rights["reasons"]),
        "candidate_archive": None,
        "ready_for_publication": False,
    }
    if model_id == "kokoro-multilingual-int8":
        result["blockers"].append("candidate-misaki-0.9.4-pyopenjtalk-is-not-the-tested-runtime-recipe")
    source_file = SOURCE / spec["archive"]
    if not source_file.is_file():
        result["blockers"].append("original-model-archive-missing")
        return result
    if spec["wheel_dir"] is None:
        result["blockers"].append("complete-offline-wheel-closure-not-available")
        return result
    folder = OUTPUT / (model_id + "-source")
    if not make_draft:
        result["candidate_wheels"] = len(list(
            (ROOT / "cache" / "temp" / spec["wheel_dir"]).glob("*.whl")))
        return result
    if folder.exists() or folder.is_symlink():
        raise ValueError("candidate staging already exists; never overwrite it: " + str(folder))
    folder.mkdir(parents=True)
    original = prepared_original(model_id, folder)
    lock = wheel_bundle(model_id, folder)
    if not lock:
        result["blockers"].append("complete-offline-wheel-closure-not-available")
        return result
    existing = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*")
                      if p.is_file())
    excluded = {"manifest-assets.json", "legal/rights.json", "runtime/locks/approved.lock"}
    (folder / "manifest-assets.json").write_text(
        json.dumps({"paths": [p for p in existing if p not in excluded]},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    attrs = {
        "package": {
            "id": model_id, "version": original["version"], "kind": "tts",
            "title": original["title"], "languages": spec["languages"],
        },
        "adapter": {
            "id": original["engine_adapter"], "api_version": 1, "trust": "builtin",
        },
        "runtime": {
            "id": spec["runtime"], "kind": "python-target", "python": "3.11",
            "platform": "windows-x64", "accelerator": "cpu",
            "source": "bundled-wheels", "install_policy": "auto",
            "lockfile": "runtime/locks/approved.lock",
        },
        "capabilities": {
            "language": original["language"], "sample_rate": original["sample_rate"],
            "voices": original["voices"],
        },
    }
    (OUTPUT / (model_id + "-spec.json")).write_text(
        json.dumps(attrs, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    from build_vwmodel_v3 import build
    archive = OUTPUT / (model_id + "-UNRELEASED-format-v3.vwmodel")
    build(folder, OUTPUT / (model_id + "-spec.json"), archive)
    manifest = inspect_archive(archive)
    if manifest["package"]["id"] != model_id:
        raise ValueError("v3 candidate package validation failed")
    result["candidate_archive"] = str(archive)
    result["candidate_wheels"] = len(lock["wheels"])
    return result


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--prepare-drafts", action="store_true",
                     help="create LOCAL non-installable QA archives only")
    args = cli.parse_args()
    report = [prepare_one(name, make_draft=args.prepare_drafts) for name in MODELS]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "HOLD-REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    for item in report:
        print("V3_MISSING_CANDIDATE", json.dumps(item, ensure_ascii=False), flush=True)
    print("UNPUBLISHABLE_CANDIDATES_ONLY; no trusted runtime locks were added")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
