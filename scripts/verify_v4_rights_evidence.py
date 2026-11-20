"""Verify publisher-authored license evidence copies and optionally bundle as ZIP.

The public committed index records exact source revision/URL and SHA-256.
Full copyrighted publisher documents remain in the ignored local cache.
No network calls, no model execution, no license grants.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_INDEX = ROOT / "docs" / "v4_upstream_evidence_index.json"
EVIDENCE = ROOT / "cache" / "v4-rights-evidence"


def checksum(path: Path) -> str:
    with path.open("rb") as inp:
        return hashlib.file_digest(inp, "sha256").hexdigest()


def verify(public_index: Path = PUBLIC_INDEX, root: Path = ROOT,
           *, wheels: bool = True) -> dict:
    root = root.resolve()
    data = json.loads(public_index.read_text(encoding="utf-8"))
    if (data.get("schema") != "voxweavetts.v4-upstream-rights-evidence"
        or data.get("all_models_public_redistribution_cleared") is not False):
        raise ValueError("invalid or potentially unsafe rights-evidence index")
    if data.get("source_errors"):
        raise ValueError("upstream source retrieval failures are present")
    evidence_root = root / "cache" / "v4-rights-evidence"
    checked = []
    for record in data["upstream_documents"]:
        if "sha256" not in record:
            raise ValueError("missing original publisher document: "+str(record))
        relative = Path(record["local_copy"])
        if (not relative.as_posix().startswith("cache/v4-rights-evidence/upstream/")
            or ".." in relative.parts or relative.is_absolute()):
            raise ValueError("invalid original-document path")
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(evidence_root.resolve()):
            raise ValueError("rights evidence escaped local QA cache")
        if (not path.is_file()
            or path.stat().st_size != record["size_bytes"]
            or checksum(path) != record["sha256"]):
            raise ValueError("source document has changed or is missing: "
                             +record["local_copy"])
        checked.append(path)
    wheel_docs = 0
    wheel_records = 0
    if wheels:
        wheel_index = evidence_root / "wheel-index.json"
        wheel_data = json.loads(wheel_index.read_text("utf-8"))
        for wheel in wheel_data["unique_wheel_evidence"].values():
            if not len(wheel["wheel_sha256"]) == 64:
                raise ValueError("wheel provenance SHA missing")
            wheel_records += 1
            for record in wheel["files"]:
                relative = Path(record["local_copy"])
                if (not relative.as_posix().startswith("cache/v4-rights-evidence/wheel-docs/")
                    or ".." in relative.parts or relative.is_absolute()):
                    raise ValueError("invalid Wheel license evidence path")
                file = root / relative
                if (file.is_symlink() or not file.resolve().is_relative_to(evidence_root.resolve())
                    or not file.is_file()
                    or file.stat().st_size != record["size_bytes"]
                    or checksum(file) != record["sha256"]):
                    raise ValueError("wheel license/metadata changed or missing: "
                                     +record["local_copy"])
                wheel_docs += 1
                checked.append(file)
    return {
        "format": "voxweavetts.v4-rights-evidence-verified",
        "publisher_source_count": len(data["source_repositories"]),
        "publisher_documents_verified": len(data["upstream_documents"]),
        "unique_wheels": wheel_records,
        "wheel_documents_verified": wheel_docs,
        "files": checked,
        "public_release_authorized": False,
    }


def bundle(report: dict, *, root: Path = ROOT) -> dict:
    base = root / "cache" / "v4-rights-evidence"
    output = base / "VoxWeaveTTS-v4-upstream-rights-evidence.zip"
    if output.is_file():
        raise ValueError("original rights archive already exists; refusing overwrite")
    inputs = [
        root / "docs" / "v4_upstream_evidence_index.json",
        base / "INDEX.json",
        base / "wheel-index.json",
    ] + report["files"]
    if len(set(inputs)) != len(inputs):
        raise ValueError("duplicate copyright evidence in archive")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as z:
        for path in sorted(inputs):
            # ZIP path refers to project-relative evidence layout.
            z.write(path, arcname=path.relative_to(root).as_posix())
    with zipfile.ZipFile(output) as z:
        bad = z.testzip()
        if bad:
            raise ValueError("license-evidence ZIP failed CRC verification")
    return {
        "archive": str(output),
        "bytes": output.stat().st_size,
        "sha256": checksum(output),
        "documents": len(report["files"]),
        "public_release_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", action="store_true")
    parser.add_argument("--skip-wheel-docs", action="store_true")
    args = parser.parse_args()
    summary = verify(wheels=not args.skip_wheel_docs)
    summary.pop("files")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if args.bundle:
        # Reread the verified local copies to build the ZIP (no network).
        archive = bundle(verify(wheels=not args.skip_wheel_docs))
        print("ARCHIVED_UPSTREAM_RIGHTS_EVIDENCE",
              json.dumps(archive,ensure_ascii=False),flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
