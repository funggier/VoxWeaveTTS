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
_EXTENSIONS = frozenset((".onnx", ".json", ".npy", ".bin", ".txt", ".md", ".fst", ".utf8", ".pt", ".pth"))
_ADAPTERS = frozenset(("vachana-onnx-v1", "fastthaig2p-kokoro-v1", "kokoro-onnx-v1", "sherpa-supertonic-v1", "sherpa-melo-zh-v1", "wayu-nc-v1", "makham-paradee-onnx-v1"))
# Only these pinned, original upstream Wayu weights may be deserialized by the
# trusted PyTorch worker. A .vwmodel manifest is untrusted data, and torch.load
# on altered .pth/.pt assets could otherwise execute arbitrary pickle code.
_WAYU_PINNED_SHA256 = {
    "config.json": "82bdfb49f558c262a2eeebc40c78758e48a90ef2d56ac8bd0678aac9d33a089e",
    "model.pth": "eb26ac6f7da4c651389b28793d0ab59be8fa7e3e7cc5d350278b2a8d0a4d7370",
    "voices/f_elderly_low.pt": "52bb2fe51db2f16b2ec45cccdd94c60207a307291aeefa43daf9d7da64534fd6",
    "voices/f_elderly_soft.pt": "8a9d0c9fa39548458d28f36395e8b6688171fcf52705cad84b6a4e2261d9ec62",
    "voices/f_mid_clear.pt": "60c27208ac13d62027833bad1e9e27728b60b3312b56deffb21b135d248e560a",
    "voices/f_mid_warm.pt": "70e581e609475023c208de252a1261be5b521ba710f67e2c81a9c12572555f37",
    "voices/f_teen_bright.pt": "8deb6ea18d3a031d3c9e0ee95cd6c821b17b176dab066eed8cd1edec0fe94210",
    "voices/f_young_bright.pt": "4a31d0aebe0f933b44338cb4ee7c3d1d02712734c01fa9adf1bc63b8f8504e22",
    "voices/f_young_clear.pt": "ac1b78525ed2e3ebd21ddc19736307b5ad30f4036bfd46e679b2b80ab1364f56",
    "voices/f_young_warm.pt": "62ae8e533e82d6bd51965af58be171d95298c135a389a08d77af467632080253",
    "voices/m_elderly_deep.pt": "0852a4b10a02422c70dcdee702a698cf48ee0135c84b0bdfce609d4a2d31485d",
    "voices/m_mid_warm.pt": "61fef6ffa19cee7c6d539fb2039bd5bac57647cb649e630f82f2b0d167d096b4",
    "voices/m_teen_bright.pt": "8a57087e0e1de3cb2d96cc2020a730301cc06c244449518b7975c0b89674153d",
    "voices/m_young_clear.pt": "86154fe8cf060516dde67fe9ce81fd11ef3e550b3bab66db0fd42ea46cae3623",
}
_WAYU_SOURCE_REVISION = "8196688df56a8d08ccfa186505343adff412ab6b"
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
        # Both TTS and AI/Translation packages deliberately use .vwmodel.
        # Route by the bounded, declared data format in the ZIP manifest,
        # not by filename or client-controlled paths. Each dedicated installer
        # still performs its complete independent security/integrity checks.
        if Path(selected).suffix.lower() != ".vwmodel":
            raise ModelPackageError("choose a .vwmodel package")
        with zipfile.ZipFile(selected) as archive:
            members = archive.infolist()
            if (not members or members[0].filename != "manifest.json"
                    or members[0].file_size > MAX_MANIFEST):
                raise ModelPackageError("invalid model package manifest")
            try:
                format_name = json.loads(archive.read(members[0]))["format"]
            except (ValueError, KeyError, TypeError, UnicodeError) as exc:
                raise ModelPackageError("invalid model package manifest") from exc
        if format_name == FORMAT:
            return install_model_package(selected)
        from .ai_model_packages import FORMAT as AI_FORMAT, install_model_package as install_ai
        if format_name == AI_FORMAT:
            return install_ai(selected)
        raise ModelPackageError("unsupported .vwmodel format")
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
    # Built-in adapter identity survives reinstallation, model removal and
    # restoring a .vwmodel. Saved language routes and presets never change.
    if manifest["engine_adapter"] == "makham-paradee-onnx-v1":
        from .makham_package import ENGINE_ID
        return ENGINE_ID
    return "model-" + manifest["package_id"] + "-" + manifest["version"].replace(".", "_")


