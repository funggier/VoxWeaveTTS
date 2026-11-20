"""Read-only v4-only Portable readiness and package environment diagnosis.

No model installation, executable execution or online calls; checks only
declared v4 packages and their isolated offline runtimes. Legacy archives are
never opened and old model files are not deleted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .universal_model_v4 import installed_packages, ready, status

ROOT = Path(__file__).resolve().parents[2]
FORMAT = "voxweavetts.portable-doctor-v4"


def report(root: Path = ROOT, *, verify_wheelhouse: bool = False) -> dict:
    root = Path(root)
    python = root / "runtime" / "python" / "python.exe"
    if not python.is_file():
        python = root / ".venv" / "Scripts" / "python.exe"
    uv = root / "runtime" / "tools" / "uv.exe"
    packages = [
        status(manifest, folder, root=root)
        for manifest, folder in installed_packages(root)
    ]
    old_packages_present = (root / "models" / "universal" / "v3").exists()
    model_ready = any(p["package_id"] == "makham-paradee"
                      and p["model_kind"] == "tts" and p["runtime_ready"]
                      for p in packages)
    all_ready = all(p["runtime_ready"] for p in packages)
    core_ready = python.is_file() and uv.is_file()
    overall = "ready" if (core_ready and model_ready and all_ready
                          and not old_packages_present) else "needs-attention"
    return {
        "format": FORMAT,
        "overall_state": overall,
        "python_ready": python.is_file(),
        "offline_installer_ready": uv.is_file(),
        "default_model_ready": model_ready,
        "legacy_directory_present": old_packages_present,
        "package_count": len(packages),
        "packages": packages,
        "network_access": False,
        "verify_wheelhouse": verify_wheelhouse,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verify-wheelhouse", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    data = report(args.root, verify_wheelhouse=args.verify_wheelhouse)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("V4_PORTABLE_DIAGNOSIS",data["overall_state"])
        print("INSTALLED_V4_MODELS",data["package_count"])
        for item in data["packages"]:
            print(item["package_id"],item["runtime_state"])
        if data["legacy_directory_present"]:
            print("NOTICE: prior model folders detected; not loaded by v4-only Core")
    return 0 if data["overall_state"] == "ready" or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
