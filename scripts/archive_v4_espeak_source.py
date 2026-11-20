"""Archive eSpeak NG source and original build/licensing evidence for V4 QA.

The bundled espeakng-loader 0.2.4 Windows wheel contains a native eSpeak-NG
DLL; the upstream build workflow at a pinned loader commit clones eSpeak NG
tag 1.52.0. Both GPL source and the upstream build recipe are needed for
redistribution review. This script does not certify a reproducible binary
build or authorize a public redistribution by itself.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dist" / "ModelPackagesV4-NoticeQA"
OUT = ROOT / "cache" / "v4-rights-evidence" / "runtime-sources" / "espeak-ng-1.52.0"
MODELS = ("kokoro-multilingual-int8", "wayu-paxa-edge-nc")
LOADER_COMMIT = "0ddc87adf77e5850d7eeb542ac8a87d421b64daa"
ESPEAK_TAG = "1.52.0"
SOURCE_URL = (
    "https://codeload.github.com/espeak-ng/espeak-ng/tar.gz/refs/tags/"
    + ESPEAK_TAG
)
LOADER_BASE = (
    "https://cdn.jsdelivr.net/gh/thewh1teagle/espeakng-loader@"
    + LOADER_COMMIT + "/"
)
LOADER_DOCS = ("LICENSE", "build.sh", ".github/workflows/build.yml")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bundled_binary_index(archive_dir: Path = SOURCE) -> dict:
    binaries = {}
    for package_id in MODELS:
        found = list(archive_dir.glob(
            f"VoxWeaveTTS-{package_id}-*-LEGAL-QA-format-v4.vwmodel"
        ))
        if len(found) != 1:
            raise ValueError("missing or duplicated v4 QA model: " + package_id)
        with zipfile.ZipFile(found[0]) as outer:
            manifest = json.loads(outer.read("manifest.json"))
            wheel_path = next(p for p in manifest["runtime"]["wheels"]
                              if Path(p).name.startswith("espeakng_loader-"))
            wheel_bytes = outer.read(wheel_path)
            pinned = next(p for p in manifest["files"] if p["path"] == wheel_path)
            if len(wheel_bytes) != pinned["size"] or sha(wheel_bytes) != pinned["sha256"]:
                raise ValueError("eSpeak loader wheel failed SHA verification")
            with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as inner:
                dll = inner.read("espeakng_loader/espeak-ng.dll")
                binaries[package_id] = {
                    "wheel_sha256": pinned["sha256"],
                    "dll_sha256": sha(dll),
                    "dll_size": len(dll),
                    "dll_member": "espeakng_loader/espeak-ng.dll",
                }
    if len({x["dll_sha256"] for x in binaries.values()}) != 1:
        raise ValueError("bundled eSpeak binaries differ across V4 model packs")
    return binaries


def get_text(url: str, *, max_bytes: int = 200_000) -> bytes:
    with urlopen(Request(url, headers={
        "User-Agent": "VoxWeaveTTS-v4-source-notice-audit",
    }), timeout=20) as response:
        data = response.read(max_bytes + 1)
    if not data or len(data) > max_bytes or b"\x00" in data:
        raise ValueError("unexpected legal/build text size or encoding")
    return data


def get_tarball(url: str, target: Path, *, max_bytes: int = 80_000_000) -> dict:
    if target.exists():
        data = target.read_bytes()
    else:
        with urlopen(Request(url, headers={
            "User-Agent": "VoxWeaveTTS-v4-source-notice-audit",
        }), timeout=45) as response:
            chunks = []
            length = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                length += len(chunk)
                if length > max_bytes:
                    raise ValueError("upstream source exceeds size bound")
                chunks.append(chunk)
        data = b"".join(chunks)
        target.write_bytes(data)
    if not data or len(data) > max_bytes:
        raise ValueError("invalid upstream source archive size")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members = archive.getmembers()
        if not members or any(
            m.name.startswith("/") or ".." in Path(m.name).parts for m in members
        ):
            raise ValueError("untrusted path in upstream source")
        copying = next((m for m in members
                        if m.name.endswith("/COPYING") and m.isfile()), None)
        if copying is None:
            raise ValueError("GPL COPYING missing from source tarball")
        copyright_text = archive.extractfile(copying).read()
        if b"GNU GENERAL PUBLIC LICENSE" not in copyright_text:
            raise ValueError("unexpected upstream GPL license")
    return {
        "url": url,
        "sha256": sha(data),
        "bytes": len(data),
        "local_copy": target.relative_to(ROOT).as_posix(),
        "license_inside_source_tar": copying.name,
        "files_in_source_tar": len(members),
    }


def collect(archive_dir: Path = SOURCE, out_dir: Path = OUT) -> dict:
    binaries = bundled_binary_index(archive_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source = get_tarball(SOURCE_URL, out_dir / "espeak-ng-1.52.0-source.tar.gz")
    loader_documents = {}
    for filename in LOADER_DOCS:
        original_url = LOADER_BASE + filename
        body = get_text(original_url)
        target = out_dir / filename.replace("/", "__")
        if target.exists() and target.read_bytes() != body:
            raise ValueError("pinned loader source text changed: " + filename)
        target.write_bytes(body)
        loader_documents[filename] = {
            "url": original_url,
            "sha256": sha(body),
            "bytes": len(body),
            "local_copy": target.relative_to(ROOT).as_posix(),
            "upstream_commit": LOADER_COMMIT,
        }
    workflow = (out_dir / ".github__workflows__build.yml").read_text("utf-8")
    if "git clone --single-branch --depth 1 -b 1.52.0" not in workflow:
        raise ValueError("loader build workflow does not reference expected eSpeak tag")
    if not (out_dir / "LICENSE").read_bytes().lstrip().startswith(b"MIT License"):
        raise ValueError("loader source MIT license not found")
    notice = {
        "schema": "voxweavetts.v4-espeak-native-source-evidence",
        "version": 1,
        "espeakng_loader_version": "0.2.4",
        "espeak_ng_version_from_build_workflow": ESPEAK_TAG,
        "native_binaries": binaries,
        "espeak_ng_upstream_source_tarball": source,
        "loader_build_documentation": loader_documents,
        "note": (
            "GPLv3+ source and original build scripts collected. A matching "
            "upstream tag does not prove the exact binary is reproducible; "
            "complete corresponding source and redistributor obligations "
            "need further review. Wheel license metadata is also missing."
        ),
        "public_release_authorized": False,
    }
    (out_dir / "INDEX.json").write_text(
        json.dumps(notice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return notice


if __name__ == "__main__":
    result = collect()
    print(json.dumps({
        "models": len(result["native_binaries"]),
        "dll_sha256": next(iter(result["native_binaries"].values()))["dll_sha256"],
        "source_tarball_sha256": result["espeak_ng_upstream_source_tarball"]["sha256"],
        "source_tarball_bytes": result["espeak_ng_upstream_source_tarball"]["bytes"],
        "loader_original_documents": list(result["loader_build_documentation"]),
        "public_release_authorized": False,
    }, indent=2), flush=True)
