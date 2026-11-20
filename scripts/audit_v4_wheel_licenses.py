"""Offline, read-only license-evidence inventory for wheels inside v4 .vwmodel.

This is a RESEARCH TOOL, not a legal clearance or publication gate.
Streams each wheel through a bounded spool file; checks its pinned outer
SHA-256 and records license fields/files plus GPL/NC/native review flags.
No executable model code, pip/uv, network call or wheel installer is run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import zipfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / "dist" / "ModelPackagesV4-QA"
_RELEVANT = ("license", "licence", "copying", "notice", "copyright")
_MISSING = "(not declared)"


def one_wheel(outer: zipfile.ZipFile, entry: str, pin: dict) -> dict:
    sha = hashlib.sha256()
    total = 0
    with tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024, mode="w+b") as work:
        with outer.open(entry) as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                sha.update(chunk)
                total += len(chunk)
                if total > pin["size"]:
                    raise ValueError("wheel exceeds signed manifest size")
                work.write(chunk)
        if total != pin["size"] or sha.hexdigest() != pin["sha256"]:
            raise ValueError("wheel SHA-256 mismatch: " + entry)
        work.seek(0)
        with zipfile.ZipFile(work) as wheel:
            names = wheel.namelist()
            # Vendored projects (e.g. setuptools/_vendor/) may carry their
            # own METADATA. The wheel distribution metadata lives at root.
            meta_paths = [n for n in names if n.endswith(".dist-info/METADATA")
                          and len(n.split("/")) == 2]
            if len(meta_paths) != 1:
                raise ValueError("wheel has missing/ambiguous METADATA: " + entry)
            metadata = BytesParser(policy=default).parsebytes(wheel.read(meta_paths[0]))
            name = metadata.get("Name") or Path(entry).name
            version = metadata.get("Version") or ""
            expression = str(metadata.get("License-Expression") or "").strip()
            field = str(metadata.get("License") or "").strip()
            classifiers = [str(x).removeprefix("License :: ").strip()
                           for x in metadata.get_all("Classifier", [])
                           if str(x).startswith("License :: ")]
            # Some legacy License headers embed the *full* license text.
            # Never copy full texts into the report; only a short classifier.
            bundled_copyleft_text = False
            if len(field) > 120:
                lower = field.lower()
                primary = " ".join(classifiers).lower()
                bundled_copyleft_text = "gnu general public" in lower
                if "bsd license" in primary:
                    # NumPy/SciPy embed third-party GPL license notices inside
                    # a BSD-licensed distribution. Do NOT call the whole
                    # NumPy/SciPy wheel GPL on account of those notices.
                    field = "BSD-style primary license; full third-party notices in METADATA"
                elif field.lstrip().lower().startswith("gnu general public license"):
                    field = "GPL full license text in METADATA"
                elif "apache" in primary:
                    field = "Apache-style primary license; long license text in METADATA"
                else:
                    field = "Long license/notice text in METADATA"
            license_files = [
                n for n in names if any(t in n.split("/")[-1].lower() for t in _RELEVANT)
                and not n.lower().endswith(".py")
            ]
            native_files = [n for n in names if n.lower().endswith((".dll", ".pyd", ".exe", ".so", ".dylib"))]
            native_evidence = []
            for native_path in native_files:
                # Native components may be duplicated inside a wheel (e.g.
                # sherpa-onnx-core installs the same DLL in two locations).
                # Hash the *actual bytes* with bounded memory, not the name.
                digest = hashlib.sha256()
                with wheel.open(native_path) as binary:
                    for block in iter(lambda: binary.read(1024 * 1024), b""):
                        digest.update(block)
                native_evidence.append({
                    "path": native_path,
                    "size": wheel.getinfo(native_path).file_size,
                    "sha256": digest.hexdigest(),
                })
            declared = bool(expression or field or classifiers)
            has_text = bool(license_files)
            terms = " ".join([expression, field] + classifiers).lower()
            flags = []
            if not declared:
                flags.append("missing-license-declaration")
            if not has_text:
                flags.append("missing-embedded-license-or-notice-text")
            if "gpl" in terms or "gnu general public" in terms:
                flags.append("gpl-source-and-redistribution-compliance-review")
            if bundled_copyleft_text and not (
                "gpl" in terms or "gnu general public" in terms
            ):
                flags.append("embedded-third-party-copyleft-notices-review")
            if "by-nc" in terms or "noncommercial" in terms:
                flags.append("noncommercial-restrictions-review")
            if native_files:
                flags.append("native-binary-license-and-source-review")
            return {
                "name": str(name), "version": str(version),
                "filename": Path(entry).name, "sha256": pin["sha256"],
                "license_expression": expression or _MISSING,
                "license_field": field or _MISSING,
                "license_classifiers": classifiers[:8],
                "license_notice_files": license_files[:15],
                "native_binary_count": len(native_files),
                "native_binaries": native_evidence,
                "flags": flags,
            }


def inspect(archives: list[Path]) -> dict:
    cache: dict[str, dict] = {}
    packages = []
    for archive in archives:
        with zipfile.ZipFile(archive) as outer:
            manifest = json.loads(outer.read("manifest.json"))
            if manifest.get("format_version") != 4:
                raise ValueError("expected a v4 archive: " + str(archive))
            pins = {item["path"]: item for item in manifest["files"]}
            wheels = []
            for entry in manifest["runtime"]["wheels"]:
                pin = pins[entry]
                if pin["sha256"] not in cache:
                    cache[pin["sha256"]] = one_wheel(outer, entry, pin)
                wheels.append(cache[pin["sha256"]])
            flagged = [w for w in wheels if w["flags"]]
            packages.append({
                "package_id": manifest["package"]["id"],
                "archive": archive.name, "wheel_count": len(wheels),
                "wheel_names": [w["name"] for w in wheels],
                "flagged_wheels": [
                    {"name": w["name"], "version": w["version"], "flags": w["flags"]}
                    for w in flagged
                ],
                "missing_declaration_count": sum(
                    "missing-license-declaration" in w["flags"] for w in wheels
                ),
                "gpl_wheel_count": sum(
                    "gpl-source-and-redistribution-compliance-review" in w["flags"]
                    for w in wheels
                ),
                "native_wheel_count": sum(w["native_binary_count"] > 0 for w in wheels),
                "native_binary_file_count": sum(w["native_binary_count"] for w in wheels),
                "manifest_rights_claim": manifest["rights"].get("spdx"),
                "public_release_authorized": False,
            })
    return {
        "format": "voxweavetts.v4-wheel-license-evidence",
        "version": 1, "scope": "read-only, offline, SHA-verified wheels",
        "unique_wheels_inspected": len(cache),
        "unique_native_payloads_inspected": len({
            item["sha256"] for wheel in cache.values()
            for item in wheel["native_binaries"]
        }),
        "package_count": len(packages),
        "public_release_authorized": False,
        "packages": packages,
        "wheel_details": sorted(cache.values(), key=lambda w: (w["name"].lower(), w["version"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packages", type=Path, default=PACKAGES)
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args()
    archives = sorted(args.packages.glob("*UNRELEASED-QA-format-v4.vwmodel"))
    if args.only is not None:
        wanted = set(args.only)
        archives = [a for a in archives
                    if any(a.name.startswith("VoxWeaveTTS-" + name + "-") for name in wanted)]
        if len(archives) != len(wanted):
            raise ValueError("one or more requested v4 packages not found")
    if not archives:
        raise ValueError("no v4 QA packages selected")
    result = inspect(archives)
    if args.write_report:
        location = args.write_report.resolve()
        qa = (ROOT / "cache" / "v4-qa-candidates").resolve()
        if not location.is_relative_to(qa):
            raise ValueError("rights audit reports must remain in local QA cache")
        location.parent.mkdir(parents=True, exist_ok=True)
        location.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print("WHEEL_LICENSE_AUDIT_REPORT", location, flush=True)
    summary = {
        "packages": [
            {k: v for k, v in p.items()
             if k in ("package_id", "wheel_count", "missing_declaration_count",
                      "gpl_wheel_count", "native_wheel_count",
                      "native_binary_file_count")}
            for p in result["packages"]
        ],
        "unique_wheels_inspected": result["unique_wheels_inspected"],
        "unique_native_payloads_inspected": result["unique_native_payloads_inspected"],
        "public_release_authorized": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
