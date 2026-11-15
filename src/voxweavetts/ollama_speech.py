"""Opt-in Ollama Speech TTS adapter scaffold (no model downloads).

Ollama v0.40.8+ supports POST /v1/audio/speech for speech-capable models.
In November 2026 native speech inference is announced for Apple Silicon only;
a Windows VoxWeaveTTS client can use an authorized private-LAN speech server
in the future. Until configured, this adapter advertises NOT READY and does
not contact Ollama. It never touches the AI Translation Ollama settings.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import wave

from .engine_contract import EngineInfo
from .processing import InputError

ENGINE_ID = "ollama-speech"
SAMPLE_RATE = 24_000
MAX_RESPONSE_BYTES = 24_000_000
MAX_INPUT_CHARS = 4096
CONFIG_FILE = Path(__file__).resolve().parents[2] / "data" / "settings" / "ollama-speech.json"
DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "base_url": "http://127.0.0.1:11434",
    "model": "",
    "voice": "default",
    "language": "en",
}
_VOICE_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_ALLOWED_LANGUAGES = {"en", "th", "ja", "zh", "ko", "es", "fr",
                      "hi", "it", "pt", "de", "ru", "multi"}


def validate_config(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or set(data) - set(DEFAULT_CONFIG):
        raise ValueError("invalid Ollama Speech configuration")
    config = {**DEFAULT_CONFIG, **data}
    if type(config["enabled"]) is not bool:
        raise ValueError("Ollama Speech enabled must be boolean")
    from .ollama_manager import validate_base_url, validate_model_name
    config["base_url"] = validate_base_url(config["base_url"])
    if config["model"]:
        config["model"] = validate_model_name(config["model"])
    elif config["enabled"]:
        raise ValueError("Ollama Speech requires a model name")
    voice = config["voice"]
    if not isinstance(voice, str) or not 1 <= len(voice) <= 80 or _VOICE_CONTROL.search(voice):
        raise ValueError("invalid Ollama Speech voice")
    if config["language"] not in _ALLOWED_LANGUAGES:
        raise ValueError("unsupported Ollama Speech voice language")
    return config


def load_config(*, strict: bool = False) -> dict[str, Any]:
    try:
        if not CONFIG_FILE.is_file():
            return DEFAULT_CONFIG.copy()
        if CONFIG_FILE.stat().st_size > 4096:
            raise ValueError("Ollama Speech settings too large")
        return validate_config(json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError, TypeError):
        if strict:
            raise
        # Bad or missing optional config must never break other TTS engines.
        return DEFAULT_CONFIG.copy()


def probe(config: dict[str, Any]) -> tuple[bool, bool, tuple[str, ...]]:
    """Installed tag and speech capability; GET/POST metadata only, no generation."""
    if not config["enabled"] or not config["model"]:
        return False, False, ()
    endpoint = config["base_url"]
    try:
        with urlopen(Request(endpoint + "/api/tags", method="GET"), timeout=1.5) as response:
            tags = json.loads(response.read(100_000))
        names = {item.get("name") for item in tags.get("models", [])
                 if isinstance(item, dict)}
        normalize = lambda value: value if ":" in value else value + ":latest"
        installed = normalize(config["model"]) in {
            normalize(item) for item in names if isinstance(item, str)
        }
        if not installed:
            return False, False, ()
        payload = json.dumps({"model": config["model"]}).encode("utf-8")
        req = Request(endpoint + "/api/show", data=payload,
                      headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=1.5) as response:
            details = json.loads(response.read(200_000))
        speech = "speech" in details.get("capabilities", [])
        voices = details.get("voices", [])
        valid_voices = tuple(x for x in voices if isinstance(x, str) and
                             1 <= len(x) <= 80 and not _VOICE_CONTROL.search(x))
        return True, speech, valid_voices[:64]
    except (OSError, ValueError, TypeError, KeyError, URLError):
        return False, False, ()


def descriptor() -> EngineInfo:
    config = load_config()
    installed, speech_capability, known_voices = probe(config)
    chosen = config["voice"]
    options = tuple(dict.fromkeys(("default", chosen, *known_voices)))
    if len(options) > 64:
        options = options[:64]
    return EngineInfo(
        id=ENGINE_ID,
        label="Ollama Speech (experimental; external server required)",
        language=config["language"],
        voice_id=chosen,
        voice_options=tuple((voice, voice) for voice in options),
        sample_rate=SAMPLE_RATE,
        assets_ready=installed,
        runtime_ready=speech_capability,
        capabilities={
            "speech": True, "speed": False, "seed_control": False,
            "voice_cloning": False, "pitch": False, "formant": False,
            "expressiveness": False, "streaming": False,
            "phoneme_dictionary": False,
        },
        commercial_status="review_required",
    )


def decode_wav_pcm(data: bytes) -> bytes:
    """Validate generated WAV; return mono PCM16 without its RIFF header."""
    from .speech import SpeechFailure
    if not isinstance(data, bytes) or len(data) > MAX_RESPONSE_BYTES:
        raise SpeechFailure("Ollama Speech response is missing or excessive")
    if not (data.startswith(b"RIFF") and data[8:12] == b"WAVE"):
        raise SpeechFailure("Ollama Speech returned non-WAV data")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            if (wav.getnchannels(), wav.getframerate(), wav.getsampwidth(),
                    wav.getcomptype()) != (1, SAMPLE_RATE, 2, "NONE"):
                raise SpeechFailure("Ollama Speech WAV must be mono PCM16 24 kHz")
            pcm = wav.readframes(MAX_RESPONSE_BYTES // 2)
    except (wave.Error, EOFError, OSError, ValueError) as exc:
        raise SpeechFailure("Ollama Speech returned invalid WAV") from exc
    if not pcm or len(pcm) % 2:
        raise SpeechFailure("Ollama Speech returned empty or truncated PCM")
    return pcm


class OllamaSpeechEngine:
    """Optional registered VoiceEngine. No network access until explicitly used."""

    id = ENGINE_ID
    sample_rate = SAMPLE_RATE

    def __init__(self) -> None:
        self._voice = "default"

    def select_voice(self, voice_id: str) -> None:
        config = load_config(strict=True)
        _installed, _speech, voices = probe(config)
        allowed = {"default", config["voice"], *voices}
        if voice_id not in allowed:
            raise InputError("unknown Ollama Speech voice")
        self._voice = voice_id

    def generate(self, text: str, speed: float) -> bytes:
        from .speech import EngineUnavailable, SpeechFailure
        if not isinstance(text, str) or not text.strip():
            return b""
        if not 0 < len(text) <= MAX_INPUT_CHARS:
            raise SpeechFailure("Ollama Speech text exceeds the API limit")
        if speed != 1.0:
            raise EngineUnavailable("Ollama Speech does not support native speed control")
        try:
            config = load_config(strict=True)
        except (OSError, ValueError, TypeError) as exc:
            raise EngineUnavailable("Ollama Speech configuration is invalid") from exc
        installed, capable, _ = probe(config)
        if not installed or not capable:
            raise EngineUnavailable("Ollama Speech model is unavailable or lacks speech capability")
        body = json.dumps({
            "model": config["model"], "voice": self._voice,
            "input": text, "response_format": "wav",
        }, ensure_ascii=False).encode("utf-8")
        req = Request(config["base_url"] + "/v1/audio/speech",
                      data=body, headers={"Content-Type": "application/json"},
                      method="POST")
        try:
            with urlopen(req, timeout=90) as response:
                wav = response.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            raise EngineUnavailable("Ollama Speech synthesis request failed") from exc
        return decode_wav_pcm(wav)
