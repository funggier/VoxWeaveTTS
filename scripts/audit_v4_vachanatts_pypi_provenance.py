"""Audit vachanatts 0.0.7 wheel versus the original PyPI source distribution.

Uses only local, SHA-pinned artifacts. Never invents a code license or puts
an unlicensed sdist into a redistributable v4 model package. The original voice
weights' Hugging Face MIT declaration is independent of this runtime Wheel.
"""
from __future__ import annotations

from email.parser import Parser
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "dist" / "ModelPackagesV4-NoticeQA"
SOURCE = (ROOT / "cache" / "v4-rights-evidence" / "vachanatts-0.0.7" /
          "vachanatts-0.0.7.tar.gz")
REPORT = (ROOT / "cache" / "v4-rights-evidence" / "runtime-sources" /
          "vachanatts-0.0.7" / "INDEX.json")
WHEEL_FILENAME = "vachanatts-0.0.7-py3-none-any.whl"
ORIGINAL_WHEEL_SHA = (
    "87244b82bc15711558ca5fd735379f3b77887ec655254c80ff6ad99c57686ad6"
)
ORIGINAL_SOURCE_SHA = (
    "c5e203446242076d70e61d1ca109d721e0bb031824dc93fed3d182db67a80bad"
)
ORIGINAL_SOURCE_URL = (
    "https://files.pythonhosted.org/packages/f2/53/"
    "c64e7b9a71db53867f90f5a21ecca3655cd0a9ac70725d3fd988e59e004c/"
    "vachanatts-0.0.7.tar.gz"
)


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def assess(package: Path, source: Path) -> dict:
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest["package"]["id"] != "vachana-thai-four-voices":
            raise ValueError("expected only the Vachana model package")
        member = next(
            n for n in manifest["runtime"]["wheels"]
            if Path(n).name == WHEEL_FILENAME
        )
        wheel_bytes = archive.read(member)
        pinned = next(p for p in manifest["files"] if p["path"] == member)
        if (len(wheel_bytes) != pinned["size"]
            or sha(wheel_bytes) != pinned["sha256"]
            or sha(wheel_bytes) != ORIGINAL_WHEEL_SHA):
            raise ValueError("Vachana Wheel does not match the PyPI 0.0.7 SHA")
        rights = manifest["rights"]["spdx"]

    src_bytes = source.read_bytes()
    if sha(src_bytes) != ORIGINAL_SOURCE_SHA:
        raise ValueError("vachanatts original PyPI source tarball SHA differs")

    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as wheel, tarfile.open(
        fileobj=io.BytesIO(src_bytes), mode="r:gz"
    ) as sdist:
        source_files = {}
        source_names = sdist.getnames()
        for member in sdist.getmembers():
            prefix = "vachanatts-0.0.7/"
            if member.isfile() and member.name.startswith(prefix+"vachanatts/"):
                relative = member.name.removeprefix(prefix)
                source_files[relative] = sdist.extractfile(member).read()

        wheel_files = set(wheel.namelist())
        verified = []
        for name, body in sorted(source_files.items()):
            if name not in wheel_files or wheel.read(name) != body:
                raise ValueError("sdist file differs from the Wheel: " + name)
            verified.append({"path": name, "sha256": sha(body)})

        aliases = []
        for name in sorted(x for x in wheel_files
                           if x.startswith("vachanatts1/") and x.endswith(".py")):
            direct = "vachanatts/" + name.removeprefix("vachanatts1/")
            code = wheel.read(name)
            aliases.append({
                "path": name,
                "sha256": sha(code),
                "equivalent_original_module": direct if direct in wheel_files else None,
                "byte_identical_to_original_module": (
                    direct in wheel_files and code == wheel.read(direct)
                ),
                "present_in_upstream_sdist": name in source_names,
            })
        metadata = Parser().parsestr(wheel.read(
            "vachanatts-0.0.7.dist-info/METADATA").decode("utf-8", "replace")
        )
        pkg_info = Parser().parsestr(sdist.extractfile(
            "vachanatts-0.0.7/PKG-INFO"
        ).read().decode("utf-8", "replace"))
        license_named_files = [
            n for n in source_names + sorted(wheel_files)
            if Path(n).name.lower() in (
                "license", "license.txt", "license.md", "copying",
                "copying.txt", "notice", "notice.txt"
            )
        ]
        declaration = {
            "wheel_license_field": metadata.get("License"),
            "wheel_license_expression": metadata.get("License-Expression"),
            "sdist_license_field": pkg_info.get("License"),
            "sdist_license_expression": pkg_info.get("License-Expression"),
            "source_license_files": license_named_files,
        }
        if len(verified) != 16 or len(aliases) != 9:
            raise ValueError("the upstream Vachana distribution changed unexpectedly")

    report = {
        "schema": "voxweavetts.v4-vachanatts-0.0.7-pypi-source-qa",
        "version": 1,
        "model_package": "vachana-thai-four-voices",
        "model_weight_license_unmodified": rights,
        "pypi_source_distribution_url": ORIGINAL_SOURCE_URL,
        "pypi_source_sha256": sha(src_bytes),
        "pypi_wheel_filename": WHEEL_FILENAME,
        "pypi_wheel_sha256": sha(wheel_bytes),
        "source_files_equal_to_wheel": verified,
        "source_files_matched": len(verified),
        "secondary_namespace_not_in_source_archive": aliases,
        "secondary_namespace_file_count": len(aliases),
        "secondary_namespace_different_from_primary_count": sum(
            not item["byte_identical_to_original_module"] for item in aliases
        ),
        "declared_code_license_evidence": declaration,
        "code_license_not_verified": (
            not any((declaration["wheel_license_field"],
                     declaration["wheel_license_expression"],
                     declaration["sdist_license_field"],
                     declaration["sdist_license_expression"],
                     declaration["source_license_files"]))
        ),
        "redistribution_status": "hold-until-code-rights-confirmed",
        "public_release_authorized": False,
        "note": (
            "The MIT model card does not automatically license PyPI code. "
            "Original Wheel and sdist were inspected unchanged. Secondary "
            "vachanatts1 modules do not appear in the PyPI sdist. No "
            "additional grant or GPL compatibility is inferred."
        ),
    }
    return report


def run(qa_dir: Path = QA, source: Path = SOURCE, output: Path = REPORT) -> dict:
    candidates = list(qa_dir.glob(
        "VoxWeaveTTS-vachana-thai-four-voices-*-LEGAL-QA-format-v4.vwmodel"
    ))
    if len(candidates) != 1:
        raise ValueError("expected exactly one original Vachana QA archive")
    result = assess(candidates[0], source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "sdist_to_wheel_files_verified": result["source_files_matched"],
        "extra_secondary_namespace_files": result[
            "secondary_namespace_file_count"],
        "extra_secondary_namespace_different_code": result[
            "secondary_namespace_different_from_primary_count"],
        "code_license_not_verified": result["code_license_not_verified"],
        "public_release_authorized": False,
    }, indent=2))
