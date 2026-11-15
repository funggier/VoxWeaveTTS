"""Trusted offline sherpa-onnx adapters for data-only multilingual .vwmodel packs.

Chinese uses the MIT MeloTTS ONNX VITS conversion. Supertonic 3 is an
optional OpenRAIL-M model supporting 31 languages, including Korean.
Never download model files at inference time or execute code from a pack.
"""
from __future__ import annotations

from pathlib import Path
from threading import RLock

from .processing import InputError

SUPER_LANGUAGES = (
    "ar", "bg", "hr", "cs", "da", "nl", "en", "et", "fi", "fr",
    "de", "el", "hi", "hu", "id", "it", "ja", "ko", "lv", "lt",
    "pl", "pt", "ro", "ru", "sk", "sl", "es", "sv", "tr", "uk", "vi",
)
# 2 selectable speaker identities per language: <= 64 voices under v1 ABI.
SUPER_VOICES = tuple(
    (f"{lang}_s{sid}", f"{lang.upper()} · speaker {sid}")
    for lang in SUPER_LANGUAGES for sid in (0, 1)
)
SUPER_FILES = (
    "duration_predictor.int8.onnx", "text_encoder.int8.onnx",
    "vector_estimator.int8.onnx", "vocoder.int8.onnx",
    "tts.json", "unicode_indexer.bin", "voice.bin",
)
MELO_FILES = ("model.onnx", "tokens.txt", "lexicon.txt")
_LOCK = RLock()


def runtime_ready() -> bool:
    try:
        from importlib.util import find_spec
        return find_spec("sherpa_onnx") is not None and find_spec("numpy") is not None
    except (ImportError, ValueError):
        return False


class SherpaVoiceEngine:
    """Fixed ONNX model type, per-job voice/language and mono PCM16 output."""

    def __init__(self, *, model_dir: Path, engine_id: str, adapter: str,
                 voices: tuple[tuple[str, str], ...], sample_rate: int) -> None:
        if adapter not in ("sherpa-supertonic-v1", "sherpa-melo-zh-v1"):
            raise InputError("unsupported sherpa adapter")
        self.id = engine_id
        self.model_dir = Path(model_dir)
        self.adapter = adapter
        self.voices = {identifier for identifier, _ in voices}
        self.voice_id = voices[0][0]
        self.sample_rate = sample_rate
        self._native = None

    def select_voice(self, voice_id: str) -> None:
        if voice_id not in self.voices:
            raise InputError("unknown sherpa voice")
        if self.adapter == "sherpa-supertonic-v1":
            lang, sep, number = voice_id.partition("_s")
            if not sep or lang not in SUPER_LANGUAGES or number not in ("0", "1"):
                raise InputError("invalid multilingual voice language")
        elif voice_id != "zh_melo":
            raise InputError("invalid Chinese voice")
        self.voice_id = voice_id

    def _create_native(self):
        from .speech import EngineUnavailable
        if not runtime_ready():
            raise EngineUnavailable("sherpa-onnx CPU runtime is not installed")
        import sherpa_onnx as sherpa
        if self.adapter == "sherpa-supertonic-v1":
            if not all((self.model_dir / name).is_file() for name in SUPER_FILES):
                raise EngineUnavailable("Supertonic 3 model assets are missing")
            model = sherpa.OfflineTtsSupertonicModelConfig(
                duration_predictor=str(self.model_dir / SUPER_FILES[0]),
                text_encoder=str(self.model_dir / SUPER_FILES[1]),
                vector_estimator=str(self.model_dir / SUPER_FILES[2]),
                vocoder=str(self.model_dir / SUPER_FILES[3]),
                tts_json=str(self.model_dir / SUPER_FILES[4]),
                unicode_indexer=str(self.model_dir / SUPER_FILES[5]),
                voice_style=str(self.model_dir / SUPER_FILES[6]),
            )
            cfg = sherpa.OfflineTtsModelConfig(
                supertonic=model, num_threads=2, provider="cpu")
        else:
            if not all((self.model_dir / name).is_file() for name in MELO_FILES):
                raise EngineUnavailable("Chinese MeloTTS model assets are missing")
            cfg = sherpa.OfflineTtsModelConfig(
                vits=sherpa.OfflineTtsVitsModelConfig(
                    model=str(self.model_dir / "model.onnx"),
                    lexicon=str(self.model_dir / "lexicon.txt"),
                    tokens=str(self.model_dir / "tokens.txt"),
                ), num_threads=2, provider="cpu")
        config = sherpa.OfflineTtsConfig(model=cfg)
        if not config.validate():
            raise EngineUnavailable("sherpa TTS model configuration is invalid")
        return sherpa.OfflineTts(config)

    def generate(self, text: str, speed: float) -> bytes:
        if not isinstance(text, str) or not text.strip():
            return b""
        from .speech import SpeechFailure, _float32_to_pcm
        import sherpa_onnx
        with _LOCK:
            if self._native is None:
                self._native = self._create_native()
            if self.adapter == "sherpa-supertonic-v1":
                lang, _, sid = self.voice_id.partition("_s")
                config = sherpa_onnx.GenerationConfig()
                config.sid = int(sid)
                config.speed = float(speed)
                config.num_steps = 4
                # pybind11 exposes extra as a copy; assign the whole mapping.
                # Mutating config.extra["lang"] silently discards the language!
                config.extra = {"lang": lang}
                audio = self._native.generate(text, config)
            else:
                audio = self._native.generate(text, 0, float(speed))
            if audio.sample_rate != self.sample_rate:
                raise SpeechFailure(f"multilingual TTS output sample rate {audio.sample_rate} != {self.sample_rate}")
            if len(audio.samples) == 0:
                raise SpeechFailure("multilingual TTS returned empty audio")
            return _float32_to_pcm(audio.samples)
