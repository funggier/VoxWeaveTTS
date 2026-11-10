"""Shared WAV renderer and current local ONNX adapters.

Engine-neutral registration is in engine_contract.py. The existing adapters
remain here for backward compatibility and will be split into packages later.
"""
from __future__ import annotations

import io
import threading
import wave
from pathlib import Path
from typing import Any

from .processing import InputError
from .engine_contract import EngineInfo, EngineRegistry, VoiceEngine
from .voice_controls import apply_voice_controls, control_schema, ffmpeg_path, validate_controls

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models" / "fastthaig2p"
ASSETS = {"model": "kokoro_thai.onnx", "voicepack": "thai_som.npy", "config": "config.json"}
MIN_SIZES = {"model": 320_000_000, "voicepack": 500_000, "config": 100}
ENGINE_ID = "fastthaig2p-cpu"
PARADEE_ENGINE_ID = "makham-paradee-cpu"
PARADEE_DIR = ROOT / "models" / "makham-paradee"
SAMPLE_RATE = 24_000
MAX_SPEECH_CHARS = 500
MAX_PLAN_SEGMENTS = 50
MAX_WAV_BYTES = 32_000_000
DEFAULT_SEED = 100
MAX_SEED = 2_147_483_647


class EngineUnavailable(Exception):
    """Engine dependency or model pack is not available."""


class SpeechFailure(Exception):
    """Synthesis failed without exposing private input in the API."""


def assets_ready() -> bool:
    try:
        return all(
            (MODEL_DIR / name).is_file() and
            (MODEL_DIR / name).stat().st_size >= MIN_SIZES[key]
            for key, name in ASSETS.items()
        )
    except OSError:
        return False


def paradee_assets_ready() -> bool:
    try:
        return (
            (PARADEE_DIR / "paradee_thai_int8.onnx").is_file()
            and (PARADEE_DIR / "paradee_thai_int8.onnx").stat().st_size > 8_000_000
            and (PARADEE_DIR / "config.json").is_file()
        )
    except OSError:
        return False


def _built_in_dsp_flags() -> dict[str, bool]:
    ready = bool(ffmpeg_path())
    return {
        "gain": True,
        "pitch_post_dsp": ready,
        "bass_post_dsp": ready,
        "treble_post_dsp": ready,
        "formant_preserve_on_pitch": ready,
        "independent_formant_shift": False,
    }


def _fast_descriptor() -> EngineInfo:
    info = engine_info()
    info.capabilities.update(_built_in_dsp_flags())
    return info


def _paradee_descriptor() -> EngineInfo:
    capabilities = {
        "speech": True, "speed": True, "seed_control": False,
        "voice_cloning": False, "pitch": False, "formant": False,
        "expressiveness": False, "streaming": False,
        "phoneme_dictionary": False,
    }
    capabilities.update(_built_in_dsp_flags())
    return EngineInfo(
        id=PARADEE_ENGINE_ID,
        label="MakHam Paradee Thai INT8 (CPU ONNX)",
        language="th",
        voice_id="paradee_thai",
        sample_rate=SAMPLE_RATE,
        assets_ready=paradee_assets_ready(),
        runtime_ready=runtime_ready(),
        capabilities=capabilities,
    )


def list_engine_info() -> list[EngineInfo]:
    """Enumerate registered adapters without loading model weights."""
    return engine_registry().list()


def get_engine_info(engine_id: str) -> EngineInfo:
    return engine_registry().get(engine_id)


def runtime_ready() -> bool:
    try:
        import importlib.util
        return all(importlib.util.find_spec(module) for module in
                   ("pythaitts", "onnxruntime", "numpy"))
    except (ImportError, ValueError):
        return False


def engine_info() -> EngineInfo:
    return EngineInfo(
        id=ENGINE_ID,
        label="FastThaiG2P / Kokoro Thai (CPU ONNX)",
        language="th",
        voice_id="thai_som",
        sample_rate=SAMPLE_RATE,
        assets_ready=assets_ready(),
        runtime_ready=runtime_ready(),
        capabilities={
            "speech": True, "speed": True, "seed_control": True, "voice_cloning": False,
            "pitch": False, "formant": False, "expressiveness": False,
            "streaming": False, "phoneme_dictionary": False,
        },
    )


