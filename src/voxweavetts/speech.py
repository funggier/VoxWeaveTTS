"""Universal v4 speech renderer and plugin-only engine registry.

Actual TTS model code runs in each installed .vwmodel v4 Worker process.
No model-specific v3 adapter, legacy model directory or built-in model loader
is imported by the Core.
"""
from __future__ import annotations

import io
import math
import threading
import wave
from dataclasses import replace
from pathlib import Path
from typing import Any

from .processing import InputError
from .engine_contract import EngineInfo, EngineRegistry, VoiceEngine
from .voice_controls import apply_voice_controls, control_schema, ffmpeg_path, validate_controls

ROOT = Path(__file__).resolve().parents[2]
ENGINE_ID = "model-makham-paradee-1_0_0"
PARADEE_ENGINE_ID = ENGINE_ID  # historic API constant; points to v4 package ID
SAMPLE_RATE = 24_000
MAX_SPEECH_CHARS = 8_000
MAX_PLAN_SEGMENTS = 512
MAX_WAV_BYTES = 32_000_000
DEFAULT_SEED = 100
MAX_SEED = 2_147_483_647

class EngineUnavailable(Exception):
    """Engine dependency or model pack is not available."""


class SpeechFailure(Exception):
    """Synthesis failed without exposing private input in the API."""


class AllChunksFailed(SpeechFailure):
    """A speech plan produced no successful speech chunk."""


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


def validate_seed(seed: Any) -> int:
    """Keep user-chosen ONNX random seeds within a reproducible integer range."""
    if type(seed) is not int or not (0 <= seed <= MAX_SEED):
        raise InputError(f"seed must be an integer from 0 to {MAX_SEED}")
    return seed


_REGISTRY_LOCK = threading.RLock()
_REGISTRY: EngineRegistry | None = None


def _worker_aware_info(info: EngineInfo) -> EngineInfo:
    from .engine_provider_catalog import provider_for_engine
    from .engine_worker_gateway import gateway
    provider = provider_for_engine(info.id)
    if provider and gateway().available(provider.backend):
        return replace(info, runtime_ready=True)
    return info


def _missing_default_info() -> EngineInfo:
    """Advertise an uninstalled v4 starter model without loading legacy code."""
    return EngineInfo(
        id=ENGINE_ID, label="MakHam Paradee (install a v4 model package)",
        language="th", supported_languages=("th", "en"),
        voice_id="paradee_thai",
        voice_options=(("paradee_thai", "MakHam Paradee"),),
        sample_rate=SAMPLE_RATE, assets_ready=False, runtime_ready=False,
        capabilities={"speech": True, "speed": True, "seed_control": False,
                      "voice_cloning": False, **_built_in_dsp_flags()},
        commercial_status="review_required",
    )


def list_engine_info() -> list[EngineInfo]:
    """Only v4-installed workers plus a harmless unready default placeholder."""
    items = [_worker_aware_info(info) for info in engine_registry().list()]
    items.sort(key=lambda info: (info.id != ENGINE_ID, info.id))
    if not any(info.id == ENGINE_ID for info in items):
        items.insert(0, _missing_default_info())
    return items


def get_engine_info(engine_id: str) -> EngineInfo:
    if engine_id == ENGINE_ID:
        return next(info for info in list_engine_info() if info.id == ENGINE_ID)
    return _worker_aware_info(engine_registry().get(engine_id))


def engine_info() -> EngineInfo:
    """Default TTS package in new v4 installations."""
    return get_engine_info(ENGINE_ID)


def assets_ready() -> bool:
    from .universal_model_v4 import for_engine
    return for_engine(ENGINE_ID) is not None


def paradee_assets_ready() -> bool:
    return assets_ready()


def runtime_ready() -> bool:
    from .universal_model_v4 import for_engine, ready
    item = for_engine(ENGINE_ID)
    return bool(item and ready(ROOT, item[0]))


def refresh_engine_registry() -> None:
    global _REGISTRY
    with _REGISTRY_LOCK:
        _REGISTRY = None


def _register_external_providers(registry: EngineRegistry) -> None:
    """Discover executable workers only from installed v4 model packages."""
    from .engine_provider_catalog import all_providers
    from .engine_worker_gateway import gateway
    from .engine_worker_proxy import ProviderVoiceEngine
    existing = {info.id for info in registry.list()}
    for provider in all_providers().values():
        if provider.driver != "external" or provider.declared_engine is None:
            continue
        data = provider.declared_engine
        engine_id = data["engine_id"]
        if engine_id in existing:
            continue
        voices = tuple((entry["id"], entry["label"]) for entry in data["voices"])
        spdx = data["license"]["spdx"].upper().replace("_", "-")
        nc = "-NC" in spdx or "NONCOMMERCIAL" in spdx
        title = data["title"]
        if nc and not title.upper().startswith(("[NC]", "[NC ", "[NONCOMMERCIAL]")):
            title = "[NC / NonCommercial] " + title

        def describe(profile=provider, engine_id=engine_id, voices=voices,
                     title=title, data=data):
            capabilities = dict(data["capabilities"])
            capabilities.setdefault("speech", True)
            capabilities.setdefault("speed", True)
            for key in ("voice_cloning", "seed_control", "pitch",
                        "formant", "streaming", "expressiveness",
                        "phoneme_dictionary"):
                capabilities.setdefault(key, False)
            capabilities.update(_built_in_dsp_flags())
            return EngineInfo(
                id=engine_id, label=title, language=data["language"],
                voice_id=voices[0][0], voice_options=voices,
                supported_languages=tuple(data.get("supported_languages", ())),
                voice_language_map=dict(data.get("voice_language_map", {})),
                sample_rate=data["sample_rate"], assets_ready=True,
                runtime_ready=gateway().available(profile.backend),
                capabilities=capabilities,
                commercial_status=data.get("review_status", "declared"),
            )

        def create(seed: int, profile=provider, engine_id=engine_id, voices=voices):
            return ProviderVoiceEngine(
                engine_id, profile, tuple(v[0] for v in voices),
                voices[0][0], seed)

        registry.register(engine_id, describe=describe, create=create)
        existing.add(engine_id)


