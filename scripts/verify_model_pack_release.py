"""VoxWeaveTTS v3 offline package-integrity and rights-metadata release gate.

Validates a *curated* list of independent v3 files against pinned model
asset digests. This validates bytes and notices, NOT legal title or permission
to commercially redistribute third-party voices or training data.

Run: python scripts/verify_model_pack_release.py --write-catalog
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
from voxweavetts.universal_model_packages import inspect_archive  # noqa: E402

MODELS = {
    "makham-paradee": {
        "version": "1.0.0", "license": "Apache-2.0",
        "assets": {"paradee_thai_int8.onnx": "ad179a2c11b54b1185e84d9c0b759a57058588405620f12163084aaad250813d"},
        "notices": ["legal/license.txt", "legal/attribution.md"],
    },
    "fastthaig2p-thai-som": {
        "version": "0.3.0", "license": "Apache-2.0",
        "assets": {
            "kokoro_thai.onnx": "a41a5ea020919e47df03226aebe72a64833bc666dfd6eeca6744d8c248270038",
            "voices/thai_som.npy": "bdec2300889bd5db59c81a4f0e1604c78124abf6096d6e84d4db1bbeef122240",
        },
        "notices": ["legal/license.txt", "legal/notice.txt", "legal/attribution.md"],
    },
    "m2m100-418m": {
        "version": "1.0.0", "license": "MIT",
        "assets": {"model.safetensors": "c061a21eec15453944783ceb4a13a216477dd4765c98fac10811818adf994968"},
        "notices": ["LICENSE", "NOTICE", "attribution.md"],
    },
    "melo-chinese-onnx": {
        "version": "1.0.0", "license": "MIT",
        "assets": {"model.onnx": "bf30582eb1b012250a35b1a4a80e7dfbcf8485e7bb9de0d95efbbeef0e4ad86d"},
        "notices": ["legal/license.txt", "legal/attribution.md"],
    },
    "supertonic3-multilingual-int8": {
        "version": "1.0.0", "license": "OpenRAIL-M",
        "assets": {
            "duration_predictor.int8.onnx": "c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db",
            "text_encoder.int8.onnx": "c7befd5ea8c3119769e8a6c1486c4edc6a3bc8365c67621c881bbb774b9902ff",
            "vector_estimator.int8.onnx": "20cd86fa5c6effedfda0e7cffe5b0569ca401c440a0c3a1d72bf39286c0db3fd",
            "vocoder.int8.onnx": "e923d60f53f95eb1ce235f1dc33ec56d9c057823c96fa6f8acf98f32b0da6152",
        },
        "notices": ["legal/license.txt", "legal/conversion-license.txt", "legal/attribution.md"],
    },
}

def digest(stream) -> str:
    sha = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        sha.update(chunk)
    return sha.hexdigest()


def inspect_one(archive: Path) -> dict:
    manifest = inspect_archive(archive)
    package_id = manifest["package"]["id"]
    expected = MODELS.get(package_id)
    if expected is None:
        raise ValueError("unreviewed v3 model package: " + package_id)
    if manifest["package"]["version"] != expected["version"]:
        raise ValueError("unexpected model version: " + package_id)
    with zipfile.ZipFile(archive) as bundle:
        rights = json.loads(bundle.read(manifest["rights"]))
        license = rights["license"]
        if license["spdx"] != expected["license"]:
            raise ValueError("license metadata differs from reviewed source")
        if license["review_status"] != "review_required":
            raise ValueError("model rights must not be silently marked cleared")
        index = {row["path"]: row for row in manifest["files"]}
        if not set(expected["assets"]) <= set(index):
            raise ValueError("missing pinned native model weights: " + package_id)
        if not set(expected["notices"]) <= set(index):
            raise ValueError("missing model license/attribution/notice")
        for name, pinned in expected["assets"].items():
            if index[name]["sha256"] != pinned:
                raise ValueError("model weights differ from immutable source pin: " + name)
        for item in manifest["files"]:
            with bundle.open(item["path"]) as source:
                actual = digest(source)
            if actual != item["sha256"]:
                raise ValueError("archive SHA-256 mismatch: " + item["path"])
            pinned = expected["assets"].get(item["path"])
            if pinned is not None and actual != pinned:
                raise ValueError("model weights do not match source pin: " + item["path"])
        for name in expected["notices"]:
            with bundle.open(name) as stream:
                notice = stream.read(1024 * 1024)
            if not notice.strip() or len(notice) > 1024 * 1024:
                raise ValueError("missing/empty notice text: " + name)
        if manifest["runtime"]["source"] == "bundled-wheels":
            if not any(row["path"].endswith(".whl") for row in manifest["files"]):
                raise ValueError("v3 offline wheel bundle missing")
            if manifest["runtime"]["lockfile"] not in index:
                raise ValueError("v3 wheel lock missing")
    with archive.open("rb") as stream:
        sha = digest(stream)
    return {
        "package_id": package_id, "version": manifest["package"]["version"],
        "format_version": 3, "filename": archive.name,
        "sha256": sha, "size_bytes": archive.stat().st_size,
        "kind": manifest["package"]["kind"], "adapter": manifest["adapter"]["id"],
        "offline": True, "runtime_source": manifest["runtime"]["source"],
        "license_spdx": license["spdx"],
        "rights_status": "review_required",
        "source_url": rights["source"]["url"],
        "declared_provenance": rights["source"]["revision"],
        "commercial_redistribution_audited": False,
        "notices": expected["notices"],
    }


def verify_all(root: Path) -> list[dict]:
    root = Path(root)
    found: dict[str, dict] = {}
    files = sorted(root.glob("*.vwmodel"))
    if len(files) != len(MODELS):
        raise ValueError(f"expected {len(MODELS)} curated v3 archives, found {len(files)}")
    for path in files:
        result = inspect_one(path)
        if result["package_id"] in found:
            raise ValueError("duplicate model identity")
        found[result["package_id"]] = result
        print("V3_PACKAGE_INTEGRITY_OK", result["package_id"],
              result["license_spdx"], result["size_bytes"], flush=True)
    if set(found) != set(MODELS):
        raise ValueError("one or more curated v3 archives are missing")
    return [found[name] for name in sorted(found)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "dist" / "ModelPackagesV3")
    parser.add_argument("--write-catalog", action="store_true")
    parser.add_argument("--release-tag", default="v0.11.0")
    args = parser.parse_args(argv)
    results = verify_all(args.root)
    if args.write_catalog:
        catalog = {
            "format": "voxweavetts.v3-audited-archive-catalog",
            "release_tag": args.release_tag,
            "integrity_verified": True,
            "rights_warning": (
                "All model rights carry review_required: hash integrity, license metadata "
                "and upstream claims do not certify commercial/training/voice rights. "
                "Follow the terms within each optional package."
            ),
            "packages": results,
        }
        target = args.root / "CATALOG-v3.json"
        target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+"\n",
                          encoding="utf-8")
        print("V3_CATALOG", target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
