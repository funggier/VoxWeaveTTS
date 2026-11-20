"""Archive exact upstream notices for the ONNX Runtime DLL inside sherpa-onnx-core.

The DLL actually bundled in the Melo and Supertonic V4 QA archives has Windows
FileVersion 1.28.2 (inspected on the Windows QA machine). This script verifies
the two bundles contain identical SHA-pinned DLLs and archives the unmodified
Microsoft source LICENSE and ThirdPartyNotices from the matching v1.28.2 tag.

GitHub's Git API was unavailable during this review, so the documented tag
URLs are fetched via jsDelivr's GitHub-backed tag CDN. The SHA-256 and byte
length record the exact downloaded contents; a tag is *not* represented as a
verified immutable commit. This is evidence collection, not legal clearance.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

import requests

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "cache" / "v4-rights-evidence"
OUT = EVIDENCE / "runtime-sources" / "onnxruntime-1.28.2"
ARCHIVES = ROOT / "dist" / "ModelPackagesV4-NoticeQA"
MODELS = ("melo-chinese-onnx", "supertonic3-multilingual-int8")
VERSION = "1.28.2"
REF = "v" + VERSION
DOCUMENTS = ("LICENSE", "ThirdPartyNotices.txt")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def observe_bundled_dlls(archive_dir: Path = ARCHIVES) -> dict:
    found = {}
    for package_id in MODELS:
        matches = list(archive_dir.glob(
            f"VoxWeaveTTS-{package_id}-*-LEGAL-QA-format-v4.vwmodel"
        ))
        if len(matches) != 1:
            raise ValueError("expected precisely one QA package: " + package_id)
        with zipfile.ZipFile(matches[0]) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            wheel_path = next(
                w for w in manifest["runtime"]["wheels"]
                if Path(w).name.startswith("sherpa_onnx_core-")
            )
            wheel_data = archive.read(wheel_path)
            pinned = next(x for x in manifest["files"] if x["path"] == wheel_path)
            if sha(wheel_data) != pinned["sha256"] or len(wheel_data) != pinned["size"]:
                raise ValueError("modified sherpa-onnx-core wheel")
            with zipfile.ZipFile(io.BytesIO(wheel_data)) as wheel:
                actual_dll = wheel.read("sherpa_onnx/lib/onnxruntime.dll")
                duplicate_dll = wheel.read(
                    "sherpa_onnx_core-2.0.1.data/data/Scripts/onnxruntime.dll"
                )
                if actual_dll != duplicate_dll:
                    raise ValueError("sherpa-onnx-core contains differing ONNX DLL copies")
                found[package_id] = {
                    "wheel_path": wheel_path,
                    "wheel_sha256": pinned["sha256"],
                    "dll_path": "sherpa_onnx/lib/onnxruntime.dll",
                    "dll_duplicate_path": (
                        "sherpa_onnx_core-2.0.1.data/data/Scripts/onnxruntime.dll"
                    ),
                    "dll_bytes": len(actual_dll),
                    "dll_sha256": sha(actual_dll),
                }
    if len({x["dll_sha256"] for x in found.values()}) != 1:
        raise ValueError("Melo and Supertonic do not bundle the same ONNX DLL")
    return found


def collect(archive_dir: Path = ARCHIVES, out_dir: Path = OUT) -> dict:
    dlls = observe_bundled_dlls(archive_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    items = {}
    for filename in DOCUMENTS:
        url = (
            "https://cdn.jsdelivr.net/gh/microsoft/onnxruntime@"
            + REF + "/" + filename
        )
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content = response.content
        if not content or len(content) > 600_000 or b"\x00" in content:
            raise ValueError("unexpected source notice size/type: " + filename)
        if filename == "LICENSE" and not content.lstrip().startswith(b"MIT License"):
            raise ValueError("source document does not contain expected MIT license")
        if (filename == "ThirdPartyNotices.txt"
            and b"THIRD PARTY SOFTWARE NOTICES" not in content[:400]):
            raise ValueError("unexpected third-party notices format")
        dest = out_dir / filename
        if dest.exists() and dest.read_bytes() != content:
            raise ValueError("previous source notice bytes changed: " + filename)
        dest.write_bytes(content)
        items[filename] = {
            "source": url,
            "repository": "microsoft/onnxruntime",
            "source_ref": REF,
            "source_ref_is_verified_commit": False,
            "sha256": sha(content),
            "bytes": len(content),
            "local_copy": dest.relative_to(ROOT).as_posix(),
        }
    report = {
        "schema": "voxweavetts.v4-sherpa-native-notice-evidence",
        "version": 1,
        "onnxruntime_windows_dll_fileversion_observed": VERSION,
        "onnxruntime_version_observation_method": (
            "Windows FileVersionInfo on SHA-matched extracted DLL"
        ),
        "model_packages": dlls,
        "upstream_documents": items,
        "licensing_note": (
            "ONNX Runtime's MIT LICENSE and all of its upstream third-party "
            "notices are unmodified. This does not clear sherpa-onnx's other "
            "native linked components or authorize public model redistribution."
        ),
        "public_release_authorized": False,
    }
    (out_dir / "INDEX.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    evidence = collect()
    print(json.dumps({
        "bundled_models": len(evidence["model_packages"]),
        "embedded_onnxruntime_dll_sha256": next(iter(
            evidence["model_packages"].values()
        ))["dll_sha256"],
        "upstream_notices": {
            k: {"sha256": v["sha256"], "bytes": v["bytes"]}
            for k, v in evidence["upstream_documents"].items()
        },
        "public_release_authorized": False,
    }, indent=2), flush=True)
