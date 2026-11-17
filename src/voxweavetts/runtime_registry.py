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

from .managed_runtime_pool import inspect_environment

ROOT = Path(__file__).resolve().parents[2]
_LOCK = threading.RLock()
_REPAIR_JOBS: dict[tuple[str, str], dict] = {}
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
    # Native v2 packages have their own storage and manifest schema.
    # Keep legacy consumers in the safety inventory until explicitly removed.
    from .universal_model_packages import installed_packages as v2_packages
    for manifest, _folder in v2_packages(root):
        if manifest["adapter"]["trust"] != "builtin":
            continue
        provider_id = ("m2m100" if manifest["package"]["kind"] == "translation"
                       and manifest["adapter"]["id"] == "m2m100-transformers-v1"
                       else None)
        if manifest["package"]["kind"] == "tts":
            profile = provider_for_adapter(manifest["adapter"]["id"])
            if profile is not None and profile.plugin_path is None:
                provider_id = profile.id
        if provider_id:
            add(provider_id, f"v2:{manifest['package']['id']}@{manifest['package']['version']}")

    from .makham_package import active_model_dir, packaged_model_dir, PACKAGE_ID, PACKAGE_VERSION
    current_makham = active_model_dir(root)
    native_makham = root / "models" / "universal" / "v2" / "tts" / PACKAGE_ID / PACKAGE_VERSION
    if current_makham is not None and current_makham not in (packaged_model_dir(root), native_makham):
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
    from .offline_wheelhouse import status as wheelhouse_status
    from .m2m_runtime import ready as m2m_ready, python_path as m2m_python, REQUIREMENTS
    root = Path(root)
    consumers = _installed_consumers(root)
    result: list[dict] = []
    for profile in all_providers(root).values():
        folder = profile.python_path(root).parent.parent
        attached = consumers.get(profile.id, [])
        recipe = profile.requirements_path(root)
        digest = hashlib.sha256(recipe.read_bytes()).hexdigest() if recipe.is_file() and not recipe.is_symlink() else None
        health = inspect_environment(root=root, folder=folder,
            python=profile.python_path(root), marker=folder / ".voxweave-ready.json",
            expected_recipe_hash=digest)
        result.append({
            "id": profile.id, "kind": "tts", "driver": profile.driver,
            "installed": folder.is_dir() and not folder.is_symlink(),
            "ready": provider_ready(profile, root=root),
            "health_state": health["state"], "health": health,
            "repair_required": health["repair_required"],
            "wheelhouse": wheelhouse_status(root, profile.id),
            "repair": dict(_REPAIR_JOBS.get((str(root.resolve()), profile.id),
                                            {"state": "not_started", "error": None})),
            "consumers": list(attached), "reference_count": len(attached),
            "can_uninstall": not attached and folder.is_dir() and not folder.is_symlink(),
            "runtime_fingerprint": _digest(recipe, "python-worker"),
            "relative_path": folder.relative_to(root).as_posix()
                if folder.is_relative_to(root) else "",
            "model_adapter_ids": list(profile.adapters),
        })
    folder = m2m_python(root).parent.parent
    attached = consumers.get("m2m100", [])
    recipe = root / REQUIREMENTS
    digest = hashlib.sha256(recipe.read_bytes()).hexdigest() if recipe.is_file() and not recipe.is_symlink() else None
    health = inspect_environment(root=root, folder=folder,
        python=m2m_python(root), marker=folder / ".voxweave-ai-ready.json",
        expected_recipe_hash=digest)
    result.append({
        "id": "m2m100", "kind": "translation", "driver": "trusted-python-worker",
        "installed": folder.is_dir() and not folder.is_symlink(),
        "ready": m2m_ready(root),
        "health_state": health["state"], "health": health,
        "repair_required": health["repair_required"],
        "wheelhouse": wheelhouse_status(root, "m2m100"),
        "repair": dict(_REPAIR_JOBS.get((str(root.resolve()), "m2m100"),
                                        {"state": "not_started", "error": None})),
        "consumers": list(attached), "reference_count": len(attached),
        "can_uninstall": not attached and folder.is_dir() and not folder.is_symlink(),
        "runtime_fingerprint": _digest(root / REQUIREMENTS, "python-worker"),
        "relative_path": folder.relative_to(root).as_posix(),
        "model_adapter_ids": ["m2m100-transformers-v1"],
    })
    return result


