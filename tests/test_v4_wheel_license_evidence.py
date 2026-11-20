"""Offline v4 wheel rights scanner: metadata evidence is not publication approval."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from audit_v4_wheel_licenses import inspect,one_wheel


def fixture(tmp: Path, *, expression: str = "MIT",
            include_license: bool = True, native: bool = False,
            extra_metadata: str | None = None) -> Path:
    wheel_buffer = io.BytesIO()
    with zipfile.ZipFile(wheel_buffer,"w") as w:
        w.writestr("fixture-1.0.0.dist-info/METADATA",
                   extra_metadata if extra_metadata is not None else
                   ("Metadata-Version: 2.4\nName: fixture\nVersion: 1.0.0\n"
                    + ("License-Expression: " + expression + "\n" if expression else "")))
        # A top-level wheel METADATA takes precedence over vendored metadata.
        w.writestr("fixture/_vendor/x-2.dist-info/METADATA",
                   "Metadata-Version: 2.4\nName: x\nVersion: 2\n")
        if include_license:
            w.writestr("fixture-1.0.0.dist-info/licenses/LICENSE","Full license text")
        if native:
            w.writestr("fixture/engine.dll",b"binary-qa-only")
    wheel_bytes=wheel_buffer.getvalue()
    name="runtime/wheels/fixture-1.0.0-py3-none-any.whl"
    manifest={
        "format_version":4,
        "package":{"id":"fixture-engine"},
        "runtime":{"wheels":[name]},
        "rights":{"spdx":"MIT"},
        "files":[{"path":name,"sha256":hashlib.sha256(wheel_bytes).hexdigest(),
                  "size":len(wheel_bytes)}],
    }
    outer=tmp/"fixture.vwmodel"
    with zipfile.ZipFile(outer,"w") as z:
        z.writestr("manifest.json",json.dumps(manifest))
        z.writestr(name,wheel_bytes)
    return outer


class V4WheelLicenseEvidenceTests(unittest.TestCase):
    def test_reports_declared_license_and_ignores_vendor_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            path=fixture(Path(temp))
            result=inspect([path])
            self.assertEqual(result["unique_wheels_inspected"],1)
            self.assertFalse(result["public_release_authorized"])
            detail=result["wheel_details"][0]
            self.assertEqual(detail["name"],"fixture")
            self.assertEqual(detail["license_expression"],"MIT")
            self.assertEqual(detail["flags"],[])
            self.assertEqual(result["packages"][0]["missing_declaration_count"],0)

    def test_missing_declaration_and_text_are_flagged_not_cleared(self):
        with tempfile.TemporaryDirectory() as temp:
            path=fixture(Path(temp),expression="",include_license=False)
            report=inspect([path])
            flags=report["wheel_details"][0]["flags"]
            self.assertIn("missing-license-declaration",flags)
            self.assertIn("missing-embedded-license-or-notice-text",flags)
            self.assertFalse(report["public_release_authorized"])

    def test_gpl_native_binary_require_separate_review(self):
        with tempfile.TemporaryDirectory() as temp:
            path=fixture(Path(temp),expression="GPL-3.0-or-later",native=True)
            report=inspect([path])
            flags=report["wheel_details"][0]["flags"]
            self.assertIn("gpl-source-and-redistribution-compliance-review",flags)
            self.assertIn("native-binary-license-and-source-review",flags)
            self.assertEqual(report["packages"][0]["gpl_wheel_count"],1)
            self.assertEqual(report["packages"][0]["native_wheel_count"],1)

    def test_bsd_primary_with_embedded_gpl_notice_is_not_mislabeled_as_gpl(self):
        metadata=("Metadata-Version: 2.4\nName: fixture\nVersion: 1.0.0\n"
                  "Classifier: License :: OSI Approved :: BSD License\n"
                  "License: Copyright 2026 BSD project. " + "BSD terms. "*14
                  + "Third-party GNU GENERAL PUBLIC LICENSE notices included\n")
        with tempfile.TemporaryDirectory() as temp:
            archive=fixture(Path(temp),expression="",extra_metadata=metadata)
            details=inspect([archive])["wheel_details"][0]
            self.assertIn("embedded-third-party-copyleft-notices-review",details["flags"])
            self.assertNotIn("gpl-source-and-redistribution-compliance-review",details["flags"])

    def test_modified_wheel_rejected_against_declared_sha(self):
        with tempfile.TemporaryDirectory() as temp:
            path=fixture(Path(temp))
            with zipfile.ZipFile(path) as archive:
                data=archive.read("runtime/wheels/fixture-1.0.0-py3-none-any.whl")
                with self.assertRaisesRegex(ValueError,"SHA-256"):
                    one_wheel(archive,"runtime/wheels/fixture-1.0.0-py3-none-any.whl",
                              {"sha256":"0"*64,"size":len(data)})


if __name__=="__main__":
    unittest.main()
