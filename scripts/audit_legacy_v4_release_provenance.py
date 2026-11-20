"""Read-only comparison of previously published v2/v3 packages and v4 QA.

Uses SHA-256 file inventory already embedded in each .vwmodel manifest.
Also verifies the precise *whole-archive* SHA and byte length against the
previously published GitHub Release. This establishes payload continuity,
not copyright clearance or permission to redistribute dependencies.

No model execution, no installation, and no release upload.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SOURCES = [
    (2, "ModelPackagesV2", "v0.10.3"),
    (3, "ModelPackagesV3", "v0.11.0"),
    (4, "ModelPackagesV4-QA", None),
]
MODEL_EXT = {".onnx", ".pt", ".pth", ".safetensors", ".bin", ".npy", ".gguf"}


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4_194_304), b""):
            h.update(chunk)
    return h.hexdigest()


def release_assets(tag: str) -> dict:
    output = subprocess.run(
        ["gh", "release", "view", tag,
         "--repo", "funggier/VoxWeaveTTS", "--json", "assets"],
        capture_output=True, text=True, check=True, timeout=40
    )
    return {a["name"]: {
        "size": a["size"],
        "sha256": str(a.get("digest", "")).removeprefix("sha256:")
    } for a in json.loads(output.stdout)["assets"]}


def inspect(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        m = json.loads(archive.read("manifest.json"))
    original = {f["path"]: {"sha256": f["sha256"], "size": f["size"]}
                for f in m["files"]}
    if m["format_version"] == 4:
        normalized = {name[7:]: data for name, data in original.items()
                      if name.startswith("assets/")}
    else:
        normalized = {name: data for name, data in original.items()
                      if not name.startswith("runtime/")}
    assets = {key: item for key, item in normalized.items()
              if not (key.startswith("legal/") or
                      key.upper().startswith(("LICENSE", "NOTICE")) or
                      "attribution" in key.lower() or
                      key in ("manifest-assets.json",))}
    legal = {key: item for key, item in normalized.items()
             if key.startswith("legal/") or
             key.upper().startswith(("LICENSE", "NOTICE")) or
             "attribution" in key.lower()}
    weights = {key: item for key, item in assets.items()
               if Path(key).suffix.lower() in MODEL_EXT}
    wheels = {Path(key).name: item for key, item in original.items()
              if key.startswith("runtime/wheels/") and key.endswith(".whl")}
    return {
        "package_id": m["package"]["id"],
        "kind": m["package"]["kind"],
        "format_version": m["format_version"],
        "archive": path.name,
        "archive_bytes": path.stat().st_size,
        "manifest_rights": m.get("rights", {}),
        "assets": assets, "weights": weights, "wheels": wheels, "legal": legal,
    }


def compare(legacy: dict | None, current: dict) -> dict:
    if legacy is None:
        return {"published_prior_format_exists": False}
    result = {"published_prior_format_exists": True}
    for category in ("weights", "assets", "legal", "wheels"):
        a, b = legacy[category], current[category]
        unchanged = sorted(k for k in a.keys() & b.keys()
                           if a[k] == b[k])
        changed = sorted(k for k in a.keys() & b.keys()
                         if a[k] != b[k])
        result[category] = {
            "old_count": len(a),
            "v4_count": len(b),
            "byte_identical_sha256": unchanged,
            "changed_sha256": changed,
            "v4_added": sorted(b.keys() - a.keys()),
            "legacy_removed": sorted(a.keys() - b.keys()),
        }
    result["all_legacy_weight_files_identical"] = (
        not result["weights"]["changed_sha256"]
        and not result["weights"]["legacy_removed"]
        and len(result["weights"]["byte_identical_sha256"]) > 0)
    return result


def run() -> dict:
    published = {tag: release_assets(tag) for _, _, tag in SOURCES if tag}
    by_format: dict[int, dict] = {}
    attest = []
    for fmt, directory, tag in SOURCES:
        indexed = {}
        for archive in sorted((DIST / directory).glob("*.vwmodel")):
            item = inspect(archive)
            if item["format_version"] != fmt:
                raise ValueError("unexpected package format: "+str(archive))
            if item["package_id"] in indexed:
                raise ValueError("duplicate model: "+item["package_id"])
            if tag:
                remote = published[tag].get(item["archive"])
                if remote is None:
                    raise ValueError("old local file not an exact release asset: "+item["archive"])
                actual = file_hash(archive)
                if actual != remote["sha256"] or item["archive_bytes"] != remote["size"]:
                    raise ValueError("prior release archive digest mismatch: "+item["archive"])
                attest.append({
                    "format": fmt, "tag": tag, "package_id": item["package_id"],
                    "name": item["archive"], "sha256": actual,
                    "size_bytes": item["archive_bytes"],
                    "published_asset_match": True,
                })
                print("VERIFIED_PUBLISHED",tag,item["package_id"],actual[:12],flush=True)
            indexed[item["package_id"]] = item
        by_format[fmt] = indexed
    results = {}
    for package_id, current in sorted(by_format[4].items()):
        earlier = {}
        for fmt in (2,3):
            earlier[f"v{fmt}"] = compare(by_format[fmt].get(package_id),current)
        results[package_id] = {
            "type": current["kind"],
            "v4_qa_file": current["archive"],
            "v4_weight_files": current["weights"],
            "v4_wheel_count": len(current["wheels"]),
            "v4_wheel_names": sorted(current["wheels"]),
            "v4_rights_claim": current["manifest_rights"],
            "prior_release_comparison": earlier,
            "previous_publication_not_licensing_clearance": True,
        }
    return {
        "schema": "voxweavetts.v2-v3-published-to-v4-provenance",
        "comparison_method": "file inventory SHA-256 and remote GitHub Release digest",
        "historical_releases": ["v0.10.3","v0.11.0"],
        "published_packages_verified": len(attest),
        "verified_previous_public_assets": attest,
        "v4_qa_packages": len(results),
        "models": results,
        "legal": {
            "historically_published_does_not_guarantee_redistribution_permission": True,
            "v4_worker_and_wheels_require_separate_rights": True,
            "public_release_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=DIST / "ModelPackagesV4-QA" /
                        "RELEASE-PROVENANCE-v2-v3-to-v4.json")
    args = parser.parse_args()
    report = run()
    output = args.output.resolve()
    safe = (DIST / "ModelPackagesV4-QA").resolve()
    if not output.is_relative_to(safe):
        raise ValueError("full QA provenance output must stay in ignored dist/ModelPackagesV4-QA")
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("REPORT",output,flush=True)
    for model, info in report["models"].items():
        p2 = info["prior_release_comparison"]["v2"]
        p3 = info["prior_release_comparison"]["v3"]
        print("RESULT",model,
              "v2_weights_identical",p2.get("all_legacy_weight_files_identical"),
              "v3_weights_identical",p3.get("all_legacy_weight_files_identical"),
              "v4_wheels",info["v4_wheel_count"],flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
