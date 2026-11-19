"""Read-only Universal v3 model and relocatable-runtime diagnosis.

No installs, subprocesses, network requests, settings writes, or model
deserialization. Deep verification hashes installed model files only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import __version__
ROOT = Path(__file__).resolve().parents[2]
FORMAT = "voxweavetts.portable-doctor-v3"
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


def report(root: Path = ROOT, *, verify_wheelhouse: bool = False) -> dict[str, Any]:
    """Read-only v3 package and relocatable-runtime diagnosis.

    The --verify-wheelhouse compatibility flag now verifies *installed v3
    package assets*, not a separately distributed runtime download.
    """
    from .universal_model_packages import (
        installed_packages, package_status, platform_compatible,
        native_adapter_profile,
    )
    from .portable_runtime_v3 import (
        ready as runtime_ready, fingerprint, runtime_folder,
    )
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise PortableDoctorError("select a real extracted portable directory")
    bundled_python = _local_file(root, "runtime/python/python.exe")
    dev_python = _local_file(root, ".venv/Scripts/python.exe")
    bundled_uv = _local_file(root, "runtime/tools/uv.exe")
    py_name = ("bundled" if bundled_python else "development" if dev_python else "missing")
    models = []
    runtimes_by_fingerprint = {}
    invalid_count = 0
    for manifest, folder in installed_packages(root):
        profile = native_adapter_profile(manifest, folder)
        status = package_status(manifest, root=root, folder=folder)
        files_verified = False
        if verify_wheelhouse:
            from hashlib import file_digest
            files_verified = True
            for entry in manifest["files"]:
                if entry["path"].startswith("runtime/wheels/"):
                    continue  # v3 discards wheel archives after verified installation
                item = folder / entry["path"]
                with item.open("rb") as stream:
                    if file_digest(stream, "sha256").hexdigest() != entry["sha256"]:
                        files_verified = False
                        break
        rt_ready = runtime_ready(root, manifest)
        models.append({
            "package_id": manifest["package"]["id"],
            "version": manifest["package"]["version"],
            "kind": manifest["package"]["kind"],
            "adapter_trusted": profile is not None,
            "runtime_id": manifest["runtime"]["id"],
            "runtime_ready": rt_ready,
            "platform_compatible": platform_compatible(manifest),
            "license_spdx": status["license"].get("spdx", "unknown"),
            "rights_review_status": status["license"].get("review_status", "unknown"),
            "file_hashes_checked": "valid" if files_verified else
                "failed" if verify_wheelhouse else "metadata-only",
        })
        if manifest["runtime"]["source"] != "core-bundled":
            digest = fingerprint(manifest)
            if digest not in runtimes_by_fingerprint:
                relative = runtime_folder(root, manifest).relative_to(root).as_posix()
                runtimes_by_fingerprint[digest] = {
                    "id": manifest["runtime"]["id"],
                    "kind": manifest["package"]["kind"],
                    "health_state": "ready" if rt_ready else "not-installed",
                    "relative_path": relative,
                    "ready": rt_ready,
                    "wheelhouse_state": "embedded-in-v3-package",
                    "recommended_action": "none" if rt_ready else
                        "uninstall-model-and-reinstall-v3-package",
                    "rights_review": None,
                    "reference_count": 0,
                    "consumers": [],
                }
            runtimes_by_fingerprint[digest]["reference_count"] += 1
            runtimes_by_fingerprint[digest]["consumers"].append(
                manifest["package"]["id"] + "@" + manifest["package"]["version"])
    # Old v2 directories are deliberately ignored, never deleted.
    base = root / "models" / "universal" / "v3"
    for kind in ("tts", "translation", "voice-cloning", "stt", "llm"):
        folder = base / kind
        if folder.is_dir() and not folder.is_symlink():
            for marker in folder.glob("*/*/manifest.json"):
                if not any((root / "models" / "universal" / "v3" /
                            item["kind"] / item["package_id"] /
                            item["version"] / "manifest.json") == marker
                           for item in models):
                    invalid_count += 1
    runtimes = list(runtimes_by_fingerprint.values())
    failures = [m for m in models if not
                (m["adapter_trusted"] and m["runtime_ready"] and
                 m["platform_compatible"] and m["file_hashes_checked"] != "failed")]
    overall = ("incomplete" if py_name == "missing"
               else "needs-attention" if failures or invalid_count
               else "incomplete" if not models else "ready")
    return {
        "format": "voxweavetts.portable-doctor-v3",
        "version": __version__,
        "core": {"python": py_name,
                 "uv": "bundled" if bundled_uv else "missing",
                 "portable": bundled_python and bundled_uv,
                 "no_operations_performed": True},
        "overall_state": overall,
        "summary": {"native_models": len(models),
                    "models_waiting_for_runtime": len(failures),
                    "invalid_native_manifests": invalid_count,
                    "invalid_wheelhouses": 0,
                    "runtimes_ready": sum(x["ready"] for x in runtimes),
                    "runtimes_with_rights_hold": 0,
                    "runtimes_total": len(runtimes)},
        "models": models, "runtimes": runtimes,
        "limitations": [
            "No network access or modification by Doctor",
            "Normal report does not rehash large model assets",
            "A ready runtime does not prove inference succeeds",
            "Native DLL and target-machine compatibility need real-device testing",
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