def engine_registry() -> EngineRegistry:
    """Only user-installed v4 TTS package Workers."""
    global _REGISTRY
    with _REGISTRY_LOCK:
        if _REGISTRY is None:
            registry = EngineRegistry()
            _register_external_providers(registry)
            _REGISTRY = registry
        return _REGISTRY


def create_voice_engine(engine_id: str, seed: int) -> VoiceEngine:
    """Create a Worker-Protocol v1 proxy for an installed v4 TTS package."""
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
    if type(speed) not in (int, float) or not math.isfinite(speed) or not 0.6 <= speed <= 5.0:
        raise InputError("speed must be a finite number from 0.6 to 5.0")
    info = get_engine_info(engine_id)
    if voice_id not in info.voice_ids:
        raise InputError(f"voice_id is not available in selected engine {engine_id}")
    segments = plan.get("segments")
    if not isinstance(segments, list) or len(segments) > MAX_PLAN_SEGMENTS:
        raise InputError(f"speech plan must have at most {MAX_PLAN_SEGMENTS} segments")
    if sum(len(s["spoken_text"]) for s in segments) > MAX_SPEECH_CHARS:
        raise InputError(f"speech renderer accepts up to {MAX_SPEECH_CHARS} spoken characters")


def render_wav(
    plan: dict[str, Any],
    *,
    speed: float = 1.0,
    voice_id: str = "paradee_thai",
    seed: int = DEFAULT_SEED,
    engine_id: str = ENGINE_ID,
    voice_controls: dict[str, Any] | None = None,
    engine: VoiceEngine | None = None,
    language_voice_routes: dict[str, dict[str, Any]] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Synthesize segments as a single WAV, retaining precise segment offsets.

    The segment timeline is based on generated samples, not playback events.
    An external playback coordinator must still provide real-time subtitle sync.
    """
    if language_voice_routes is not None:
        from .mixed_synthesis import render_mixed_language_wav
        return render_mixed_language_wav(
            plan, speed=speed, voice_id=voice_id, seed=seed,
            engine_id=engine_id, voice_controls=voice_controls,
            language_voice_routes=language_voice_routes,
            engine=engine,
        )
    validate_speech_request(plan, speed, voice_id, engine_id)
    seed = validate_seed(seed)
    controls = validate_controls(voice_controls)
    # A fresh model instance per speech job prevents its random state from
    # drifting between otherwise identical utterances.
    engine = engine if engine is not None else create_voice_engine(engine_id, seed=seed)
    if len(get_engine_info(engine_id).voice_ids) > 1:
        select_voice = getattr(engine, "select_voice", None)
        if not callable(select_voice):
            raise SpeechFailure("multi-voice adapter must implement select_voice")
        select_voice(voice_id)
    rate = engine.sample_rate
    if rate < 8_000 or rate > 96_000:
        raise SpeechFailure("unsupported engine sample rate")
    timeline: list[dict[str, Any]] = []
    pieces: list[bytes] = []
    frames = 0
    chunk_success: list[bool] = []
    for segment in plan["segments"]:
        kind = segment["kind"]
        start_frame = frames
        if kind == "speech" and segment["spoken_text"].strip():
            for chunk in _chunks(segment["spoken_text"]):
                if chunk.strip():
                    try:
                        audio = engine.generate(chunk, float(speed))
                        if not isinstance(audio, bytes) or not audio or len(audio) % 2:
                            raise SpeechFailure("invalid or empty engine PCM16 output")
                        if any((controls[k] != 0 for k in ("gain_db", "pitch_semitones", "bass_db", "treble_db"))):
                            audio = apply_voice_controls(audio, rate, controls)
                        if not audio or len(audio) % 2:
                            raise SpeechFailure("invalid processed PCM16 output")
                    except Exception as exc:
                        if (isinstance(exc, MemoryError)
                            or isinstance(exc, OSError) and
                               (getattr(exc, "winerror", None) == 1455
                                or "paging file is too small" in str(exc).lower())):
                            raise  # Cannot safely retry while Windows is out of commit.
                        # Recover from per-chunk inference errors, not from
                        # invalid speech plan / global request validation.
                        chunk_success.append(False)
                        continue
                    chunk_success.append(True)
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
    if chunk_success and not any(chunk_success):
        raise AllChunksFailed("all TTS chunks failed")
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
        "seed": seed if get_engine_info(engine_id).capabilities.get("seed_control") else None,
        "voice_controls": controls,
        "sample_rate": rate,
        "duration_ms": round(frames * 1000 / rate),
        "segments": timeline,
        "chunk_success": chunk_success,
    }