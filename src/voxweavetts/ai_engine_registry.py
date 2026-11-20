"""Independent AI Engine Registry, with trusted, opt-in translation adapters.

M2M100 executes only inside its v4 package Worker; Ollama is a separate
user-configured local service, not a .vwmodel package.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Protocol, runtime_checkable

ADAPTER_API_VERSION = 1


@dataclass(frozen=True)
class AIEngineInfo:
    id: str
    label: str
    kind: str
    supports_prompt: bool
    supports_tools: bool
    assets_ready: bool
    runtime_ready: bool
    installation: str
    api_version: int = ADAPTER_API_VERSION
    commercial_status: str = "review_required"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "label": self.label, "kind": self.kind,
            "supports_prompt": self.supports_prompt,
            "supports_tools": self.supports_tools,
            "assets_ready": self.assets_ready, "runtime_ready": self.runtime_ready,
            "ready": self.assets_ready and self.runtime_ready,
            "installation": self.installation,
            "api_version": self.api_version,
            "commercial_status": self.commercial_status,
        }


@runtime_checkable
class AIEngine(Protocol):
    def process(self, text: str, settings: dict[str, Any],
                context: list[dict[str, str]]) -> str: ...


class AIEngineRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[str, tuple[Callable[[], AIEngineInfo], Callable[[], AIEngine]]] = {}

    def register(self, engine_id: str, *, describe: Callable[[], AIEngineInfo],
                 create: Callable[[], AIEngine]) -> None:
        if (not isinstance(engine_id, str) or not 1 <= len(engine_id) <= 96
                or not engine_id.isascii() or any(
                    c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in engine_id
                )):
            raise ValueError("invalid AI engine ID")
        if not callable(describe) or not callable(create):
            raise TypeError("AI adapter description and factory must be callable")
        with self._lock:
            if engine_id in self._items:
                raise ValueError("AI engine already registered")
            self._items[engine_id] = (describe, create)

    def is_registered(self, engine_id: str) -> bool:
        with self._lock:
            return engine_id in self._items

    def describe(self, engine_id: str) -> AIEngineInfo:
        with self._lock:
            item = self._items.get(engine_id)
        if item is None:
            raise ValueError("unknown AI engine")
        info = item[0]()
        if (not isinstance(info, AIEngineInfo) or info.id != engine_id
                or info.api_version != ADAPTER_API_VERSION or
                info.kind not in {"llm", "translation"}):
            raise ValueError("invalid AI adapter metadata")
        return info

    def list(self) -> list[AIEngineInfo]:
        with self._lock:
            keys = list(self._items)
        return [self.describe(key) for key in keys]

    def create(self, engine_id: str) -> AIEngine:
        with self._lock:
            item = self._items.get(engine_id)
        if item is None:
            raise ValueError("unknown AI engine")
        adapter = item[1]()
        if not isinstance(adapter, AIEngine):
            raise TypeError("AI engine adapter contract is missing process()")
        return adapter


class OllamaAdapter:
    def process(self, text: str, settings: dict[str, Any],
                context: list[dict[str, str]]) -> str:
        # The Ollama implementation stays in the processor, where the trusted
        # instructions and external-data boundary are built.
        from .ai_processing import _ollama_chat
        return _ollama_chat(text, settings, context)


class M2M100Adapter:
    """Only the installed v4 model's own Worker can run translation."""

    def process(self, text: str, settings: dict[str, Any],
                context: list[dict[str, str]]) -> str:
        if settings["operation"] != "translate":
            raise RuntimeError("M2M100 translates text only")
        info = m2m_info()
        if not info.assets_ready or not info.runtime_ready:
            raise RuntimeError("M2M100 v4 translation package is not installed")
        from .m2m_runtime import translate
        return translate(text, settings)


def ollama_info() -> AIEngineInfo:
    # A bounded loopback query verifies that the local server is reachable.
    # It never starts Ollama or downloads a model.
    import json
    from urllib.request import urlopen
    try:
        with urlopen("http://127.0.0.1:11434/api/tags", timeout=0.5) as response:
            models = json.load(response).get("models", [])
            running = True
    except (OSError, ValueError, TypeError):
        models = []
        running = False
    return AIEngineInfo(
        "ollama", "Ollama (Local LLM)", "llm", True, False,
        bool(models), running,
        "Local Ollama at 127.0.0.1:11434; select one of its installed models",
    )


def m2m_info() -> AIEngineInfo:
    from .universal_model_v4 import installed_packages
    ready_files = any(m["package"]["kind"] == "translation"
                      and m["package"]["id"] == "m2m100-418m"
                      for m, _ in installed_packages())
    from .m2m_runtime import ready as isolated_runtime_ready
    deps = isolated_runtime_ready()
    return AIEngineInfo(
        "m2m100", "M2M100 418M (ทดลอง / accuracy varies)", "translation", False, False,
        ready_files, deps,
        "Universal .vwmodel v4 only: offline model/runtime; "
        "requires the optional isolated M2M100 Python runtime (torch, transformers, "
        "sentencepiece, safetensors) installed automatically from one verified file; "
        "experimental translation quality - verify meaning before live use",
    )


_AI_ENGINES = AIEngineRegistry()
_AI_ENGINES.register("ollama", describe=ollama_info, create=OllamaAdapter)
_AI_ENGINES.register("m2m100", describe=m2m_info, create=M2M100Adapter)


def ai_engines() -> AIEngineRegistry:
    return _AI_ENGINES