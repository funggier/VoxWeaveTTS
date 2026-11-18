"""Read-only portability and runtime readiness diagnosis.

No installs, subprocesses, downloads, settings writes or model deserialization.
Reports only trusted runtime IDs and data-only installed v2 model metadata.
Optional deep wheel inspection verifies *bytes* against application-owned locks,
without creating a temporary wheel snapshot or marking a runtime installed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import __version__
from .offline_wheelhouse import (
    WheelhouseError, _check_directory, _digest, _inspect_wheel,
    _present, trusted_lock,
)
from .runtime_registry import inventory
from .universal_model_packages import (
    installed_packages, native_adapter_profile, platform_compatible,
)

ROOT = Path(__file__).resolve().parents[2]
FORMAT = "voxweavetts.portable-doctor-v1"
_MAKHAM = ("makham-paradee", "1.0.0")


class PortableDoctorError(ValueError):
    pass


def _local_file(root: Path, relative: str) -> bool:
    """Do not count redirected tools or root-external files as portable."""
    current = root
    if root.is_symlink():
        return False
    for component in Path(relative).parts:
        current = current / component
        if current.is_symlink():
            return False
    return (current.is_file()
            and current.resolve().is_relative_to(root.resolve()))


def _check_wheels(root: Path, runtime_id: str) -> tuple[str, int]:
    """Full lock/wheel SHA-256 and structural checks; never change bytes."""
    try:
        lock = trusted_lock(root, runtime_id)
        folder = _check_directory(root, runtime_id)
        _present(lock, folder)
        for row in lock["wheels"]:
            file = folder / row["filename"]
            _inspect_wheel(file, row)
            if _digest(file) != row["sha256"]:
                return "hash-mismatch", len(lock["wheels"])
        return "verified-for-inspection", len(lock["wheels"])
    except (OSError, ValueError, UnicodeError, RuntimeError, WheelhouseError):
        return "unavailable-or-unsafe", 0


def _next_action(entry: dict, *, uv_available: bool, base_python: bool) -> str:
    # A corrupt wheelhouse is unsafe even if an already-installed runtime
    # happens to work; never give a falsely reassuring "none" in deep mode.
    if entry["wheelhouse_state"] in ("hash-mismatch", "unavailable-or-unsafe"):
        return "replace-corrupt-wheelhouse"
    if entry["ready"]:
        return "none"
    if entry["health_state"] == "unsafe-environment":
        return "inspect-unsafe-runtime-manually"
    if not base_python:
        return "restore-portable-python"
    if not uv_available:
        return "restore-bundled-uv"
    if entry["wheelhouse_state"] == "verified-for-inspection":
        return ("rebuild-from-verified-wheelhouse" if entry["installed"]
                else "install-from-verified-wheelhouse")
    if entry["wheelhouse_state"] == "present-unverified":
        return ("verify-and-rebuild-wheelhouse" if entry["installed"]
                else "verify-and-install-wheelhouse")
    if entry["wheelhouse_state"] == "recipe-unsupported":
        return "review-online-provider-recipe"
    if entry["wheelhouse_state"] == "not-published":
        return "wheelhouse-not-published"
    return "supply-matching-wheelhouse"


def report(root: Path = ROOT, *, verify_wheelhouse: bool = False) -> dict[str, Any]:
    """Inspect an extracted portable root without loading any ML models."""
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise PortableDoctorError("select a real extracted Portable directory")
    bundled_python = _local_file(root, "runtime/python/python.exe")
    dev_python = _local_file(root, ".venv/Scripts/python.exe")
    core = ("bundled" if bundled_python else
            "development" if dev_python else "missing")
    bundled_uv = _local_file(root, "runtime/tools/uv.exe")
    # External uv in PATH is deliberately NOT portable or required to run doctor.
    # Do not launch it and do not trust arbitrary PATH for a standalone build.
    uv = "bundled" if bundled_uv else "missing"
    py_ok = bundled_python or dev_python

    records = inventory(root)
    runtimes: list[dict] = []
    state_by_id: dict[str, dict] = {}
    for raw in records:
        wheel = raw["wheelhouse"]
        wheel_state = wheel["state"]
        checked = False
        wheel_count = int(wheel["wheels"])
        if verify_wheelhouse and wheel["ready_to_verify"]:
            wheel_state, wheel_count = _check_wheels(root, raw["id"])
            checked = True
        info = {
            "id": raw["id"],
            "kind": raw["kind"],
            "installed": bool(raw["installed"]),
            "ready": bool(raw["ready"]),
            "health_state": raw["health_state"],
            "wheelhouse_state": wheel_state,
            "wheelhouse_sha256_checked": checked,
            "wheel_count": wheel_count,
            "relative_path": raw["relative_path"],
            "consumers": list(raw["consumers"]),
            "reference_count": int(raw["reference_count"]),
            "rights_review": raw.get("rights_review"),
        }
        info["recommended_action"] = _next_action(
            info, uv_available=bundled_uv, base_python=py_ok,
        )
        runtimes.append(info)
        state_by_id[raw["id"]] = info

    models: list[dict] = []
    valid = installed_packages(root)
    for manifest, folder in valid:
        metadata = native_adapter_profile(manifest, folder)
        runtime_id = manifest["runtime"]["id"]
        builtin_makham = (
            manifest["package"]["kind"] == "tts"
            and (manifest["package"]["id"], manifest["package"]["version"]) == _MAKHAM
            and manifest["adapter"]["id"] == "makham-paradee-onnx-v1"
        )
        runtime_ready = (
            builtin_makham and bundled_python
            or bool(state_by_id.get(runtime_id, {}).get("ready", False))
        )
        models.append({
            "package_id": manifest["package"]["id"],
            "version": manifest["package"]["version"],
            "kind": manifest["package"]["kind"],
            "adapter_trusted": metadata is not None,
            "runtime_id": runtime_id,
            "runtime_ready": runtime_ready,
            "platform_compatible": platform_compatible(manifest),
            "license_spdx": metadata["license"]["spdx"] if metadata else "unknown",
            "rights_review_status": (
                metadata["license"]["review_status"] if metadata else "unknown"
            ),
            "file_hashes_checked": "metadata-only",
        })

    # An invalid manifest is not silently counted as an installed model;
    # report count only, never follow links or expose user-added paths.
    invalid_count = 0
    valid_files = {(folder / "manifest.json").resolve() for _, folder in valid}
    for kind in ("tts", "translation"):
        base = root / "models" / "universal" / "v2" / kind
        if base.is_dir() and not base.is_symlink():
            for file in base.glob("*/*/manifest.json"):
                if file.is_symlink() or file.resolve() not in valid_files:
                    invalid_count += 1

    blocking_models = [
        m for m in models if not (
            m["adapter_trusted"] and m["platform_compatible"] and m["runtime_ready"]
        )
    ]
    core_ready = core != "missing"
    invalid_wheelhouses = sum(
        r["wheelhouse_state"] in ("hash-mismatch", "unavailable-or-unsafe")
        for r in runtimes
    )
    status = ("incomplete" if not core_ready or not models
              else "needs-attention" if blocking_models or invalid_count
              or invalid_wheelhouses else "ready")
    return {
        "format": FORMAT,
        "version": __version__,
        "core": {
            "python": core, "uv": uv,
            "portable": bundled_python and bundled_uv,
            "no_operations_performed": True,
        },
        "overall_state": status,
        "summary": {
            "native_models": len(models),
            "models_waiting_for_runtime": len(blocking_models),
            "invalid_native_manifests": invalid_count,
            "invalid_wheelhouses": invalid_wheelhouses,
            "runtimes_ready": sum(x["ready"] for x in runtimes),
            "runtimes_with_rights_hold": sum(
                (r.get("rights_review") or {}).get("publication_state") == "hold"
                for r in runtimes
            ),
            "runtimes_total": len(runtimes),
        },
        "models": models,
        "runtimes": runtimes,
        "limitations": [
            "Model weight bytes are not SHA-checked by this report",
            "Wheelhouse hash verification is read-only and not legal clearance",
            "A ready runtime does not prove model inference succeeds",
            "Fresh-machine install and third-party dependency licenses need separate tests",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verify-wheelhouse", action="store_true",
                        help="read and verify wheel ZIP structure and SHA-256 (slower)")
    parser.add_argument("--strict", action="store_true",
                        help="exit 2 if core or installed model is not usable")
    args = parser.parse_args(argv)
    try:
        data = report(args.root, verify_wheelhouse=args.verify_wheelhouse)
    except (PortableDoctorError, OSError, ValueError) as exc:
        parser.exit(1, "Portable diagnostic failed: " + str(exc) + "\n")
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        core = data["core"]
        print(f"VoxWeaveTTS {data['version']} | {data['overall_state']}")
        print(f"Core Python: {core['python']} | bundled uv: {core['uv']}")
        print(f"Native models: {data['summary']['native_models']} "
              f"| unavailable models: {data['summary']['models_waiting_for_runtime']} "
              f"| invalid manifests: {data['summary']['invalid_native_manifests']}")
        for model in data["models"]:
            print(f"  MODEL {model['package_id']}@{model['version']}: "
                  f"{'ready' if model['runtime_ready'] else 'runtime-missing'} "
                  f"| rights={model['license_spdx']} "
                  f"| review={model['rights_review_status']}")
        for runtime in data["runtimes"]:
            print(f"  RUNTIME {runtime['id']}: {runtime['health_state']} "
                  f"| wheelhouse={runtime['wheelhouse_state']} "
                  f"| next={runtime['recommended_action']}"
                  + (" | rights=" + runtime["rights_review"]["commercial_status"]
                     + "/" + runtime["rights_review"]["publication_state"]
                     if runtime.get("rights_review") else ""))
        print("Read-only diagnosis. No dependencies, models or settings changed.")
    return 2 if args.strict and data["overall_state"] != "ready" else 0


if __name__ == "__main__":
    raise SystemExit(main())
