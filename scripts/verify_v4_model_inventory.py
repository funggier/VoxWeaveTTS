"""Verify all eight offline v4 model packages without trusting self-asserted rights.

The archive scan is read-only. A technically complete set is NOT permission
to publicly redistribute bundled third-party model weights and dependencies.
The required RIGHTS_HOLD output is deliberate until separately reviewed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from voxweavetts.universal_model_v4 import inspect_archive

EXPECTED = {
    "makham-paradee": "tts",
    "fastthaig2p-thai-som": "tts",
    "melo-chinese-onnx": "tts",
    "supertonic3-multilingual-int8": "tts",
    "kokoro-multilingual-int8": "tts",
    "vachana-thai-four-voices": "tts",
    "wayu-paxa-edge-nc": "tts",
    "m2m100-418m": "translation",
}


def audit(folder: Path, *, deep: bool = False) -> dict:
    found = {}
    issues = []
    for archive in sorted(Path(folder).glob("*.vwmodel")):
        try:
            manifest = inspect_archive(archive)
            name = manifest["package"]["id"]
            if name not in EXPECTED or name in found:
                issues.append("unexpected/duplicate v4 package: " + archive.name)
                continue
            if (manifest["package"]["kind"] != EXPECTED[name]
                or manifest["format_version"] != 4):
                issues.append("unexpected model kind or format: " + name)
                continue
            with archive.open("rb") as stream:
                sha = hashlib.file_digest(stream, "sha256").hexdigest()
            if deep:
                with zipfile.ZipFile(archive) as z:
                    for row in manifest["files"]:
                        digest = hashlib.sha256()
                        actual = 0
                        with z.open(row["path"]) as item:
                            for block in iter(lambda: item.read(1024 * 1024), b""):
                                digest.update(block)
                                actual += len(block)
                        if actual != row["size"] or digest.hexdigest() != row["sha256"]:
                            raise ValueError("v4 SHA-256 mismatch: " + row["path"])
            found[name] = {
                "archive": archive.name, "sha256": sha, "bytes": archive.stat().st_size,
                "format_version": 4, "model_kind": EXPECTED[name],
                "voice_count": len(manifest["engine"].get("voices", [])),
                "runtime_wheel_count": len(manifest["runtime"]["wheels"]),
                "rights_status": manifest["rights"].get("review_status", "declared"),
                "rights_license": manifest["rights"]["spdx"],
                "technical_package_verified": True,
                "public_release_authorized": False,
            }
        except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
            issues.append("v4 package failed verification: "
                          + archive.name + " (" + type(exc).__name__ + ")")
    missing = sorted(set(EXPECTED) - set(found))
    issues.extend("missing v4 model: " + name for name in missing)
    held = sorted(name for name, info in found.items()
                  if info["rights_status"] in ("hold", "review_required", "declared"))
    return {
        "format": "voxweavetts.v4-local-model-qa-audit",
        "version": 1, "public_release_authorized": False,
        "all_eight_present": not issues,
        "deep_assets_verified": bool(deep),
        "expected": len(EXPECTED), "found": len(found),
        "missing": missing, "issues": issues,
        "rights_pending": held, "packages": found,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packages", type=Path,
                        default=ROOT / "dist" / "ModelPackagesV4-QA")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--write-catalog", action="store_true")
    parser.add_argument("--require-cleared", action="store_true")
    args = parser.parse_args()
    report = audit(args.packages, deep=args.deep)
    if args.write_catalog and report["all_eight_present"]:
        location = args.packages / "CATALOG-v4-QA.json"
        location.write_text(json.dumps(report, ensure_ascii=False, indent=2)
                            + "\n", encoding="utf-8")
        print("CATALOG_V4_QA", location)
    print(json.dumps({k:v for k,v in report.items() if k!="packages"},
                     ensure_ascii=False, indent=2))
    if not report["all_eight_present"]:
        return 2
    if args.require_cleared:
        print("PUBLIC_RELEASE_BLOCKED: pack provenance/redistribution rights require independent approval")
        return 2
    print("EIGHT_V4_ARCHIVES_READY_FOR_PRIVATE_QA_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
