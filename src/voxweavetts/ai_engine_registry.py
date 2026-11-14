"""Independent AI Engine Registry, with trusted, opt-in translation adapters.

Like the Voice Engine Registry, model files are data, never executable plugins.
The two built-in adapters may be unavailable until their separate runtime/assets
are present. More adapters can be registered by trusted application code.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Protocol, runtime_checkable

ADAPTER_API_VERSION = 1
MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "ai" / "m2m100_418m"
_M2M_FILES = ("config.json", "vocab.json", "sentencepiece.bpe.model", "model.safetensors")


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


_M2M_INFERENCE_LOCK = RLock()


from functools import lru_cache


@lru_cache(maxsize=2)
def _loaded_m2m(folder: str):
    from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
    tokenizer = M2M100Tokenizer.from_pretrained(folder, local_files_only=True)
    model = M2M100ForConditionalGeneration.from_pretrained(
        folder, local_files_only=True, use_safetensors=True
    ).eval()
    return tokenizer, model


class M2M100Adapter:
    """Translate with explicitly installed local safetensors; no hub downloads."""

    def process(self, text: str, settings: dict[str, Any],
                context: list[dict[str, str]]) -> str:
        if settings["operation"] != "translate":
            raise RuntimeError("M2M100 translates text only")
        from .ai_model_packages import resolve_model, installed_packages
        info = m2m_info()
        if not info.assets_ready or not info.runtime_ready:
            raise RuntimeError("M2M100 model/runtime not installed")
        folder = resolve_model(settings["model"]) if settings["model"] else None
        if folder is None and not settings["model"]:
            packages = installed_packages()
            if len(packages) == 1:
                folder = packages[0][1]
            elif all((MODEL_DIR / name).is_file() for name in _M2M_FILES):
                folder = MODEL_DIR
        if folder is None:
            raise RuntimeError("choose an installed M2M100 model in AI Settings")
        source = settings["source_language"]
        target = settings["target_language"]
        if source == "auto":
            raise RuntimeError("M2M100 requires an explicit source language")
        if source == target:
            return text
        # Import only in this optional adapter. Keep core and portable runtime
        # dependency-free. The trusted local folder must use safetensors, not
        # untrusted model Python/pickle from a ZIP package.
        # Cache each trusted local model once and serialize tokenizer source
        # changes. Recreating 418M parameters for every live chat is not viable.
        tokenizer, model = _loaded_m2m(str(folder))
        with _M2M_INFERENCE_LOCK:
            tokenizer.src_lang = source
            tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            output = model.generate(**tokens,
                                    forced_bos_token_id=tokenizer.get_lang_id(target),
                                    max_new_tokens=512)
            decoded = tokenizer.batch_decode(output, skip_special_tokens=True)
        return decoded[0] if decoded else ""


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
    from .ai_model_packages import installed_packages
    ready_files = bool(installed_packages()) or all(
        (MODEL_DIR / name).is_file() for name in _M2M_FILES
    )
    deps = all(find_spec(name) is not None
               for name in ("torch", "transformers", "sentencepiece", "safetensors"))
    return AIEngineInfo(
        "m2m100", "M2M100 418M (Local Translation)", "translation", False, False,
        ready_files, deps,
        "Optional local safetensors + tokenizer under models/ai/m2m100_418m; "
        "requires torch, transformers, sentencepiece, safetensors",
    )


_AI_ENGINES = AIEngineRegistry()
_AI_ENGINES.register("ollama", describe=ollama_info, create=OllamaAdapter)
_AI_ENGINES.register("m2m100", describe=m2m_info, create=M2M100Adapter)


def ai_engines() -> AIEngineRegistry:
    return _AI_ENGINES