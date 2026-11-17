"""MakHam Paradee model assets, portable package identity and safe legacy removal.

The engine id stays 'makham-paradee-cpu' even when its model is installed as a
removable .vwmodel. No generic archive may provide executable Python modules.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ID = "makham-paradee"
PACKAGE_VERSION = "1.0.0"
ENGINE_ID = "makham-paradee-cpu"
ADAPTER = "makham-paradee-onnx-v1"
ARCHIVE_NAME = "VoxWeaveTTS-MakHam-Paradee-Thai-English-v1.0.0.vwmodel"
UPSTREAM = "https://huggingface.co/pythainlp/MakHamTTS"
SOURCE_REVISION = "pythaitts-1.0.0-local-int8-snapshot"
PINNED_ASSETS = {
    "paradee_thai_int8.onnx":
        "ad179a2c11b54b1185e84d9c0b759a57058588405620f12163084aaad250813d",
    "config.json":
        "1340bbfedc4871b311c8dedcd5cf85022f80773db120b1cd85883ecb1883ca43",
}


def disabled_marker(root: Path = ROOT) -> Path:
    # An explicit uninstall must not silently fall back to the old bundled
    # directory left behind by a pre-v2 portable update.
    return Path(root) / "data" / "settings" / ".makham-model-disabled"


def disable_legacy_fallback(root: Path = ROOT) -> None:
    marker = disabled_marker(root)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("MakHam model explicitly uninstalled; reinstall its .vwmodel to restore.\n", encoding="utf-8")


def clear_disabled_marker(root: Path = ROOT) -> None:
    disabled_marker(root).unlink(missing_ok=True)


def legacy_model_dir(root: Path = ROOT) -> Path:
    return Path(root) / "models" / "makham-paradee"


def packaged_model_dir(root: Path = ROOT) -> Path:
    return (Path(root) / "models" / "packages" / PACKAGE_ID / PACKAGE_VERSION)


def _verified_pinned_weights(folder: Path) -> bool:
    for name, digest in PINNED_ASSETS.items():
        path = folder / name
        if not path.is_file() or path.is_symlink():
            return False
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                return False
    return True


def active_model_dir(root: Path = ROOT) -> Path | None:
    """Prefer pinned native v2 assets; older assets are never deleted here."""
    native = Path(root) / "models" / "universal" / "v2" / "tts" / PACKAGE_ID / PACKAGE_VERSION
    if native.is_dir() and not native.is_symlink():
        from .universal_model_packages import _installed_manifest
        verified = _installed_manifest(native)
        if (verified is not None and verified["adapter"]["id"] == ADAPTER
            and _verified_pinned_weights(native)):
            return native
    # An explicit v2 uninstall must not resurrect a leftover v1 package.
    if disabled_marker(root).exists():
        return None
    folder = packaged_model_dir(root)
    manifest = folder / "manifest.json"
    try:
        if (not folder.is_symlink() and manifest.is_file()
            and not manifest.is_symlink() and manifest.stat().st_size < 24576):
            from .model_packages import validate_manifest
            value = validate_manifest(json.loads(manifest.read_text(encoding="utf-8")))
            if value["engine_adapter"] == ADAPTER and all(
                (folder / name).is_file() and not (folder / name).is_symlink()
                and (folder / name).stat().st_size > 1000
                for name in PINNED_ASSETS
            ):
                # ONNX is data, but only exact vetted bits should be accepted
                # as the bundled identity, even after user-side file changes.
                if _verified_pinned_weights(folder):
                    return folder
    except (OSError, ValueError, TypeError):
        pass
    if disabled_marker(root).exists():
        return None
    legacy = legacy_model_dir(root)
    if not legacy.is_symlink() and all(
        (legacy / name).is_file() and
        (legacy / name).stat().st_size > (8_000_000 if name.endswith(".onnx") else 1000)
        for name in PINNED_ASSETS
    ):
        return legacy
    return None


def legacy_present(root: Path = ROOT) -> bool:
    """Old builds use unpackaged model weights at models/makham-paradee."""
    return active_model_dir_legacy(root)


def active_model_dir_legacy(root: Path = ROOT) -> bool:
    folder = legacy_model_dir(root)
    try:
        return bool(not folder.is_symlink() and all(
            (folder / name).is_file() and
            (folder / name).stat().st_size > (8_000_000 if name.endswith(".onnx") else 1000)
            for name in PINNED_ASSETS
        ))
    except OSError:
        return False


def _pinned_legacy(root: Path) -> bool:
    folder = legacy_model_dir(root)
    if not active_model_dir_legacy(root) or set(p.name for p in folder.iterdir()) != set(PINNED_ASSETS):
        return False
    for name, digest in PINNED_ASSETS.items():
        file = folder / name
        if file.is_symlink():
            return False
        with file.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                return False
    return True


def recovery_archive(root: Path = ROOT) -> Path:
    return Path(root) / "models" / "recovery-packages" / ARCHIVE_NAME


def remove_legacy_model(*, root: Path = ROOT) -> bool:
    """Explicit user action only; produce a verified local recovery ZIP first.

    Never deletes modified assets, arbitrary files, symlinks, other packages,
    the trusted engine/worker, presets, settings or shared runtimes.
    """
    root = Path(root)
    folder = legacy_model_dir(root)
    if not folder.exists():
        return False
    if not _pinned_legacy(root):
        raise ValueError("unrecognized MakHam legacy model files; refusing deletion")
    archive = recovery_archive(root)
    if not archive.is_file():
        from .model_packages import pack_local_makham
        pack_local_makham(folder, archive)
    from .model_packages import validate_manifest
    import zipfile
    with zipfile.ZipFile(archive) as z:
        manifest = validate_manifest(json.loads(z.read("manifest.json")))
        if (manifest["package_id"] != PACKAGE_ID
            or manifest["version"] != PACKAGE_VERSION
            or z.testzip() is not None):
            raise ValueError("MakHam recovery archive failed verification")
    # This directory contains only two byte-pinned model files, not user data.
    # Avoid a Windows cached ONNX session holding a file open by requiring
    # the caller to stop the affected worker before reaching this operation.
    shutil.rmtree(folder)
    disable_legacy_fallback(root)
    return True
