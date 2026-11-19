"""Read-only verification of an extracted VoxWeaveTTS Universal v3 Portable.

Run on Windows from the project directory, for example:

  $stage = "$PWD\\dist\\VoxWeaveTTS-v3-validation-20261119"
  & "$stage\\runtime\\python\\python.exe" -X utf8 scripts\\verify_portable_model_packages.py --stage "$stage" --deep

The script verifies the native bundled MakHam package, embedded recovery
archive, runtime tools, and (optionally) every installed model SHA-256.
It does NOT install packages, modify settings, start a server, or download data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def verify(stage: Path, *, deep: bool = False) -> dict:
    stage = Path(stage).resolve()
    python = stage / "runtime" / "python" / "python.exe"
    if not python.is_file():
        raise ValueError("stage lacks the bundled Python interpreter")
    if Path(sys.executable).resolve() != python.resolve():
        raise ValueError("run verification with the Python bundled inside this stage")
    if not (stage / "runtime" / "tools" / "uv.exe").is_file():
        raise ValueError("offline v3 installer uv.exe is missing")
    if not (stage / "scripts" / "wheelhouse-locks").is_dir():
        raise ValueError("application-approved offline wheel locks are missing")
    if not (stage / "Start-Console.cmd").is_file() or not (stage / "VoxWeaveTTS.exe").is_file():
        raise ValueError("portable launchers are missing")
    stage_src = (stage / "src").resolve()
    if not stage_src.is_dir():
        raise ValueError("portable source is missing")
    sys.path.insert(0, str(stage_src))
    from voxweavetts.portable_doctor import report
    from voxweavetts.universal_model_packages import (
        inspect_archive, installed_packages, native_tts_packages,
    )
    status = report(stage, verify_wheelhouse=deep)
    if status["overall_state"] != "ready":
        raise ValueError("v3 portable doctor rejected stage: " + status["overall_state"])
    installed = installed_packages(stage)
    core = [(m, folder) for m, folder in installed
            if m["package"]["id"] == "makham-paradee"
            and m["package"]["kind"] == "tts"
            and m["package"]["version"] == "1.0.0"]
    if len(core) != 1 or len(native_tts_packages(stage)) != 1 or len(installed) != 1:
        raise ValueError("expected exactly one ready Universal v3 bundled MakHam model")
    bundled_manifest = core[0][0]
    if bundled_manifest["runtime"]["source"] != "core-bundled":
        raise ValueError("built-in MakHam is not using the v3 core runtime")
    archives = sorted((stage / "models" / "recovery-packages").glob("*.vwmodel"))
    if len(archives) != 1:
        raise ValueError("expected one offline v3 MakHam recovery archive")
    restored_manifest = inspect_archive(archives[0])
    if restored_manifest != bundled_manifest:
        raise ValueError("recovery archive and bundled model metadata differ")
    return {
        "format": "voxweavetts.portable-v3-verification",
        "verified": True,
        "stage": str(stage),
        "model": bundled_manifest["package"]["id"],
        "recovery_archive": archives[0].name,
        "deep_hash_verified": bool(deep),
        "verified_models": status["summary"]["native_models"],
        "offline_installer_bundled": True,
        "read_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True,
                        help="Extracted Universal v3 Portable directory")
    parser.add_argument("--deep", action="store_true",
                        help="Hash all installed model assets (read-only)")
    args = parser.parse_args(argv)
    try:
        result = verify(args.stage, deep=args.deep)
    except (OSError, ValueError, ImportError) as exc:
        parser.exit(2, "Portable v3 validation failed: " + str(exc) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
