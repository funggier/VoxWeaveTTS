"""Build a native Universal .vwmodel v3 from model assets and v3-only metadata.

Input folder must already contain:
  manifest-assets.json : {"paths": ["model.onnx", ...]}
  legal/rights.json    : {"license": {...}, "source": {...}}
A separate JSON spec describes package, adapter, runtime and capabilities.
No v1 manifest is used or embedded. No model code or pip hooks are executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voxweavetts.universal_model_packages import (
    FORMAT, VERSION, UniversalPackageError, validate_manifest,
    make_package, _path, _validate_assets,
)

def build(source: Path, spec_path: Path, output: Path) -> Path:
    source, spec_path, output = map(Path, (source, spec_path, output))
    if not source.is_dir() or not spec_path.is_file():
        raise UniversalPackageError("source folder and native v3 spec required")
    if spec_path.stat().st_size > 65_536:
        raise UniversalPackageError("v3 spec too large")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or set(spec) != {
        "package", "adapter", "runtime", "capabilities",
    }:
        raise UniversalPackageError("invalid native v3 spec keys")
    assets = source / "manifest-assets.json"
    rights = source / "legal" / "rights.json"
    if not assets.is_file() or not rights.is_file():
        raise UniversalPackageError("native assets and rights files are required")
    manifest_names = set()
    for item in source.rglob("*"):
        if item.is_symlink():
            raise UniversalPackageError("symlinks forbidden in model source")
        if not item.is_file():
            continue
        relative = item.relative_to(source).as_posix()
        _path(relative)
        if relative.lower() == "manifest.json":
            raise UniversalPackageError("native builder does not accept embedded manifest.json")
        if relative.casefold() in manifest_names:
            raise UniversalPackageError("case-colliding source assets")
        manifest_names.add(relative.casefold())
    declared_lock = spec["runtime"].get("lockfile") if isinstance(spec["runtime"], dict) else None
    names = sorted(
        [item.relative_to(source).as_posix() for item in source.rglob("*") if item.is_file()],
        key=lambda s: s.casefold(),
    )
    if declared_lock is not None and declared_lock not in names:
        raise UniversalPackageError("runtime lock not present in source")
    files = []
    for name in names:
        file = source.joinpath(*PurePosixPath(name).parts)
        with file.open("rb") as inp:
            digest = hashlib.file_digest(inp, "sha256").hexdigest()
        files.append({"path": name, "size": file.stat().st_size, "sha256": digest})
    manifest = {
        "format": FORMAT, "format_version": VERSION,
        **spec, "assets": "manifest-assets.json",
        "rights": "legal/rights.json", "files": files,
    }
    validate_manifest(manifest)
    _validate_assets(source, manifest)
    return make_package(source, manifest, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Directory with model files and v3 data-only metadata")
    parser.add_argument("--spec", type=Path, required=True, help="Native Universal v3 spec JSON")
    parser.add_argument("--output", type=Path, required=True, help="Output .vwmodel filename")
    args = parser.parse_args()
    result = build(args.source, args.spec, args.output)
    with result.open("rb") as inp:
        digest = hashlib.file_digest(inp, "sha256").hexdigest()
    print("Native Universal v3 package created:", result)
    print("SHA256:", digest)
    print("No v1 format, scripts, dependencies or install hooks executed")


if __name__ == "__main__":
    main()
