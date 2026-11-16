"""Local-only NC Wayu engine adapter using the shared isolated-worker gateway.

All heavy ML dependencies live in runtime/engine-envs/wayu-nc. The main
VoxWeaveTTS Python process imports no Wayu/PyTorch/TLTK runtime.
Weight license is CC BY-NC 4.0 (not commercially cleared).
"""
from __future__ import annotations

from pathlib import Path

from .engine_contract import EngineInfo
from .engine_worker_gateway import WorkerError, WorkerResourceError, gateway
from .processing import InputError

ENGINE_ID = "personal-nc-wayu-paxa-edge-cpu"
WORKER_BACKEND = "wayu-nc-v1"
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


def assets_ready(model_dir: Path = MODEL_DIR) -> bool:
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
    return gateway().available(WORKER_BACKEND)


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
    """Front-end proxy only; heavy model is cached in one persistent subprocess."""

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
            raise EngineUnavailable("isolated Wayu NC runtime missing; run Install-WayuWorker.ps1")
        try:
            return gateway().synthesize(
                WORKER_BACKEND, text=text, voice_id=self.voice_id,
                speed=speed, seed=self.seed,
            )
        except WorkerResourceError as exc:
            from .speech import EngineUnavailable
            raise EngineUnavailable(
                "not enough available system memory to synthesize speech; "
                "close memory-heavy applications or increase the Windows page file"
            ) from exc
        except WorkerError as exc:
            from .speech import SpeechFailure
            raise SpeechFailure("isolated NC voice worker failed; check logs/engine-workers") from exc
