"""Optional, local-only Wayu Paxa Edge Thai/English TTS.

The MODEL WEIGHTS are CC BY-NC 4.0. The Apache-2.0 inference
code does not change that restriction. Never bundle weights with a
commercial-cleared app or download models implicitly during synthesis.
"""
from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
from threading import RLock
from typing import Any

from .engine_contract import EngineInfo
from .processing import InputError

ENGINE_ID = "personal-nc-wayu-paxa-edge-cpu"
MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "personal" / "wayu-paxa-tts-edge"
SAMPLE_RATE = 24_000
VOICES = (
    ("f_teen_bright", "หญิงวัยรุ่น — สดใส มีชีวิตชีวา"),
    ("f_young_bright", "หญิงวัยหนุ่มสาว — สดใส"),
    ("f_young_clear", "หญิงวัยหนุ่มสาว — ชัดเจน"),
    ("f_young_warm", "หญิงวัยหนุ่มสาว — อบอุ่น"),
    ("f_mid_clear", "หญิงวัยกลางคน — ชัดเจน"),
    ("f_mid_warm", "หญิงวัยกลางคน — นุ่มนวล"),
    ("f_elderly_soft", "หญิงวัยสูงอายุ — อ่อนโยน"),
    ("f_elderly_low", "หญิงวัยสูงอายุ — ทุ้มต่ำ"),
    ("m_teen_bright", "ชายวัยรุ่น — สดใส"),
    ("m_young_clear", "ชายวัยหนุ่ม — ชัดเจน"),
    ("m_mid_warm", "ชายวัยกลางคน — อบอุ่น"),
    ("m_elderly_deep", "ชายวัยสูงอายุ — ทุ้มลึก"),
)
_LOCK = RLock()
_NATIVE: Any = None
_NATIVE_DIR: Path | None = None


def assets_ready(model_dir: Path = MODEL_DIR) -> bool:
    """Check a fixed, offline model directory without loading PyTorch weights."""
    try:
        return (
            (model_dir / "config.json").is_file()
            and (model_dir / "model.pth").is_file()
            and (model_dir / "model.pth").stat().st_size > 20_000_000
            and all((model_dir / "voices" / (voice + ".pt")).is_file()
                    for voice, _ in VOICES)
        )
    except OSError:
        return False


def runtime_ready() -> bool:
    try:
        return all(find_spec(name) is not None for name in
                   ("wayu_tts", "kokoro", "tltk", "torch", "numpy",
                    "pandas", "sklearn", "spacy", "en_core_web_sm",
                    "misaki", "pythainlp"))
    except (ImportError, ValueError):
        return False


def descriptor() -> EngineInfo:
    from .speech import _built_in_dsp_flags
    capabilities = {
        "speech": True, "speed": True, "seed_control": True,
        "voice_cloning": False, "pitch": False, "formant": False,
        "expressiveness": False, "streaming": False, "phoneme_dictionary": False,
    }
    capabilities.update(_built_in_dsp_flags())
    return EngineInfo(
        id=ENGINE_ID,
        label="[NC / NonCommercial] Wayu Paxa Edge — ไทย/อังกฤษ 12 เสียง",
        language="th", voice_id="f_young_warm", voice_options=VOICES,
        sample_rate=SAMPLE_RATE,
        assets_ready=assets_ready(), runtime_ready=runtime_ready(),
        capabilities=capabilities, commercial_status="hold",
    )


class PersonalWayuEngine:
    """Reuse the model in memory for short live-chat utterances, safely serialized."""

    id = ENGINE_ID
    sample_rate = SAMPLE_RATE

    def __init__(self, seed: int = 100, *, model_dir: Path = MODEL_DIR) -> None:
        self.seed = seed
        self.model_dir = Path(model_dir)
        self.voice_id = "f_young_warm"

    def select_voice(self, voice_id: str) -> None:
        if voice_id not in dict(VOICES):
            raise InputError("unknown Wayu NC voice")
        self.voice_id = voice_id

    def generate(self, text: str, speed: float) -> bytes:
        if not isinstance(text, str) or not text.strip():
            return b""
        if not assets_ready(self.model_dir):
            from .speech import EngineUnavailable
            raise EngineUnavailable("Wayu NC model assets missing from models/personal")
        if not runtime_ready():
            from .speech import EngineUnavailable
            raise EngineUnavailable("Wayu NC Python dependencies or English spaCy model unavailable")
        global _NATIVE, _NATIVE_DIR
        from .speech import _float32_to_pcm
        with _LOCK:
            model_path = self.model_dir.resolve()
            if _NATIVE is None or _NATIVE_DIR != model_path:
                from wayu_tts import ThaiTTS
                # Pass a verified directory, NOT a HF repo id: offline inference.
                _NATIVE = ThaiTTS.from_pretrained(model_path, device="cpu")
                if _NATIVE.sample_rate != SAMPLE_RATE:
                    _NATIVE = None
                    _NATIVE_DIR = None
                    from .speech import SpeechFailure
                    raise SpeechFailure("Wayu NC sample rate differs from adapter")
                _NATIVE_DIR = model_path
            audio = _NATIVE(text, voice=self.voice_id, speed=float(speed), seed=self.seed)
            return _float32_to_pcm(audio)
