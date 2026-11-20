"""Convert the entire known v3 model *inventory* to standalone v4 QA packages.

This is a one-way, streaming migration: every model weight, license notice and
offline runtime wheel is copied from the original .vwmodel and checked against
its original SHA-256. Each v4 pack includes its own executable Worker Protocol
v1 implementation and therefore does not require a Core model-specific adapter.

The output is LOCAL QA ONLY, never an automatically publishable release.
These archives contain third-party models/wheels (some rights HOLD/NC) and
require separate redistribution review before a public release.

The original v3 archives are not modified or removed. Only the v4 examples are
retained as the basis for future package authors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import BinaryIO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from voxweavetts.universal_model_v4 import (
    FORMAT, VERSION, V4PackageError, inspect_archive as inspect_v4,
    validate_manifest as validate_v4,
)
from voxweavetts.universal_model_packages import inspect_archive as inspect_v3

RELEASED = ROOT / "dist" / "ModelPackagesV3"
CANDIDATES = ROOT / "cache" / "v3-unreleased-candidates"
OUTPUT = ROOT / "dist" / "ModelPackagesV4-QA"
TTS_WORKER = ROOT / "examples" / "v4-model-plugin" / "plugin" / "worker.py"
TRANSLATOR_WORKER = ROOT / "examples" / "v4-translation-plugin" / "plugin" / "worker.py"
SOURCES = {
    "makham-paradee": RELEASED / "VoxWeaveTTS-MakHam-Paradee-Thai-English-v1.0.0-format-v3.vwmodel",
    "fastthaig2p-thai-som": RELEASED / "VoxWeaveTTS-fastthaig2p-thai-som-0.3.0-format-v3.vwmodel",
    "melo-chinese-onnx": RELEASED / "VoxWeaveTTS-melo-chinese-onnx-1.0.0-format-v3.vwmodel",
    "supertonic3-multilingual-int8": RELEASED / "VoxWeaveTTS-supertonic3-multilingual-int8-1.0.0-format-v3.vwmodel",
    "m2m100-418m": RELEASED / "VoxWeaveTTS-m2m100-418m-1.0.0-format-v3.vwmodel",
    "kokoro-multilingual-int8": CANDIDATES / "kokoro-multilingual-int8-UNRELEASED-QA-scriptless-format-v3.vwmodel",
    "vachana-thai-four-voices": CANDIDATES / "vachana-thai-four-voices-UNRELEASED-QA-scriptless-format-v3.vwmodel",
    "wayu-paxa-edge-nc": CANDIDATES / "wayu-paxa-edge-nc-UNRELEASED-QA-offline-format-v3.vwmodel",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _asset_destination(path: str) -> str | None:
    if path.startswith("runtime/locks/") or path == "manifest-assets.json":
        return None
    if path.startswith("runtime/wheels/"):
        return path
    if path in ("LICENSE", "NOTICE"):
        return "assets/" + path + ".txt"
    return "assets/" + path


def _write_checked(z_out: zipfile.ZipFile, dest: str,
                   z_in: zipfile.ZipFile, source_name: str,
                   digest: str, size: int) -> None:
    sha = hashlib.sha256()
    actual = 0
    with z_in.open(source_name) as source, z_out.open(dest, "w", force_zip64=True) as output:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            actual += len(chunk)
            if actual > size:
                raise V4PackageError("v3 asset grew during conversion: " + source_name)
            sha.update(chunk)
            output.write(chunk)
    if actual != size or sha.hexdigest() != digest:
        raise V4PackageError("original v3 asset fails SHA-256 check: " + source_name)


def _manifest(source: zipfile.ZipFile, v3: dict, extra_wheels: list[dict],
              worker: bytes) -> tuple[dict, dict[str, tuple[zipfile.ZipFile | None, str, bytes | None, dict | None]]]:
    asset_index: dict[str, tuple[zipfile.ZipFile | None, str, bytes | None, dict | None]] = {}
    for row in v3["files"]:
        dest = _asset_destination(row["path"])
        if dest is not None:
            asset_index[dest] = (source, row["path"], None, row)
    for item in extra_wheels:
        row, z = item["row"], item["zip"]
        if row["path"] in asset_index:
            raise V4PackageError("duplicate v4 extra wheel")
        asset_index[row["path"]] = (z, row["path"], None, row)
    license_data = json.loads(source.read(v3["rights"]))
    rights_info = license_data["license"]
    if not isinstance(rights_info, dict) or rights_info.get("review_status") not in ("hold", "review_required"):
        raise V4PackageError("model rights require independent review")
    engine_type = v3["package"]["kind"]
    if engine_type == "tts":
        metadata = {
            "protocol": 1, "entrypoint": "plugin/worker.py",
            "language": v3["capabilities"]["language"],
            "sample_rate": v3["capabilities"]["sample_rate"],
            "voices": [
                {"id": v["id"], "label": v["label"]}
                for v in v3["capabilities"]["voices"]
            ],
        }
        adapter_data = json.dumps({
            "backend": v3["adapter"]["id"],
            "voices": [v["id"] for v in metadata["voices"]],
            "sample_rate": metadata["sample_rate"],
        }, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        asset_index["plugin/adapter.json"] = (None, "", adapter_data, None)
    else:
        metadata = {
            "protocol": 1, "entrypoint": "plugin/worker.py",
            "operation": "translate", "languages": v3["package"]["languages"],
        }
        adapter_data = json.dumps({
            "backend": v3["adapter"]["id"],
            "languages": metadata["languages"],
        }, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        asset_index["plugin/adapter.json"] = (None, "", adapter_data, None)
    asset_index["plugin/worker.py"] = (None, "", worker, None)
    wheelpaths = sorted(path for path in asset_index if path.startswith("runtime/wheels/"))
    index = []
    for name in sorted(asset_index, key=str.casefold):
        source_zip, original_name, data, row = asset_index[name]
        if row is None:
            assert data is not None
            index.append({"path": name, "size": len(data), "sha256": _sha(data)})
        else:
            index.append({"path": name, "size": row["size"], "sha256": row["sha256"]})
    manifest = validate_v4({
        "format": FORMAT, "format_version": VERSION,
        "package": {
            "id": v3["package"]["id"], "version": v3["package"]["version"],
            "title": v3["package"]["title"], "kind": engine_type,
            "languages": v3["package"]["languages"],
        },
        "engine": metadata,
        "runtime": {"python": "3.11", "platform": "windows-x64", "wheels": wheelpaths},
        "rights": {
            "spdx": rights_info["spdx"], "url": rights_info["url"],
            "attribution": rights_info["attribution"],
            "source": license_data["source"]["url"],
            "review_status": rights_info["review_status"],
        },
        "files": index,
    })
    return manifest, asset_index


def convert_one(model_id: str, *, output: Path = OUTPUT) -> dict:
    if model_id not in SOURCES:
        raise ValueError("unknown v4 model conversion")
    source_path = SOURCES[model_id]
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if (output.resolve() == RELEASED.resolve()
        or output.resolve() == CANDIDATES.resolve()):
        raise V4PackageError("never overwrite original v3 archives")
    v3 = inspect_v3(source_path)
    if v3["package"]["id"] != model_id:
        raise V4PackageError("original model identity mismatch")
    output.mkdir(parents=True, exist_ok=True)
    destination = output / (
        "VoxWeaveTTS-" + model_id + "-" + v3["package"]["version"]
        + "-UNRELEASED-QA-format-v4.vwmodel")
    if destination.exists() or destination.is_symlink():
        raise V4PackageError("v4 QA output already exists; not overwriting: " + destination.name)
    if v3["package"]["kind"] == "tts":
        worker = TTS_WORKER.read_bytes()
    else:
        worker = TRANSLATOR_WORKER.read_bytes()
    extra_wheels: list[dict] = []
    fast_zip = None
    if model_id == "makham-paradee":
        fast_path = SOURCES["fastthaig2p-thai-som"]
        fast_zip = zipfile.ZipFile(fast_path)
        fast_manifest = inspect_v3(fast_path)
        extra_wheels = [{"row": row, "zip": fast_zip} for row in fast_manifest["files"]
                        if row["path"].startswith("runtime/wheels/")]
        if len(extra_wheels) < 10:
            raise V4PackageError("MakHam v4 requires a fully bundled offline Python runtime")
    try:
        with zipfile.ZipFile(source_path) as original:
            manifest, asset_index = _manifest(original, v3, extra_wheels, worker)
            marker = json.dumps(
                manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            if len(marker) > 131_072:
                raise V4PackageError("v4 manifest exceeds bounded metadata size")
            try:
                with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED,
                                     compresslevel=5, allowZip64=True) as archive:
                    archive.writestr("manifest.json", marker)
                    for name, (source_zip, source_name, inline, row) in sorted(
                            asset_index.items(), key=lambda pair: pair[0].casefold()):
                        if inline is not None:
                            archive.writestr(name, inline)
                        else:
                            assert source_zip is not None and row is not None
                            _write_checked(archive, name, source_zip, source_name,
                                           row["sha256"], row["size"])
                found = inspect_v4(destination)
                if found != manifest:
                    raise V4PackageError("new v4 archive fails structural round-trip")
                with destination.open("rb") as src:
                    digest = hashlib.file_digest(src, "sha256").hexdigest()
                return {
                    "model": model_id, "source": source_path.name,
                    "output": str(destination), "bytes": destination.stat().st_size,
                    "sha256": digest, "kind": manifest["package"]["kind"],
                    "voice_count": len(manifest["engine"].get("voices", [])),
                    "wheel_count": len(manifest["runtime"]["wheels"]),
                    "rights": manifest["rights"]["review_status"],
                    "public_release_allowed": False,
                }
            except BaseException:
                destination.unlink(missing_ok=True)
                raise
    finally:
        if fast_zip is not None:
            fast_zip.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", nargs="*", choices=sorted(SOURCES),
                    default=list(SOURCES))
    ap.add_argument("--output", type=Path, default=OUTPUT)
    args = ap.parse_args()
    if not TRANSLATOR_WORKER.is_file():
        raise V4PackageError("v4 translation Worker has not been created")
    results = []
    for model in args.models:
        print("V4_CONVERT_START", model, flush=True)
        result = convert_one(model, output=args.output)
        print("V4_CONVERT_READY", json.dumps(result, ensure_ascii=False), flush=True)
        results.append(result)
    print("V4_CONVERT_QA_ONLY", len(results), "no public redistribution authorized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
