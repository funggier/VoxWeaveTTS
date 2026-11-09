"""Model-backed speech rendering with real PCM silence and pluggable adapters.

Only FastThaiG2P ONNX on CPU is currently supported; it is a *fixed* Thai
voice (not a voice clone). External assets live outside Git in models/.
"""
from __future__ import annotations

import io
import re
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .processing import InputError

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models" / "fastthaig2p"
ASSETS = {"model": "kokoro_thai.onnx", "voicepack": "thai_som.npy", "config": "config.json"}
MIN_SIZES = {"model": 320_000_000, "voicepack": 500_000, "config": 100}
ENGINE_ID = "fastthaig2p-cpu"
SAMPLE_RATE = 24_000
MAX_SPEECH_CHARS = 500
MAX_PLAN_SEGMENTS = 50
MAX_WAV_BYTES = 32_000_000


class EngineUnavailable(Exception):
    """Engine dependency or model pack is not available."""


class SpeechFailure(Exception):
    """Synthesis failed without exposing private input in the API."""


class VoiceEngine(Protocol):
    id: str
    sample_rate: int

    def generate(self, text: str, speed: float) -> bytes:
        """Return mono signed 16-bit PCM bytes without a WAV header."""


@dataclass(frozen=True)
class EngineInfo:
    id: str
    label: str
    language: str
    voice_id: str
    sample_rate: int
    assets_ready: bool
    runtime_ready: bool
    capabilities: dict[str, bool]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "language": self.language,
            "voice_id": self.voice_id,
            "sample_rate": self.sample_rate,
            "assets_ready": self.assets_ready,
            "runtime_ready": self.runtime_ready,
            "capabilities": self.capabilities,
        }


def assets_ready() -> bool:
    try:
        return all(
            (MODEL_DIR / name).is_file() and
            (MODEL_DIR / name).stat().st_size >= MIN_SIZES[key]
            for key, name in ASSETS.items()
        )
    except OSError:
        return False


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
            "speech": True, "speed": True, "voice_cloning": False,
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


class FastThaiG2PEngine:
    id = ENGINE_ID
    sample_rate = SAMPLE_RATE
    _lock = threading.Lock()
    _native: Any = None

    @classmethod
    def _get_native(cls) -> Any:
        if cls._native is None:
            if not assets_ready():
                raise EngineUnavailable(
                    "FastThaiG2P model files are missing; run scripts/Install-ThaiEngine.ps1"
                )
            if not runtime_ready():
                raise EngineUnavailable(
                    "PyThaiTTS ONNX dependencies are not installed in the selected Python runtime"
                )
            from pythaitts.pretrained.fastthaig2p.tts import TTS
            cls._native = TTS(
                model_path=MODEL_DIR / ASSETS["model"],
                voicepack_path=MODEL_DIR / ASSETS["voicepack"],
                config_path=MODEL_DIR / ASSETS["config"],
                device="cpu",
                intra_op_threads=4,
                speed=1.0,
            )
        return cls._native

    def generate(self, text: str, speed: float) -> bytes:
        if not isinstance(text, str) or not text.strip():
            return b""
        # One shared model instance; don't mutate its speed concurrently.
        with type(self)._lock:
            native = type(self)._get_native()
            native.speed = speed
            return _float32_to_pcm(native.generate(text))


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


def validate_speech_request(plan: dict[str, Any], speed: float, voice_id: str) -> None:
    if type(speed) not in (int, float) or not 0.6 <= speed <= 1.5:
        raise InputError("speed must be a number from 0.6 to 1.5")
    if voice_id != "thai_som":
        raise InputError("this engine supports only voice_id=thai_som (not voice cloning)")
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
    engine: VoiceEngine | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Synthesize segments as a single WAV, retaining precise segment offsets.

    The segment timeline is based on generated samples, not playback events.
    An external playback coordinator must still provide real-time subtitle sync.
    """
    validate_speech_request(plan, speed, voice_id)
    engine = engine if engine is not None else FastThaiG2PEngine()
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
        "sample_rate": rate,
        "duration_ms": round(frames * 1000 / rate),
        "segments": timeline,
    }
