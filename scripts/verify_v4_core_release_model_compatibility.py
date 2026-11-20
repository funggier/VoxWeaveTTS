"""Validate a staged portable Core against the actual public seven V4 packs.

A Core may pass every isolated unit test yet reject previously published
packages; this release gate catches precisely that compatibility regression.
Never installs or downloads anything and never changes any model archive.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGES = ROOT / "dist" / "ModelPackagesV4-PublicSeven"
EXPECTED = {
    "makham-paradee": "Apache-2.0",
    "fastthaig2p-thai-som": "Apache-2.0",
    "melo-chinese-onnx": "MIT",
    "supertonic3-multilingual-int8": "OpenRAIL-M",
    "kokoro-multilingual-int8": "Apache-2.0",
    "wayu-paxa-edge-nc": "CC-BY-NC-4.0",
    "m2m100-418m": "MIT",
}
LEGAL_SOURCE = {
    "kokoro-multilingual-int8": (
        "espeak-ng-1.52.0", "phonemizer-3.6.0"
    ),
    "wayu-paxa-edge-nc": (
        "espeak-ng-1.52.0", "phonemizer-fork-3.3.2",
        "gensim-4.4.0", "num2words-0.5.6"
    ),
}


def verify(stage: Path, packages: Path = DEFAULT_PACKAGES) -> dict:
    stage = stage.resolve()
    packages = packages.resolve()
    if not (stage / "runtime/python/python.exe").is_file():
        raise ValueError("not a full Windows portable Core stage")
    path = stage / "src" / "voxweavetts" / "universal_model_v4.py"
    if not path.is_file():
        raise ValueError("portable Core V4 validator is missing")
    # Do not accidentally use a dev source module loaded earlier.
    import importlib.util
    spec = importlib.util.spec_from_file_location("_portable_core_v4_release_gate", path)
    if spec is None or spec.loader is None:
        raise ValueError("unable to load portable validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifests = {}
    for model, rights in EXPECTED.items():
        candidates = list(packages.glob(
            f"VoxWeaveTTS-{model}-*-format-v4.vwmodel"
        ))
        if len(candidates) != 1:
            raise ValueError("expected one public V4 model: " + model)
        archive = candidates[0]
        try:
            manifest = module.inspect_archive(archive)
        except Exception as error:
            raise AssertionError(
                f"Core incompatible with released {model}: {error}"
            ) from error
        if (manifest["package"]["id"] != model
            or manifest["rights"]["spdx"] != rights):
            raise ValueError("upstream model identity/license changed: " + model)
        with zipfile.ZipFile(archive) as bundle:
            paths = set(bundle.namelist())
        for component in LEGAL_SOURCE.get(model, ()):
            name = f"assets/legal/source/{component}-source.tar.gz"
            if name not in paths:
                raise ValueError("missing original source archive: " + name)
        manifests[model] = {
            "compatible": True,
            "version": manifest["package"]["version"],
            "upstream_license": rights,
            "legal_source_archive_count": len(LEGAL_SOURCE.get(model, ())),
        }
    public_models = list(packages.glob("*.vwmodel"))
    if len(public_models) != 7:
        raise ValueError("public model directory must contain exactly seven packs")
    if any("vachana" in archive.name.casefold()
           or "vachanatts" in archive.name.casefold()
           for archive in public_models):
        raise ValueError("private Vachana package included in public release")
    return {
        "schema": "voxweavetts.v4-core-public-model-compatibility",
        "compatible_package_count": len(manifests),
        "core_stage": str(stage),
        "core_v4_only": module.VERSION == 4,
        "kokoro_original_gpl_sources_present": True,
        "wayu_original_gpl_lgpl_sources_present": True,
        "vachana_excluded": True,
        "models": manifests,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--packages", type=Path, default=DEFAULT_PACKAGES)
    args = parser.parse_args()
    print(json.dumps(verify(args.stage, args.packages),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