def repair_async(runtime_id: str, expected_fingerprint: str,
                 *, root: Path = ROOT) -> dict:
    """Start an explicit offline repair from one allowlisted runtime record.

    A model or browser can request only a known ID, never a path, command,
    dependency list or network source. Existing venv remains on disk until a
    complete staged environment passes dependency and ABI checks.
    """
    root = Path(root)
    if (not isinstance(runtime_id, str) or not _RUNTIME_ID.fullmatch(runtime_id)
        or not isinstance(expected_fingerprint, str)
        or not re.fullmatch("[0-9a-f]{64}", expected_fingerprint)):
        raise RuntimeRegistryError("invalid runtime repair request")
    entries = inventory(root)
    entry = next((item for item in entries if item["id"] == runtime_id), None)
    if entry is None:
        raise RuntimeRegistryError("unknown runtime")
    if entry["runtime_fingerprint"] != expected_fingerprint:
        raise RuntimeRegistryError("runtime recipe changed; refresh before repair")
    if not entry["installed"] or not entry["repair_required"]:
        raise RuntimeRegistryError("runtime does not require repair")
    key = (str(root.resolve()), runtime_id)
    with _LOCK:
        active = _REPAIR_JOBS.get(key, {})
        if active.get("state") == "repairing":
            return dict(active)
        _REPAIR_JOBS[key] = {"state": "repairing", "error": None}

    def work() -> None:
        try:
            refreshed = next((item for item in inventory(root)
                              if item["id"] == runtime_id), None)
            if (refreshed is None or not refreshed["repair_required"]
                or refreshed["runtime_fingerprint"] != expected_fingerprint):
                raise RuntimeRegistryError("runtime changed before repair")
            if runtime_id == "m2m100":
                from .m2m_runtime import repair
                repair(root)
            else:
                from .engine_provider_installer import repair
                repair(runtime_id, root=root)
            with _LOCK:
                _REPAIR_JOBS[key] = {"state": "ready", "error": None}
        except Exception as exc:
            # A worker thread must never remain stuck in "repairing" if a
            # dependency installer times out or a filesystem operation fails.
            with _LOCK:
                _REPAIR_JOBS[key] = {"state": "failed",
                                     "error": str(exc) or "runtime repair failed"}
    threading.Thread(target=work, name="repair-runtime-" + runtime_id,
                     daemon=True).start()
    return {"state": "repairing", "error": None}


def install_verified_async(runtime_id: str, expected_fingerprint: str,
                           *, root: Path = ROOT) -> dict:
    """Explicit opt-in: verify every wheel then install/repair from pinned data."""
    from .offline_wheelhouse import status as wheelhouse_status
    root = Path(root)
    if (not isinstance(runtime_id, str) or not _RUNTIME_ID.fullmatch(runtime_id)
        or not isinstance(expected_fingerprint, str)
        or not re.fullmatch("[0-9a-f]{64}", expected_fingerprint)):
        raise RuntimeRegistryError("invalid verified runtime installation request")
    entry = next((x for x in inventory(root) if x["id"] == runtime_id), None)
    if (entry is None or entry["runtime_fingerprint"] != expected_fingerprint):
        raise RuntimeRegistryError("runtime recipe changed; refresh before install")
    if entry["ready"] or (entry["installed"] and not entry["repair_required"]):
        raise RuntimeRegistryError("runtime does not require verified installation")
    if wheelhouse_status(root, runtime_id)["ready_to_verify"] is not True:
        raise RuntimeRegistryError("trusted verified wheelhouse not prepared")
    key = (str(root.resolve()), runtime_id)
    with _LOCK:
        current = _REPAIR_JOBS.get(key, {})
        if current.get("state") == "repairing":
            return dict(current)
        _REPAIR_JOBS[key] = {"state": "repairing", "source": "wheelhouse",
                             "error": None}

    def work() -> None:
        try:
            refreshed = next((x for x in inventory(root)
                              if x["id"] == runtime_id), None)
            if (refreshed is None or refreshed["runtime_fingerprint"] != expected_fingerprint
                or refreshed["ready"]
                or (refreshed["installed"] and not refreshed["repair_required"])):
                raise RuntimeRegistryError("runtime changed before verified install")
            from .verified_runtime_installer import install_verified
            install_verified(runtime_id, root=root)
            with _LOCK:
                _REPAIR_JOBS[key] = {"state": "ready", "source": "wheelhouse",
                                     "error": None}
        except Exception as exc:
            with _LOCK:
                _REPAIR_JOBS[key] = {"state": "failed", "source": "wheelhouse",
                                     "error": str(exc) or "verified install failed"}
    threading.Thread(target=work, name="verified-runtime-" + runtime_id,
                     daemon=True).start()
    return {"state": "repairing", "source": "wheelhouse", "error": None}


def remove_unreferenced(runtime_id: str, expected_fingerprint: str,
                        *, root: Path = ROOT) -> bool:
    """Remove only known environment after a freshly derived reference check."""
    root = Path(root)
    if (not isinstance(runtime_id, str) or not _RUNTIME_ID.fullmatch(runtime_id)
        or not isinstance(expected_fingerprint, str)
        or not re.fullmatch("[0-9a-f]{64}", expected_fingerprint)):
        raise RuntimeRegistryError("invalid runtime removal request")
    with _LOCK:
        job = _REPAIR_JOBS.get((str(root.resolve()), runtime_id), {})
        if job.get("state") == "repairing":
            raise RuntimeRegistryError("runtime is being installed or repaired")
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
