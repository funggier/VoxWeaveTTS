"""Pinned MakHam Paradee built-in v3 model identity.

The engine id stays 'makham-paradee-cpu' even when its model is installed as a
removable .vwmodel v3. Model files never inject executable code.
"""
from __future__ import annotations

import hashlib
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
    """Only the verified v3 MakHam package may activate the bundled voice.

    Old v1/v2 weights remain untouched on disk, but are never loaded.
    """
    if disabled_marker(root).exists():
        return None
    native = Path(root) / "models" / "universal" / "v3" / "tts" / PACKAGE_ID / PACKAGE_VERSION
    if native.is_dir() and not native.is_symlink():
        from .universal_model_packages import _installed_manifest
        verified = _installed_manifest(native)
        if (verified is not None and verified["adapter"]["id"] == ADAPTER
            and _verified_pinned_weights(native)):
            return native
    return None