def display_model_title(manifest: dict[str, Any]) -> str:
    """Mark confirmed NC model weights in all installed-model listings.

    Unreviewed or merely restricted licenses are not necessarily NonCommercial;
    do not mislabel OpenRAIL or review_required as NC.
    """
    title = manifest["title"]
    spdx = str(manifest["license"]["spdx"]).upper().replace("_", "-")
    noncommercial = bool(re.search(r"(?<![A-Z])NC(?![A-Z])", spdx)) or "NONCOMMERCIAL" in spdx
    return "[NC / NonCommercial] " + title if noncommercial and not title.upper().startswith(("[NC]", "[NC ", "[NONCOMMERCIAL]")) else title


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
    adapter = manifest["engine_adapter"]
    expected_rate = {"vachana-onnx-v1": 22_050, "sherpa-melo-zh-v1": 44_100, "sherpa-supertonic-v1": 44_100}.get(adapter, 24_000)
    expected_language = ("multi" if adapter in ("kokoro-onnx-v1", "sherpa-supertonic-v1")
                         else "zh" if adapter == "sherpa-melo-zh-v1" else "th")
    if manifest["language"] != expected_language or type(manifest["sample_rate"]) is not int or manifest["sample_rate"] != expected_rate:
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
    if (not isinstance(voices, list) or not 1 <= len(voices) <= 64
        or (manifest["engine_adapter"] == "fastthaig2p-kokoro-v1" and len(voices) != 1)):
        raise ModelPackageError("model needs one or more voices")
    seen_voices: set[str] = set()
    seen_paths: set[str] = set()
    if adapter == "makham-paradee-onnx-v1":
        from .makham_package import (PACKAGE_ID as MAK_ID, PACKAGE_VERSION as MAK_VERSION,
                                     SOURCE_REVISION as MAK_REVISION, UPSTREAM as MAK_UPSTREAM,
                                     PINNED_ASSETS as MAK_ASSETS)
        if (manifest["package_id"] != MAK_ID
            or manifest["version"] != MAK_VERSION
            or manifest["license"]["spdx"] != "Apache-2.0"
            or manifest["license"]["review_status"] not in ("review_required", "cleared")
            or manifest["source"] != {"url": MAK_UPSTREAM, "revision": MAK_REVISION}
            or len(voices) != 1 or not isinstance(voices[0], dict)
            or voices[0].get("id") != "paradee_thai"
            or voices[0].get("asset") != "paradee_thai_int8.onnx"):
            raise ModelPackageError("MakHam must use the vetted original assets and Apache-2.0 license")
    if adapter == "wayu-nc-v1":
        from .personal_wayu_engine import VOICES as WAYU_VOICES
        if (any(not isinstance(v, dict) or "id" not in v for v in voices)
            or [v["id"] for v in voices] != [voice_id for voice_id, _ in WAYU_VOICES]
            or manifest["package_id"] != "wayu-paxa-edge-nc"
            or manifest["version"] != "1.0.0"
            or manifest["license"]["spdx"] != "CC-BY-NC-4.0"
            or manifest["license"]["review_status"] != "hold"
            or manifest["source"]["url"] != "https://huggingface.co/wayu-ai/wayu-paxa-tts-edge"
            or manifest["source"]["revision"] != _WAYU_SOURCE_REVISION):
            raise ModelPackageError("Wayu NC package must retain the vetted upstream version, voices and license")
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
        if adapter == "makham-paradee-onnx-v1":
            if asset != "paradee_thai_int8.onnx":
                raise ModelPackageError("MakHam must use original model weights")
        elif adapter == "wayu-nc-v1":
            if asset != "voices/" + identifier + ".pt":
                raise ModelPackageError("Wayu NC voice must use its pinned original asset")
        elif adapter == "kokoro-onnx-v1":
            if asset != "voices-v1.0.bin" or not re.fullmatch(r"[abefhijpz][fm]_[a-z][a-z0-9_]*", identifier):
                raise ModelPackageError("unsupported Kokoro voice asset or identifier")
        elif adapter == "sherpa-supertonic-v1":
            from .sherpa_voice_engine import SUPER_LANGUAGES
            if asset != "voice.bin" or not re.fullmatch(r"[a-z]{2}_s[01]", identifier) or identifier[:2] not in SUPER_LANGUAGES:
                raise ModelPackageError("unsupported Supertonic voice mapping")
        elif adapter == "sherpa-melo-zh-v1":
            if asset != "model.onnx" or identifier != "zh_melo":
                raise ModelPackageError("unsupported Chinese Melo voice mapping")
        else:
            required_extension = ".onnx" if adapter == "vachana-onnx-v1" else ".npy"
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
        if adapter == "makham-paradee-onnx-v1" and path in MAK_ASSETS:
            if entry["sha256"] != MAK_ASSETS[path]:
                raise ModelPackageError("MakHam model asset differs from the verified original")
        if Path(path).suffix.lower() in (".pth", ".pt") and adapter != "wayu-nc-v1":
            raise ModelPackageError("serialized PyTorch weights are only permitted for vetted Wayu NC packages")
        if adapter == "wayu-nc-v1" and path in _WAYU_PINNED_SHA256:
            if entry["sha256"] != _WAYU_PINNED_SHA256[path]:
                raise ModelPackageError("Wayu NC PyTorch model differs from vetted upstream")
        elif adapter == "wayu-nc-v1" and Path(path).suffix.lower() in (".pth", ".pt"):
            raise ModelPackageError("unexpected executable-serialization asset")
        file_index[path.lower()] = entry
        total += entry["size"]
    required_files = (tuple(MAK_ASSETS) if adapter == "makham-paradee-onnx-v1" else
                      tuple(_WAYU_PINNED_SHA256) if adapter == "wayu-nc-v1" else
                      ("speaker_config.json",) if adapter == "vachana-onnx-v1" else
                      ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin") if adapter == "kokoro-onnx-v1" else
                      ("duration_predictor.int8.onnx", "text_encoder.int8.onnx", "vector_estimator.int8.onnx", "vocoder.int8.onnx", "tts.json", "unicode_indexer.bin", "voice.bin") if adapter == "sherpa-supertonic-v1" else
                      ("model.onnx", "tokens.txt", "lexicon.txt") if adapter == "sherpa-melo-zh-v1" else
                      ("config.json", "kokoro_thai.onnx"))
    if adapter == "makham-paradee-onnx-v1" and set(file_index) != {
        *MAK_ASSETS, "legal/license.txt", "legal/attribution.md",
    }:
        raise ModelPackageError("MakHam requires only pinned weights and legal attribution")
    if adapter == "wayu-nc-v1" and not {"readme.md", "legal/license.txt", "legal/attribution.md", "legal/acceptable-use.txt"} <= set(file_index):
        raise ModelPackageError("Wayu NC needs complete attribution and acceptable-use notices")
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
        file_info = {row["path"].lower(): row for row in manifest["files"]}
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
            if (base == PACKAGES_DIR
                    and manifest["engine_adapter"] == "makham-paradee-onnx-v1"):
                from .makham_package import clear_disabled_marker
                clear_disabled_marker()
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
        if manifest["engine_adapter"] == "makham-paradee-onnx-v1":
            expected = {"manifest.json"} | {row["path"] for row in manifest["files"]}
            actual = set()
            for entry in target.rglob("*"):
                if entry.is_symlink():
                    raise ModelPackageError("MakHam package contains symlink; refusing deletion")
                if entry.is_file():
                    name = entry.relative_to(target).as_posix()
                    actual.add(name)
                    if name != "manifest.json":
                        row = next((f for f in manifest["files"] if f["path"] == name), None)
                        if row is None or hashlib.sha256(entry.read_bytes()).hexdigest() != row["sha256"]:
                            raise ModelPackageError("MakHam package contains modified or unknown files")
            if actual != expected:
                raise ModelPackageError("MakHam package files are incomplete; refusing deletion")
        shutil.rmtree(target)
        if (base == PACKAGES_DIR
                and manifest["engine_adapter"] == "makham-paradee-onnx-v1"):
            from .makham_package import disable_legacy_fallback
            disable_legacy_fallback()
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
    # Reproducible model packages: ZIP entries use fixed metadata rather
    # than workstation timestamps. This preserves published SHA-256 values
    # across subsequent Portable builds from the same pinned model assets.
    def member(name: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        return info

    with zipfile.ZipFile(output, "w", allowZip64=True, compression=zipfile.ZIP_DEFLATED, compresslevel=3) as zipped:
        zipped.writestr(member("manifest.json"), json.dumps(manifest, ensure_ascii=False, indent=2),
                        compress_type=zipfile.ZIP_DEFLATED, compresslevel=3)
        for entry in manifest["files"]:
            with (source / entry["path"]).open("rb") as input_stream:
                with zipped.open(member(entry["path"]), "w", force_zip64=True) as stored:
                    shutil.copyfileobj(input_stream, stored, length=_CHUNK)
    return output



def _legal_paths(source: Path) -> list[str]:
    """Optional, data-only legal notices included in signed-by-manifest ZIP."""
    notices = ("license.txt", "notice.txt", "attribution.md")
    return ["legal/" + name for name in notices
            if (source / "legal" / name).is_file()]


def _stage_legal_notices(stage: Path, pack_name: str) -> None:
    """Include verbatim upstream notices and separately explained provenance."""
    origin = ROOT / "model-packs" / pack_name
    if not origin.is_dir():
        raise ModelPackageError("missing model package legal notices")
    for name in ("LICENSE.txt", "NOTICE.txt", "ATTRIBUTION.md"):
        file = origin / name
        if not file.is_file():
            if name == "NOTICE.txt" and pack_name == "vachana":
                continue
            raise ModelPackageError("missing legal notice: " + str(file))
        # Lowercase ZIP member names for compatibility with the published
        # v0.4.2 portable installer (which looks up normalized path keys).
        out = stage / "legal" / name.lower()
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, out)


