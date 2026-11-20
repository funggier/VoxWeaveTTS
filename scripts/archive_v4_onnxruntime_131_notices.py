"""SHA-pin original ONNX Runtime 1.31.1 notices for four offline v4 model packs.

This is source/notice evidence, not redistribution clearance. The exact wheel
and DLL bytes are obtained from SHA-verified local QA packages. Microsoft
upstream texts are fetched from the v1.31.1 tag via jsDelivr; tag immutability
and end-to-end dependency clearance are not claimed.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "dist" / "ModelPackagesV4-NoticeQA"
OUT = ROOT / "cache" / "v4-rights-evidence" / "runtime-sources" / "onnxruntime-1.31.1"
MODELS = (
    "makham-paradee", "fastthaig2p-thai-som",
    "kokoro-multilingual-int8", "vachana-thai-four-voices",
)
VERSION = "1.31.1"
BASE = "https://cdn.jsdelivr.net/gh/microsoft/onnxruntime@v1.31.1/"
DOCUMENTS = ("LICENSE", "ThirdPartyNotices.txt", "VERSION_NUMBER")
WHEEL_PREFIX = "onnxruntime-1.31.1-"
DLL_PATH = "onnxruntime/capi/onnxruntime.dll"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(archive_dir: Path = QA) -> dict:
    result = {}
    for model in MODELS:
        found = list(archive_dir.glob(
            f"VoxWeaveTTS-{model}-*-LEGAL-QA-format-v4.vwmodel"
        ))
        if len(found) != 1:
            raise ValueError("expected precisely one local QA archive: " + model)
        with zipfile.ZipFile(found[0]) as outer:
            manifest = json.loads(outer.read("manifest.json"))
            wheel_path = next(
                n for n in manifest["runtime"]["wheels"]
                if Path(n).name.startswith(WHEEL_PREFIX)
            )
            expected = next(x for x in manifest["files"] if x["path"] == wheel_path)
            wheel_bytes = outer.read(wheel_path)
            if (sha(wheel_bytes) != expected["sha256"]
                or len(wheel_bytes) != expected["size"]):
                raise ValueError("ONNX Runtime wheel bytes differ from manifest")
            with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as inner:
                dll = inner.read(DLL_PATH)
                native_entries = []
                for name in (
                    DLL_PATH,
                    "onnxruntime/capi/onnxruntime_providers_shared.dll",
                    "onnxruntime/capi/onnxruntime_pybind11_state.pyd",
                ):
                    payload = inner.read(name)
                    native_entries.append({
                        "path": name, "size": len(payload), "sha256": sha(payload),
                    })
                result[model] = {
                    "wheel_path": wheel_path,
                    "wheel_sha256": expected["sha256"],
                    "dll_sha256": sha(dll),
                    "native_binaries": native_entries,
                }
    if len({x["wheel_sha256"] for x in result.values()}) != 1:
        raise ValueError("ONNX Runtime wheel differs across four QA models")
    if len({x["dll_sha256"] for x in result.values()}) != 1:
        raise ValueError("ONNX Runtime DLL differs across four QA models")
    return result


def download_text(url: str, maximum: int = 650_000) -> bytes:
    request = Request(url, headers={
        "User-Agent": "VoxWeaveTTS-v4-technical-notice-audit",
    })
    with urlopen(request, timeout=20) as response:
        content = response.read(maximum + 1)
    if not content or len(content) > maximum or b"\0" in content:
        raise ValueError("unexpected ONNX Runtime notice size/type")
    return content


def collect(archive_dir: Path = QA, out_dir: Path = OUT) -> dict:
    models = inventory(archive_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    docs = {}
    for name in DOCUMENTS:
        content = download_text(BASE + name)
        if name == "LICENSE" and not content.lstrip().startswith(b"MIT License"):
            raise ValueError("unexpected Microsoft source LICENSE")
        if (name == "ThirdPartyNotices.txt"
            and b"THIRD PARTY SOFTWARE NOTICES" not in content[:300]):
            raise ValueError("unexpected Microsoft third-party notice format")
        if name == "VERSION_NUMBER" and content.strip() != VERSION.encode():
            raise ValueError("source tag version does not match native package")
        target = out_dir / name
        if target.is_file() and target.read_bytes() != content:
            raise ValueError("previous original notice bytes unexpectedly changed")
        target.write_bytes(content)
        docs[name] = {
            "source_url": BASE + name,
            "sha256": sha(content),
            "bytes": len(content),
            "local_copy": target.relative_to(ROOT).as_posix(),
            "source_tag": "v" + VERSION,
            "source_tag_resolved_to_immutable_commit": False,
        }
    index = {
        "schema": "voxweavetts.v4-onnxruntime-131-original-notices",
        "version": 1,
        "component": "Microsoft ONNX Runtime",
        "component_version": VERSION,
        "dll_windows_fileversion_observed": "1.31.1.20261023.3.6af1a93",
        "dll_version_observation": "Windows VersionInfo on unpacked identical DLL",
        "bundled_packages": models,
        "upstream_documents": docs,
        "public_release_authorized": False,
        "note": (
            "MIT/ThirdPartyNotices are copied verbatim from the matching source "
            "tag, separately from voice model licenses. This is technical QA "
            "and does not establish all transitive native rights."
        ),
    }
    (out_dir / "INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return index


if __name__ == "__main__":
    result = collect()
    print(json.dumps({
        "packages_verified": len(result["bundled_packages"]),
        "unique_onnxruntime_wheel_sha256": next(iter(
            result["bundled_packages"].values()))["wheel_sha256"],
        "unique_native_dll_sha256": next(iter(
            result["bundled_packages"].values()))["dll_sha256"],
        "upstream_documents": {
            name: item["sha256"]
            for name, item in result["upstream_documents"].items()
        },
        "public_release_authorized": False,
    }, indent=2))
