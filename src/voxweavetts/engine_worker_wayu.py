"""Wayu Paxa NC inference loaded *only* inside its isolated worker process."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .personal_wayu_engine import MODEL_DIR, SAMPLE_RATE, VOICES, assets_ready


class WayuBackend:
    sample_rate = SAMPLE_RATE

    def __init__(self, model_dir: Path = MODEL_DIR) -> None:
        self.model_dir = Path(model_dir)
        self._native: Any = None

    def synthesize(self, text: str, *, voice_id: str, speed: float,
                   seed: int) -> bytes:
        if voice_id not in dict(VOICES):
            raise ValueError("unknown voice")
        if not assets_ready(self.model_dir):
            raise RuntimeError("local model assets are unavailable")
        if self._native is None:
            from wayu_tts import ThaiTTS
            # A checked Path is not a HuggingFace repo ID; no model download.
            self._native = ThaiTTS.from_pretrained(self.model_dir.resolve(), device="cpu")
            if self._native.sample_rate != SAMPLE_RATE:
                self._native = None
                raise RuntimeError("unexpected sample rate")
        import numpy as np
        audio = np.asarray(self._native(text, voice=voice_id, speed=speed, seed=seed),
                           dtype=np.float32)
        if audio.ndim != 1 or not audio.size or not np.isfinite(audio).all():
            raise ValueError("invalid synthesizer output")
        return (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
