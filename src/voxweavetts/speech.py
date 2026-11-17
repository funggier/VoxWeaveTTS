"""Shared WAV renderer and current local ONNX adapters.

Engine-neutral registration is in engine_contract.py. The existing adapters
remain here for backward compatibility and will be split into packages later.
"""
from __future__ import annotations

import io
import math
import threading
from dataclasses import replace
import wave
from pathlib import Path
from typing import Any

from .processing import InputError
from .engine_contract import EngineInfo, EngineRegistry, VoiceEngine
from .model_packages import installed_packages, engine_id_for, display_model_title
from .voice_controls import apply_voice_controls, control_schema, ffmpeg_path, validate_controls

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models" / "fastthaig2p"
ASSETS = {"model": "kokoro_thai.onnx", "voicepack": "thai_som.npy", "config": "config.json"}
MIN_SIZES = {"model": 320_000_000, "voicepack": 500_000, "config": 100}
ENGINE_ID = "fastthaig2p-cpu"
PARADEE_ENGINE_ID = "makham-paradee-cpu"
PARADEE_DIR = ROOT / "models" / "makham-paradee"
VACHANA_ENGINE_ID = "vachana-cpu"
VACHANA_DIR = ROOT / "models" / "vachana"
VACHANA_RATE = 22_050
VACHANA_VOICES = (
    ("th_f_1", "หญิง 1 — Vachana"),
    ("th_f_2", "หญิง 2 — Vachana"),
    ("th_m_1", "ชาย 1 — Vachana"),
    ("th_m_2", "ชาย 2 — Vachana"),
)
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


def vachana_assets_ready() -> bool:
    """Only advertise the whole local test voice family when all files exist."""
    try:
        config = VACHANA_DIR / "speaker_config.json"
        return (config.is_file() and config.stat().st_size > 1000
                and all((VACHANA_DIR / "voices" / (voice + ".onnx")).is_file()
                        and (VACHANA_DIR / "voices" / (voice + ".onnx")).stat().st_size > 60_000_000
                        for voice, _ in VACHANA_VOICES))
    except OSError:
        return False


def vachana_runtime_ready() -> bool:
    try:
        import importlib.util
        return all(importlib.util.find_spec(m) for m in
                   ("vachanatts", "onnxruntime", "numpy", "pythainlp", "ssg"))
    except (ImportError, ValueError):
        return False


def _vachana_descriptor() -> EngineInfo:
    capabilities = {
        "speech": True, "speed": True, "seed_control": False,
        "voice_cloning": False, "pitch": False, "formant": False,
        "expressiveness": False, "streaming": False, "phoneme_dictionary": False,
    }
    capabilities.update(_built_in_dsp_flags())
    return EngineInfo(
        id=VACHANA_ENGINE_ID, label="Vachana Thai VITS — 4 voices (CPU ONNX)",
        language="th", supported_languages=("th", "en"),
        voice_id="th_f_1", voice_options=VACHANA_VOICES,
        sample_rate=VACHANA_RATE, assets_ready=vachana_assets_ready(),
        runtime_ready=vachana_runtime_ready(), capabilities=capabilities,
        # Public model card says MIT, but full pack/third-party provenance
        # remains under review: this is developer-only, not in portable ZIP.
        commercial_status="hold",
    )


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
        supported_languages=("th", "en"),
        voice_id="paradee_thai",
        sample_rate=SAMPLE_RATE,
        assets_ready=paradee_assets_ready(),
        runtime_ready=runtime_ready(),
        capabilities=capabilities,
    )


def _worker_aware_info(info: EngineInfo) -> EngineInfo:
    from .engine_provider_catalog import provider_for_engine
    from .engine_worker_gateway import gateway
    provider = provider_for_engine(info.id)
    if provider and gateway().available(provider.backend):
        return replace(info, runtime_ready=True)
    return info


