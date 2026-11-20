"""Add verbatim third-party Wheel license texts to a PRIVATE v4 QA package.

Preserves the original Worker, weights, configurations, model license and
runtime Wheel bytes. Uses original license/notice files extracted from those
exact SHA-verified Wheels. Maintains full SHA-256 index. *Does not* grant
distribution rights or publish a Release, including for unknown-license Wheels.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
EVIDENCE = ROOT / "cache" / "v4-rights-evidence"
OUT = ROOT / "dist" / "ModelPackagesV4-LegalQA"
DATA = ROOT / "dist" / "ModelPackagesV4-QA"
WHEEL_LICENSE_AUDIT = ROOT / "cache" / "v4-qa-candidates" / "rights-wheel-audit-20261120.json"
LEGAL_PREFIX = "assets/legal/runtime-docs/"


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(source: Path, output: Path) -> dict:
    from voxweavetts.universal_model_v4 import inspect_archive
    original = inspect_archive(source)
    if "UNRELEASED-QA" not in source.name:
        raise ValueError("legal QA preparation accepts only unpublished v4 QA archives")
    if output.is_file():
        raise FileExistsError("legal QA already exists; refusing overwrite")
    index = json.loads((EVIDENCE / "wheel-index.json").read_text("utf-8"))
    metadata = json.loads(WHEEL_LICENSE_AUDIT.read_text("utf-8"))
    wheel_map = {entry["wheel_sha256"]: entry for entry
                 in index["unique_wheel_evidence"].values()}
    audit_map = {x["sha256"]: x for x in metadata["wheel_details"]}
    pkg_name = original["package"]["id"]
    wheel_files = [r for r in original["files"]
                   if r["path"] in original["runtime"]["wheels"]]
    additional: dict[str, bytes] = {}
    records = []
    for wheel in wheel_files:
        digest = wheel["sha256"]
        if digest not in wheel_map or digest not in audit_map:
            raise ValueError("missing SHA-pinned rights evidence: " + wheel["path"])
        from_index = wheel_map[digest]
        docs = []
        serial = 0
        for doc in from_index["files"]:
            lower = doc["member_path"].lower()
            if lower.endswith("/metadata"):
                # The original METADATA remains unchanged INSIDE the wheel.
                continue
            if not any(t in lower.rsplit("/", 1)[-1]
                       for t in ("license", "licence", "notice", "copying", "copyright")):
                continue
            expected = ROOT / doc["local_copy"]
            if (not expected.is_file()
                or not expected.resolve().is_relative_to(EVIDENCE.resolve())):
                raise ValueError("missing original wheel-license evidence")
            data = expected.read_bytes()
            if hash_bytes(data) != doc["sha256"]:
                raise ValueError("upstream license evidence altered")
            member = f"{LEGAL_PREFIX}{digest[:12]}-{serial:03}.txt"
            if member in additional:
                raise ValueError("duplicate notice path")
            additional[member] = data
            docs.append({
                "wheel_member_path": doc["member_path"],
                "notice_package_path": member,
                "source_sha256": doc["sha256"],
            })
            serial += 1
        row = audit_map[digest]
        records.append({
            "wheel": wheel["path"], "wheel_sha256": digest,
            "license_expression": row["license_expression"],
            "license_field": row["license_field"],
            "license_classifiers": row["license_classifiers"],
            "license_flags": row["flags"],
            "original_license_files_copied": docs,
            "license_declaration_missing": (
                "missing-license-declaration" in row["flags"]),
        })

    if pkg_name in ("melo-chinese-onnx", "supertonic3-multilingual-int8"):
        # The split sherpa-onnx-core wheel does not contain Apache's LICENSE;
        # preserve the original upstream LICENSE from a pinned Git commit.
        source_index = json.loads((EVIDENCE / "INDEX.json").read_text("utf-8"))
        source_doc = next(
            (d for d in source_index["upstream_documents"]
             if d["repository"] == "k2-fsa/sherpa-onnx"
             and d["source_path"] == "LICENSE" and "sha256" in d), None)
        if source_doc is None:
            raise ValueError("pinned sherpa-onnx LICENSE evidence missing")
        data = (ROOT / source_doc["local_copy"]).read_bytes()
        if hash_bytes(data) != source_doc["sha256"]:
            raise ValueError("original pinned sherpa-onnx LICENSE changed")
        additional["assets/legal/sherpa-onnx-apache-2.0.txt"] = data
    # Attach verbatim pinned upstream licenses when the original Wheel
    # declares Apache but omits its license text.
    runtime_source = EVIDENCE / "runtime-sources" / "INDEX.json"
    for dep in ("flatbuffers", "sentencepiece"):
        if not any(Path(x["path"]).name.lower().startswith(dep + "-")
                   for x in wheel_files):
            continue
        row = json.loads(runtime_source.read_text("utf-8"))[dep]
        original_license = (ROOT / row["local_copy"]).read_bytes()
        if hash_bytes(original_license) != row["sha256"]:
            raise ValueError("original upstream license was altered: " + dep)
        additional[f"assets/legal/{dep}-source-license.txt"] = original_license
    notice = {
        "format": "voxweavetts.v4-original-license-evidence",
        "package_id": pkg_name,
        "weight_license_spdx_unmodified": original["rights"]["spdx"],
        "model_attribution_unmodified": original["rights"]["attribution"],
        "runtime_wheels": records,
        "notice": (
            "These are copies of licenses from the actual bundled Wheel files. "
            "A Wheel without a license declaration is not assumed to be "
            "relicensed or cleared. Preserve original upstream conditions. "
            "Commercial use is not required by the VoxWeaveTTS project."
        ),
        "historical_weight_hashes_identical_to_v2": bool(
            pkg_name in json.loads((ROOT / "docs" /
                "v4_weight_continuity_summary.json").read_text("utf-8"))["models"]
        ),
        "v4_legal_review_pending": True,
        "source_index": "docs/v4_upstream_evidence_index.json",
    }
    additional["assets/legal/WHEEL_RIGHTS_INDEX.json"] = (
        json.dumps(notice, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest = copy.deepcopy(original)
    manifest["files"].extend({
        "path": name, "size": len(data), "sha256": hash_bytes(data)
    } for name, data in sorted(additional.items()))
    manifest["files"].sort(key=lambda item: item["path"])
    if len(manifest["files"]) > 512:
        raise ValueError("v4 package member count exceeded")
    # Validate exact schema and all target paths before writing multi-GB output.
    from voxweavetts.universal_model_v4 import validate_manifest
    validate_manifest(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(source) as inp, zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED,
            compresslevel=6, allowZip64=True) as dest:
            dest.writestr("manifest.json",
                          json.dumps(manifest, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8"))
            for item in original["files"]:
                name = item["path"]
                h = hashlib.sha256()
                size = 0
                with inp.open(name) as a, dest.open(name, "w") as b:
                    for chunk in iter(lambda: a.read(1_048_576), b""):
                        h.update(chunk)
                        size += len(chunk)
                        b.write(chunk)
                if h.hexdigest() != item["sha256"] or size != item["size"]:
                    raise ValueError("old model or Wheel altered: "+name)
            for name, data in sorted(additional.items()):
                dest.writestr(name, data)
        repacked = inspect_archive(output)
        if repacked["files"] != manifest["files"]:
            raise ValueError("QA package manifest differs after rebuild")
        return {
            "id": pkg_name, "format": 4,
            "same_original_model_and_wheel_sha256": True,
            "unchanged_files": len(original["files"]),
            "extra_original_notice_files": len(additional),
            "wheel_count": len(wheel_files),
            "has_wheels_without_license_declarations": any(
                r["license_declaration_missing"] for r in records),
            "file": str(output), "bytes": output.stat().st_size,
            "public_release_authorized": False,
        }
    except BaseException:
        if output.exists():
            output.unlink()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, default=OUT,
                        help="separate QA-only destination (no overwrite)")
    args = parser.parse_args()
    for name in args.models:
        paths = list(DATA.glob(f"VoxWeaveTTS-{name}-*-UNRELEASED-QA-format-v4.vwmodel"))
        if len(paths) != 1:
            raise ValueError("expected exactly one original v4 QA package: "+name)
        dest = args.output_dir / paths[0].name.replace(
            "-UNRELEASED-QA-format-v4", "-LEGAL-QA-format-v4")
        print("LEGAL_QA",json.dumps(build(paths[0],dest),ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