def _float32_to_pcm(raw: Any) -> bytes:
    """Clip waveform floats to valid signed 16-bit PCM, with no wrapper."""
    import numpy as np

    values = np.asarray(raw, dtype=np.float32)
    if values.ndim != 1 or values.size == 0:
        raise SpeechFailure("engine returned invalid mono audio")
    if not np.isfinite(values).all():
        raise SpeechFailure("engine returned non-finite audio")
    return (np.clip(values, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


def validate_seed(seed: Any) -> int:
    """Keep user-chosen ONNX random seeds within a reproducible integer range."""
    if type(seed) is not int or not (0 <= seed <= MAX_SEED):
        raise InputError(f"seed must be an integer from 0 to {MAX_SEED}")
    return seed


class FastThaiG2PEngine:
    """A new ONNX session is created per speech job for reproducible inference.

    ONNX random operators advance their generator state on each session.run().
    Merely calling onnxruntime.set_seed() before each generate() on a reused
    session does NOT rewind that state. Seed before *session construction*.
    The session and its seed are scoped to this one render_wav invocation.
    """

    id = ENGINE_ID
    sample_rate = SAMPLE_RATE
    _lock = threading.Lock()

    def __init__(self, seed: int = DEFAULT_SEED):
        self.seed = validate_seed(seed)
        self._native: Any = None

    def _get_native(self) -> Any:
        if self._native is None:
            if not assets_ready():
                raise EngineUnavailable(
                    "FastThaiG2P model files are missing; run scripts/Install-ThaiEngine.ps1"
                )
            if not runtime_ready():
                raise EngineUnavailable(
                    "PyThaiTTS ONNX dependencies are not installed in the selected Python runtime"
                )
            import onnxruntime as ort
            from pythaitts.pretrained.fastthaig2p.tts import TTS
            # IMPORTANT: seed the runtime BEFORE creating the ONNX session.
            ort.set_seed(self.seed)
            self._native = TTS(
                model_path=MODEL_DIR / ASSETS["model"],
                voicepack_path=MODEL_DIR / ASSETS["voicepack"],
                config_path=MODEL_DIR / ASSETS["config"],
                device="cpu",
                intra_op_threads=4,
                speed=1.0,
            )
        return self._native

    def generate(self, text: str, speed: float) -> bytes:
        if not isinstance(text, str) or not text.strip():
            return b""
        # ORT's session seed initialization is process-wide. Serialize both
        # session creation and model execution for the M1 CPU preview.
        with type(self)._lock:
            native = self._get_native()
            native.speed = speed
            return _float32_to_pcm(native.generate(text))


class MakHamParadeeEngine:
    """Local, single-voice CPU ONNX adapter (model is bundled with PyThaiTTS)."""

    id = PARADEE_ENGINE_ID
    sample_rate = SAMPLE_RATE
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._native: Any = None

    def generate(self, text: str, speed: float) -> bytes:
        if not isinstance(text, str) or not text.strip():
            return b""
        with type(self)._lock:
            if self._native is None:
                if not paradee_assets_ready():
                    raise EngineUnavailable(
                        "MakHam Paradee assets missing in models/makham-paradee"
                    )
                if not runtime_ready():
                    raise EngineUnavailable("PyThaiTTS ONNX dependencies unavailable")
                from pythaitts.pretrained.makham.paradee_tts import MakHamTTSParadee
                self._native = MakHamTTSParadee(
                    model_path=PARADEE_DIR / "paradee_thai_int8.onnx",
                    config_path=PARADEE_DIR / "config.json",
                    intra_op_threads=4, speed=1.0,
                )
            self._native.speed = speed
            return _float32_to_pcm(self._native.generate(text))


_REGISTRY_LOCK = threading.RLock()
_REGISTRY: EngineRegistry | None = None


def engine_registry() -> EngineRegistry:
    """Return the explicit, extension-ready registry.

    A future model adapter registers an ID, descriptor factory and engine
    factory. It does not need to modify the HTTP server or the WAV renderer.
    """
    global _REGISTRY
    with _REGISTRY_LOCK:
        if _REGISTRY is None:
            registry = EngineRegistry()
            registry.register(
                ENGINE_ID, describe=_fast_descriptor,
                create=lambda seed: FastThaiG2PEngine(seed=seed),
            )
            registry.register(
                PARADEE_ENGINE_ID, describe=_paradee_descriptor,
                create=lambda seed: MakHamParadeeEngine(),
            )
            _REGISTRY = registry
        return _REGISTRY


def create_voice_engine(engine_id: str, seed: int) -> VoiceEngine:
    return engine_registry().create(engine_id, seed)


def _chunks(text: str, limit: int = 110) -> list[str]:
    """Bound TTS text spans without silently dropping characters."""
    if not text:
        return []
    out: list[str] = []
    rest = text
    while len(rest) > limit:
        cut_at = max(rest.rfind(ch, 0, limit + 1) for ch in (" ", "\n", ".", "!", "?", "ฯ", "。", "،", "，"))
        if cut_at < max(10, limit // 3):
            cut_at = limit
        elif rest[cut_at] == " " or rest[cut_at] == "\n":
            cut_at += 1
        if cut_at <= 0:
            cut_at = limit
        out.append(rest[:cut_at])
        rest = rest[cut_at:]
    if rest:
        out.append(rest)
    return out


def validate_speech_request(plan: dict[str, Any], speed: float, voice_id: str,
                            engine_id: str = ENGINE_ID) -> None:
    if type(speed) not in (int, float) or not 0.6 <= speed <= 1.5:
        raise InputError("speed must be a number from 0.6 to 1.5")
    info = get_engine_info(engine_id)
    if voice_id != info.voice_id:
        raise InputError(f"engine {engine_id} supports only voice_id={info.voice_id}; voice cloning not supported")
    segments = plan.get("segments")
    if not isinstance(segments, list) or len(segments) > MAX_PLAN_SEGMENTS:
        raise InputError(f"speech plan must have at most {MAX_PLAN_SEGMENTS} segments")
    if sum(len(s["spoken_text"]) for s in segments) > MAX_SPEECH_CHARS:
        raise InputError(f"initial CPU speech API accepts up to {MAX_SPEECH_CHARS} spoken characters")


def render_wav(
    plan: dict[str, Any],
    *,
    speed: float = 1.0,
    voice_id: str = "thai_som",
    seed: int = DEFAULT_SEED,
    engine_id: str = ENGINE_ID,
    voice_controls: dict[str, Any] | None = None,
    engine: VoiceEngine | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Synthesize segments as a single WAV, retaining precise segment offsets.

    The segment timeline is based on generated samples, not playback events.
    An external playback coordinator must still provide real-time subtitle sync.
    """
    validate_speech_request(plan, speed, voice_id, engine_id)
    seed = validate_seed(seed)
    controls = validate_controls(voice_controls)
    # A fresh model instance per speech job prevents its random state from
    # drifting between otherwise identical utterances.
    engine = engine if engine is not None else create_voice_engine(engine_id, seed=seed)
    rate = engine.sample_rate
    if rate < 8_000 or rate > 96_000:
        raise SpeechFailure("unsupported engine sample rate")
    timeline: list[dict[str, Any]] = []
    pieces: list[bytes] = []
    frames = 0
    for segment in plan["segments"]:
        kind = segment["kind"]
        start_frame = frames
        if kind == "speech" and segment["spoken_text"].strip():
            for chunk in _chunks(segment["spoken_text"]):
                if chunk.strip():
                    audio = engine.generate(chunk, float(speed))
                    if len(audio) % 2:
                        raise SpeechFailure("engine emitted partial PCM sample")
                    if any((controls[k] != 0 for k in ("gain_db", "pitch_semitones", "bass_db", "treble_db"))):
                        audio = apply_voice_controls(audio, rate, controls)
                    frames += len(audio) // 2
                    pieces.append(audio)
        elif kind == "silence":
            silence_frames = round(rate * segment["silence_ms"] / 1000)
            pieces.append(b"\0\0" * silence_frames)
            frames += silence_frames
        elif kind not in ("speech", "skip"):
            raise SpeechFailure("unknown speech plan segment")
        if frames * 2 > MAX_WAV_BYTES:
            raise InputError("generated audio exceeds size limit")
        # Never echo original protected text. Only the display text is public.
        timeline.append({
            "kind": kind,
            "display_text": segment["display_text"],
            "source_start": segment["source_start"],
            "source_end": segment["source_end"],
            "start_ms": round(start_frame * 1000 / rate),
            "end_ms": round(frames * 1000 / rate),
        })
    if frames == 0:
        raise InputError("no speech or silence to render")
    audio_buffer = io.BytesIO()
    with wave.open(audio_buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        for piece in pieces:
            writer.writeframesraw(piece)
        writer.writeframes(b"")
    return audio_buffer.getvalue(), {
        "engine_id": engine.id,
        "voice_id": voice_id,
        "seed": seed if engine_id == ENGINE_ID else None,
        "voice_controls": controls,
        "sample_rate": rate,
        "duration_ms": round(frames * 1000 / rate),
        "segments": timeline,
    }