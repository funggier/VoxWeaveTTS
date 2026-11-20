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
        (x.startswith("assets/legal/") and x.endswith((".txt",".md",".json")))
        or x in {
            "assets/legal/source/espeak-ng-1.52.0-source.tar.gz",
            "assets/legal/source/phonemizer-3.6.0-source.tar.gz",
            "assets/legal/source/phonemizer-fork-3.3.2-source.tar.gz",
            "assets/legal/source/gensim-4.4.0-source.tar.gz",
            "assets/legal/source/num2words-0.5.6-source.tar.gz",
        }
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


def check(original_folder: Path, updated_folder: Path, *,
          models: list[str] | None = None,
          require_native_notices: bool = False,
          require_espeak_source: bool = False,
          require_onnxruntime_131: bool = False,
          require_copyleft_sources: bool = False) -> dict:
    from voxweavetts.provider_rights import KNOWN_V4_MODELS
    results_by_model = {}
    chosen = models if models is not None else list(KNOWN_V4_MODELS)
    if not chosen or len(chosen) != len(set(chosen)) or any(
        item not in KNOWN_V4_MODELS for item in chosen
    ):
        raise ValueError("unknown or duplicate requested v4 models")
    for package_id in chosen:
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
            if require_native_notices:
                if package_id not in (
                    "melo-chinese-onnx", "supertonic3-multilingual-int8"
                ):
                    raise ValueError("native notice gate only supports sherpa models")
                provenance = json.loads(zipfile_reader.read(
                    "assets/legal/onnxruntime-1.28.2-provenance.json"))
                if (provenance["component_version"] != "1.28.2"
                    or provenance["public_release_authorized"] is not False):
                    raise ValueError("unexpected ONNX Runtime provenance data")
                wheel = next(
                    p for p in m1["files"]
                    if p["path"].startswith("runtime/wheels/sherpa_onnx_core-")
                )
                if provenance["origin_wheel_sha256"] != wheel["sha256"]:
                    raise ValueError("source notice belongs to a different Wheel")
                import io
                with zipfile.ZipFile(io.BytesIO(
                    zipfile_reader.read(wheel["path"]))) as nested:
                    binary = nested.read("sherpa_onnx/lib/onnxruntime.dll")
                if hashlib.sha256(binary).hexdigest() != provenance["binary_dll_sha256"]:
                    raise ValueError("source notice belongs to another ONNX DLL")
                for details in provenance["upstream_licenses"].values():
                    notice = zipfile_reader.read(details["package_path"])
                    if hashlib.sha256(notice).hexdigest() != details["sha256"]:
                        raise ValueError("ONNX upstream notice bytes changed")
                results["onnxruntime_upstream_notices_verified"] = True
            if require_onnxruntime_131:
                if package_id not in (
                    "makham-paradee", "fastthaig2p-thai-som",
                    "kokoro-multilingual-int8", "vachana-thai-four-voices",
                ):
                    raise ValueError("no ONNX Runtime 1.31.1 wheel for this model")
                origin = json.loads(zipfile_reader.read(
                    "assets/legal/onnxruntime-1.31.1-provenance.json"))
                if (origin["component_version"] != "1.31.1"
                    or origin["public_release_authorized"] is not False):
                    raise ValueError("unexpected original ORT source reference")
                wheel = next(
                    r for r in m1["files"]
                    if r["path"].startswith("runtime/wheels/onnxruntime-1.31.1-")
                )
                if wheel["sha256"] != origin["wheel_sha256"]:
                    raise ValueError("original ORT notice does not belong to this wheel")
                import io
                with zipfile.ZipFile(io.BytesIO(
                    zipfile_reader.read(wheel["path"]))) as nested:
                    native = nested.read("onnxruntime/capi/onnxruntime.dll")
                    for record in origin["native_binaries"]:
                        payload = nested.read(record["path"])
                        if (hashlib.sha256(payload).hexdigest() != record["sha256"]
                            or len(payload) != record["size"]):
                            raise ValueError("modified ORT native component")
                if hashlib.sha256(native).hexdigest() != origin["dll_sha256"]:
                    raise ValueError("original ORT DLL SHA-256 differs")
                if set(origin["upstream_documents"]) != {
                    "LICENSE", "ThirdPartyNotices.txt", "VERSION_NUMBER"
                }:
                    raise ValueError("incomplete ORT upstream documents")
                for name, doc in origin["upstream_documents"].items():
                    content = zipfile_reader.read(doc["path"])
                    if hashlib.sha256(content).hexdigest() != doc["sha256"]:
                        raise ValueError("modified original ORT source notice")
                    if name == "VERSION_NUMBER" and content.strip() != b"1.31.1":
                        raise ValueError("incorrect ONNX Runtime source version")
                results["onnxruntime_131_notices_verified"] = True
            if require_espeak_source:
                if package_id not in (
                    "kokoro-multilingual-int8", "wayu-paxa-edge-nc"
                ):
                    raise ValueError("eSpeak source gate supports only G2P models")
                espeak = json.loads(zipfile_reader.read(
                    "assets/legal/espeak-ng-1.52.0-provenance.json"))
                if (espeak["eSpeak_ng_source_version"] != "1.52.0"
                    or espeak["public_release_authorized"] is not False
                    or espeak["source_to_dll_exact_build_reproducibility_verified"] is not False):
                    raise ValueError("unexpected eSpeak native provenance")
                wheel = next(
                    p for p in m1["files"]
                    if p["path"].startswith("runtime/wheels/espeakng_loader-")
                )
                if espeak["origin_wheel_sha256"] != wheel["sha256"]:
                    raise ValueError("eSpeak source belongs to another Wheel")
                import io
                with zipfile.ZipFile(io.BytesIO(
                    zipfile_reader.read(wheel["path"]))) as nested:
                    dll = nested.read("espeakng_loader/espeak-ng.dll")
                if hashlib.sha256(dll).hexdigest() != espeak["binary_dll_sha256"]:
                    raise ValueError("eSpeak native DLL does not match provenance")
                source = zipfile_reader.read(
                    espeak["espeak_ng_source_package_path"])
                if hashlib.sha256(source).hexdigest() != (
                    espeak["espeak_ng_gpl_source_archive_sha256"]
                ):
                    raise ValueError("embedded eSpeak GPL source bytes changed")
                import tarfile
                with tarfile.open(fileobj=io.BytesIO(source), mode="r:gz") as bundle:
                    copying = next((
                        item for item in bundle.getmembers()
                        if item.name.endswith("/COPYING") and item.isfile()
                    ), None)
                    if copying is None or b"GNU GENERAL PUBLIC LICENSE" not in (
                        bundle.extractfile(copying).read()
                    ):
                        raise ValueError("embedded GPL source archive lacks COPYING")
                for details in espeak["loader_build_documentation"].values():
                    content = zipfile_reader.read(details["package_path"])
                    if hashlib.sha256(content).hexdigest() != details["sha256"]:
                        raise ValueError("original eSpeak loader document changed")
                results["espeak_upstream_source_and_build_docs_verified"] = True
            if require_copyleft_sources:
                source_index = (
                    "assets/legal/copyleft-upstream-sources-index.json"
                )
                expected = {
                    "phonemizer": "3.6.0",
                    "phonemizer-fork": "3.3.2",
                    "gensim": "4.4.0",
                    "num2words": "0.5.6",
                }
                packages_needed = {}
                for pkg, version in expected.items():
                    for wheel in m1["files"]:
                        if wheel["path"].startswith(
                            f"runtime/wheels/{pkg.replace('-', '_')}-{version}-"
                        ):
                            packages_needed[pkg] = wheel
                if packages_needed:
                    report = json.loads(zipfile_reader.read(source_index))
                    if set(report["packages"]) != set(packages_needed):
                        raise ValueError("GPL/LGPL sources missing/unexpected")
                    if report["upstream_terms_still_apply"] is not True:
                        raise ValueError("upstream copyleft rights removed")
                    for pkg, wheel in packages_needed.items():
                        item = report["packages"][pkg]
                        source = zipfile_reader.read(item["source_path"])
                        if (item["wheel_sha256"] != wheel["sha256"]
                            or hashlib.sha256(source).hexdigest()
                            != item["source_sha256"]):
                            raise ValueError("GPL/LGPL source does not match Wheel")
                        import io
                        import tarfile
                        with tarfile.open(fileobj=io.BytesIO(source),
                                          mode="r:gz") as tf:
                            if not tf.getmembers():
                                raise ValueError("empty GPL/LGPL source archive")
                    results["copyleft_sources_verified"] = len(packages_needed)
                elif source_index in {f["path"] for f in m2["files"]}:
                    raise ValueError("unneeded GPL/LGPL source index")
            if package_id == "wayu-paxa-edge-nc":
                assert results["original_model_license"] == "CC-BY-NC-4.0"
        results_by_model[package_id] = results
    return {
        "schema": "voxweavetts.v4-legal-copy-manifest-audit",
        "packages_verified": len(results_by_model),
        "total_original_wheels_preserved": sum(m["original_wheel_count"]
                                               for m in results_by_model.values()),
        "total_new_legal_files": sum(m["added_license_document_count"]
                                     for m in results_by_model.values()),
        "original_licensing_restrictions_preserved": True,
        "technical_legal_evidence_complete": True,
        "native_notices_required": require_native_notices,
        "espeak_source_required": require_espeak_source,
        "onnxruntime_131_required": require_onnxruntime_131,
        "copyleft_sources_required": require_copyleft_sources,
        "public_release_authorized": False,
        "models": results_by_model,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, default=ORIGINAL)
    parser.add_argument("--repacked", type=Path, default=REPACKED)
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--require-native-notices", action="store_true")
    parser.add_argument("--require-espeak-source", action="store_true")
    parser.add_argument("--require-onnxruntime-131", action="store_true")
    parser.add_argument("--require-copyleft-sources", action="store_true")
    args = parser.parse_args()
    result = check(args.original, args.repacked, models=args.models,
                   require_native_notices=args.require_native_notices,
                   require_espeak_source=args.require_espeak_source,
                   require_onnxruntime_131=args.require_onnxruntime_131,
                   require_copyleft_sources=args.require_copyleft_sources)
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