def _hardlink_or_copy(original_file: Path, target: Path) -> None:
    if not original_file.is_file():
        raise ModelPackageError("missing local model asset: " + str(original_file))
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(original_file, target)
    except OSError:
        shutil.copy2(original_file, target)


def create_makham_manifest(source: Path) -> dict[str, Any]:
    """Signed-by-sha metadata for original MakHam Paradee INT8 + Apache notices."""
    from .makham_package import (PACKAGE_ID, PACKAGE_VERSION, UPSTREAM,
                                 SOURCE_REVISION, PINNED_ASSETS, ADAPTER)
    source = Path(source)
    files = []
    for name in (*PINNED_ASSETS, "legal/license.txt", "legal/attribution.md"):
        file = source.joinpath(*PurePosixPath(name).parts)
        if not file.is_file() or file.is_symlink():
            raise ModelPackageError("missing original MakHam asset or license: " + name)
        with file.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        files.append({"path": name, "size": file.stat().st_size, "sha256": digest})
    return validate_manifest({
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "package_id": PACKAGE_ID, "version": PACKAGE_VERSION,
        "title": "MakHam Paradee Thai / English INT8 (CPU ONNX)",
        "engine_adapter": ADAPTER, "language": "th", "sample_rate": 24000,
        "voices": [{"id": "paradee_thai", "label": "Paradee",
                    "asset": "paradee_thai_int8.onnx"}],
        "files": files,
        "license": {
            "spdx": "Apache-2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0",
            "attribution": (
                "MakHamTTS by PyThaiNLP / Wannaphong Phatthiyaphaibun. "
                "Paradee distillation by Sahil Mahendrakar. "
                "Original ONNX weights and config unchanged; model source: "
                "https://huggingface.co/pythainlp/MakHamTTS. "
                "Training dataset pythainlp/MakHamTTS-dataset declares CC BY 4.0."
            ),
            "review_status": "review_required",
        },
        "source": {"url": UPSTREAM, "revision": SOURCE_REVISION},
        "dependencies": ["pythaitts==1.0.0", "onnxruntime"],
    })


