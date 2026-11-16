"""Trusted bridge to the existing VoxWeaveTTS engine adapters, out of process.

All older working model adapters are reused unchanged *inside* their respective
isolated Python environments. Presets/voice IDs remain backward compatible.
"""
from __future__ import annotations

from typing import Any

from .engine_provider_catalog import Provider, provider_for_engine


class LegacyBackend:
    def __init__(self, provider: Provider) -> None:
        if provider.driver != "legacy":
            raise ValueError("invalid legacy provider")
        self.provider = provider
        self.sample_rate = provider.sample_rate
        self._cached: dict[str, Any] = {}

    def synthesize(self, text: str, *, engine_id: str, voice_id: str,
                   speed: float, seed: int) -> bytes:
        profile = provider_for_engine(engine_id)
        if profile is None or profile.id != self.provider.id:
            raise ValueError("engine is not registered for this provider")
        from . import speech

        from .processing import InputError
        try:
            info = speech.engine_registry().get(engine_id)
        except InputError:
            # A new .vwmodel can be installed while this persistent process
            # is already running. Refresh metadata without killing the worker
            # or disrupting unrelated queued voices.
            speech.refresh_engine_registry()
            info = speech.engine_registry().get(engine_id)
        if info.sample_rate != self.sample_rate:
            raise ValueError("provider sample rate mismatch")
        if voice_id not in info.voice_ids:
            raise ValueError("unknown voice for provider engine")
        if not info.assets_ready:
            raise ValueError("provider model weights not installed")
        # FastThaiG2P seeds ONNX on construction. A fresh instance must be made
        # per call to retain deterministic seed behavior.
        stochastic = info.capabilities.get("seed_control", False)
        if stochastic or engine_id not in self._cached:
            engine = speech.engine_registry().create(engine_id, seed)
            if not stochastic:
                self._cached[engine_id] = engine
        else:
            engine = self._cached[engine_id]
        if len(info.voice_ids) > 1:
            engine.select_voice(voice_id)
        pcm = engine.generate(text, speed)
        if not isinstance(pcm, bytes) or not pcm or len(pcm) % 2:
            raise ValueError("native legacy engine emitted invalid PCM")
        return pcm
