"""Stage exactly seven full/offline V4 model archives, never Vachana.

The upstream models retain their original licenses, including OpenRAIL-M
and Wayu CC-BY-NC-4.0. Each model's unchanged original payload is matched
against local original QA and license evidence. This is a publisher-directed
packaging process, not a legal opinion or license re-grant. Fail closed on
missing notices, source tarballs, format corruption or unexpected packages.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from voxweavetts.universal_model_v4 import inspect_archive
from verify_v4_legal_packaging import check

TAG = "v0.12.1-modelpacks-v4"
OUT = ROOT / "dist" / "ModelPackagesV4-PublicSeven"
ORIGINAL = ROOT / "dist" / "ModelPackagesV4-QA"
REVIEW = ROOT / "dist" / "ModelPackagesV4-SevenReleaseReview"
TOKENIZERS_REVIEW = ROOT / "dist" / "ModelPackagesV4-TokenizersLegalQA"
MODEL_TERMS = {
    "makham-paradee": "Apache-2.0",
    "fastthaig2p-thai-som": "Apache-2.0",
    "melo-chinese-onnx": "MIT",
    "supertonic3-multilingual-int8": "OpenRAIL-M",
    "kokoro-multilingual-int8": "Apache-2.0",
    "wayu-paxa-edge-nc": "CC-BY-NC-4.0",
    "m2m100-418m": "MIT",
}
PRIVATE_MODEL = "vachana-thai-four-voices"
# Core v0.12.1 rejected GPL/LGPL legal-source .tar.gz files; v0.12.2 fixes it.
CORE_MINIMUM = {
    model: ("v0.12.2" if model in {
        "kokoro-multilingual-int8", "wayu-paxa-edge-nc"
    } else "v0.12.1")
    for model in MODEL_TERMS
}
ORT131 = {
    "makham-paradee", "fastthaig2p-thai-som", "kokoro-multilingual-int8",
}
SHERPA = {"melo-chinese-onnx", "supertonic3-multilingual-int8"}
ESPEAK = {"kokoro-multilingual-int8", "wayu-paxa-edge-nc"}
COPYLEFT = {"kokoro-multilingual-int8", "wayu-paxa-edge-nc"}
TOKENIZERS = {"wayu-paxa-edge-nc", "m2m100-418m"}


def sha_file(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def check_extra_terms(package: Path, model: str) -> None:
    manifest = inspect_archive(package)
    if (manifest["package"]["id"] != model
        or manifest["rights"]["spdx"] != MODEL_TERMS[model]
        or manifest["format_version"] != 4):
        raise ValueError("original model terms or identity changed")
    wheels = manifest["runtime"]["wheels"]
    with zipfile.ZipFile(package) as archived:
        names = set(archived.namelist())
        legal = {"assets/legal/WHEEL_RIGHTS_INDEX.json"}
        model_license = (
            "assets/LICENSE.txt" if model == "m2m100-418m"
            else "assets/legal/license.txt"
        )
        legal.add(model_license)
        if model in ORT131:
            legal |= {
                "assets/legal/onnxruntime-1.31.1-LICENSE.txt",
                "assets/legal/onnxruntime-1.31.1-ThirdPartyNotices.txt",
                "assets/legal/onnxruntime-1.31.1-provenance.json",
            }
        if model in SHERPA:
            legal |= {
                "assets/legal/onnxruntime-1.28.2-LICENSE.txt",
                "assets/legal/onnxruntime-1.28.2-ThirdPartyNotices.txt",
                "assets/legal/onnxruntime-1.28.2-provenance.json",
                "assets/legal/sherpa-onnx-apache-2.0.txt",
            }
        if model in ESPEAK:
            legal |= {
                "assets/legal/source/espeak-ng-1.52.0-source.tar.gz",
                "assets/legal/espeak-ng-1.52.0-provenance.json",
                "assets/legal/espeakng-loader-LICENSE.txt",
            }
        if model in COPYLEFT:
            legal.add("assets/legal/copyleft-upstream-sources-index.json")
        if model in TOKENIZERS:
            legal |= {
                "assets/legal/tokenizers-0.22.2-source-license.txt",
                "assets/legal/tokenizers-0.22.2-license-provenance.json",
            }
        if model == "wayu-paxa-edge-nc":
            legal.add("assets/legal/acceptable-use.txt")
            legal |= {
                "assets/legal/source/phonemizer-fork-3.3.2-source.tar.gz",
                "assets/legal/source/gensim-4.4.0-source.tar.gz",
                "assets/legal/source/num2words-0.5.6-source.tar.gz",
            }
        if model == "kokoro-multilingual-int8":
            legal.add("assets/legal/source/phonemizer-3.6.0-source.tar.gz")
        absent = legal - names
        if absent:
            raise ValueError(model + ": missing license/source files: "
                             + ", ".join(sorted(absent)))
        if PRIVATE_MODEL in package.name or any(
            PRIVATE_MODEL in path for path in names
        ) or any("vachanatts" in path.casefold() for path in wheels):
            raise ValueError("private Vachana code must not be released")


def discover(model: str) -> Path:
    if model not in MODEL_TERMS or model == PRIVATE_MODEL:
        raise ValueError("not in seven original-license V4 release models")
    base = TOKENIZERS_REVIEW if model in TOKENIZERS else REVIEW
    matches = list(base.glob(
        f"VoxWeaveTTS-{model}-*-LEGAL-QA-format-v4.vwmodel"
    ))
    if len(matches) != 1:
        raise ValueError("missing/duplicate corresponding QA archive " + model)
    return matches[0]


def stage(output_dir: Path = OUT) -> dict:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("release destination must be fresh/empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = {
        "schema": "voxweavetts.v4-first-party-seven-model-release",
        "tag": TAG,
        "compatible_portable_core": "v0.12.2",
        "minimum_portable_core_by_model": dict(CORE_MINIMUM),
        "compatibility_note": (
            "Kokoro and Wayu require Core v0.12.2 for original GPL/LGPL "
            "source .tar.gz files. All five other models accept v0.12.1."
        ),
        "model_count": len(MODEL_TERMS),
        "private_model_excluded": PRIVATE_MODEL,
        "models": {},
        "legal_statement": (
            "Each third-party model retains its original upstream terms. "
            "Redistributors and recipients must observe notices, copyright "
            "attribution, OpenRAIL use restrictions, GPL/LGPL source obligations "
            "and Wayu CC-BY-NC noncommercial limits. No license is re-granted."
        ),
        "formal_legal_opinion": False,
    }
    try:
        for model in MODEL_TERMS:
            source = discover(model)
            args = {
                "models": [model],
                "require_native_notices": model in SHERPA,
                "require_espeak_source": model in ESPEAK,
                "require_onnxruntime_131": model in ORT131,
                "require_copyleft_sources": model in COPYLEFT,
            }
            audit = check(ORIGINAL, source.parent, **args)
            if (audit["packages_verified"] != 1
                or not audit["original_licensing_restrictions_preserved"]):
                raise ValueError("original model package audit failed: " + model)
            check_extra_terms(source, model)
            filename = source.name.replace("-LEGAL-QA-format-v4",
                                           "-format-v4")
            if filename == source.name:
                raise ValueError("unrecognized QA package filename")
            target = output_dir / filename
            if target.exists():
                raise FileExistsError("model package target already exists")
            expected_sha = sha_file(source)
            shutil.copy2(source, target)
            if sha_file(target) != expected_sha:
                raise ValueError("model archive SHA-256 differs after staging")
            copied = inspect_archive(target)
            if copied["package"]["id"] != model:
                raise ValueError("staged V4 package identity mismatch")
            catalog["models"][model] = {
                "filename": filename,
                "sha256": expected_sha,
                "bytes": target.stat().st_size,
                "license": MODEL_TERMS[model],
                "minimum_portable_core": CORE_MINIMUM[model],
                "original_worker_weights_and_wheels_unchanged": True,
                "wheel_count": audit["total_original_wheels_preserved"],
                "embedded_legal_evidence_files":
                    audit["total_new_legal_files"],
                "original_terms_apply": True,
            }
        if len(catalog["models"]) != 7 or PRIVATE_MODEL in catalog["models"]:
            raise ValueError("seven-model release membership incorrect")
        checksums = "".join(
            f'{details["sha256"]} *{details["filename"]}\n'
            for details in sorted(catalog["models"].values(),
                                  key=lambda x: x["filename"])
        )
        (output_dir / f"SHA256SUMS-{TAG}.txt").write_text(
            checksums, encoding="utf-8"
        )
        (output_dir / "CATALOG-v4-seven.json").write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return catalog
    except BaseException:
        # Do not delete user files. Output path is required fresh/empty.
        raise


if __name__ == "__main__":
    result = stage()
    print(json.dumps({
        "release_tag": result["tag"],
        "seven_packages_staged": result["model_count"],
        "original_licenses": {
            m: r["license"] for m, r in result["models"].items()
        },
        "total_bytes": sum(r["bytes"] for r in result["models"].values()),
        "private_vachana_excluded": True,
    }, indent=2))
