"""Universal .vwmodel v3: offline, single-file, relocatable model packages.

v3 is the sole accepted package format. There is no v1/v3 reader or fallback.
Runtime wheels may be bundled, but executable scripts, hooks, unpinned model
weights and external installers are never run from the model archive.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import stat
import sys
import tempfile
import threading
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FORMAT = "voxweavetts.model-package"
VERSION = 3
MAX_MANIFEST = 65_536
MAX_FILES = 160
MAX_TOTAL_SIZE = 8_000_000_000
MAX_METADATA = 65_536
CHUNK = 1024 * 1024
_ID = re.compile(r"[a-z][a-z0-9_-]{1,47}\Z")
_ADAPTER = re.compile(r"[a-z][a-z0-9-]{1,63}\Z")
_VERSION = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[A-Za-z]{2,4})?\Z")
_VOICE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}\Z")
_EXTENSIONS = {".onnx", ".json", ".npy", ".bin", ".txt", ".md", ".fst",
               ".utf8", ".safetensors", ".model", ".lock", ".whl", ".pt", ".pth"}
_KINDS = {"tts", "voice-cloning", "stt", "translation", "llm"}
_LOCK = threading.RLock()

# These are built-in worker families, not imported from a model ZIP.
# Package self-reported "trust" is not sufficient to register an adapter.
_BUILTINS = {
    "makham-paradee-onnx-v1": ("tts", "pythaitts", ("paradee_thai_int8.onnx", "config.json"), 24000),
    "vachana-onnx-v1": ("tts", "vachana", ("speaker_config.json",), 22050),
    "fastthaig2p-kokoro-v1": ("tts", "pythaitts", ("config.json", "kokoro_thai.onnx"), 24000),
    "kokoro-onnx-v1": ("tts", "kokoro", ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin"), 24000),
    "sherpa-supertonic-v1": ("tts", "sherpa", ("duration_predictor.int8.onnx", "text_encoder.int8.onnx", "vector_estimator.int8.onnx", "vocoder.int8.onnx", "tts.json", "unicode_indexer.bin", "voice.bin"), 44100),
    "sherpa-melo-zh-v1": ("tts", "sherpa", ("model.onnx", "tokens.txt", "lexicon.txt"), 44100),
    "m2m100-transformers-v1": ("translation", "m2m100", ("config.json", "vocab.json", "sentencepiece.bpe.model", "model.safetensors"), 0),
    # Serialized PyTorch is allowed ONLY for this exact first-party SHA-pinned
    # upstream Wayu NC package. Never allow arbitrary pickle extensions.
    "wayu-nc-v1": ("tts", "wayu-nc", ("config.json", "model.pth"), 24000),
}


class UniversalPackageError(ValueError):
    """Rejected a malformed or unsafe Universal v3 package."""


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 230:
        raise UniversalPackageError("invalid v3 file path")
    if "\\" in value or ":" in value or value.startswith("/"):
        raise UniversalPackageError("unsafe v3 file path")
    parts = PurePosixPath(value).parts
    windows_devices = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{index}" for prefix in ("COM", "LPT") for index in range(1, 10)
    }
    if (not 1 <= len(parts) <= 5 or any(
        p in ("", ".", "..") or p.startswith(".") or p.endswith((" ", "."))
        or p.split(".")[0].upper() in windows_devices
        or any(ord(c) <= 32 or ord(c) == 127 or c in '<>"|?*' for c in p)
        for p in parts
    ) or PurePosixPath(value).as_posix() != value or
        (PurePosixPath(value).suffix.lower() not in _EXTENSIONS
         and value not in ("LICENSE", "NOTICE"))):
        raise UniversalPackageError("unsupported v3 file path")
    return value


def _index(files: Any) -> dict[str, dict]:
    if not isinstance(files, list) or not 2 <= len(files) <= MAX_FILES:
        raise UniversalPackageError("invalid v3 file index")
    result: dict[str, dict] = {}
    total = 0
    for row in files:
        if not isinstance(row, dict) or set(row) != {"path", "size", "sha256"}:
            raise UniversalPackageError("invalid v3 file descriptor")
        name = _path(row["path"])
        if name.casefold() in result or name.casefold() == "manifest.json":
            raise UniversalPackageError("duplicate or reserved v3 file name")
        if (type(row["size"]) is not int or not 0 < row["size"] <= MAX_TOTAL_SIZE or
            not isinstance(row["sha256"], str) or not _SHA.fullmatch(row["sha256"])):
            raise UniversalPackageError("invalid v3 file size/hash")
        total += row["size"]
        result[name.casefold()] = row
    if total > MAX_TOTAL_SIZE:
        raise UniversalPackageError("v3 package too large")
    return result


def _runtime(spec: Any, files: dict[str, dict]) -> None:
    if not isinstance(spec, dict) or set(spec) != {
        "id", "kind", "python", "platform", "accelerator",
        "source", "install_policy", "lockfile",
    }:
        raise UniversalPackageError("invalid v3 runtime declaration")
    if not isinstance(spec["id"], str) or not _ADAPTER.fullmatch(spec["id"]):
        raise UniversalPackageError("invalid runtime id")
    if spec["kind"] not in ("core", "python-target"):
        raise UniversalPackageError("unsupported v3 runtime kind")
    if spec["python"] != "3.11":
        raise UniversalPackageError("v3 supports Python 3.11 portable only")
    if spec["platform"] not in ("windows-x64", "any"):
        raise UniversalPackageError("v3 runtime must target Windows x64 or any")
    if spec["accelerator"] != "cpu":
        raise UniversalPackageError("unsupported v3 accelerator")
    if spec["source"] == "core-bundled":
        if (spec["kind"] != "core" or spec["install_policy"] != "reuse-only"
            or spec["lockfile"] is not None):
            raise UniversalPackageError("invalid bundled-core runtime")
    elif spec["source"] == "bundled-wheels":
        lock = spec["lockfile"]
        if (spec["kind"] != "python-target" or spec["install_policy"] != "auto"
            or not isinstance(lock, str) or _path(lock) != lock
            or not lock.startswith("runtime/locks/")
            or lock.casefold() not in files
            or files[lock.casefold()]["size"] > MAX_METADATA):
            raise UniversalPackageError("v3 requires hash-pinned offline wheels")
    else:
        raise UniversalPackageError("online/recipe/reuse-only dependency install forbidden")


def _capabilities(manifest: dict, files: dict[str, dict]) -> None:
    kind = manifest["package"]["kind"]
    cap = manifest["capabilities"]
    if not isinstance(cap, dict):
        raise UniversalPackageError("invalid v3 native capabilities")
    if kind == "tts":
        if set(cap) != {"language", "sample_rate", "voices"}:
            raise UniversalPackageError("TTS capabilities required")
        if (cap["language"] not in ("th", "en", "multi", "zh")
            or type(cap["sample_rate"]) is not int
            or not 8_000 <= cap["sample_rate"] <= 96_000):
            raise UniversalPackageError("unsupported voice sample rate/language")
        if not isinstance(cap["voices"], list) or not 1 <= len(cap["voices"]) <= 64:
            raise UniversalPackageError("invalid v3 voice list")
        ids = set()
        for voice in cap["voices"]:
            if not isinstance(voice, dict) or set(voice) != {"id", "label", "asset"}:
                raise UniversalPackageError("invalid voice entry")
            if (not isinstance(voice["id"], str) or not _VOICE.fullmatch(voice["id"])
                or voice["id"] in ids or not isinstance(voice["label"], str)
                or not 1 <= len(voice["label"]) <= 110 or
                not isinstance(voice["asset"], str) or
                _path(voice["asset"]).casefold() not in files):
                raise UniversalPackageError("invalid native v3 voice asset")
            ids.add(voice["id"])
    elif kind == "translation":
        if (set(cap) != {"model_family"} or
            not isinstance(cap["model_family"], str)
            or not _ADAPTER.fullmatch(cap["model_family"])):
            raise UniversalPackageError("invalid translation capabilities")
    else:
        if (set(cap) != {"features"} or not isinstance(cap["features"], list)
            or len(cap["features"]) > 32 or any(
                not isinstance(f, str) or not _ADAPTER.fullmatch(f) for f in cap["features"]
            ) or len(set(cap["features"])) != len(cap["features"])):
            raise UniversalPackageError("invalid universal capabilities")


def validate_manifest(value: Any) -> dict:
    if (not isinstance(value, dict) or set(value) != {
        "format", "format_version", "package", "adapter", "runtime",
        "assets", "rights", "files", "capabilities",
    } or value["format"] != FORMAT or
        type(value["format_version"]) is not int or value["format_version"] != VERSION):
        raise UniversalPackageError("expected Universal .vwmodel v3; older packages are unsupported")
    pkg = value["package"]
    if (not isinstance(pkg, dict) or set(pkg) != {
        "id", "version", "kind", "title", "languages",
    } or not isinstance(pkg["id"], str) or not _ID.fullmatch(pkg["id"])):
        raise UniversalPackageError("invalid v3 package identity")
    if not isinstance(pkg["version"], str) or not _VERSION.fullmatch(pkg["version"]):
        raise UniversalPackageError("invalid v3 version")
    if pkg["kind"] not in _KINDS or not isinstance(pkg["title"], str) or not 1 <= len(pkg["title"]) <= 120:
        raise UniversalPackageError("invalid v3 package kind/title")
    langs = pkg["languages"]
    if (not isinstance(langs, list) or not 1 <= len(langs) <= 64
        or any(not isinstance(s, str) or not _LANGUAGE.fullmatch(s) for s in langs)
        or len(set(langs)) != len(langs)):
        raise UniversalPackageError("invalid v3 languages")
    adapter = value["adapter"]
    if (not isinstance(adapter, dict) or set(adapter) != {"id", "api_version", "trust"}
        or not isinstance(adapter["id"], str) or not _ADAPTER.fullmatch(adapter["id"])
        or type(adapter["api_version"]) is not int or adapter["api_version"] != 1
        or adapter["trust"] not in ("builtin", "external")):
        raise UniversalPackageError("invalid v3 adapter identity")
    files = _index(value["files"])
    if (value["assets"] != "manifest-assets.json" or value["rights"] != "legal/rights.json"
        or value["assets"] not in files or value["rights"] not in files
        or files[value["assets"]]["size"] > MAX_METADATA
        or files[value["rights"]]["size"] > MAX_METADATA):
        raise UniversalPackageError("v3 package needs hashed assets and rights metadata")
    _runtime(value["runtime"], files)
    if (value["runtime"]["source"] == "core-bundled"
        and value["adapter"]["id"] != "makham-paradee-onnx-v1"):
        raise UniversalPackageError("core-bundled is reserved for verified MakHam")
    _capabilities(value, files)
    for row in files.values():
        name = row["path"]
        ext = PurePosixPath(name).suffix.lower()
        if ext == ".whl" and (value["runtime"]["source"] != "bundled-wheels"
                              or not name.startswith("runtime/wheels/")):
            raise UniversalPackageError("unapproved wheel material")
        # Only the exactly pinned original NC Wayu weights may use PyTorch
        # serialized .pt/.pth, NEVER arbitrary serialized/ executable bytes.
        if ext in (".pt", ".pth"):
            from .wayu_native_trust import PINNED_ASSETS, PACKAGE_ID, PACKAGE_VERSION
            if (adapter["id"] != "wayu-nc-v1"
                or pkg["id"] != PACKAGE_ID or pkg["version"] != PACKAGE_VERSION
                or name not in PINNED_ASSETS
                or row["sha256"] != PINNED_ASSETS[name]):
                raise UniversalPackageError("untrusted serialized PyTorch asset")
        if ext in (".pkl", ".py", ".dll", ".exe"):
            raise UniversalPackageError("executable asset forbidden in native v3")
    if adapter["id"] == "wayu-nc-v1":
        from .wayu_native_trust import PINNED_ASSETS, PACKAGE_ID, PACKAGE_VERSION
        from .personal_wayu_engine import VOICES
        cap = value["capabilities"]
        if (adapter["trust"] != "builtin" or pkg["kind"] != "tts"
            or pkg["id"] != PACKAGE_ID or pkg["version"] != PACKAGE_VERSION
            or pkg["languages"] != ["th", "en"]
            or value["runtime"]["id"] != "wayu-nc"
            or value["runtime"]["kind"] != "python-target"
            or value["runtime"]["source"] != "bundled-wheels"
            or value["runtime"]["install_policy"] != "auto"
            or value["runtime"]["accelerator"] != "cpu"
            or cap["language"] != "th" or cap["sample_rate"] != 24000
            or set(PINNED_ASSETS) - {r["path"] for r in value["files"]}
            or [v["id"] for v in cap["voices"]] != [v[0] for v in VOICES]
            or any(v["asset"] != "voices/" + v["id"] + ".pt"
                   for v in cap["voices"])
            or any(files[name.casefold()]["sha256"] != sha
                   for name, sha in PINNED_ASSETS.items())):
            raise UniversalPackageError("Wayu NC v3 requires the exact pinned weights/voices")
    return value


def _small_json(folder: Path, name: str) -> dict:
    file = folder.joinpath(*PurePosixPath(name).parts)
    if not file.is_file() or file.is_symlink() or file.stat().st_size > MAX_METADATA:
        raise UniversalPackageError("invalid v3 metadata location/size")
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise UniversalPackageError("invalid v3 JSON metadata") from exc
    if not isinstance(data, dict):
        raise UniversalPackageError("v3 metadata must be an object")
    return data


def _validate_assets(folder: Path, manifest: dict) -> None:
    paths = _small_json(folder, manifest["assets"])
    excluded = {manifest["assets"], manifest["rights"]}
    if manifest["runtime"]["lockfile"]:
        excluded.add(manifest["runtime"]["lockfile"])
    expected = {row["path"] for row in manifest["files"]} - excluded
    if (set(paths) != {"paths"} or not isinstance(paths["paths"], list)
        or any(not isinstance(x, str) for x in paths["paths"])
        or len(set(paths["paths"])) != len(paths["paths"])
        or set(paths["paths"]) != expected):
        raise UniversalPackageError("v3 asset index mismatch")
    rights = _small_json(folder, manifest["rights"])
    if set(rights) != {"license", "source"}:
        raise UniversalPackageError("v3 rights/provenance metadata required")
    lic, src = rights["license"], rights["source"]
    if (not isinstance(lic, dict) or set(lic) != {"spdx", "url", "attribution", "review_status"}
        or any(not isinstance(v, str) for v in lic.values())
        or not 1 <= len(lic["spdx"]) <= 80 or not lic["url"].startswith("https://")
        or len(lic["url"]) > 350 or not 1 <= len(lic["attribution"]) <= 1000
        or lic["review_status"] not in ("review_required", "hold", "cleared")
        or not isinstance(src, dict) or set(src) != {"url", "revision"}
        or not all(isinstance(v, str) for v in src.values())
        or not src["url"].startswith("https://") or len(src["url"]) > 350
        or len(src["revision"]) > 150):
        raise UniversalPackageError("invalid v3 rights declaration")
    lock_path = manifest["runtime"]["lockfile"]
    if lock_path:
        lock = _small_json(folder, lock_path)
        if (set(lock) != {"requirements", "wheels"}
            or not isinstance(lock["requirements"], list) or not isinstance(lock["wheels"], list)
            or len(lock["requirements"]) > MAX_FILES or len(lock["wheels"]) > MAX_FILES):
            raise UniversalPackageError("invalid v3 runtime lock")
        requirements = set()
        for item in lock["requirements"]:
            if (not isinstance(item, dict) or set(item) != {"name", "version"}
                or not isinstance(item["name"], str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", item["name"])
                or item["name"].casefold() in requirements
                or not isinstance(item["version"], str)
                or not re.fullmatch(r"[0-9A-Za-z.+_-]{1,60}", item["version"])):
                raise UniversalPackageError("unsafe or duplicate dependency")
            requirements.add(item["name"].casefold())
        expected_wheels = {p for p in expected if p.endswith(".whl")}
        wheels = set()
        file_index = {r["path"]: r for r in manifest["files"]}
        for wheel in lock["wheels"]:
            if (not isinstance(wheel, dict) or set(wheel) != {"path", "sha256"}
                or not isinstance(wheel["path"], str)
                or wheel["path"] not in expected_wheels
                or wheel["sha256"] != file_index[wheel["path"]]["sha256"]):
                raise UniversalPackageError("unverified offline wheel")
            wheels.add(wheel["path"])
        if len(wheels) != len(lock["wheels"]) or wheels != expected_wheels:
            raise UniversalPackageError("v3 wheels and lock disagree")
        if manifest["runtime"]["source"] == "bundled-wheels" and not wheels:
            raise UniversalPackageError("declared offline wheels missing")


def _model_files(manifest: dict) -> list[dict]:
    ignore = {manifest["assets"], manifest["rights"]}
    return [r for r in manifest["files"]
            if r["path"] not in ignore and not r["path"].startswith("runtime/")]


def _trusted_adapter(manifest: dict) -> tuple[str, str, tuple[str, ...], int] | None:
    if manifest["adapter"]["trust"] != "builtin":
        return None
    name = manifest["adapter"]["id"]
    result = _BUILTINS.get(name)
    return (result if result and result[0] == manifest["package"]["kind"] else None)


def native_adapter_profile(manifest: dict, folder: Path) -> dict | None:
    """Validate a v3-native model against a known built-in worker contract.

    The descriptor is constructed from v3 capabilities, not archived code.
    """
    trusted = _trusted_adapter(manifest)
    if trusted is None:
        return None
    kind, runtime_id, required, sample_rate = trusted
    if manifest["runtime"]["id"] != runtime_id:
        raise UniversalPackageError("v3 adapter/runtime mismatch")
    installed = {r["path"]: r for r in _model_files(manifest)}
    if not set(required).issubset(installed):
        raise UniversalPackageError("native model lacks built-in adapter assets")
    if kind == "tts":
        cap = manifest["capabilities"]
        if cap["sample_rate"] != sample_rate:
            raise UniversalPackageError("native TTS sampling rate mismatch")
        voices = cap["voices"]
        adapter_id = manifest["adapter"]["id"]
        for voice in voices:
            asset = voice["asset"]
            vid = voice["id"]
            if adapter_id == "makham-paradee-onnx-v1" and (asset != "paradee_thai_int8.onnx" or vid != "paradee_thai"):
                raise UniversalPackageError("invalid MakHam native voice mapping")
            if adapter_id == "vachana-onnx-v1" and asset != "voices/" + vid + ".onnx":
                raise UniversalPackageError("invalid Vachana native voice mapping")
            if adapter_id == "fastthaig2p-kokoro-v1" and (not asset.startswith("voices/") or not asset.endswith(".npy")):
                raise UniversalPackageError("invalid FastThai native voice mapping")
            if adapter_id == "kokoro-onnx-v1" and asset != "voices-v1.0.bin":
                raise UniversalPackageError("invalid Kokoro native voice mapping")
            if adapter_id == "sherpa-supertonic-v1" and asset != "voice.bin":
                raise UniversalPackageError("invalid Supertonic native voice mapping")
            if adapter_id == "sherpa-melo-zh-v1" and (asset != "model.onnx" or vid != "zh_melo"):
                raise UniversalPackageError("invalid Melo native voice mapping")
            if adapter_id == "wayu-nc-v1" and asset != "voices/" + vid + ".pt":
                raise UniversalPackageError("invalid Wayu NC voice mapping")
        if adapter_id == "makham-paradee-onnx-v1":
            from .makham_package import PINNED_ASSETS, PACKAGE_ID, PACKAGE_VERSION, UPSTREAM, SOURCE_REVISION
            if (manifest["package"]["id"] != PACKAGE_ID
                or manifest["package"]["version"] != PACKAGE_VERSION
                or len(voices) != 1
                or cap["language"] != "th"):
                raise UniversalPackageError("invalid MakHam native package identity")
            for name, digest in PINNED_ASSETS.items():
                if installed[name]["sha256"] != digest:
                    raise UniversalPackageError("MakHam native weight differs from verified upstream")
            rights = _small_json(folder, manifest["rights"])
            if (rights["source"] != {"url": UPSTREAM, "revision": SOURCE_REVISION}
                or rights["license"]["spdx"] != "Apache-2.0"):
                raise UniversalPackageError("MakHam pinned source/rights mismatch")
        if adapter_id == "wayu-nc-v1":
            from .wayu_native_trust import (
                PINNED_ASSETS, SOURCE_URL, SOURCE_REVISION, LICENSE_SPDX,
            )
            rights = _small_json(folder, manifest["rights"])
            if (rights["source"] != {"url": SOURCE_URL, "revision": SOURCE_REVISION}
                or rights["license"]["spdx"] != LICENSE_SPDX
                or rights["license"]["review_status"] != "hold"
                or rights["license"]["url"] != "https://creativecommons.org/licenses/by-nc/4.0/"
                or not all(installed.get(name, {}).get("sha256") == sha
                           for name, sha in PINNED_ASSETS.items())):
                raise UniversalPackageError("Wayu NC model rights/source or weights do not match pinned original")
        if adapter_id == "vachana-onnx-v1" and cap["language"] != "th":
            raise UniversalPackageError("Vachana language mismatch")
        if adapter_id == "sherpa-melo-zh-v1" and cap["language"] != "zh":
            raise UniversalPackageError("Melo language mismatch")
    elif manifest["capabilities"]["model_family"] != "m2m100":
        raise UniversalPackageError("translation model family mismatch")
    rights = _small_json(folder, manifest["rights"])
    return {
        "package_id": manifest["package"]["id"],
        "version": manifest["package"]["version"],
        "title": manifest["package"]["title"],
        "engine_adapter": manifest["adapter"]["id"],
        "files": _model_files(manifest),
        "license": rights["license"], "source": rights["source"],
        "language": manifest["capabilities"].get("language", "multi"),
        "sample_rate": manifest["capabilities"].get("sample_rate", 0),
        "voices": manifest["capabilities"].get("voices", []),
        "dependencies": [],
        "format_version": 3,
    }


def engine_id_for(manifest: dict) -> str:
    """Stable v3 engine identity, independent of old stored manifests."""
    package_id = manifest["package_id"] if "package_id" in manifest else manifest["package"]["id"]
    version = manifest["version"] if "version" in manifest else manifest["package"]["version"]
    return "model-" + package_id + "-" + version.replace(".", "_")


def display_model_title(manifest: dict) -> str:
    """Decorate only explicitly NC licensed models, not 'review_required'."""
    title = manifest["title"] if "title" in manifest else manifest["package"]["title"]
    license_info = manifest.get("license") or {}
    spdx = str(license_info.get("spdx", "")).upper().replace("_", "-")
    noncommercial = bool(re.search(r"(?<![A-Z])NC(?![A-Z])", spdx)) or "NONCOMMERCIAL" in spdx
    return ("[NC / NonCommercial] " + title if noncommercial
            and not title.upper().startswith(("[NC]", "[NC ", "[NONCOMMERCIAL]"))
            else title)


def platform_compatible(manifest: dict) -> bool:
    wanted = manifest["runtime"]["platform"]
    current = ("windows-" if sys.platform == "win32" else
               "macos-" if sys.platform == "darwin" else "linux-") + (
        "arm64" if platform.machine().lower() in ("aarch64", "arm64") else "x64")
    return wanted in ("any", current)


def runtime_compatibility(manifest: dict, *, root: Path = ROOT) -> str:
    """Structural compatibility, independent of whether dependencies are installed."""
    rt = manifest["runtime"]
    if _trusted_adapter(manifest) is None:
        return "adapter-not-approved"
    if rt["id"] != _trusted_adapter(manifest)[1]:
        return "runtime-id-mismatch"
    if not platform_compatible(manifest):
        return "platform-incompatible"
    if rt["python"] != "3.11" or rt["accelerator"] != "cpu":
        return "runtime-unsupported"
    if rt["source"] not in ("core-bundled", "bundled-wheels"):
        return "offline-runtime-required"
    return "compatible"


def activation_compatible(manifest: dict, root: Path = ROOT) -> bool:
    return runtime_compatibility(manifest, root=root) == "compatible"


def runtime_fingerprint(manifest: dict) -> str:
    validate_manifest(manifest)
    from .portable_runtime_v3 import fingerprint
    return fingerprint(manifest)


def _base(root: Path, kind: str) -> Path:
    return Path(root) / "models" / "universal" / "v3" / kind


def _is_contained_file(folder: Path, relative_name: str) -> bool:
    """Reject symlinked/junction parents, not just symlinked final files."""
    path = folder.joinpath(*PurePosixPath(relative_name).parts)
    try:
        if not path.is_file() or path.is_symlink():
            return False
        if not path.resolve(strict=True).is_relative_to(folder.resolve(strict=True)):
            return False
        parent = path.parent
        while parent != folder:
            if parent.is_symlink():
                return False
            parent = parent.parent
        return True
    except (OSError, ValueError):
        return False


def _installed_manifest(folder: Path) -> dict | None:
    marker = folder / "manifest.json"
    try:
        if (not _is_contained_file(folder, "manifest.json")
            or marker.stat().st_size > MAX_MANIFEST):
            return None
        manifest = validate_manifest(json.loads(marker.read_text(encoding="utf-8")))
        for row in manifest["files"]:
            # Verified wheels are consumed once, never duplicated inside the
            # installed model. Manifest/lock hashes remain immutable.
            if row["path"].startswith("runtime/wheels/"):
                continue
            asset = folder.joinpath(*PurePosixPath(row["path"]).parts)
            if (not _is_contained_file(folder, row["path"])
                or asset.stat().st_size != row["size"]):
                return None
        metadata = {manifest["assets"], manifest["rights"]}
        if manifest["runtime"]["lockfile"]:
            metadata.add(manifest["runtime"]["lockfile"])
        hashes = {r["path"]: r["sha256"] for r in manifest["files"]}
        for name in metadata:
            if hashlib.sha256((folder / name).read_bytes()).hexdigest() != hashes[name]:
                return None
        _validate_assets(folder, manifest)
        native_adapter_profile(manifest, folder)
        return manifest
    except (OSError, ValueError, KeyError, TypeError):
        return None


def installed_packages(root: Path = ROOT) -> list[tuple[dict, Path]]:
    root = Path(root)
    result: list[tuple[dict, Path]] = []
    for kind in sorted(_KINDS):
        base = _base(root, kind)
        for item in sorted(base.glob("*/*/manifest.json")):
            folder = item.parent
            if (item.is_symlink() or folder.is_symlink() or folder.parent.is_symlink()
                or not folder.resolve().is_relative_to(base.resolve())):
                continue
            manifest = _installed_manifest(folder)
            if (manifest and folder == base / manifest["package"]["id"] / manifest["package"]["version"]):
                result.append((manifest, folder))
    return result


def native_tts_packages(root: Path = ROOT) -> list[tuple[dict, Path]]:
    return [(native_adapter_profile(m, f), f)
            for m, f in installed_packages(root)
            if m["package"]["kind"] == "tts" and activation_compatible(m, root)]


def native_translation_packages(root: Path = ROOT) -> list[tuple[dict, Path]]:
    return [(native_adapter_profile(m, f), f)
            for m, f in installed_packages(root)
            if m["package"]["kind"] == "translation" and activation_compatible(m, root)]


def installed_for_engine(engine_id: str, *, root: Path = ROOT) -> tuple[dict, Path] | None:
    """Resolve a trusted v3 model by its stable Engine ID."""
    from .makham_package import ENGINE_ID
    for manifest, folder in installed_packages(root):
        if manifest["package"]["kind"] != "tts":
            continue
        expected = (ENGINE_ID if manifest["adapter"]["id"] == "makham-paradee-onnx-v1"
                    else engine_id_for(manifest))
        if expected == engine_id:
            return manifest, folder
    return None


def runtime_for_provider(provider_id: str, *, root: Path = ROOT,
                         engine_id: str | None = None) -> dict | None:
    """Select the exact package runtime; no global Python-venv fallback."""
    from .portable_runtime_v3 import ready
    if engine_id:
        pair = installed_for_engine(engine_id, root=root)
        if pair is None:
            return None
        manifest = pair[0]
        return manifest if (manifest["runtime"]["id"] == provider_id
                            and ready(root, manifest)) else None
    for manifest, _folder in installed_packages(root):
        if (manifest["package"]["kind"] == "tts"
            and manifest["runtime"]["id"] == provider_id
            and ready(root, manifest)):
            return manifest
    return None


def package_status(manifest: dict, *, root: Path = ROOT, folder: Path | None = None) -> dict:
    from .portable_runtime_v3 import ready as runtime_ready
    native = native_adapter_profile(manifest, folder) if folder else None
    reason = runtime_compatibility(manifest, root=root)
    allow = reason == "compatible" and native is not None
    ready = bool(allow and runtime_ready(root, manifest))
    if allow and not ready:
        reason = "runtime-not-installed"
    rights = _small_json(folder, manifest["rights"]) if folder else {}
    cap = manifest["capabilities"]
    return {
        "package_id": manifest["package"]["id"], "version": manifest["package"]["version"],
        "title": manifest["package"]["title"], "model_kind": manifest["package"]["kind"],
        "format_version": 3, "engine_adapter": manifest["adapter"]["id"],
        "adapter_trusted": native is not None,
        "runtime_id": manifest["runtime"]["id"],
        "runtime_fingerprint": runtime_fingerprint(manifest),
        "runtime_source": manifest["runtime"]["source"],
        "runtime_ready": ready,
        "runtime_state": "ready" if ready else reason,
        "engine_id": (
            "makham-paradee-cpu"
            if allow and manifest["adapter"]["id"] == "makham-paradee-onnx-v1"
            else engine_id_for(manifest) if allow and manifest["package"]["kind"] == "tts"
            else ""
        ),
        "voices": cap.get("voices", []),
        "languages": manifest["package"]["languages"],
        "license": rights.get("license", {}),
        "source": rights.get("source", {}),
        "dependencies": [],
    }


def inspect_archive(archive: str | Path) -> dict:
    source = Path(archive)
    if source.suffix.lower() != ".vwmodel" or not source.is_file():
        raise UniversalPackageError("select a Universal .vwmodel v3")
    with zipfile.ZipFile(source) as bundle:
        members = bundle.infolist()
        if (not 3 <= len(members) <= MAX_FILES + 1
            or members[0].filename != "manifest.json"
            or members[0].file_size > MAX_MANIFEST
            or len({m.filename.casefold() for m in members}) != len(members)):
            raise UniversalPackageError("invalid v3 ZIP member list")
        try:
            manifest = validate_manifest(json.loads(bundle.read(members[0]).decode("utf-8")))
        except (ValueError, UnicodeError) as exc:
            raise UniversalPackageError("malformed v3 manifest") from exc
        index = _index(manifest["files"])
        if {m.filename.casefold() for m in members} != set(index) | {"manifest.json"}:
            raise UniversalPackageError("v3 archive files disagree with manifest")
        for item in members:
            if (item.is_dir() or item.flag_bits & 1 or
                stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK):
                raise UniversalPackageError("links, directories and encrypted ZIP forbidden")
            if item.filename == "manifest.json":
                continue
            row = index[item.filename.casefold()]
            if (item.filename != row["path"] or item.file_size != row["size"]
                or not item.compress_size or item.file_size > item.compress_size * 1500):
                raise UniversalPackageError("v3 ZIP contains unsafe/compressed asset")
        return manifest


def install_model_package(archive: str | Path, *, root: Path = ROOT) -> dict:
    with _LOCK:
        manifest = inspect_archive(archive)
        root = Path(root)
        base = _base(root, manifest["package"]["kind"])
        target = base / manifest["package"]["id"] / manifest["package"]["version"]
        if (target.exists() or target.is_symlink() or any(
            m["package"]["id"] == manifest["package"]["id"]
            and m["package"]["version"] == manifest["package"]["version"]
            for m, _ in installed_packages(root)
        )):
            raise UniversalPackageError("this v3 package identity is already installed")
        if (base.is_symlink() or target.parent.is_symlink()
            or not base.resolve().is_relative_to(root.resolve())):
            raise UniversalPackageError("symlinked model destination forbidden")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.parent.resolve().is_relative_to(root.resolve()):
            raise UniversalPackageError("redirected model destination forbidden")
        stage = Path(tempfile.mkdtemp(prefix=".install-v3-", dir=target.parent))
        try:
            with zipfile.ZipFile(archive) as bundle:
                for row in manifest["files"]:
                    name = row["path"]
                    output = stage.joinpath(*PurePosixPath(name).parts)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    digest = hashlib.sha256()
                    amount = 0
                    with bundle.open(name) as src, output.open("xb") as dst:
                        while chunk := src.read(CHUNK):
                            amount += len(chunk)
                            if amount > row["size"]:
                                raise UniversalPackageError("v3 asset exceeds declared size")
                            digest.update(chunk)
                            dst.write(chunk)
                    if amount != row["size"] or digest.hexdigest() != row["sha256"]:
                        raise UniversalPackageError("v3 asset SHA-256 mismatch")
            _validate_assets(stage, manifest)
            if native_adapter_profile(manifest, stage) is None:
                raise UniversalPackageError("unsupported v3 adapter: trusted built-in worker required")
            if runtime_compatibility(manifest, root=root) != "compatible":
                raise UniversalPackageError("v3 runtime is incompatible with this device")
            (stage / "manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            if target.exists():
                raise UniversalPackageError("v3 package was installed concurrently")
            from .portable_runtime_v3 import install as install_runtime, uninstall_if_unreferenced
            created_runtime = False
            try:
                created_runtime = install_runtime(root, manifest, stage)
                # The imported and SHA-verified wheels are no longer needed
                # after installing the relocatable shared runtime.
                wheel_dir = stage / "runtime" / "wheels"
                if wheel_dir.is_dir():
                    shutil.rmtree(wheel_dir)
                stage.rename(target)
            except BaseException:
                if created_runtime:
                    uninstall_if_unreferenced(root, manifest)
                raise
            if manifest["adapter"]["id"] == "makham-paradee-onnx-v1" and root.resolve() == ROOT.resolve():
                from .makham_package import clear_disabled_marker
                clear_disabled_marker(root)
            return {
                "engine_id": ("makham-paradee-cpu" if manifest["adapter"]["id"] == "makham-paradee-onnx-v1"
                              else engine_id_for(manifest) if manifest["package"]["kind"] == "tts" else ""),
                "package_id": manifest["package"]["id"],
                "version": manifest["package"]["version"],
                "package_kind": manifest["package"]["kind"],
                "engine_adapter": manifest["adapter"]["id"],
                "format_version": 3,
                "runtime_status": "ready",
                "activation_supported": activation_compatible(manifest),
            }
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def remove_model_package(package_id: str, version: str, *, root: Path = ROOT) -> bool:
    if (not isinstance(package_id, str) or not _ID.fullmatch(package_id)
        or not isinstance(version, str) or not _VERSION.fullmatch(version)):
        raise UniversalPackageError("invalid v3 package removal identity")
    with _LOCK:
        for manifest, folder in installed_packages(root):
            if manifest["package"]["id"] == package_id and manifest["package"]["version"] == version:
                if (folder.is_symlink()
                    or not folder.resolve().is_relative_to(_base(root, manifest["package"]["kind"]).resolve())):
                    raise UniversalPackageError("unmanaged or redirected v3 model directory")
                declared = {"manifest.json"} | {r["path"] for r in manifest["files"]}
                directories = set()
                for name in declared:
                    directories.update(parent.as_posix()
                                       for parent in PurePosixPath(name).parents
                                       if parent.as_posix() != ".")
                for item in folder.rglob("*"):
                    relative = item.relative_to(folder).as_posix()
                    if (item.is_symlink()
                        or not item.resolve().is_relative_to(folder.resolve())
                        or (item.is_file() and relative not in declared)
                        or (item.is_dir() and relative not in directories)
                        or not (item.is_file() or item.is_dir())):
                        raise UniversalPackageError("model folder contains unmanaged files; refusing deletion")
                # This is an explicit destructive action. Do not delete model
                # weights or user-added files modified after installation.
                for row in manifest["files"]:
                    if row["path"].startswith("runtime/wheels/"):
                        continue
                    with (folder / row["path"]).open("rb") as stream:
                        if hashlib.file_digest(stream, "sha256").hexdigest() != row["sha256"]:
                            raise UniversalPackageError("modified v3 model asset; refusing deletion")
                shutil.rmtree(folder)
                from .portable_runtime_v3 import uninstall_if_unreferenced
                uninstall_if_unreferenced(root, manifest)
                if manifest["adapter"]["id"] == "makham-paradee-onnx-v1" and Path(root).resolve() == ROOT.resolve():
                    from .makham_package import disable_legacy_fallback
                    disable_legacy_fallback(root)
                if not any(folder.parent.iterdir()):
                    folder.parent.rmdir()
                return True
    return False


def make_package(source: Path, manifest: dict, output: Path) -> Path:
    validate_manifest(manifest)
    source, output = Path(source), Path(output)
    if output.suffix.lower() != ".vwmodel":
        raise UniversalPackageError("output must end with .vwmodel")
    if output.exists() or output.is_symlink():
        raise UniversalPackageError("v3 output already exists; refusing overwrite")
    if output.resolve().is_relative_to(source.resolve()):
        raise UniversalPackageError("v3 output cannot be inside source assets")
    for row in manifest["files"]:
        file = source.joinpath(*PurePosixPath(row["path"]).parts)
        if (not _is_contained_file(source, row["path"])
            or file.stat().st_size != row["size"]):
            raise UniversalPackageError("missing, redirected or symlinked v3 source asset")
        with file.open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != row["sha256"]:
                raise UniversalPackageError("v3 source SHA-256 mismatch")
    _validate_assets(source, manifest)
    native_adapter_profile(manifest, source)
    output.parent.mkdir(parents=True, exist_ok=True)
    def info(name: str) -> zipfile.ZipInfo:
        entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.create_system = 3
        entry.external_attr = (stat.S_IFREG | 0o644) << 16
        return entry
    created = False
    try:
        with output.open("xb") as target:
            created = True
            with zipfile.ZipFile(target, "w", allowZip64=True,
                                 compression=zipfile.ZIP_DEFLATED, compresslevel=3) as result:
                result.writestr(info("manifest.json"), json.dumps(manifest, ensure_ascii=False, indent=2))
                for row in manifest["files"]:
                    with (source / row["path"]).open("rb") as src, result.open(info(row["path"]), "w", force_zip64=True) as dst:
                        shutil.copyfileobj(src, dst, CHUNK)
        return output
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
