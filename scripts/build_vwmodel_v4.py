"""Create a single-file Universal v4 plugin from local assets, no network.

The developer supplies a source folder with plugin/worker.py and a JSON spec:
  {"package": {...}, "engine": {...}, "runtime": {...}, "rights": {...}}
The builder computes SHA256 for every file, then writes manifest.json first.
There is deliberately no publisher whitelist: the person who clicks Install
chooses to trust the archive's executable worker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from voxweavetts.universal_model_v4 import (
    FORMAT, VERSION, V4PackageError, _path, validate_manifest, inspect_archive,
)


def build(source: Path, spec_path: Path, output: Path) -> Path:
    source, spec_path, output = map(Path, (source, spec_path, output))
    if not source.is_dir() or source.is_symlink() or not spec_path.is_file():
        raise V4PackageError("v4 source directory / manifest spec required")
    if output.exists() or output.is_symlink():
        raise V4PackageError("v4 output already exists")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or set(spec) != {"package", "engine", "runtime", "rights"}:
        raise V4PackageError("invalid v4 builder spec")
    paths = []
    for path in source.rglob("*"):
        if path.is_symlink():
            raise V4PackageError("v4 builder cannot package links")
        if not path.is_file():
            continue
        relative = _path(path.relative_to(source).as_posix())
        if relative.casefold() == "manifest.json":
            raise V4PackageError("source must not contain manifest.json")
        paths.append(relative)
    if len({path.casefold() for path in paths}) != len(paths):
        raise V4PackageError("duplicate v4 source paths")
    files = []
    for relative in sorted(paths, key=str.casefold):
        path = source / relative
        with path.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        files.append({"path": relative, "size": path.stat().st_size, "sha256": sha})
    m = validate_manifest({
        "format": FORMAT, "format_version": VERSION,
        **spec, "files": files,
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=5, allowZip64=True) as zip_out:
            zip_out.writestr("manifest.json", json.dumps(
                m, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            for relative in sorted(paths, key=str.casefold):
                zip_out.write(source / relative, arcname=relative)
        inspect_archive(output)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source, args.spec, args.output)
    with result.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    print("V4_OFFLINE_PACKAGE_READY", result, digest)


if __name__ == "__main__":
    main()
