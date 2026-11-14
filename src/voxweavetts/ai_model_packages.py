"""Verified data-only AI model packages (.vwmodel), optional and portable.

The package never executes scripts, imports modules or installs dependencies.
Only a trusted built-in adapter can interpret the model weights and metadata.
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "models" / "ai" / "packages"
FORMAT = "voxweavetts.ai-model-package"
VERSION = 1
MAX_SIZE = 2_500_000_000
MAX_FILES = 20
MAX_MANIFEST = 24_576
_ID = re.compile(r"[a-z][a-z0-9_-]{1,47}\Z")
_VERSION = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ALLOWED = {
    "config.json", "generation_config.json", "tokenizer_config.json",
    "special_tokens_map.json", "vocab.json", "sentencepiece.bpe.model",
    "model.safetensors", "README.md", "LICENSE", "NOTICE", "attribution.md",
}
_REQUIRED = {"config.json", "vocab.json", "sentencepiece.bpe.model",
             "model.safetensors"}
_LOCK = threading.RLock()
_DIALOG_LOCK = threading.Lock()


class AIModelPackageError(ValueError):
    pass


class AIModelPickerUnavailable(RuntimeError):
    pass


def package_key(manifest: dict) -> str:
    return manifest["package_id"] + "@" + manifest["version"]


def validate_manifest(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {
        "format", "format_version", "package_id", "version", "title",
        "engine_adapter", "files", "license", "source"
    }:
        raise AIModelPackageError("invalid AI model manifest schema")
    if value["format"] != FORMAT or type(value["format_version"]) is not int or value["format_version"] != VERSION:
        raise AIModelPackageError("unsupported AI model package format")
    if not isinstance(value["package_id"], str) or not _ID.fullmatch(value["package_id"]):
        raise AIModelPackageError("invalid AI package ID")
    if not isinstance(value["version"], str) or not _VERSION.fullmatch(value["version"]):
        raise AIModelPackageError("invalid AI package version")
    if value["engine_adapter"] != "m2m100-transformers-v1":
        raise AIModelPackageError("unsupported AI engine adapter")
    if not isinstance(value["title"], str) or not 1 <= len(value["title"]) <= 120:
        raise AIModelPackageError("invalid AI package title")
    license_info = value["license"]
    if not isinstance(license_info, dict) or set(license_info) != {
        "spdx", "url", "attribution", "review_status"
    } or any(not isinstance(license_info[k], str) for k in license_info):
        raise AIModelPackageError("invalid AI model license")
    if (not 1 <= len(license_info["spdx"]) <= 80
        or not license_info["url"].startswith("https://")
        or len(license_info["url"]) > 350
        or not 1 <= len(license_info["attribution"]) <= 1000
        or license_info["review_status"] not in {"review_required", "hold", "cleared"}):
        raise AIModelPackageError("invalid AI license metadata")
    source = value["source"]
    if not isinstance(source, dict) or set(source) != {"url", "revision"} or any(
        not isinstance(x, str) for x in source.values()
    ) or not source["url"].startswith("https://") or len(source["url"]) > 350 or len(source["revision"]) > 150:
        raise AIModelPackageError("invalid source provenance")
    files = value["files"]
    if not isinstance(files, list) or not len(_REQUIRED) <= len(files) <= MAX_FILES:
        raise AIModelPackageError("invalid AI model files list")
    names = set()
    total = 0
    for f in files:
        if not isinstance(f, dict) or set(f) != {"path", "size", "sha256"}:
            raise AIModelPackageError("invalid AI model file descriptor")
        name = f["path"]
        if not isinstance(name, str) or name not in _ALLOWED or name in names:
            raise AIModelPackageError("unknown or duplicated AI asset")
        if type(f["size"]) is not int or not 0 < f["size"] <= MAX_SIZE:
            raise AIModelPackageError("invalid AI model asset size")
        if not isinstance(f["sha256"], str) or not _SHA256.fullmatch(f["sha256"]):
            raise AIModelPackageError("invalid AI model asset digest")
        total += f["size"]
        names.add(name)
    if not _REQUIRED <= names or total > MAX_SIZE:
        raise AIModelPackageError("missing required M2M100 safetensors / tokenizer files")
    return value


def _folder(manifest: dict, base: Path) -> Path:
    return base / manifest["package_id"] / manifest["version"]


def installed_packages(*, base: Path = PACKAGES_DIR) -> list[tuple[dict, Path]]:
    entries = []
    for manifest_path in sorted(Path(base).glob("*/*/manifest.json")):
        if manifest_path.is_symlink() or manifest_path.parent.is_symlink() or manifest_path.parent.parent.is_symlink():
            continue
        try:
            if manifest_path.stat().st_size > MAX_MANIFEST:
                continue
            manifest = validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
            folder = _folder(manifest, Path(base))
            if folder != manifest_path.parent:
                continue
            if any(not (folder / f["path"]).is_file()
                   or (folder / f["path"]).stat().st_size != f["size"]
                   for f in manifest["files"]):
                continue
            entries.append((manifest, folder))
        except (OSError, ValueError, TypeError):
            continue
    return entries


def resolve_model(model_key: str, *, base: Path = PACKAGES_DIR) -> Path | None:
    """Match an installed model by exact manifest key; never accept a raw path."""
    for manifest, folder in installed_packages(base=base):
        if model_key == package_key(manifest):
            return folder
    return None


def install_model_package(archive: str | Path, *, base: Path = PACKAGES_DIR) -> dict:
    source = Path(archive)
    if source.suffix.lower() != ".vwmodel" or not source.is_file():
        raise AIModelPackageError("choose a .vwmodel package")
    with _LOCK, zipfile.ZipFile(source, "r") as bundle:
        members = bundle.infolist()
        if not 2 <= len(members) <= MAX_FILES + 1 or len({m.filename for m in members}) != len(members):
            raise AIModelPackageError("invalid ZIP member list")
        if members[0].filename != "manifest.json" or members[0].file_size > MAX_MANIFEST:
            raise AIModelPackageError("AI manifest must be the first ZIP entry")
        try:
            manifest = validate_manifest(json.loads(bundle.read(members[0]).decode("utf-8")))
        except (ValueError, UnicodeError) as exc:
            raise AIModelPackageError("invalid AI model manifest JSON") from exc
        file_index = {f["path"]: f for f in manifest["files"]}
        if {m.filename for m in members} != set(file_index) | {"manifest.json"}:
            raise AIModelPackageError("ZIP files do not match signed index")
        for member in members:
            if member.is_dir() or stat.S_IFMT(member.external_attr >> 16) == stat.S_IFLNK:
                raise AIModelPackageError("symlinks and executable ZIP entries are not supported")
            if member.filename == "manifest.json":
                continue
            descriptor = file_index[member.filename]
            if (member.file_size != descriptor["size"] or member.compress_size == 0
                    or member.file_size > member.compress_size * 1500):
                raise AIModelPackageError("AI model file size or compression ratio invalid")
        base = Path(base)
        target = _folder(manifest, base)
        if target.exists():
            raise AIModelPackageError("AI model version already installed")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".install-ai-", dir=target.parent))
        try:
            for descriptor in manifest["files"]:
                name = descriptor["path"]
                digest = hashlib.sha256()
                size = 0
                with bundle.open(name) as stream, (staging / name).open("xb") as out:
                    while chunk := stream.read(1024 * 1024):
                        size += len(chunk)
                        if size > descriptor["size"]:
                            raise AIModelPackageError("model asset exceeded manifest size")
                        digest.update(chunk)
                        out.write(chunk)
                    out.flush()
                    os.fsync(out.fileno())
                if digest.hexdigest() != descriptor["sha256"] or size != descriptor["size"]:
                    raise AIModelPackageError("AI model SHA256 mismatch")
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            if target.exists():
                raise AIModelPackageError("model already installed")
            staging.rename(target)
            return manifest
        finally:
            if staging.exists():
                shutil.rmtree(staging)


def remove_model_package(package_id: str, version: str, *, base: Path = PACKAGES_DIR) -> bool:
    if not isinstance(package_id, str) or not _ID.fullmatch(package_id):
        raise AIModelPackageError("invalid package ID")
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise AIModelPackageError("invalid package version")
    with _LOCK:
        base = Path(base)
        folder = base / package_id / version
        if not folder.exists():
            return False
        if folder.is_symlink():
            raise AIModelPackageError("symlink model removal rejected")
        manifest = validate_manifest(json.loads((folder / "manifest.json").read_text(encoding="utf-8")))
        if _folder(manifest, base) != folder:
            raise AIModelPackageError("package identity mismatch")
        shutil.rmtree(folder)
        if not any(folder.parent.iterdir()):
            folder.parent.rmdir()
        return True


def install_model_package_dialog(*, choose_file=None) -> dict | None:
    if not _DIALOG_LOCK.acquire(blocking=False):
        raise AIModelPickerUnavailable("a model picker is already open")
    try:
        if choose_file is None:
            from .model_packages import _native_model_picker
            choose_file = _native_model_picker
        selected = choose_file()
        return install_model_package(selected) if selected else None
    except Exception as exc:
        from .model_packages import ModelPackageDialogUnavailable
        if isinstance(exc, ModelPackageDialogUnavailable):
            raise AIModelPickerUnavailable("native AI model dialog unavailable") from exc
        raise
    finally:
        _DIALOG_LOCK.release()
