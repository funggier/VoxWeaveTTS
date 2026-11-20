"""Check that v4 license-enriched packages preserve all original model/runtime bytes.

The previous v4 QA models have identical weights to actual published V2.
This verifier confirms the new packages change only additional legal/notice
assets, do not change the original model License, attribution, Worker or Wheel
SHA-256, and retain the mandatory original restrictions.

This is technical/rights-evidence QA, not permission to release a model.
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

ORIGINAL = ROOT / "dist" / "ModelPackagesV4-QA"
REPACKED = ROOT / "dist" / "ModelPackagesV4-LegalQA"


def assess(original: dict, enriched: dict) -> dict:
    if original["package"] != enriched["package"]:
        raise ValueError("model identity or language changed")
    if original["engine"] != enriched["engine"]:
        raise ValueError("v4 worker protocol/voice changed")
    if original["runtime"] != enriched["runtime"]:
        raise ValueError("v4 offline runtime specification changed")
    if original["rights"] != enriched["rights"]:
        raise ValueError("original model license and attribution must not change")
    prior = {f["path"]: f for f in original["files"]}
    current = {f["path"]: f for f in enriched["files"]}
    for name, info in prior.items():
        if current.get(name) != info:
            raise ValueError("model/Worker/Wheel bytes changed: " + name)
    extra = sorted(set(current) - set(prior))
    if not extra or not all(
        x.startswith("assets/legal/") and x.endswith((".txt",".md",".json"))
        for x in extra
    ):
        raise ValueError("unexpected new executable or model asset")
    index = "assets/legal/WHEEL_RIGHTS_INDEX.json"
    if index not in extra:
        raise ValueError("v4 legal index missing")
    return {
        "package_id": original["package"]["id"],
        "original_model_license": original["rights"]["spdx"],
        "original_worker_and_all_runtime_wheels_unchanged": True,
        "original_model_weights_and_configs_unchanged": True,
        "license_data_additions_only": True,
        "added_license_document_count": len(extra),
        "original_wheel_count": len(original["runtime"]["wheels"]),
    }


def check(original_folder: Path, updated_folder: Path) -> dict:
    from voxweavetts.provider_rights import KNOWN_V4_MODELS
    models = {}
    for package_id in KNOWN_V4_MODELS:
        old = list(original_folder.glob(
            f"VoxWeaveTTS-{package_id}-*-UNRELEASED-QA-format-v4.vwmodel"))
        new = list(updated_folder.glob(
            f"VoxWeaveTTS-{package_id}-*-LEGAL-QA-format-v4.vwmodel"))
        if len(old) != 1 or len(new) != 1:
            raise ValueError("missing/duplicate original or legal QA package: "+package_id)
        m1 = inspect_archive(old[0])
        m2 = inspect_archive(new[0])
        results = assess(m1,m2)
        with zipfile.ZipFile(new[0]) as zipfile_reader:
            evidence = json.loads(zipfile_reader.read("assets/legal/WHEEL_RIGHTS_INDEX.json"))
            if (evidence["package_id"] != package_id
                or evidence["weight_license_spdx_unmodified"] != m1["rights"]["spdx"]
                or len(evidence["runtime_wheels"]) != len(m1["runtime"]["wheels"])):
                raise ValueError("v4 wheel rights index does not match archive: "+package_id)
            # Extra notices are small; SHA-256 verify each original copy.
            old_names = {f["path"] for f in m1["files"]}
            for file in m2["files"]:
                if file["path"] not in old_names:
                    content = zipfile_reader.read(file["path"])
                    if (len(content) != file["size"] or
                        hashlib.sha256(content).hexdigest() != file["sha256"]):
                        raise ValueError("modified legal notice: " + file["path"])
            results["missing_wheel_license_declaration"] = [
                row["wheel"].split("/")[-1]
                for row in evidence["runtime_wheels"]
                if row["license_declaration_missing"]
            ]
            if package_id == "wayu-paxa-edge-nc":
                assert results["original_model_license"] == "CC-BY-NC-4.0"
        models[package_id] = results
    return {
        "schema": "voxweavetts.v4-legal-copy-manifest-audit",
        "packages_verified": len(models),
        "total_original_wheels_preserved": sum(m["original_wheel_count"]
                                               for m in models.values()),
        "total_new_legal_files": sum(m["added_license_document_count"]
                                     for m in models.values()),
        "original_licensing_restrictions_preserved": True,
        "technical_legal_evidence_complete": True,
        "public_release_authorized": False,
        "models": models,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, default=ORIGINAL)
    parser.add_argument("--repacked", type=Path, default=REPACKED)
    args = parser.parse_args()
    result = check(args.original, args.repacked)
    dest = args.repacked / "CATALOG-LegalQA-v4.json"
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "models"},
                     ensure_ascii=False,indent=2),flush=True)
    for item in result["models"].values():
        print("LEGAL_QA_PRESERVED",item["package_id"],item["original_model_license"],
              "wheel_missing_declared_license",len(item["missing_wheel_license_declaration"]),
              flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
