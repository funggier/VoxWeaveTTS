#!/usr/bin/env python3
"""Curate local wheel files for a first-party runtime. NO downloads.

By default, writes an untrusted DRAFT under cache/wheelhouse-drafts.
Only --publish-reviewed records the hashes in app-owned scripts/wheelhouse-locks
and copies data to runtime/wheelhouse; review origin, licensing and transitive
dependencies before publishing or including any files in a portable release.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voxweavetts.offline_wheelhouse import (WheelhouseError, _digest, _wheel_dir,
    _lock_path, draft_lock, trusted_lock, verified_wheels)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-id", required=True,
                        help="trusted built-in runtime ID (e.g. sherpa, m2m100)")
    parser.add_argument("--source", type=Path, required=True,
                        help="local folder containing ALL compatible binary .whl files")
    parser.add_argument("--publish-reviewed", action="store_true",
                        help="explicitly curate reviewed wheels and trusted lock")
    args = parser.parse_args()
    draft = draft_lock(ROOT, args.runtime_id, args.source)
    drafts = ROOT / "cache" / "wheelhouse-drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    candidate = drafts / (args.runtime_id + ".json")
    candidate.write_text(json.dumps(draft, indent=2) + "\n", encoding="utf-8")
    print("Draft:", candidate, "Wheels:", len(draft["wheels"]))
    print("Review wheel provenance, distribution rights and dependency closure.")
    if not args.publish_reviewed:
        print("Not trusted or installed. Use --publish-reviewed after review.")
        return 0
    lock_file = _lock_path(ROOT, args.runtime_id)
    destination = _wheel_dir(ROOT, args.runtime_id)
    if lock_file.exists() or destination.exists() or destination.is_symlink():
        raise WheelhouseError("trusted lock or wheelhouse already exists; refusing overwrite")
    if destination.is_relative_to(args.source.resolve()) or args.source.resolve().is_relative_to(destination.resolve()):
        raise WheelhouseError("source/destination directories must not overlap")
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.with_name("." + destination.name + ".import")
    if stage.exists() or stage.is_symlink():
        raise WheelhouseError("staging folder already exists")
    stage.mkdir()
    try:
        for row in draft["wheels"]:
            source = args.source / row["filename"]
            target = stage / row["filename"]
            shutil.copyfile(source, target)
            if target.stat().st_size != row["size"] or _digest(target) != row["sha256"]:
                raise WheelhouseError("wheel changed while staging")
        stage.rename(destination)
        lock_file.write_text(json.dumps(draft, indent=2) + "\n", encoding="utf-8")
        # Verify the published lock against all copied binary data, not just filenames.
        with verified_wheels(ROOT, args.runtime_id):
            pass
        print("Published reviewed wheelhouse:", destination)
    except Exception:
        # Keep published data intact if verification after publish fails: a
        # broken lock should not be silently overwritten by another attempt.
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, WheelhouseError) as exc:
        print("Wheelhouse preparation failed:", exc, file=sys.stderr)
        raise SystemExit(1)
