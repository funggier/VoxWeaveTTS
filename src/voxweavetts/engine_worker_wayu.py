"""Wayu Paxa NC inference, restricted to vetted local model weight files.

All heavy PyTorch imports and model deserialization occur inside this isolated
worker. The externally selectable model ID resolves only to an installed,
SHA-verified, data-only .vwmodel package. No arbitrary file paths are accepted.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .personal_wayu_engine import (
    ENGINE_ID as PERSONAL_ENGINE_ID, MODEL_DIR, SAMPLE_RATE, VOICES, assets_ready,
)


def _verified_package_path(engine_id: str) -> Path:
    from .universal_model_packages import engine_id_for, native_tts_packages
    for manifest, folder in native_tts_packages():
        if (manifest["engine_adapter"] == "wayu-nc-v1"
                and engine_id_for(manifest) == engine_id):
            return folder
    raise ValueError("unknown or untrusted NC model package")


def _check_pinned_weights(model_dir: Path) -> None:
    """Reject altered serialized PyTorch weights before calling torch.load."""
    from .wayu_native_trust import PINNED_ASSETS
    for name, expected in PINNED_ASSETS.items():
        path = model_dir / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Wayu NC package weight asset is missing or a link")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("Wayu NC package weights do not match pinned upstream")


class WayuBackend:
    sample_rate = SAMPLE_RATE

    def __init__(self, model_dir: Path = MODEL_DIR) -> None:
        self.model_dir = Path(model_dir)
        self._native_by_dir: dict[Path, Any] = {}

    def synthesize(self, text: str, *, voice_id: str, speed: float,
                   seed: int, engine_id: str | None = None) -> bytes:
        if voice_id not in dict(VOICES):
            raise ValueError("unknown voice")
        if engine_id is None or engine_id == PERSONAL_ENGINE_ID:
            folder, is_package = self.model_dir, False
        else:
            folder, is_package = _verified_package_path(engine_id), True
        folder = folder.resolve()
        if not assets_ready(folder):
            raise RuntimeError("local model assets are unavailable")

        if folder not in self._native_by_dir:
            # .pth/.pt checkpoints may contain Python pickle objects. A newly
            # installed archive cannot supply executable code, and its original
            # model files are independently pinned to upstream SHA-256 here.
            if is_package:
                _check_pinned_weights(folder)
            from wayu_tts import ThaiTTS
            native = ThaiTTS.from_pretrained(folder, device="cpu")
            if native.sample_rate != SAMPLE_RATE:
                raise RuntimeError("unexpected sample rate")
            self._native_by_dir[folder] = native

        import numpy as np
        audio = np.asarray(
            self._native_by_dir[folder](text, voice=voice_id, speed=speed, seed=seed),
            dtype=np.float32,
        )
        if audio.ndim != 1 or not audio.size or not np.isfinite(audio).all():
            raise ValueError("invalid synthesizer output")
        return (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