def pack_local_makham(source: Path, output: Path) -> Path:
    """Export a restorable .vwmodel from the exact byte-pinned local weights."""
    from .makham_package import PINNED_ASSETS
    source = Path(source)
    for name, expected in PINNED_ASSETS.items():
        file = source / name
        if not file.is_file() or file.is_symlink():
            raise ModelPackageError("missing verified MakHam weight: " + name)
        with file.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise ModelPackageError("MakHam weight differs from the verified original")
    cache = ROOT / "cache" / "temp"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pack-makham-", dir=cache) as temp:
        staged = Path(temp)
        for name in PINNED_ASSETS:
            _hardlink_or_copy(source / name, staged / name)
        license_source = ROOT / "docs" / "third-party" / "MAKHAM_APACHE-2.0.txt"
        if not license_source.is_file():
            license_source = ROOT / "model-packs" / "fastthaig2p" / "LICENSE.txt"
        if not license_source.is_file():
            raise ModelPackageError("full Apache-2.0 license text is unavailable")
        legal = staged / "legal"
        legal.mkdir(parents=True)
        shutil.copy2(license_source, legal / "license.txt")
        (legal / "attribution.md").write_text(
            "# MakHam Paradee — attribution and modification notice\n\n"
            "Authors: PyThaiNLP / Wannaphong Phatthiyaphaibun; "
            "Paradee distillation framework by Sahil Mahendrakar.\n"
            "Original model: https://huggingface.co/pythainlp/MakHamTTS\n"
            "Model license: Apache-2.0 — "
            "https://www.apache.org/licenses/LICENSE-2.0\n"
            "Training dataset: https://huggingface.co/datasets/pythainlp/"
            "MakHamTTS-dataset (declares CC BY 4.0).\n"
            "Changes: original INT8 ONNX weights and config are unchanged; "
            "they have only been repackaged into a data-only VoxWeaveTTS "
            ".vwmodel with this attribution and license.\n"
            "No affiliation or endorsement by upstream maintainers is implied.\n",
            encoding="utf-8",
        )
        return make_package(staged, create_makham_manifest(staged), output)


