"""Engine-agnostic, versioned adapter contract and explicit engine registry.

This module imports no ML framework. Built-in and future user-trained engines
implement the same PCM16 interface; only trusted application code registers
factories. Nothing is automatically imported from user-supplied directories.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Protocol, runtime_checkable

from .processing import InputError

ADAPTER_API_VERSION = 1


@runtime_checkable
class VoiceEngine(Protocol):
    """Minimal synchronous adapter contract, independent of model internals."""

    id: str
    sample_rate: int

    def generate(self, text: str, speed: float) -> bytes:
        """Return headerless little-endian signed PCM16 mono frames.

        An adapter may resample its model output to sample_rate, but MUST NOT
        add WAV headers or change subtitle/display text.
        """


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
    adapter_api_version: int = ADAPTER_API_VERSION
    # Distribution review status is not an endorsement of any model.
    commercial_status: str = "review_required"
    # Optional list of selectable fixed voices (id, display label).
    # The legacy voice_id remains the default and existing adapters unchanged.
    voice_options: tuple[tuple[str, str], ...] = ()

    @property
    def voice_ids(self) -> tuple[str, ...]:
        return tuple(item[0] for item in self.voice_options) if self.voice_options else (self.voice_id,)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "language": self.language,
            "voice_id": self.voice_id,
            "voices": [{"id": identifier, "label": label} for identifier, label in
                       (self.voice_options or ((self.voice_id, self.voice_id),))],
            "sample_rate": self.sample_rate,
            "assets_ready": self.assets_ready,
            "runtime_ready": self.runtime_ready,
            "capabilities": dict(self.capabilities),
            "adapter_api_version": self.adapter_api_version,
            "commercial_status": self.commercial_status,
        }


@dataclass(frozen=True)
class EngineRegistration:
    id: str
    describe: Callable[[], EngineInfo]
    create: Callable[[int], VoiceEngine]


class EngineRegistry:
    """Explicit registrations. Does not load/download models or execute plugins."""

    def __init__(self) -> None:
        self._items: dict[str, EngineRegistration] = {}
        self._lock = RLock()

    def register(
        self, engine_id: str, *,
        describe: Callable[[], EngineInfo],
        create: Callable[[int], VoiceEngine],
    ) -> None:
        if not isinstance(engine_id, str) or not engine_id or len(engine_id) > 96:
            raise ValueError("engine id must be a short non-empty string")
        if not engine_id.isascii() or any(
            c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in engine_id
        ):
            raise ValueError("engine id must use lowercase a-z, 0-9, - or _")
        if not callable(describe) or not callable(create):
            raise TypeError("engine describe and create must be callable")
        with self._lock:
            if engine_id in self._items:
                raise ValueError("engine id already registered")
            self._items[engine_id] = EngineRegistration(engine_id, describe, create)

    def list(self) -> list[EngineInfo]:
        with self._lock:
            entries = list(self._items.values())
        return [self._check_descriptor(item) for item in entries]

    @staticmethod
    def _check_descriptor(item: EngineRegistration) -> EngineInfo:
        info = item.describe()
        if not isinstance(info, EngineInfo) or info.id != item.id:
            raise ValueError("engine descriptor ID does not match registration")
        if info.adapter_api_version != ADAPTER_API_VERSION:
            raise ValueError("unsupported engine adapter API version")
        if not (8_000 <= info.sample_rate <= 96_000):
            raise ValueError("unsupported engine output sample rate")
        if not info.voice_id or not info.language:
            raise ValueError("engine must declare a voice and language")
        if (info.voice_id not in info.voice_ids
            or len(info.voice_ids) != len(set(info.voice_ids))
            or len(info.voice_ids) > 64
            or any(not voice or not label or len(voice) > 100 or len(label) > 120
                   for voice, label in (info.voice_options or ((info.voice_id, info.voice_id),)))):
            raise ValueError("invalid selectable voice list")
        if info.commercial_status not in {
            "review_required", "hold", "excluded", "cleared"
        }:
            raise ValueError("invalid commercial license-review status")
        return info

    def get(self, engine_id: str) -> EngineInfo:
        with self._lock:
            entry = self._items.get(engine_id)
        if entry is None:
            raise InputError("unknown engine_id")
        return self._check_descriptor(entry)

    def create(self, engine_id: str, seed: int) -> VoiceEngine:
        with self._lock:
            entry = self._items.get(engine_id)
        if entry is None:
            raise InputError("unknown engine_id")
        info = self._check_descriptor(entry)
        instance = entry.create(seed)
        if not isinstance(instance, VoiceEngine):
            raise TypeError("engine adapter must implement id, sample_rate and generate")
        if instance.id != engine_id or instance.sample_rate != info.sample_rate:
            raise ValueError("engine adapter output contract mismatch")
        return instance
