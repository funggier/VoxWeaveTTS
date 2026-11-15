"""Trusted Kokoro-82M v1.0 ONNX CPU adapter for data-only .vwmodel packages.

The package contains ONNX and voice weights only.  Language is determined by
the selected *voice*, never by an untrusted script from the package.
"""
from __future__ import annotations

from threading import RLock
from pathlib import Path

from .processing import InputError

# Kokoro v1.0 language/voice families. The Chinese ONNX variant is a
# separate checkpoint, so the v1.0 package deliberately omits z* voices.
VOICE_LANGUAGES = {
    "a": "en-us", "b": "en-gb", "e": "es",
    "f": "fr-fr", "h": "hi", "i": "it", "j": "ja", "p": "pt-br",
}
LANGUAGE_CODES = {
    "a": "en", "b": "en", "e": "es", "f": "fr",
    "h": "hi", "i": "it", "j": "ja", "p": "pt",
}
VOICE_CATALOG = (
    ("af_heart", "English (US) - Heart"),
    ("af_bella", "English (US) - Bella"),
    ("am_michael", "English (US) - Michael"),
    ("am_puck", "English (US) - Puck"),
    ("bf_emma", "English (UK) - Emma"),
    ("bm_george", "English (UK) - George"),
    ("ef_dora", "Spanish - Dora"),
    ("em_alex", "Spanish - Alex"),
    ("ff_siwis", "French - Siwis"),
    ("hf_alpha", "Hindi - Alpha"),
    ("hm_omega", "Hindi - Omega"),
    ("if_sara", "Italian - Sara"),
    ("im_nicola", "Italian - Nicola"),
    ("jf_alpha", "Japanese - Alpha"),
    ("jf_nezumi", "Japanese - Nezumi"),
    ("jm_kumo", "Japanese - Kumo"),
    ("pf_dora", "Portuguese - Dora"),
    ("pm_alex", "Portuguese - Alex"),
)
RATE = 24_000
_INFERENCE_LOCK = RLock()


def runtime_ready() -> bool:
    try:
        from importlib.util import find_spec
        return all(find_spec(name) is not None
                   for name in ("kokoro_onnx", "onnxruntime", "numpy",
                                "phonemizer", "espeakng_loader"))
    except (ImportError, ValueError):
        return False


class KokoroOnnxEngine:
    """ONNX/CPU, fixed v1.0 model, one selectable voice per utterance."""

    sample_rate = RATE

    def __init__(self, *, model_dir: Path, engine_id: str,
                 voices: tuple[tuple[str, str], ...]) -> None:
        self.id = engine_id
        self.model_dir = Path(model_dir)
        self.voices = {identifier for identifier, _ in voices}
        self.voice_id = voices[0][0]
        self._native = None
        self._japanese_g2p = None

    def select_voice(self, voice_id: str) -> None:
        if voice_id not in self.voices or voice_id[0] not in VOICE_LANGUAGES:
            raise InputError("unsupported Kokoro voice")
        self.voice_id = voice_id

    def _japanese_phonemes(self, text: str) -> str:
        """Use Kokoro's Japanese frontend; eSpeak spells kanji as letter names."""
        from .speech import EngineUnavailable, SpeechFailure
        if self._japanese_g2p is None:
            try:
                from misaki import ja
                self._japanese_g2p = ja.JAG2P()
            except (ImportError, OSError, RuntimeError) as exc:
                raise EngineUnavailable(
                    "Japanese Kokoro G2P is unavailable: install misaki[ja]==0.8.0 "
                    "and unidic-lite==1.0.8 in the active Python runtime"
                ) from exc
        try:
            phonemes, _ = self._japanese_g2p(text)
        except Exception as exc:
            raise SpeechFailure("Japanese Kokoro G2P failed to parse text") from exc
        if not isinstance(phonemes, str) or not phonemes.strip():
            raise SpeechFailure("Japanese Kokoro G2P produced no phonemes")
        return phonemes

    def generate(self, text: str, speed: float) -> bytes:
        if not isinstance(text, str) or not text.strip():
            return b""
        if not runtime_ready():
            from .speech import EngineUnavailable
            raise EngineUnavailable("Kokoro ONNX CPU dependencies are unavailable")
        with _INFERENCE_LOCK:
            if self._native is None:
                onnx_file = self.model_dir / "kokoro-v1.0.int8.onnx"
                voices_file = self.model_dir / "voices-v1.0.bin"
                if not onnx_file.is_file() or not voices_file.is_file():
                    from .speech import EngineUnavailable
                    raise EngineUnavailable("Kokoro model weights are not installed")
                from kokoro_onnx import Kokoro
                self._native = Kokoro(str(onnx_file), str(voices_file))
            if self.voice_id[0] == "j":
                # The ONNX wrapper defaults to eSpeak, which reads kanji as
                # "Chinese letter"/"Japanese letter" even with lang="ja".
                # Misaki returns model-native phonemes; bypass eSpeak entirely.
                audio, sample_rate = self._native.create(
                    self._japanese_phonemes(text), voice=self.voice_id,
                    speed=float(speed), lang="ja", is_phonemes=True,
                )
            else:
                audio, sample_rate = self._native.create(
                    text, voice=self.voice_id, speed=float(speed),
                    lang=VOICE_LANGUAGES[self.voice_id[0]],
                )
            if sample_rate != self.sample_rate:
                raise RuntimeError("Kokoro output rate mismatch")
            from .speech import _float32_to_pcm
            return _float32_to_pcm(audio)
