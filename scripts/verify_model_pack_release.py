"""Verify redistributable optional model packs against pinned upstream hashes.

Offline release gate: does not download anything, upload credentials or execute
untrusted code. Runs in the developer checkout with already downloaded source
model files and checks exact asset digests, legal notices and package integrity.

  python scripts/verify_model_pack_release.py --write-catalog
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
from voxweavetts.model_packages import validate_manifest  # noqa: E402

PACKS = (
    {
        "file": "VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel",
        "id": "vachana-thai-four-voices",
        "version": "1.0.0",
        "adapter": "vachana-onnx-v1",
        "license": "MIT",
        "source": "https://huggingface.co/VIZINTZOR/VachanaTTS",
        "pinned_revision": "6fa5f03a26f8ec0c0e0582e9e6812efa84d38688",
        "assets": {
            "voices/th_f_1.onnx": "e87f6d6f825680118cc412f6f9da944bdece5ebe772769a14b2d8359a07c5bf1",
            "voices/th_f_2.onnx": "9131b63ef9699e40f59b579be50cd32c688b86a73269394529248274883edb1c",
            "voices/th_m_1.onnx": "c63bedc664d8a2c525181360f4dfa624d2940b3636de6caff141353f72d984bd",
            "voices/th_m_2.onnx": "dbb7e73e093b5ba7b1bc0612c1a31a63e76874a1af3d0231bbf4ab68720cb837",
        },
        "notices": ("legal/license.txt", "legal/attribution.md"),
        "conditions": (
            "Upstream model card declares MIT for the model repository; "
            "retain publisher/permission notice. Training data and voice "
            "rights were not independently audited."
        ),
        "additional_training_license": None,
    },
    {
        "file": "VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel",
        "id": "fastthaig2p-thai-som",
        "version": "0.3.0",
        "adapter": "fastthaig2p-kokoro-v1",
        "license": "Apache-2.0",
        "source": "https://github.com/awslabs/FastThaiG2P/releases/tag/v0.3.0",
        "pinned_revision": "v0.3.0",
        "assets": {
            "config.json": "ea8e1a52dd433e27d953255d2bf340fc754ec62a60686d112136c4eee603709f",
            "kokoro_thai.onnx": "a41a5ea020919e47df03226aebe72a64833bc666dfd6eeca6744d8c248270038",
            "voices/thai_som.npy": "bdec2300889bd5db59c81a4f0e1604c78124abf6096d6e84d4db1bbeef122240",
        },
        "notices": ("legal/license.txt", "legal/notice.txt", "legal/attribution.md"),
        "conditions": (
            "FastThaiG2P repository is Apache-2.0 with upstream NOTICE; "
            "Thai Som training dataset declares CC BY 4.0 and must be "
            "attributed. Complete provenance/voice rights not independently audited."
        ),
        "additional_training_license": "CC-BY-4.0 (Som TTS dataset)",
    },
)


def sha256_stream(handle) -> str:
    digest = hashlib.sha256()
    while block := handle.read(1024 * 1024):
        digest.update(block)
    return digest.hexdigest()


def verify_one(package_spec: dict) -> dict:
    file = ROOT / "dist" / "ModelPackages" / package_spec["file"]
    if not file.is_file():
        raise ValueError(f"missing package: {file}")
    with zipfile.ZipFile(file) as zipped:
        names = zipped.namelist()
        if not names or names[0] != "manifest.json":
            raise ValueError("manifest must be the first member")
        manifest = validate_manifest(json.loads(zipped.read("manifest.json")))
        if (manifest["package_id"] != package_spec["id"]
            or manifest["version"] != package_spec["version"]
            or manifest["engine_adapter"] != package_spec["adapter"]
            or manifest["license"]["spdx"] != package_spec["license"]
            or manifest["source"]["revision"] != package_spec["pinned_revision"]
            or manifest["license"]["review_status"] != "review_required"):
            raise ValueError("package manifest identity/licensing changed")
        expected = {entry["path"]: entry for entry in manifest["files"]}
        if len(names) != len(expected) + 1 or set(names) != {"manifest.json", *expected}:
            raise ValueError("package member list does not match manifest")
        for name in [*package_spec["assets"], *package_spec["notices"]]:
            if name not in expected:
                raise ValueError("package lacks required source file or legal notice: " + name)
        for name, row in expected.items():
            with zipped.open(name) as handle:
                actual = sha256_stream(handle)
            if actual != row["sha256"]:
                raise ValueError("package bytes and manifest digest mismatch: " + name)
            if name in package_spec["assets"] and actual != package_spec["assets"][name]:
                raise ValueError("package model bytes differ from pinned upstream: " + name)
        with zipped.open("legal/attribution.md") as handle:
            notes = handle.read()
        if package_spec["source"].split("/")[2].encode() not in notes:
            raise ValueError("upstream attribution URL missing")
    with file.open("rb") as handle:
        package_digest = sha256_stream(handle)
    return {
        "package_id": package_spec["id"],
        "version": package_spec["version"],
        "file": file.name,
        "size_bytes": file.stat().st_size,
        "sha256": package_digest,
        "download_url": (
            "https://github.com/funggier/VoxWeaveTTS/releases/download/"
            "modelpacks-v0.4.2/" + file.name
        ),
        "engine_adapter": package_spec["adapter"],
        "voices": [x["id"] for x in manifest["voices"]],
        "upstream_source": package_spec["source"],
        "source_revision": package_spec["pinned_revision"],
        "upstream_declared_license": package_spec["license"],
        "training_license": package_spec["additional_training_license"],
        "conditions": package_spec["conditions"],
        "review_status": manifest["license"]["review_status"],
        "upstream_asset_sha256": package_spec["assets"],
        "embedded_notices": list(package_spec["notices"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-catalog", action="store_true")
    args = parser.parse_args()
    items = []
    for source in PACKS:
        result = verify_one(source)
        items.append(result)
        print(f"VERIFIED {result['file']} ({result['size_bytes']:,} bytes) "
              f"SHA256={result['sha256']}", flush=True)
    doc = {
        "schema_version": 1,
        "project": "VoxWeaveTTS",
        "release_tag": "modelpacks-v0.4.2",
        "note": (
            "Licenses are as declared at pinned upstream sources. "
            "VoxWeaveTTS has not independently certified all training data "
            "or voice rights. No warranty of commercial use or compatibility."
        ),
        "packages": items,
    }
    if args.write_catalog:
        output = ROOT / "model-packs" / "catalog.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        print("CATALOG_WRITTEN", output, flush=True)


if __name__ == "__main__":
    main()
