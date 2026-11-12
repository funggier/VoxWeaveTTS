"""Verified, data-only model package (.vwmodel) management.

A model package supplies *only* metadata and model weights for a preinstalled,
trusted Engine adapter. It cannot supply Python code, DLLs or new executables.
Do not confuse a package author's license claims with audited redistribution.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import threading
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "models" / "packages"
FORMAT = "voxweavetts.model-package"
FORMAT_VERSION = 1
PACKAGE_LIMIT = 2_000_000_000
MAX_FILES = 80
MAX_MANIFEST = 24_576
_CHUNK = 1024 * 1024
_PACKAGE_ID = re.compile(r"[a-z][a-z0-9_-]{1,47}\Z")
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
_VOICE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_EXTENSIONS = frozenset((".onnx", ".json", ".npy", ".txt", ".md"))
_ADAPTERS = frozenset(("vachana-onnx-v1", "fastthaig2p-kokoro-v1"))
_LOCK = threading.RLock()
_DIALOG_LOCK = threading.Lock()


class ModelPackageDialogUnavailable(RuntimeError):
    """Windows native file chooser could not be started."""


def install_model_package_dialog(*, choose_file=None) -> dict[str, Any] | None:
    """User chooses a local .vwmodel file; never accepts a web-supplied path."""
    if not _DIALOG_LOCK.acquire(blocking=False):
        raise ModelPackageDialogUnavailable("a model selection dialog is already open")
    try:
        selected = (choose_file or _native_model_picker)()
        if not selected:
            return None
        return install_model_package(selected)
    finally:
        _DIALOG_LOCK.release()


def _native_model_picker() -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
    except Exception as exc:
        raise ModelPackageDialogUnavailable("native model dialog unavailable") from exc
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        selected = filedialog.askopenfilename(
            parent=root, title="VoxWeaveTTS — Install Model Package",
            filetypes=[("VoxWeaveTTS Model Packages", "*.vwmodel")],
        )
        return selected or None
    except (OSError, RuntimeError, tk.TclError) as exc:
        raise ModelPackageDialogUnavailable("native model dialog unavailable") from exc
    finally:
        try:
            root.destroy()
        except (OSError, RuntimeError, tk.TclError):
            pass




class ModelPackageError(ValueError):
    """Rejected package or an invalid local package operation."""


def _relative_asset(raw: str) -> str:
    if not isinstance(raw, str) or not raw or len(raw) > 180 or "\\" in raw or ":" in raw:
        raise ModelPackageError("invalid model asset name")
    parts = PurePosixPath(raw).parts
    if (any(x in ("", ".", "..") or x.startswith(".") for x in parts)
        or raw.startswith("/") or str(PurePosixPath(raw)) != raw
        or any(ord(c) < 32 or ord(c) == 127 for c in raw)):
        raise ModelPackageError("invalid model asset path")
    if len(parts) > 4 or PurePosixPath(raw).suffix.lower() not in _EXTENSIONS:
        raise ModelPackageError("unsupported model asset path")
    return raw


def engine_id_for(manifest: dict[str, Any]) -> str:
    return "model-" + manifest["package_id"] + "-" + manifest["version"].replace(".", "_")


def validate_manifest(manifest: Any) -> dict[str, Any]:
    """Strict, stable data-only v1 schema. No arbitrary hooks or scripts."""
    if not isinstance(manifest, dict) or set(manifest) != {
        "format", "format_version", "package_id", "version", "title",
        "engine_adapter", "language", "sample_rate", "voices", "files",
        "license", "source", "dependencies",
    }:
        raise ModelPackageError("invalid model manifest schema")
    if manifest["format"] != FORMAT or type(manifest["format_version"]) is not int or manifest["format_version"] != FORMAT_VERSION:
        raise ModelPackageError("unsupported model manifest version")
    if not isinstance(manifest["package_id"], str) or not _PACKAGE_ID.fullmatch(manifest["package_id"]):
        raise ModelPackageError("invalid package identifier")
    if not isinstance(manifest["version"], str) or not _VERSION.fullmatch(manifest["version"]):
        raise ModelPackageError("invalid package version")
    if manifest["engine_adapter"] not in _ADAPTERS:
        raise ModelPackageError("this engine adapter is not supported")
    if not isinstance(manifest["title"], str) or not 1 <= len(manifest["title"]) <= 100:
        raise ModelPackageError("invalid model title")
    expected_rate = 22_050 if manifest["engine_adapter"] == "vachana-onnx-v1" else 24_000
    if manifest["language"] != "th" or type(manifest["sample_rate"]) is not int or manifest["sample_rate"] != expected_rate:
        raise ModelPackageError("unsupported sample rate/language for this adapter")
    lic = manifest["license"]
    if not isinstance(lic, dict) or set(lic) != {"spdx", "url", "attribution", "review_status"}:
        raise ModelPackageError("model license provenance is required")
    if (not isinstance(lic["spdx"], str) or not 1 <= len(lic["spdx"]) <= 80
        or not isinstance(lic["url"], str) or not lic["url"].startswith("https://") or len(lic["url"]) > 350
        or not isinstance(lic["attribution"], str) or not 2 <= len(lic["attribution"]) <= 1000
        or lic["review_status"] not in ("review_required", "hold", "cleared")):
        raise ModelPackageError("invalid model license provenance")
    source = manifest["source"]
    if not isinstance(source, dict) or set(source) != {"url", "revision"}:
        raise ModelPackageError("model source provenance is required")
    if (not isinstance(source["url"], str) or not source["url"].startswith("https://")
        or len(source["url"]) > 350 or not isinstance(source["revision"], str)
        or len(source["revision"]) > 150):
        raise ModelPackageError("invalid model source provenance")
    deps = manifest["dependencies"]
    if (not isinstance(deps, list) or len(deps) > 12
        or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9_.<>!=,-]{1,100}", x) for x in deps)):
        raise ModelPackageError("invalid dependency declaration")
    voices = manifest["voices"]
    if (not isinstance(voices, list) or not 1 <= len(voices) <= 32
        or (manifest["engine_adapter"] == "fastthaig2p-kokoro-v1" and len(voices) != 1)):
        raise ModelPackageError("model needs one or more voices")
    seen_voices: set[str] = set()
    seen_paths: set[str] = set()
    for voice in voices:
        if not isinstance(voice, dict) or set(voice) != {"id", "label", "asset"}:
            raise ModelPackageError("invalid voice schema")
        identifier = voice["id"]
        if not isinstance(identifier, str) or not _VOICE.fullmatch(identifier) or identifier in seen_voices:
            raise ModelPackageError("invalid or repeated voice")
        seen_voices.add(identifier)
        if not isinstance(voice["label"], str) or not 1 <= len(voice["label"]) <= 110:
            raise ModelPackageError("invalid voice label")
        asset = _relative_asset(voice["asset"])
        required_extension = ".onnx" if manifest["engine_adapter"] == "vachana-onnx-v1" else ".npy"
        if not asset.startswith("voices/") or not asset.endswith(required_extension) or asset.lower() in seen_paths:
            raise ModelPackageError("invalid or repeated voice weight file")
        seen_paths.add(asset.lower())
    files = manifest["files"]
    if not isinstance(files, list) or not 2 <= len(files) <= MAX_FILES:
        raise ModelPackageError("invalid model file index")
    file_index: dict[str, dict[str, Any]] = {}
    total = 0
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "size", "sha256"}:
            raise ModelPackageError("invalid asset descriptor")
        path = _relative_asset(entry["path"])
        if (path.lower() in file_index or type(entry["size"]) is not int
            or not 0 < entry["size"] <= PACKAGE_LIMIT
            or not isinstance(entry["sha256"], str) or not _SHA256.fullmatch(entry["sha256"])):
            raise ModelPackageError("invalid or repeated model file")
        file_index[path.lower()] = entry
        total += entry["size"]
    required_files = ("speaker_config.json",) if manifest["engine_adapter"] == "vachana-onnx-v1" else ("config.json", "kokoro_thai.onnx")
    if total > PACKAGE_LIMIT or not all(name in file_index for name in required_files):
        raise ModelPackageError("model exceeds size limit or has no speaker config")
    for voice in voices:
        if voice["asset"].lower() not in file_index or file_index[voice["asset"].lower()]["size"] < 1024:
            raise ModelPackageError("voice references missing or empty model data")
    if len(engine_id_for(manifest)) > 96:
        raise ModelPackageError("model identifier too long for the Engine registry")
    return manifest


def _installed_dir(manifest: dict[str, Any], base: Path) -> Path:
    validate_manifest(manifest)
    return base / manifest["package_id"] / manifest["version"]


def install_model_package(archive: str | Path, *, base: Path = PACKAGES_DIR) -> dict[str, Any]:
    """Stream-verify and atomically install an explicitly selected .vwmodel ZIP."""
    archive = Path(archive)
    if archive.suffix.lower() != ".vwmodel" or not archive.is_file():
        raise ModelPackageError("select a .vwmodel package")
    base = Path(base)
    with _LOCK, zipfile.ZipFile(archive, "r") as zip_file:
        members = zip_file.infolist()
        if not 2 <= len(members) <= MAX_FILES + 1 or len({m.filename.lower() for m in members}) != len(members):
            raise ModelPackageError("invalid package file list")
        if not members[0].filename == "manifest.json" or members[0].file_size > MAX_MANIFEST:
            raise ModelPackageError("package manifest must be the first ZIP member")
        try:
            manifest = validate_manifest(json.loads(zip_file.read(members[0]).decode("utf-8")))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ModelPackageError("invalid model package manifest") from exc
        expected = {"manifest.json"} | {item["path"] for item in manifest["files"]}
        if {m.filename for m in members} != expected:
            raise ModelPackageError("ZIP files do not match the manifest")
        file_info = {row["path"]: row for row in manifest["files"]}
        for member in members:
            if member.is_dir() or stat.S_IFMT(member.external_attr >> 16) == stat.S_IFLNK:
                raise ModelPackageError("model package cannot contain symlinks or folders")
            if member.filename == "manifest.json":
                continue
            _relative_asset(member.filename)
            if member.file_size != file_info[member.filename.lower()]["size"]:
                raise ModelPackageError("asset size does not match manifest")
            if member.compress_size == 0 or member.file_size > member.compress_size * 1500:
                raise ModelPackageError("asset compression ratio rejected")
        target = _installed_dir(manifest, base)
        if target.exists():
            raise ModelPackageError("this exact package version is already installed")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".install-", dir=target.parent))
        try:
            for row in manifest["files"]:
                out = staging.joinpath(*PurePosixPath(row["path"]).parts)
                out.parent.mkdir(parents=True, exist_ok=True)
                hasher = hashlib.sha256()
                consumed = 0
                with zip_file.open(row["path"]) as source, out.open("xb") as destination:
                    while chunk := source.read(_CHUNK):
                        consumed += len(chunk)
                        if consumed > row["size"]:
                            raise ModelPackageError("model asset exceeds declared size")
                        destination.write(chunk)
                        hasher.update(chunk)
                if consumed != row["size"] or hasher.hexdigest() != row["sha256"]:
                    raise ModelPackageError("model asset SHA-256 mismatch")
            (staging / "manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            if target.exists():
                raise ModelPackageError("package already exists")
            # This is a same-volume directory rename; the original installed
            # models/other versions remain untouched on any failure.
            staging.rename(target)
            return manifest
        finally:
            if staging.exists():
                shutil.rmtree(staging)


def installed_packages(*, base: Path = PACKAGES_DIR) -> list[tuple[dict[str, Any], Path]]:
    """Discover metadata only; never import/execute code from package folders."""
    results = []
    base = Path(base)
    if not base.is_dir():
        return results
    for file in sorted(base.glob("*/*/manifest.json")):
        if file.is_symlink() or file.parent.is_symlink() or file.parent.parent.is_symlink():
            continue
        try:
            if file.stat().st_size > MAX_MANIFEST:
                continue
            raw = validate_manifest(json.loads(file.read_text(encoding="utf-8")))
            if _installed_dir(raw, base) != file.parent:
                continue
            if not all((file.parent / row["path"]).is_file()
                       and (file.parent / row["path"]).stat().st_size == row["size"]
                       for row in raw["files"]):
                continue
            results.append((raw, file.parent))
        except (OSError, ValueError, TypeError):
            continue
    return results


def remove_model_package(package_id: str, version: str, *, base: Path = PACKAGES_DIR) -> bool:
    if not isinstance(package_id, str) or not _PACKAGE_ID.fullmatch(package_id):
        raise ModelPackageError("invalid package id")
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ModelPackageError("invalid version")
    with _LOCK:
        base = Path(base)
        target = base / package_id / version
        if not target.exists():
            return False
        if target.is_symlink():
            raise ModelPackageError("cannot remove symlinked model folder")
        manifest_file = target / "manifest.json"
        try:
            manifest = validate_manifest(json.loads(manifest_file.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            raise ModelPackageError("unrecognized package; refusing deletion") from exc
        if manifest["package_id"] != package_id or manifest["version"] != version:
            raise ModelPackageError("manifest/package identity mismatch")
        shutil.rmtree(target)
        if not any(target.parent.iterdir()):
            target.parent.rmdir()
        return True


def make_package(source: Path, manifest: dict[str, Any], output: Path) -> Path:
    """Developer-side pack creation; does not grant redistribution permission."""
    validate_manifest(manifest)
    source = Path(source)
    output = Path(output)
    if output.suffix.lower() != ".vwmodel":
        raise ModelPackageError("output must end with .vwmodel")
    for entry in manifest["files"]:
        path = source.joinpath(*PurePosixPath(entry["path"]).parts)
        if not path.is_file() or path.is_symlink() or path.stat().st_size != entry["size"]:
            raise ModelPackageError("missing or changed source asset")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != entry["sha256"]:
                raise ModelPackageError("source asset SHA-256 mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", allowZip64=True, compression=zipfile.ZIP_DEFLATED, compresslevel=3) as zipped:
        zipped.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for entry in manifest["files"]:
            zipped.write(source / entry["path"], entry["path"])
    return output



def create_vachana_manifest(source: Path) -> dict[str, Any]:
    """Produce metadata for locally downloaded Vachana voices.

    License declaration is informational: full upstream rights require review.
    """
    source = Path(source)
    names = ("th_f_1", "th_f_2", "th_m_1", "th_m_2")
    assets = ["speaker_config.json"] + ["voices/" + name + ".onnx" for name in names]
    files = []
    for name in assets:
        path = source.joinpath(*PurePosixPath(name).parts)
        if not path.is_file():
            raise ModelPackageError("missing Vachana model file")
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        files.append({"path": name, "sha256": digest, "size": path.stat().st_size})
    manifest = {
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "package_id": "vachana-thai-four-voices", "version": "1.0.0",
        "title": "Vachana Thai VITS — 4 voices",
        "engine_adapter": "vachana-onnx-v1",
        "language": "th", "sample_rate": 22050,
        "voices": [
            {"id": name, "label": label, "asset": "voices/" + name + ".onnx"}
            for name, label in (
                ("th_f_1", "หญิง 1"), ("th_f_2", "หญิง 2"),
                ("th_m_1", "ชาย 1"), ("th_m_2", "ชาย 2")
            )
        ],
        "files": files,
        "license": {
            "spdx": "MIT", "url": "https://huggingface.co/VIZINTZOR/VachanaTTS",
            "attribution": "VachanaTTS; review upstream training datasets and derivatives",
            "review_status": "review_required",
        },
        "source": {
            "url": "https://huggingface.co/VIZINTZOR/VachanaTTS",
            "revision": "6fa5f03a26f8ec0c0e0582e9e6812efa84d38688",
        },
        "dependencies": ["vachanatts==0.0.7", "onnxruntime", "pythainlp", "ssg"],
    }
    return validate_manifest(manifest)



def create_fastthai_manifest(source: Path) -> dict[str, Any]:
    """Metadata for a local FastThaiG2P/Kokoro Thai Som ONNX model pack.

    The source license is declared Apache-2.0; the weight/dataset rights
    remain review_required. This function never uploads model data.
    """
    source = Path(source)
    names = ("config.json", "kokoro_thai.onnx", "voices/thai_som.npy")
    files = []
    for name in names:
        file = source / name
        if not file.is_file():
            raise ModelPackageError("missing FastThaiG2P model asset: " + name)
        with file.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        files.append({"path": name, "sha256": digest, "size": file.stat().st_size})
    return validate_manifest({
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "package_id": "fastthaig2p-thai-som", "version": "0.3.0",
        "title": "FastThaiG2P Kokoro Thai - Som",
        "engine_adapter": "fastthaig2p-kokoro-v1",
        "language": "th", "sample_rate": 24000,
        "voices": [{"id": "thai_som", "label": "Thai Som",
                    "asset": "voices/thai_som.npy"}],
        "files": files,
        "license": {
            "spdx": "Apache-2.0",
            "url": "https://github.com/awslabs/FastThaiG2P",
            "attribution": "FastThaiG2P by Charin Polpanumas / AWS; independently verify Kokoro model weights and dataset rights",
            "review_status": "review_required",
        },
        "source": {
            "url": "https://github.com/awslabs/FastThaiG2P/releases/tag/v0.3.0",
            "revision": "v0.3.0",
        },
        "dependencies": ["pythaitts", "onnxruntime", "numpy"],
    })


def pack_local_fastthai(source: Path, output: Path) -> Path:
    """Stage existing locally owned model files into the data-only layout."""
    temp_base = ROOT / "cache" / "temp"
    temp_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voxweavetts-fastthai-pack-", dir=temp_base) as temp:
        stage = Path(temp)
        for original, target_name in (
            ("config.json", "config.json"),
            ("kokoro_thai.onnx", "kokoro_thai.onnx"),
            ("thai_som.npy", "voices/thai_som.npy"),
        ):
            original_file = Path(source) / original
            if not original_file.is_file():
                raise ModelPackageError("missing local FastThai model: " + original)
            target = stage / target_name
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(original_file, target)
            except OSError:
                shutil.copy2(original_file, target)
        return make_package(stage, create_fastthai_manifest(stage), output)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="VoxWeaveTTS model packages")
    actions = parser.add_subparsers(dest="action", required=True)
    install = actions.add_parser("install")
    install.add_argument("file", type=Path)
    remove = actions.add_parser("remove")
    remove.add_argument("package_id")
    remove.add_argument("version")
    actions.add_parser("list")
    build = actions.add_parser("pack-vachana")
    build.add_argument("--source", type=Path, default=ROOT / "models" / "vachana")
    build.add_argument("--output", type=Path, default=ROOT / "dist" / "ModelPackages" /
                       "VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel")
    fast = actions.add_parser("pack-fastthai")
    fast.add_argument("--source", type=Path, default=ROOT / "models" / "fastthaig2p")
    fast.add_argument("--output", type=Path, default=ROOT / "dist" / "ModelPackages" /
                      "VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel")
    args = parser.parse_args()
    try:
        if args.action == "install":
            data = install_model_package(args.file)
            print("Installed", data["package_id"], data["version"])
        elif args.action == "remove":
            removed = remove_model_package(args.package_id, args.version)
            print("Removed" if removed else "Not installed")
        elif args.action == "list":
            for m, _path in installed_packages():
                print(m["package_id"], m["version"], len(m["voices"]), "voices",
                      m["license"]["spdx"], m["license"]["review_status"])
        elif args.action == "pack-vachana":
            manifest = create_vachana_manifest(args.source)
            print("Built", make_package(args.source, manifest, args.output))
            print("Rights status:", manifest["license"]["review_status"])
        elif args.action == "pack-fastthai":
            print("Built", pack_local_fastthai(args.source, args.output))
            print("Rights status: review_required - not cleared for redistribution")
    except (ModelPackageError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(2, "Model package operation failed: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
