"""Bootstrap and verify the v4 default voice in a disposable Portable stage.

Invoked by Build-Portable-V4.ps1 under the embedded Python interpreter.
No v3 model/package code, external download or license-server access.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from voxweavetts.universal_model_v4 import (
    install, inspect_archive, installed_packages, ready, V4PackageError
)


def verify(stage: Path) -> None:
    packages = installed_packages(stage)
    if (len(packages) != 1 or packages[0][0]["package"]["id"] != "makham-paradee"
        or packages[0][0]["package"]["kind"] != "tts"
        or not ready(stage, packages[0][0])
        or (stage / "models/universal/v3").exists()):
        raise V4PackageError("v4 Portable does not have exactly one ready MakHam default")
    print("V4_ONLY_MODEL_BOOTSTRAP_PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    stage = args.stage.resolve()
    if not (stage / "runtime/python/python.exe").is_file() or "dist" not in stage.parts:
        raise V4PackageError("v4 bootstrap requires a disposable dist Portable stage")
    if args.verify_only:
        verify(stage)
        return
    if args.package is None:
        raise V4PackageError("v4 MakHam archive required")
    m = inspect_archive(args.package)
    if (m["package"]["id"] != "makham-paradee"
        or m["package"]["version"] != "1.0.0"
        or m["package"]["kind"] != "tts"):
        raise V4PackageError("default v4 package must be the pinned MakHam identity")
    result = install(args.package, root=stage)
    if result["format_version"] != 4 or result["runtime_status"] != "ready":
        raise V4PackageError("default v4 model install failed")
    print("V4_DEFAULT_MODEL_INSTALLED",result["engine_id"])
    verify(stage)


if __name__ == "__main__":
    main()
