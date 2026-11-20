"""Read-only v4-only Windows Portable model / runtime verification.

Never executes, installs, repairs or deletes model files. The legacy v3 layout
is not supported, and no v3 reader is imported. A v4 default MakHam package
must be present and its runtime must be ready.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from voxweavetts.portable_doctor import report


def verify(stage: Path, *, deep: bool = False) -> dict:
    stage = Path(stage).resolve()
    data = report(stage)
    if data["overall_state"] != "ready":
        raise ValueError("v4-only Portable is not ready: " + data["overall_state"])
    if data["legacy_directory_present"]:
        raise ValueError("v3 directory is not permitted in new v4 Portable")
    models = data["packages"]
    if len(models) != 1 or models[0]["package_id"] != "makham-paradee":
        raise ValueError("expected only the default MakHam v4 model in Portable")
    if models[0]["format_version"] != 4 or not models[0]["runtime_ready"]:
        raise ValueError("v4 MakHam runtime is not ready")
    forbidden = {
        "universal_model_packages.py", "portable_runtime_v3.py",
        "package_install_v3.py", "makham_package.py",
        "engine_worker_host.py", "engine_worker_legacy.py",
        "engine_worker_wayu.py",
    }
    source = stage / "src/voxweavetts"
    if any((source / name).exists() for name in forbidden):
        raise ValueError("v3-specific source module found inside v4 Portable")
    if deep:
        from voxweavetts.universal_model_v4 import installed_packages, _sha
        for manifest, folder in installed_packages(stage):
            for item in manifest["files"]:
                if item["path"].startswith("runtime/wheels/"):
                    continue
                path = folder / item["path"]
                if _sha(path) != item["sha256"]:
                    raise ValueError("changed v4 model asset: " + item["path"])
    return {
        "format": "voxweavetts.portable-v4-verification",
        "ready": True,
        "deep": deep,
        "model": models[0]["package_id"],
        "format_version": 4,
        "v3_package_support": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--deep", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.stage, deep=args.deep),
                         ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(2, "Portable v4-only check failed: " + str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
