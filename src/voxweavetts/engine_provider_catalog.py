"""Universal v4-only discovery of user-installed external TTS Workers.

The Core neither hardcodes model architectures nor approves separate provider
directories. The user's single Install click is the permission to execute the
Worker bundled in a hash-verified v4 .vwmodel. No v3 readers or adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Provider:
    id: str
    backend: str
    driver: str
    sample_rate: int
    adapters: tuple[str, ...]
    builtins: tuple[str, ...]
    requirements_file: str
    plugin_path: Path | None = None
    declared_engine: dict[str, Any] | None = None

    @property
    def runtime_dir(self) -> str:
        return self.id

    @property
    def external_worker(self) -> Path | None:
        return self.plugin_path / "worker.py" if self.plugin_path else None


def all_providers(root: Path = ROOT) -> dict[str, Provider]:
    from .universal_model_v4 import installed_packages, engine_id, backend_id
    providers: dict[str, Provider] = {}
    for manifest, folder in installed_packages(root):
        if manifest["package"]["kind"] != "tts":
            continue
        entry = manifest["engine"]
        rights = manifest["rights"]
        identifier = "v4-" + manifest["package"]["id"] + "-" + manifest["package"]["version"].replace(".", "-")
        providers[identifier] = Provider(
            id=identifier,
            backend=backend_id(manifest),
            driver="external",
            sample_rate=entry["sample_rate"],
            adapters=(),
            builtins=(engine_id(manifest),),
            requirements_file="",
            plugin_path=folder / "plugin",
            declared_engine={
                "engine_id": engine_id(manifest),
                "title": manifest["package"]["title"],
                "language": entry["language"],
                "sample_rate": entry["sample_rate"],
                "voices": entry["voices"],
                "supported_languages": manifest["package"]["languages"],
                "voice_language_map": entry.get("voice_language_map", {}),
                "capabilities": {"speech": True, "speed": True},
                "license": {
                    "spdx": rights["spdx"],
                    "url": rights["url"],
                    "attribution": rights["attribution"],
                },
                "review_status": ("hold" if rights.get("review_status") == "hold" else "review_required"),
            },
        )
    return providers


def provider_for_engine(engine_id: str, *, root: Path = ROOT) -> Provider | None:
    return next((p for p in all_providers(root).values()
                 if engine_id in p.builtins), None)


def provider_for_backend(backend: str, *, root: Path = ROOT) -> Provider | None:
    return next((p for p in all_providers(root).values()
                 if p.backend == backend), None)
