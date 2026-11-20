"""Build private v3 Vachana QA candidate using scriptless ssg wheel.

The original Vachana wheels and v3 candidate remain untouched. Output under
cache/ is NOT for public redistribution, pending independent license clearance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "cache" / "v3-unreleased-candidates"
WHEELS = ROOT / "cache" / "temp" / "qa-vachana-scriptless"
NAME = "vachana-thai-four-voices"
SOURCE = QA / (NAME + "-source")
STAGE = QA / (NAME + "-qa-scriptless-source")
ARCHIVE = QA / (NAME + "-UNRELEASED-QA-scriptless-format-v3.vwmodel")
SSG = "ssg-0.0.8-py3-none-any.whl"

def build() -> dict:
    if not SOURCE.is_dir() or not (WHEELS / SSG).is_file():
        raise ValueError("first prepare native v3 candidate and scriptless QA wheel")
    if STAGE.exists() or STAGE.is_symlink() or ARCHIVE.exists():
        raise ValueError("QA output exists; refusing to overwrite")
    shutil.copytree(SOURCE, STAGE, symlinks=False)
    wheel = STAGE / "runtime" / "wheels" / SSG
    shutil.copyfile(WHEELS / SSG, wheel)
    with wheel.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    lockfile = STAGE / "runtime" / "locks" / "approved.lock"
    lock = json.loads(lockfile.read_text(encoding="utf-8"))
    changed = 0
    for item in lock["wheels"]:
        if item["path"] == "runtime/wheels/" + SSG:
            item["sha256"] = digest
            changed += 1
    if changed != 1:
        raise ValueError("ssg wheel declaration missing or ambiguous")
    lockfile.write_text(json.dumps(lock, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_vwmodel_v3 import build as build_v3
    archive = build_v3(STAGE, QA / (NAME + "-spec.json"), ARCHIVE)
    return {"output": str(archive), "sha256_ssg": digest,
            "qa_only": True, "public_release_allowed": False}

def main():
    _ = argparse.ArgumentParser(description=__doc__).parse_args()
    print("VACHANA_SCRIPTLESS_V3_CANDIDATE",
          json.dumps(build(), ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
