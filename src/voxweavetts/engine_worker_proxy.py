"""Thin IPC VoiceEngine-compatible proxy for legacy and new installed engines."""
from __future__ import annotations

from .engine_provider_catalog import Provider
from .engine_worker_gateway import WorkerError, gateway
from .processing import InputError


class ProviderVoiceEngine:
    """Preserves Engine ID, voice selection, PCM contract and sample rate."""

    def __init__(self, engine_id: str, provider: Provider,
                 voice_ids: tuple[str, ...], voice_id: str, seed: int) -> None:
        self.id = engine_id
        self.sample_rate = provider.sample_rate
        self.backend = provider.backend
        self.seed = seed
        self.voices = set(voice_ids)
        self.voice_id = voice_id

    def select_voice(self, voice_id: str) -> None:
        if voice_id not in self.voices:
            raise InputError("voice does not belong to the selected engine")
        self.voice_id = voice_id

    def generate(self, text: str, speed: float) -> bytes:
        if not isinstance(text, str) or not text.strip():
            return b""
        try:
            return gateway().synthesize(
                self.backend, engine_id=self.id, text=text,
                voice_id=self.voice_id, speed=speed, seed=self.seed,
            )
        except WorkerError as exc:
            from .speech import SpeechFailure
            raise SpeechFailure("isolated TTS provider failed; check logs/engine-workers") from exc
