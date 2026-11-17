"""Universal .vwmodel v2: independent, declarative, data-only model packages.

No embedded v1 manifests, code execution, pip hooks or untrusted imports.
v2 assets live separately from earlier packages, and model installation never
creates or modifies a Python runtime. Runtime setup is an explicit separate step.
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
VERSION = 2
MAX_MANIFEST = 65_536
MAX_FILES = 120
MAX_TOTAL_SIZE = 4_000_000_000
MAX_METADATA = 65_536
CHUNK = 1024 * 1024
_ID = re.compile(r"[a-z][a-z0-9_-]{1,47}\Z")
_ADAPTER = re.compile(r"[a-z][a-z0-9-]{1,63}\Z")
_VERSION = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[A-Za-z]{2,4})?\Z")
_VOICE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}\Z")
_EXTENSIONS = {".onnx", ".json", ".npy", ".bin", ".txt", ".md", ".fst",
               ".utf8", ".safetensors", ".model", ".lock", ".whl"}
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
}


class UniversalPackageError(ValueError):
    """Rejected a malformed or unsafe Universal v2 package."""


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 230:
        raise UniversalPackageError("invalid v2 file path")
    if "\\" in value or ":" in value or value.startswith("/"):
        raise UniversalPackageError("unsafe v2 file path")
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
        raise UniversalPackageError("unsupported v2 file path")
    return value


def _index(files: Any) -> dict[str, dict]:
    if not isinstance(files, list) or not 2 <= len(files) <= MAX_FILES:
        raise UniversalPackageError("invalid v2 file index")
    result: dict[str, dict] = {}
    total = 0
    for row in files:
        if not isinstance(row, dict) or set(row) != {"path", "size", "sha256"}:
            raise UniversalPackageError("invalid v2 file descriptor")
        name = _path(row["path"])
        if name.casefold() in result or name.casefold() == "manifest.json":
            raise UniversalPackageError("duplicate or reserved v2 file name")
        if (type(row["size"]) is not int or not 0 < row["size"] <= MAX_TOTAL_SIZE or
            not isinstance(row["sha256"], str) or not _SHA.fullmatch(row["sha256"])):
            raise UniversalPackageError("invalid v2 file size/hash")
        total += row["size"]
        result[name.casefold()] = row
    if total > MAX_TOTAL_SIZE:
        raise UniversalPackageError("v2 package too large")
    return result


def _runtime(spec: Any, files: dict[str, dict]) -> None:
    if not isinstance(spec, dict) or set(spec) != {
        "id", "kind", "python", "platform", "accelerator",
        "source", "install_policy", "lockfile",
    }:
        raise UniversalPackageError("invalid v2 runtime metadata")
    if not isinstance(spec["id"], str) or not _ADAPTER.fullmatch(spec["id"]):
        raise UniversalPackageError("invalid v2 runtime id")
    if spec["kind"] not in ("python-venv", "none"):
        raise UniversalPackageError("invalid runtime kind")
    if not isinstance(spec["python"], str) or not re.fullmatch(r"3\.(?:11|12|13|14)|none", spec["python"]):
        raise UniversalPackageError("invalid runtime Python version")
    if spec["platform"] not in ("windows-x64", "linux-x64", "macos-arm64", "any"):
        raise UniversalPackageError("invalid runtime platform")
    if spec["accelerator"] not in ("cpu", "cuda", "directml", "none"):
        raise UniversalPackageError("invalid runtime accelerator")
    if spec["source"] not in ("reuse-only", "recipe-only", "bundled-wheels"):
        raise UniversalPackageError("invalid runtime source")
    if spec["install_policy"] not in ("reuse-only", "reuse-or-create"):
        raise UniversalPackageError("invalid runtime install policy")
    lock = spec["lockfile"]
    if spec["source"] == "reuse-only":
        if lock is not None or spec["install_policy"] != "reuse-only":
            raise UniversalPackageError("reuse-only package cannot declare an installer")
    elif (spec["install_policy"] != "reuse-or-create"
          or not isinstance(lock, str) or _path(lock) != lock
          or not lock.startswith("runtime/locks/")
          or lock.casefold() not in files or files[lock.casefold()]["size"] > MAX_METADATA):
        raise UniversalPackageError("v2 runtime requires verified lock")
    if spec["kind"] == "none" and (spec["source"] != "reuse-only" or
                                   spec["python"] != "none" or
                                   spec["accelerator"] != "none"):
        raise UniversalPackageError("runtime-free model cannot install dependencies")
    if spec["kind"] == "python-venv" and spec["python"] == "none":
        raise UniversalPackageError("Python runtime needs its version")


def _capabilities(manifest: dict, files: dict[str, dict]) -> None:
    kind = manifest["package"]["kind"]
    cap = manifest["capabilities"]
    if not isinstance(cap, dict):
        raise UniversalPackageError("invalid v2 native capabilities")
    if kind == "tts":
        if set(cap) != {"language", "sample_rate", "voices"}:
            raise UniversalPackageError("TTS capabilities required")
        if (cap["language"] not in ("th", "en", "multi", "zh")
            or type(cap["sample_rate"]) is not int
            or not 8_000 <= cap["sample_rate"] <= 96_000):
            raise UniversalPackageError("unsupported voice sample rate/language")
        if not isinstance(cap["voices"], list) or not 1 <= len(cap["voices"]) <= 64:
            raise UniversalPackageError("invalid v2 voice list")
        ids = set()
        for voice in cap["voices"]:
            if not isinstance(voice, dict) or set(voice) != {"id", "label", "asset"}:
                raise UniversalPackageError("invalid voice entry")
            if (not isinstance(voice["id"], str) or not _VOICE.fullmatch(voice["id"])
                or voice["id"] in ids or not isinstance(voice["label"], str)
                or not 1 <= len(voice["label"]) <= 110 or
                not isinstance(voice["asset"], str) or
                _path(voice["asset"]).casefold() not in files):
                raise UniversalPackageError("invalid native v2 voice asset")
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
        raise UniversalPackageError("expected native Universal .vwmodel v2 (no v1 bridge)")
    pkg = value["package"]
    if (not isinstance(pkg, dict) or set(pkg) != {
        "id", "version", "kind", "title", "languages",
    } or not isinstance(pkg["id"], str) or not _ID.fullmatch(pkg["id"])):
        raise UniversalPackageError("invalid v2 package identity")
    if not isinstance(pkg["version"], str) or not _VERSION.fullmatch(pkg["version"]):
        raise UniversalPackageError("invalid v2 version")
    if pkg["kind"] not in _KINDS or not isinstance(pkg["title"], str) or not 1 <= len(pkg["title"]) <= 120:
        raise UniversalPackageError("invalid v2 package kind/title")
    langs = pkg["languages"]
    if (not isinstance(langs, list) or not 1 <= len(langs) <= 64
        or any(not isinstance(s, str) or not _LANGUAGE.fullmatch(s) for s in langs)
        or len(set(langs)) != len(langs)):
        raise UniversalPackageError("invalid v2 languages")
    adapter = value["adapter"]
    if (not isinstance(adapter, dict) or set(adapter) != {"id", "api_version", "trust"}
        or not isinstance(adapter["id"], str) or not _ADAPTER.fullmatch(adapter["id"])
        or type(adapter["api_version"]) is not int or adapter["api_version"] != 1
        or adapter["trust"] not in ("builtin", "external")):
        raise UniversalPackageError("invalid v2 adapter identity")
    files = _index(value["files"])
    if (value["assets"] != "manifest-assets.json" or value["rights"] != "legal/rights.json"
        or value["assets"] not in files or value["rights"] not in files
        or files[value["assets"]]["size"] > MAX_METADATA
        or files[value["rights"]]["size"] > MAX_METADATA):
        raise UniversalPackageError("v2 package needs hashed assets and rights metadata")
    _runtime(value["runtime"], files)
    _capabilities(value, files)
    for row in files.values():
        name = row["path"]
        ext = PurePosixPath(name).suffix.lower()
        if ext == ".whl" and (value["runtime"]["source"] != "bundled-wheels"
                              or not name.startswith("runtime/wheels/")):
            raise UniversalPackageError("unapproved wheel material")
        # Never load arbitrary pickle/PyTorch legacy serialization.
        if name.endswith((".pt", ".pth", ".pkl", ".py", ".dll", ".exe")):
            raise UniversalPackageError("executable or pickle asset forbidden in native v2")
    return value


def _small_json(folder: Path, name: str) -> dict:
    file = folder.joinpath(*PurePosixPath(name).parts)
    if not file.is_file() or file.is_symlink() or file.stat().st_size > MAX_METADATA:
        raise UniversalPackageError("invalid v2 metadata location/size")
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise UniversalPackageError("invalid v2 JSON metadata") from exc
    if not isinstance(data, dict):
        raise UniversalPackageError("v2 metadata must be an object")
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
        raise UniversalPackageError("v2 asset index mismatch")
    rights = _small_json(folder, manifest["rights"])
    if set(rights) != {"license", "source"}:
        raise UniversalPackageError("v2 rights/provenance metadata required")
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
        raise UniversalPackageError("invalid v2 rights declaration")
    lock_path = manifest["runtime"]["lockfile"]
    if lock_path:
        lock = _small_json(folder, lock_path)
        if (set(lock) != {"requirements", "wheels"}
            or not isinstance(lock["requirements"], list) or not isinstance(lock["wheels"], list)
            or len(lock["requirements"]) > 100 or len(lock["wheels"]) > MAX_FILES):
            raise UniversalPackageError("invalid v2 runtime lock")
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
            raise UniversalPackageError("v2 wheels and lock disagree")
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
    """Validate a v2-native model against a known built-in worker contract.

    The resulting descriptor is constructed from v2 capabilities in memory.
    There is no v1 manifest, migration or dependency on the v1 validator.
    """
    trusted = _trusted_adapter(manifest)
    if trusted is None:
        return None
    kind, runtime_id, required, sample_rate = trusted
    if manifest["runtime"]["id"] != runtime_id:
        raise UniversalPackageError("v2 adapter/runtime mismatch")
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
        "format_version": 2,
    }


def engine_id_for(manifest: dict) -> str:
    """Stable native v2 engine identity, independent of legacy packages."""
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


def _runtime_python_abi(manifest: dict, root: Path = ROOT) -> str | None:
    """Read an existing *worker* environment, never assume Core's Python ABI."""
    runtime_id = manifest["runtime"]["id"]
    folder = (Path(root) / "runtime" /
              ("ai-envs" if runtime_id == "m2m100" else "engine-envs") /
              runtime_id)
    config = folder / "pyvenv.cfg"
    try:
        if not config.is_file() or config.is_symlink():
            return None
        if not config.resolve(strict=True).is_relative_to(folder.resolve(strict=True)):
            return None
        if config.stat().st_size > 8192:
            return "invalid"
        lines = config.read_text(encoding="utf-8").splitlines()
        for key in ("version_info", "version"):
            for line in lines:
                label, sep, value = line.partition("=")
                if sep and label.strip().lower() == key:
                    match = re.match(r"\s*(3\.\d+)(?:\.|\s|$)", value)
                    return match.group(1) if match else "invalid"
    except (OSError, UnicodeError):
        return "invalid"
    return None


