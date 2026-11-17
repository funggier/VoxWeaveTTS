"""Unified local runtime inventory and reference-safe uninstall.

All runtime identities and folders are curated by the application. Model
manifests cannot supply executable paths, shell commands or deletion targets.
A runtime can be removed only by explicit user confirmation after checking
that no installed models (including legacy built-ins) depend on it.
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_LOCK = threading.RLock()
_RUNTIME_ID = re.compile(r"[a-z][a-z0-9-]{1,39}\Z")


class RuntimeRegistryError(ValueError):
    pass


def _digest(recipe: Path, category: str) -> str:
    if not recipe.is_file() or recipe.is_symlink():
        return ""
    with recipe.open("rb") as source:
        recipe_hash = hashlib.file_digest(source, "sha256").hexdigest()
    spec = "|".join((category, recipe_hash, platform.system().lower(),
                     platform.machine().lower(), f"{sys.version_info.major}.{sys.version_info.minor}"))
    return hashlib.sha256(spec.encode("utf-8")).hexdigest()


def _installed_consumers(root: Path) -> dict[str, list[str]]:
    from .engine_provider_catalog import provider_for_adapter
    from .model_packages import installed_packages as installed_tts
    from .ai_model_packages import installed_packages as installed_ai
    consumers: dict[str, list[str]] = {}
    def add(owner: str, key: str) -> None:
        current = consumers.setdefault(owner, [])
        if key not in current:
            current.append(key)

    for manifest, _folder in installed_tts(base=root / "models" / "packages"):
        profile = provider_for_adapter(manifest["engine_adapter"])
        if profile is not None:
            add(profile.id, f"{manifest['package_id']}@{manifest['version']}")
    for manifest, _folder in installed_ai(base=root / "models" / "ai" / "packages"):
        if manifest["engine_adapter"] == "m2m100-transformers-v1":
            add("m2m100", f"{manifest['package_id']}@{manifest['version']}")

    from .makham_package import active_model_dir, packaged_model_dir
    if active_model_dir(root) is not None and active_model_dir(root) != packaged_model_dir(root):
        add("pythaitts", "built-in:makham-paradee-cpu")
    from .speech import ASSETS, MIN_SIZES, VACHANA_VOICES
    # Built-in engines without weights are not runtime consumers.
    fast = root / "models" / "fastthaig2p"
    if all((fast / name).is_file() and (fast / name).stat().st_size >= MIN_SIZES[key]
           for key, name in ASSETS.items()):
        add("pythaitts", "built-in:fastthaig2p-cpu")
    vachana = root / "models" / "vachana"
    if ((vachana / "speaker_config.json").is_file() and
        all((vachana / "voices" / (voice + ".onnx")).is_file()
            for voice, _label in VACHANA_VOICES)):
        add("vachana", "built-in:vachana-cpu")
    from .personal_wayu_engine import assets_ready as wayu_ready
    if wayu_ready(root / "models" / "personal" / "wayu-paxa-tts-edge"):
        add("wayu-nc", "personal:wayu-paxa-edge")
    from .ai_engine_registry import _M2M_FILES
    legacy = root / "models" / "ai" / "m2m100_418m"
    if legacy.is_dir() and not legacy.is_symlink() and all(
        (legacy / name).is_file() for name in _M2M_FILES
    ):
        add("m2m100", "legacy:m2m100-418m")
    return consumers


def inventory(root: Path = ROOT) -> list[dict]:
    """Derive real reference counts; do not maintain stale editable counters."""
    from .engine_provider_catalog import all_providers
    from .engine_provider_installer import ready as provider_ready
    from .m2m_runtime import ready as m2m_ready, python_path as m2m_python, REQUIREMENTS
    root = Path(root)
    consumers = _installed_consumers(root)
    result: list[dict] = []
    for profile in all_providers(root).values():
        folder = profile.python_path(root).parent.parent
        attached = consumers.get(profile.id, [])
        recipe = profile.requirements_path(root)
        result.append({
            "id": profile.id, "kind": "tts", "driver": profile.driver,
            "installed": folder.is_dir() and not folder.is_symlink(),
            "ready": provider_ready(profile, root=root),
            "consumers": list(attached), "reference_count": len(attached),
            "can_uninstall": not attached and folder.is_dir() and not folder.is_symlink(),
            "runtime_fingerprint": _digest(recipe, "python-worker"),
            "relative_path": folder.relative_to(root).as_posix()
                if folder.is_relative_to(root) else "",
            "model_adapter_ids": list(profile.adapters),
        })
    folder = m2m_python(root).parent.parent
    attached = consumers.get("m2m100", [])
    result.append({
        "id": "m2m100", "kind": "translation", "driver": "trusted-python-worker",
        "installed": folder.is_dir() and not folder.is_symlink(),
        "ready": m2m_ready(root),
        "consumers": list(attached), "reference_count": len(attached),
        "can_uninstall": not attached and folder.is_dir() and not folder.is_symlink(),
        "runtime_fingerprint": _digest(root / REQUIREMENTS, "python-worker"),
        "relative_path": folder.relative_to(root).as_posix(),
        "model_adapter_ids": ["m2m100-transformers-v1"],
    })
    return result


def remove_unreferenced(runtime_id: str, expected_fingerprint: str,
                        *, root: Path = ROOT) -> bool:
    """Remove only known environment after a freshly derived reference check."""
    root = Path(root)
    if (not isinstance(runtime_id, str) or not _RUNTIME_ID.fullmatch(runtime_id)
        or not isinstance(expected_fingerprint, str)
        or not re.fullmatch("[0-9a-f]{64}", expected_fingerprint)):
        raise RuntimeRegistryError("invalid runtime removal request")
    with _LOCK:
        target = next((entry for entry in inventory(root)
                       if entry["id"] == runtime_id), None)
        if target is None:
            raise RuntimeRegistryError("unknown runtime")
        if target["runtime_fingerprint"] != expected_fingerprint:
            raise RuntimeRegistryError("runtime recipe changed; refresh before removal")
        if target["reference_count"]:
            raise RuntimeRegistryError("runtime is shared by installed models; remove those models first")
        relative = Path(target["relative_path"])
        folder = root / relative
        if (not target["installed"] or not target["can_uninstall"]
            or folder.is_symlink() or any(parent.is_symlink() for parent in folder.parents
                                          if parent != root.parent and parent != root)
            or not relative.parts or relative.parts[0] != "runtime"
            or len(relative.parts) != 3
            or relative.parts[1] not in ("engine-envs", "ai-envs")
            or folder.resolve().parent != (root / relative.parent).resolve()):
            raise RuntimeRegistryError("unmanaged or missing runtime directory")
        # Never kill all Python/Ollama. Only stop the specifically owned worker.
        if root.resolve() == ROOT.resolve():
            if runtime_id == "m2m100":
                from .m2m_runtime import reset
                reset()
            else:
                from .engine_provider_catalog import all_providers
                from .engine_worker_gateway import gateway
                gateway().reset(all_providers(root)[runtime_id].backend)
        shutil.rmtree(folder)
        return True