def list_engine_info() -> list[EngineInfo]:
    """Enumerate local and isolated adapters without loading model weights."""
    return [_worker_aware_info(info) for info in engine_registry().list()]


def get_engine_info(engine_id: str) -> EngineInfo:
    return _worker_aware_info(engine_registry().get(engine_id))


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
        supported_languages=("th", "en"),
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

    def __init__(self, seed: int = DEFAULT_SEED, *,
                 model_dir: Path = MODEL_DIR, engine_id: str = ENGINE_ID,
                 voicepack_name: str = "thai_som.npy"):
        self.seed = validate_seed(seed)
        self.model_dir = Path(model_dir)
        self.voicepack_name = voicepack_name
        self.id = engine_id
        self._native: Any = None

    def _get_native(self) -> Any:
        if self._native is None:
            source = self.model_dir
            voicepack = source / self.voicepack_name
            if not all(path.is_file() for path in
                       (source / "kokoro_thai.onnx", voicepack, source / "config.json")):
                raise EngineUnavailable("FastThaiG2P model package assets are missing")
            if not runtime_ready():
                raise EngineUnavailable(
                    "PyThaiTTS ONNX dependencies are not installed in the selected Python runtime"
                )
            import onnxruntime as ort
            from pythaitts.pretrained.fastthaig2p.tts import TTS
            # IMPORTANT: seed the runtime BEFORE creating the ONNX session.
            ort.set_seed(self.seed)
            self._native = TTS(
                model_path=self.model_dir / "kokoro_thai.onnx",
                voicepack_path=voicepack,
                config_path=self.model_dir / "config.json",
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


class VachanaEngine:
    """Four selectable fixed voices, loaded only from trusted local ONNX files.

    Do not use vachanatts.TTS wrapper: it transparently downloads remote model
    files into the current working directory. This adapter must be offline.
    """

    id = VACHANA_ENGINE_ID
    sample_rate = VACHANA_RATE
    _lock = threading.RLock()

    def __init__(self, *, model_dir: Path = VACHANA_DIR,
                 engine_id: str = VACHANA_ENGINE_ID,
                 voices: tuple[tuple[str, str], ...] = VACHANA_VOICES,
                 voice_assets: dict[str, str] | None = None) -> None:
        self.id = engine_id
        self.model_dir = Path(model_dir)
        self.voices = voices
        self.voice_assets = voice_assets or {name: "voices/" + name + ".onnx" for name, _ in voices}
        self.voice_id = voices[0][0]
        self._voice: Any = None

    def select_voice(self, voice_id: str) -> None:
        if voice_id not in {item[0] for item in self.voices}:
            raise InputError("unsupported Vachana voice")
        if voice_id != self.voice_id:
            self._voice = None
        self.voice_id = voice_id

    def generate(self, text: str, speed: float) -> bytes:
        if not isinstance(text, str) or not text.strip():
            return b""
        with type(self)._lock:
            if self._voice is None:
                if not (self.model_dir / "speaker_config.json").is_file() or not all(
                    (self.model_dir / "voices" / (identifier + ".onnx")).is_file()
                    for identifier, _label in self.voices
                ):
                    raise EngineUnavailable("Vachana model pack is not installed")
                if not vachana_runtime_ready():
                    raise EngineUnavailable("VachanaTTS dependency not installed")
                from vachanatts.voice import Voice
                voice_path = self.model_dir / self.voice_assets[self.voice_id]
                self._voice = Voice.load(
                    model_path=voice_path,
                    config_path=self.model_dir / "speaker_config.json",
                    use_cuda=False,
                )
                if self._voice.config.sample_rate != self.sample_rate:
                    raise SpeechFailure("Vachana sample rate did not match model metadata")
            from vachanatts.config import SpeechConfig
            settings = SpeechConfig(length_scale=1.0 / float(speed),
                                    noise_scale=0.667, noise_w_scale=0.8)
            chunks = [chunk.audio_int16_bytes
                      for chunk in self._voice.synthesize(text, settings)]
            result = b"".join(chunks)
            if not result:
                raise SpeechFailure("Vachana returned empty audio")
            return result


_REGISTRY_LOCK = threading.RLock()
_REGISTRY: EngineRegistry | None = None


def refresh_engine_registry() -> None:
    """Re-scan trusted local model manifests after install/removal."""
    global _REGISTRY
    with _REGISTRY_LOCK:
        _REGISTRY = None


def _register_model_packages(registry: EngineRegistry) -> None:
    """A package selects an existing trusted adapter, never imports pack code."""
    allowed = {"vachana-onnx-v1", "fastthaig2p-kokoro-v1", "kokoro-onnx-v1",
               "sherpa-supertonic-v1", "sherpa-melo-zh-v1"}
    for manifest, model_dir in installed_packages():
        if manifest["engine_adapter"] not in allowed:
            continue
        engine_id = engine_id_for(manifest)
        voices = tuple((entry["id"], entry["label"]) for entry in manifest["voices"])
        label = display_model_title(manifest) + " · " + manifest["version"]
        commercial = manifest["license"]["review_status"]
        adapter = manifest["engine_adapter"]

        def description(engine_id=engine_id, voices=voices, model_dir=model_dir,
                        label=label, commercial=commercial, manifest=manifest,
                        adapter=adapter):
            ready = all((model_dir / row["path"]).is_file()
                        and (model_dir / row["path"]).stat().st_size == row["size"]
                        for row in manifest["files"])
            is_vachana = adapter == "vachana-onnx-v1"
            is_kokoro = adapter == "kokoro-onnx-v1"
            is_sherpa = adapter in ("sherpa-supertonic-v1", "sherpa-melo-zh-v1")
            flags = dict(_vachana_descriptor().capabilities if is_vachana
                         else engine_info().capabilities)
            if is_kokoro or is_sherpa:
                flags.update({"seed_control": False, "voice_cloning": False,
                              "phoneme_dictionary": False})
            if is_kokoro:
                from .kokoro_engine import runtime_ready as adapter_ready
            elif is_sherpa:
                from .sherpa_voice_engine import runtime_ready as adapter_ready
            elif is_vachana:
                adapter_ready = vachana_runtime_ready
            else:
                adapter_ready = runtime_ready
            return EngineInfo(
                id=engine_id, label=label, language=manifest["language"],
                voice_id=voices[0][0], voice_options=voices,
                # These already-installed adapter families can synthesize
                # English in addition to their original package language.
                # Keep the manifest language as the native language.
                supported_languages=((manifest["language"], "en")
                    if adapter in ("fastthaig2p-kokoro-v1", "vachana-onnx-v1",
                                   "sherpa-melo-zh-v1") else ()),
                voice_language_map=({voice_id: voice_id[:2] for voice_id, _ in voices}
                                    if adapter == "sherpa-supertonic-v1" else {}),
                sample_rate=manifest["sample_rate"],
                assets_ready=ready, runtime_ready=adapter_ready(),
                capabilities=flags, commercial_status=commercial,
            )

        voice_assets = {voice["id"]: voice["asset"] for voice in manifest["voices"]}

        def create(seed: int, engine_id=engine_id, model_dir=model_dir,
                   voices=voices, voice_assets=voice_assets, adapter=adapter):
            if adapter == "kokoro-onnx-v1":
                from .kokoro_engine import KokoroOnnxEngine
                return KokoroOnnxEngine(model_dir=model_dir, engine_id=engine_id,
                                       voices=voices)
            if adapter in ("sherpa-supertonic-v1", "sherpa-melo-zh-v1"):
                from .sherpa_voice_engine import SherpaVoiceEngine
                return SherpaVoiceEngine(
                    model_dir=model_dir, engine_id=engine_id,
                    adapter=adapter, voices=voices,
                    sample_rate=44_100,
                )
            if adapter == "fastthaig2p-kokoro-v1":
                return FastThaiG2PEngine(
                    seed=seed, model_dir=model_dir, engine_id=engine_id,
                    voicepack_name=voice_assets[voices[0][0]])
            return VachanaEngine(model_dir=model_dir, engine_id=engine_id,
                                 voices=voices, voice_assets=voice_assets)
        registry.register(engine_id, describe=description, create=create)



def _register_external_providers(registry: EngineRegistry) -> None:
    """Discover explicitly approved worker-only extensions without importing code.

    A model .vwmodel never supplies Python. New engine architectures instead
    implement the stable JSONL Worker Protocol in a separately trusted provider.
    """
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
            capabilities.update(_built_in_dsp_flags())
            return EngineInfo(
                id=engine_id, label=title, language=data["language"],
                voice_id=voices[0][0], voice_options=voices,
                supported_languages=tuple(data.get("supported_languages", ())),
                voice_language_map=dict(data.get("voice_language_map", {})),
                sample_rate=data["sample_rate"], assets_ready=True,
                runtime_ready=gateway().available(profile.backend),
                capabilities=capabilities, commercial_status="hold",
            )

        def create(seed: int, profile=provider, engine_id=engine_id, voices=voices):
            return ProviderVoiceEngine(
                engine_id, profile, tuple(v[0] for v in voices),
                voices[0][0], seed)

        registry.register(engine_id, describe=describe, create=create)
        existing.add(engine_id)


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
            registry.register(
                VACHANA_ENGINE_ID, describe=_vachana_descriptor,
                create=lambda seed: VachanaEngine(),
            )
            # Safe-by-default optional network TTS provider: not ready until
            # a user supplies a local settings file and a speech-capable model.
            from .ollama_speech import ENGINE_ID as OLLAMA_SPEECH_ID, descriptor as ollama_speech_descriptor, OllamaSpeechEngine
            registry.register(OLLAMA_SPEECH_ID, describe=ollama_speech_descriptor,
                              create=lambda seed: OllamaSpeechEngine())
            from .personal_wayu_engine import (
                ENGINE_ID as WAYU_NC_ID, descriptor as wayu_nc_descriptor,
                PersonalWayuEngine,
            )
            registry.register(WAYU_NC_ID, describe=wayu_nc_descriptor,
                              create=lambda seed: PersonalWayuEngine(seed=seed))
            _register_model_packages(registry)
            _register_external_providers(registry)
            _REGISTRY = registry
        return _REGISTRY


def create_voice_engine(engine_id: str, seed: int) -> VoiceEngine:
    """Prefer an installed isolated provider; preserve native legacy fallback.

    This transition does not rename existing engine IDs or break saved presets.
    Model families with different dependency requirements never share an env.
    """
    from .engine_provider_catalog import provider_for_engine
    from .engine_worker_gateway import gateway
    profile = provider_for_engine(engine_id)
    if profile is not None and profile.driver == "legacy" and gateway().available(profile.backend):
        from .engine_worker_proxy import ProviderVoiceEngine
        info = get_engine_info(engine_id)
        proxy = ProviderVoiceEngine(engine_id, profile, info.voice_ids, info.voice_id, seed)
        # Preserve public attributes of the historical FastThaiG2P adapter.
        # Existing user code and model-package tests read these properties.
        for manifest, model_dir in installed_packages():
            if engine_id_for(manifest) == engine_id:
                proxy.model_dir = model_dir
                if manifest["engine_adapter"] == "fastthaig2p-kokoro-v1":
                    proxy.voicepack_name = manifest["voices"][0]["asset"]
                break
        return proxy
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
        "seed": seed if get_engine_info(engine_id).capabilities.get("seed_control") else None,
        "voice_controls": controls,
        "sample_rate": rate,
        "duration_ms": round(frames * 1000 / rate),
        "segments": timeline,
    }