def runtime_compatibility(manifest: dict, *, root: Path = ROOT) -> str:
    """Return an actionable reason without installing or executing anything."""
    rt = manifest["runtime"]
    trusted = _trusted_adapter(manifest)
    if trusted is None:
        return "adapter-not-approved"
    if rt["id"] != trusted[1]:
        return "runtime-id-mismatch"
    if not platform_compatible(manifest):
        return "platform-incompatible"
    if rt["kind"] != "python-venv":
        return "runtime-kind-unsupported"
    if rt["accelerator"] != "cpu":
        return "accelerator-unsupported"
    if rt["source"] != "reuse-only":
        return "runtime-recipe-pending"
    abi = _runtime_python_abi(manifest, root)
    if abi is not None and abi != rt["python"]:
        return "python-abi-mismatch"
    return "compatible"


def activation_compatible(manifest: dict, root: Path = ROOT) -> bool:
    # A missing runtime is installable separately; mismatched installed
    # runtime environments are not eligible for synthesis.
    return runtime_compatibility(manifest, root=root) == "compatible"


def runtime_fingerprint(manifest: dict) -> str:
    validate_manifest(manifest)
    rt = manifest["runtime"]
    index = {r["path"]: r["sha256"] for r in manifest["files"]}
    record = {**rt, "lock_sha256": index.get(rt["lockfile"], ""),
              "adapter_id": manifest["adapter"]["id"],
              "adapter_api_version": manifest["adapter"]["api_version"]}
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _base(root: Path, kind: str) -> Path:
    return Path(root) / "models" / "universal" / "v2" / kind


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


