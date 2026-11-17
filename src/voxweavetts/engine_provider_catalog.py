"""Curated + explicitly approved external provider catalog for isolated TTS.

The .vwmodel format is data only. New model architectures can instead use a
separately reviewed engine-provider folder containing a Worker-Protocol v1
implementation. Approval is required for executable code and dependency install.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_EXTERNAL_ID = re.compile(r"[a-z][a-z0-9-]{2,31}\Z")
_ENGINE_ID = re.compile(r"[a-z][a-z0-9_-]{2,95}\Z")
_VOICE_ID = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}\Z")


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

    def python_path(self, root: Path = ROOT) -> Path:
        path = Path(root) / "runtime" / "engine-envs" / self.runtime_dir
        return path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    def requirements_path(self, root: Path = ROOT) -> Path:
        if self.plugin_path is not None:
            return self.plugin_path / "requirements.txt"
        return Path(root) / "scripts" / "engine-dependencies" / self.requirements_file

    @property
    def external_worker(self) -> Path | None:
        return self.plugin_path / "worker.py" if self.plugin_path is not None else None


# First-party, vetted dependency recipes. No model manifest can change them.
PROVIDERS: dict[str, Provider] = {
    "wayu-nc": Provider(
        "wayu-nc", "wayu-nc-v1", "wayu", 24000,
        ("wayu-nc-v1",), ("personal-nc-wayu-paxa-edge-cpu",), "wayu-nc.txt",
    ),
    "pythaitts": Provider(
        "pythaitts", "pythaitts-v1", "legacy", 24000,
        ("fastthaig2p-kokoro-v1", "makham-paradee-onnx-v1"), ("fastthaig2p-cpu", "makham-paradee-cpu"),
        "pythaitts.txt",
    ),
    "vachana": Provider(
        "vachana", "vachana-v1", "legacy", 22050,
        ("vachana-onnx-v1",), ("vachana-cpu",), "vachana.txt",
    ),
    "kokoro": Provider(
        "kokoro", "kokoro-onnx-v1", "legacy", 24000,
        ("kokoro-onnx-v1",), (), "kokoro.txt",
    ),
    "sherpa": Provider(
        "sherpa", "sherpa-onnx-v1", "legacy", 44100,
        ("sherpa-supertonic-v1", "sherpa-melo-zh-v1"),
        (), "sherpa.txt",
    ),
}


class ProviderApprovalError(ValueError):
    pass


def _sha256(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            hash_.update(block)
    return hash_.hexdigest()


def _validate_external_manifest(raw: Any, folder: Path) -> Provider:
    required = {
        "format", "version", "provider_id", "engine_id", "title",
        "language", "sample_rate", "voices", "license", "capabilities",
    }
    optional = {"supported_languages", "voice_language_map"}
    if (not isinstance(raw, dict) or not required <= set(raw)
            or set(raw) - required - optional):
        raise ProviderApprovalError("invalid external engine provider schema")
    name = raw["provider_id"]
    engine_id = raw["engine_id"]
    if (raw["format"] != "voxweavetts.engine-provider" or raw["version"] != 1
        or not isinstance(name, str) or not _EXTERNAL_ID.fullmatch(name)
        or name in PROVIDERS or folder.name != name
        or not isinstance(engine_id, str) or not _ENGINE_ID.fullmatch(engine_id)
        or any(engine_id in p.builtins for p in PROVIDERS.values())
        or not isinstance(raw["title"], str) or not 1 <= len(raw["title"]) <= 100
        or not isinstance(raw["language"], str) or raw["language"] not in (
            "th", "en", "multi", "ja", "zh", "ko", "fr", "de", "es", "vi",
        )
        or type(raw["sample_rate"]) is not int or not 8000 <= raw["sample_rate"] <= 96000):
        raise ProviderApprovalError("invalid external engine identity")
    lic = raw["license"]
    if (not isinstance(lic, dict) or set(lic) != {"spdx", "url", "attribution"}
        or not isinstance(lic["spdx"], str) or not 1 <= len(lic["spdx"]) <= 80
        or not isinstance(lic["url"], str) or not lic["url"].startswith("https://")
        or not isinstance(lic["attribution"], str) or not lic["attribution"]):
        raise ProviderApprovalError("missing or invalid engine license information")
    voices = raw["voices"]
    if (not isinstance(voices, list) or not 1 <= len(voices) <= 64
        or any(not isinstance(v, dict) or set(v) != {"id", "label"}
               or not isinstance(v["id"], str) or not _VOICE_ID.fullmatch(v["id"])
               or not isinstance(v["label"], str) or not 1 <= len(v["label"]) <= 110
               for v in voices)
        or len({v["id"] for v in voices}) != len(voices)):
        raise ProviderApprovalError("invalid voice list")
    # Approved engine providers can explicitly advertise languages shared by
    # every voice (bilingual models), or per-voice language assignments. The
    # version-1 schema remains backwards compatible for single-language ones.
    supported = raw.get("supported_languages", [])
    voice_map = raw.get("voice_language_map", {})
    language_code = lambda x: (isinstance(x, str) and len(x) == 2
                               and x.isascii() and x.isalpha() and x.islower())
    if (not isinstance(supported, list) or len(supported) > 33
        or len(supported) != len(set(str(x) for x in supported))
        or any(not language_code(x) for x in supported)
        or (supported and raw["language"] != "multi"
            and raw["language"] not in supported)
        or not isinstance(voice_map, dict)
        or not set(voice_map) <= {v["id"] for v in voices}
        or any(not language_code(lang) for lang in voice_map.values())
        or (voice_map and supported)):
        raise ProviderApprovalError("invalid provider language capabilities")
    caps = raw["capabilities"]
    if (not isinstance(caps, dict) or not all(
        isinstance(key, str) and isinstance(value, bool) and len(key) < 64
        for key, value in caps.items())
        or len(caps) > 30):
        raise ProviderApprovalError("invalid capabilities")
    if not all((folder / name).is_file() and
               not (folder / name).is_symlink()
               for name in ("provider.json", "requirements.txt", "worker.py")):
        raise ProviderApprovalError("provider files missing")
    return Provider(name, "external-" + name, "external",
                    raw["sample_rate"], (), (engine_id,), "requirements.txt",
                    plugin_path=folder, declared_engine=raw)


def _external_provider(folder: Path) -> Provider | None:
    """Only code explicitly approved by the user, pinned to exact file hashes."""
    try:
        if folder.is_symlink():
            return None
        files = {name: folder / name for name in
                 ("provider.json", "worker.py", "requirements.txt")}
        approval = folder / "approved.json"
        if not approval.is_file() or approval.is_symlink() or approval.stat().st_size > 2048:
            return None
        state = json.loads(approval.read_text(encoding="utf-8"))
        if (not isinstance(state, dict) or set(state) != {"format", "files"}
            or state["format"] != "voxweavetts.approved-provider-v1"
            or not isinstance(state["files"], dict)
            or set(state["files"]) != set(files)):
            return None
        if any(not target.is_file() or target.is_symlink()
               or _sha256(target) != state["files"][name]
               for name, target in files.items()):
            return None
        manifest = json.loads(files["provider.json"].read_text(encoding="utf-8"))
        return _validate_external_manifest(manifest, folder)
    except (OSError, ValueError, TypeError, AttributeError, UnicodeError):
        return None


def approve_provider_folder(folder: Path, *, root: Path = ROOT,
                            trust_code: bool = False) -> Provider:
    """Explicitly pin locally installed executable code after manual review."""
    if not trust_code:
        raise ProviderApprovalError("executable provider requires explicit trust")
    base = (Path(root) / "extensions" / "engine-providers").resolve()
    folder = Path(folder).resolve()
    if folder.parent != base:
        raise ProviderApprovalError("provider must be in extensions/engine-providers")
    files = {name: folder / name for name in
             ("provider.json", "worker.py", "requirements.txt")}
    manifest_file = files["provider.json"]
    if not manifest_file.is_file() or manifest_file.stat().st_size > 12_000:
        raise ProviderApprovalError("invalid provider manifest size")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    profile = _validate_external_manifest(manifest, folder)
    hashes = {name: _sha256(file) for name, file in files.items()}
    approval = {"format": "voxweavetts.approved-provider-v1", "files": hashes}
    (folder / "approved.json").write_text(
        json.dumps(approval, indent=2) + "\n", encoding="utf-8")
    return profile


def all_providers(root: Path = ROOT) -> dict[str, Provider]:
    providers = dict(PROVIDERS)
    base = Path(root) / "extensions" / "engine-providers"
    if base.is_dir():
        for folder in sorted(base.iterdir()):
            if folder.is_dir() and _EXTERNAL_ID.fullmatch(folder.name):
                p = _external_provider(folder)
                if p is not None and p.id not in providers and all(
                    p.builtins[0] not in old.builtins for old in providers.values()
                ):
                    providers[p.id] = p
    return providers


def provider_for_adapter(adapter: str) -> Provider | None:
    return next((p for p in PROVIDERS.values() if adapter in p.adapters), None)


def provider_for_engine(engine_id: str, *, root: Path = ROOT) -> Provider | None:
    for profile in all_providers(root).values():
        if engine_id in profile.builtins:
            return profile
    if not engine_id.startswith("model-"):
        return None
    from .model_packages import engine_id_for, installed_packages
    for manifest, _ in installed_packages():
        if engine_id_for(manifest) == engine_id:
            return provider_for_adapter(manifest["engine_adapter"])
    return None


def provider_for_backend(backend: str, *, root: Path = ROOT) -> Provider | None:
    return next((p for p in all_providers(root).values() if p.backend == backend), None)


def provider_status(root: Path = ROOT) -> list[dict]:
    from .model_packages import installed_packages
    installed = installed_packages()
    profiles = []
    for item in all_providers(root).values():
        attached = list(item.builtins) + [
            "model-" + m["package_id"] + "-" + m["version"].replace(".", "_")
            for m, _ in installed if m["engine_adapter"] in item.adapters
        ]
        profiles.append({
            "id": item.id, "backend": item.backend,
            "runtime_ready": item.python_path(root).is_file(),
            "engines": attached, "adapter_types": list(item.adapters),
            "independent_environment": str(item.python_path(root).parent.parent.relative_to(root)),
            "external": item.driver == "external",
        })
    return profiles