def create_vachana_manifest(source: Path) -> dict[str, Any]:
    """Produce metadata for locally downloaded Vachana voices.

    License declaration follows pinned upstream model card; training-data and
    speaker-rights provenance has not been independently audited.
    """
    source = Path(source)
    names = ("th_f_1", "th_f_2", "th_m_1", "th_m_2")
    assets = ["speaker_config.json"] + ["voices/" + name + ".onnx" for name in names] + _legal_paths(source)
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

    Upstream repo declares Apache-2.0; Som TTS dataset declares CC BY 4.0.
    Attribution notices ship in the resulting archive. Full provenance
    remains review_required (not commercial-cleared by VoxWeaveTTS).
    """
    source = Path(source)
    names = ("config.json", "kokoro_thai.onnx", "voices/thai_som.npy", *_legal_paths(source))
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


def pack_local_vachana(source: Path, output: Path) -> Path:
    """Repack pinned upstream ONNX files plus machine-readable license notes."""
    temp_base = ROOT / "cache" / "temp"
    temp_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="voxweavetts-vachana-pack-", dir=temp_base,
    ) as temp:
        stage = Path(temp)
        for name in (
            "speaker_config.json", "voices/th_f_1.onnx",
            "voices/th_f_2.onnx", "voices/th_m_1.onnx", "voices/th_m_2.onnx",
        ):
            _hardlink_or_copy(Path(source) / name, stage / name)
        _stage_legal_notices(stage, "vachana")
        return make_package(stage, create_vachana_manifest(stage), output)


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
            _hardlink_or_copy(Path(source) / original, stage / target_name)
        _stage_legal_notices(stage, "fastthaig2p")
        return make_package(stage, create_fastthai_manifest(stage), output)


def create_kokoro_manifest(source: Path) -> dict[str, Any]:
    """Kokoro v1.0 INT8 model and voice pack, pinned to upstream ONNX assets."""
    from .kokoro_engine import VOICE_CATALOG
    source = Path(source)
    files = []
    for name in ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin", "legal/license.txt",
                 "legal/attribution.md"):
        path = source / name
        if not path.is_file():
            raise ModelPackageError("missing Kokoro asset: " + name)
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        files.append({"path": name, "size": path.stat().st_size, "sha256": digest})
    return validate_manifest({
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "package_id": "kokoro-multilingual-int8", "version": "1.0.0",
        "title": "Kokoro 82M Multilingual INT8 (CPU)",
        "engine_adapter": "kokoro-onnx-v1", "language": "multi",
        "sample_rate": 24000,
        "voices": [{"id": identifier, "label": label, "asset": "voices-v1.0.bin"}
                   for identifier, label in VOICE_CATALOG],
        "files": files,
        "license": {
            "spdx": "Apache-2.0",
            "url": "https://huggingface.co/hexgrad/Kokoro-82M",
            "attribution": "Kokoro-82M by hexgrad. ONNX runtime/quantization by thewh1teagle; see embedded legal/attribution.md. Review exact voice and training rights independently.",
            "review_status": "review_required",
        },
        "source": {
            "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1",
            "revision": "model-files-v1.1 (Kokoro v1.0 INT8, voices-v1.0.bin)",
        },
        "dependencies": ["kokoro-onnx==0.6.0", "onnxruntime", "numpy",
                         "phonemizer", "espeakng-loader"],
    })


def pack_local_kokoro(source: Path, output: Path) -> Path:
    """Pack previously verified original ONNX and ZIP-encoded voice files."""
    source = Path(source)
    temp_base = ROOT / "cache" / "temp"
    temp_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vox-kokoro-pack-", dir=temp_base) as temp:
        stage = Path(temp)
        for name in ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin",
                     "legal/license.txt", "legal/attribution.md"):
            _hardlink_or_copy(source / name, stage / name)
        return make_package(stage, create_kokoro_manifest(stage), output)


def create_wayu_manifest(source: Path) -> dict[str, Any]:
    """Only the SHA-pinned Wayu Edge 12-voice original, never arbitrary pickles."""
    from .personal_wayu_engine import VOICES as WAYU_VOICES
    source = Path(source)
    names = [
        *_WAYU_PINNED_SHA256,
        "README.md", "legal/license.txt", "legal/attribution.md",
        "legal/acceptable-use.txt",
    ]
    files = []
    for name in names:
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise ModelPackageError("Wayu NC package missing file: " + name)
        with path.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        files.append({"path": name, "size": path.stat().st_size, "sha256": sha})
    return validate_manifest({
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "package_id": "wayu-paxa-edge-nc", "version": "1.0.0",
        "title": "Wayu Paxa Edge - Thai / English - 12 voices",
        "engine_adapter": "wayu-nc-v1", "language": "th",
        "sample_rate": 24_000,
        "voices": [{"id": ident, "label": ident.replace("_", " "),
                    "asset": "voices/" + ident + ".pt"}
                   for ident, _ in WAYU_VOICES],
        "files": files,
        "license": {
            "spdx": "CC-BY-NC-4.0",
            "url": "https://creativecommons.org/licenses/by-nc/4.0/",
            "attribution": (
                "Wayu Research; Kunat Pipatanakul, Potsawee Manakul, "
                "Warit Sirichotedumrong, Sittipong Sripaisarnmongkol, "
                "Pakorn Nathong, Phatrasek Jirabovonvisut. "
                "Original weights unchanged; repackaged for VoxWeaveTTS. "
                "NonCommercial only. Upstream acceptable-use policy applies."
            ),
            "review_status": "hold",
        },
        "source": {
            "url": "https://huggingface.co/wayu-ai/wayu-paxa-tts-edge",
            "revision": _WAYU_SOURCE_REVISION,
        },
        "dependencies": ["wayu-nc-v1"],
    })


def pack_local_wayu(source: Path, output: Path) -> Path:
    """Local opt-in NC repack, preserving upstream weights and notices intact."""
    source = Path(source)
    cache = ROOT / "cache" / "temp"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pack-wayu-nc-", dir=cache) as temp:
        stage = Path(temp)
        for name in (*_WAYU_PINNED_SHA256, "README.md"):
            _hardlink_or_copy(source / name, stage / name)
        legal = stage / "legal"
        legal.mkdir()
        (legal / "license.txt").write_text(
            "Wayu Paxa Edge original weights and voices: CC BY-NC 4.0 International.\\n"
            "Full legally controlling license: https://creativecommons.org/licenses/by-nc/4.0/legalcode.en\\n"
            "You may share and adapt for NonCommercial purposes only; give attribution, "
            "link the license, and indicate modifications. No extra restrictions.\\n",
            encoding="utf-8",
        )
        (legal / "attribution.md").write_text(
            "# Attribution and modification notice\\n\\n"
            "Original work: Wayu-Paxa-TTS-Edge (Wayu Research / wayu-ai).\\n"
            "Original weights and 12 voice assets: CC BY-NC 4.0.\\n"
            "Source: https://huggingface.co/wayu-ai/wayu-paxa-tts-edge\\n"
            f"Pinned source revision: {_WAYU_SOURCE_REVISION}\\n"
            "Authors: Kunat Pipatanakul, Potsawee Manakul, "
            "Warit Sirichotedumrong, Sittipong Sripaisarnmongkol, "
            "Pakorn Nathong, Phatrasek Jirabovonvisut.\\n"
            "Paper: Building and Evaluating Fixed-Voice Thai TTS from Synthetic Speech\\n"
            "https://arxiv.org/abs/2609.03502\\n\\n"
            "Modification: Model weights, configuration and voice files are byte-for-byte "
            "unchanged from the pinned upstream revision. Only a data-only VoxWeaveTTS "
            ".vwmodel ZIP/manifest and additional legal attribution notes were added.\\n"
            "No affiliation or endorsement by Wayu Research is implied. "
            "Not commercially licensed. No warranties.\\n",
            encoding="utf-8",
        )
        (legal / "acceptable-use.txt").write_text(
            "Wayu Research acceptable-use policy also applies to this model and outputs.\\n"
            "https://www.wayuresearch.org/terms#acceptable-use\\n"
            "Do not impersonate, deceive, defraud or misrepresent synthetic voice "
            "as an authentic recording. Do not infringe rights or use in unlawful "
            "or safety-critical applications. Follow the full upstream terms.\\n",
            encoding="utf-8",
        )
        return make_package(stage, create_wayu_manifest(stage), output)


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
    makham = actions.add_parser("pack-makham")
    from .makham_package import ARCHIVE_NAME as MAK_ARCHIVE_NAME
    makham.add_argument("--source", type=Path,
                        default=ROOT / "models" / "makham-paradee")
    makham.add_argument("--output", type=Path,
                        default=ROOT / "dist" / "ModelPackages" / MAK_ARCHIVE_NAME)
    wayu = actions.add_parser("pack-wayu")
    wayu.add_argument("--source", type=Path,
                      default=ROOT / "models" / "personal" / "wayu-paxa-tts-edge")
    wayu.add_argument("--output", type=Path, default=ROOT / "dist" / "ModelPackages" /
                      "VoxWeaveTTS-Wayu-Paxa-Edge-Thai-English-12Voices-NC-v1.0.0.vwmodel")
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
            print("Built", pack_local_vachana(args.source, args.output))
            print("Rights status: review_required - see embedded legal/attribution.md")
        elif args.action == "pack-fastthai":
            print("Built", pack_local_fastthai(args.source, args.output))
            print("Rights status: review_required - refer to included Apache/CC BY notices")
        elif args.action == "pack-makham":
            print("Built", pack_local_makham(args.source, args.output))
            print("Rights: Apache-2.0 with full license and training data attribution")
        elif args.action == "pack-wayu":
            print("Built", pack_local_wayu(args.source, args.output))
            print("Rights: CC BY-NC 4.0 (NonCommercial only); upstream weights unmodified")
    except (ModelPackageError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(2, "Model package operation failed: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