def package_status(manifest: dict, *, root: Path = ROOT, folder: Path | None = None) -> dict:
    from .runtime_registry import inventory
    native = native_adapter_profile(manifest, folder) if folder else None
    reason = runtime_compatibility(manifest, root=root)
    allow = reason == "compatible" and native is not None
    ready = False
    if allow:
        entry = next((p for p in inventory(root)
                      if p["id"] == manifest["runtime"]["id"]), None)
        ready = bool(entry and entry["ready"])
        if not ready:
            reason = "runtime-not-installed"
    rights = _small_json(folder, manifest["rights"]) if folder else {}
    cap = manifest["capabilities"]
    return {
        "package_id": manifest["package"]["id"], "version": manifest["package"]["version"],
        "title": manifest["package"]["title"], "model_kind": manifest["package"]["kind"],
        "format_version": 2, "engine_adapter": manifest["adapter"]["id"],
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
        raise UniversalPackageError("select a native Universal .vwmodel v2")
    with zipfile.ZipFile(source) as bundle:
        members = bundle.infolist()
        if (not 3 <= len(members) <= MAX_FILES + 1
            or members[0].filename != "manifest.json"
            or members[0].file_size > MAX_MANIFEST
            or len({m.filename.casefold() for m in members}) != len(members)):
            raise UniversalPackageError("invalid v2 ZIP member list")
        try:
            manifest = validate_manifest(json.loads(bundle.read(members[0]).decode("utf-8")))
        except (ValueError, UnicodeError) as exc:
            raise UniversalPackageError("malformed native v2 manifest") from exc
        index = _index(manifest["files"])
        if {m.filename.casefold() for m in members} != set(index) | {"manifest.json"}:
            raise UniversalPackageError("v2 archive files disagree with manifest")
        for item in members:
            if (item.is_dir() or item.flag_bits & 1 or
                stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK):
                raise UniversalPackageError("links, directories and encrypted ZIP forbidden")
            if item.filename == "manifest.json":
                continue
            row = index[item.filename.casefold()]
            if (item.filename != row["path"] or item.file_size != row["size"]
                or not item.compress_size or item.file_size > item.compress_size * 1500):
                raise UniversalPackageError("v2 ZIP contains unsafe/compressed asset")
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
            raise UniversalPackageError("this v2 package identity is already installed")
        if (base.is_symlink() or target.parent.is_symlink()
            or not base.resolve().is_relative_to(root.resolve())):
            raise UniversalPackageError("symlinked model destination forbidden")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.parent.resolve().is_relative_to(root.resolve()):
            raise UniversalPackageError("redirected model destination forbidden")
        stage = Path(tempfile.mkdtemp(prefix=".install-v2-", dir=target.parent))
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
                                raise UniversalPackageError("v2 asset exceeds declared size")
                            digest.update(chunk)
                            dst.write(chunk)
                    if amount != row["size"] or digest.hexdigest() != row["sha256"]:
                        raise UniversalPackageError("v2 asset SHA-256 mismatch")
            _validate_assets(stage, manifest)
            native_adapter_profile(manifest, stage)
            (stage / "manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            if target.exists():
                raise UniversalPackageError("v2 package was installed concurrently")
            stage.rename(target)
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
                "format_version": 2,
                "runtime_status": "runtime-not-executed",
                "activation_supported": activation_compatible(manifest),
            }
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def remove_model_package(package_id: str, version: str, *, root: Path = ROOT) -> bool:
    if (not isinstance(package_id, str) or not _ID.fullmatch(package_id)
        or not isinstance(version, str) or not _VERSION.fullmatch(version)):
        raise UniversalPackageError("invalid v2 package removal identity")
    with _LOCK:
        for manifest, folder in installed_packages(root):
            if manifest["package"]["id"] == package_id and manifest["package"]["version"] == version:
                if (folder.is_symlink()
                    or not folder.resolve().is_relative_to(_base(root, manifest["package"]["kind"]).resolve())):
                    raise UniversalPackageError("unmanaged or redirected v2 model directory")
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
                    with (folder / row["path"]).open("rb") as stream:
                        if hashlib.file_digest(stream, "sha256").hexdigest() != row["sha256"]:
                            raise UniversalPackageError("modified v2 model asset; refusing deletion")
                shutil.rmtree(folder)
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
        raise UniversalPackageError("v2 output already exists; refusing overwrite")
    if output.resolve().is_relative_to(source.resolve()):
        raise UniversalPackageError("v2 output cannot be inside source assets")
    for row in manifest["files"]:
        file = source.joinpath(*PurePosixPath(row["path"]).parts)
        if (not _is_contained_file(source, row["path"])
            or file.stat().st_size != row["size"]):
            raise UniversalPackageError("missing, redirected or symlinked v2 source asset")
        with file.open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != row["sha256"]:
                raise UniversalPackageError("v2 source SHA-256 mismatch")
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
