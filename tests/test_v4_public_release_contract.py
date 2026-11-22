"""Guardrail: public v0.12.11 Core cannot silently bundle pending-rights QA models."""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class PublicV4ReleaseContractTests(unittest.TestCase):
    def test_public_core_builder_requires_explicit_private_qa_opt_in(self):
        source=(ROOT/"scripts/Build-Portable-V4.ps1").read_text("utf-8")
        self.assertIn("[switch]$IncludeUnreleasedQaMakHam",source)
        self.assertIn("if ($IncludeUnreleasedQaMakHam)",source)
        self.assertIn("UNRELEASED-QA MakHam cannot be included in a public ZIP",source)
        self.assertIn("PUBLIC_V4_CORE_NO_MODEL_ASSETS_PASS",source)
        self.assertIn("V4_PUBLIC_CORE_MODEL_PACKAGES=0",source)
        self.assertIn("Copy-Tree (Join-Path $root 'third_party_licenses')",source)

    def test_version_is_exact_release_not_dev(self):
        version=(ROOT/"src/voxweavetts/__init__.py").read_text("utf-8")
        pyproject=(ROOT/"pyproject.toml").read_text("utf-8")
        self.assertIn('__version__ = "0.12.11"',version)
        self.assertIn('version = "0.12.11"',pyproject)
        self.assertNotIn("0.12.11.dev0",version)

    def test_distributable_example_is_a_tone_not_speech(self):
        spec=json.loads((ROOT/"examples/v4-demo-tone/spec.json").read_text("utf-8"))
        self.assertEqual(spec["format_version"],4) if "format_version" in spec else None
        self.assertEqual(spec["package"]["id"],"demo-tone-plugin")
        self.assertEqual(spec["rights"]["spdx"],"MIT")
        self.assertEqual(spec["runtime"]["wheels"],[])
        self.assertIn("not speech",spec["package"]["title"].lower())

    def test_upstream_uv_license_copies_have_pinned_provenance(self):
        attrs=(ROOT/".gitattributes").read_text("utf-8")
        self.assertIn("third_party_licenses/uv/LICENSE-MIT -text",attrs)
        self.assertIn("third_party_licenses/uv/LICENSE-APACHE -text",attrs)
        folder=ROOT/"third_party_licenses/uv"
        provenance=json.loads((folder/"SOURCE.json").read_text("utf-8"))
        self.assertEqual(provenance["version"],"0.12.9")
        self.assertEqual(len(provenance["source_revision"]),40)
        self.assertEqual(provenance["license"],"MIT OR Apache-2.0")
        self.assertEqual({x["file"] for x in provenance["files"]},
                         {"LICENSE-MIT","LICENSE-APACHE"})
        for row in provenance["files"]:
            raw=(folder/row["file"]).read_bytes()
            self.assertEqual(len(raw),row["size"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row["sha256"])
            self.assertIn(provenance["source_revision"],row["url"])

    def test_release_notes_do_not_claim_uncleared_weights_are_shipped(self):
        notes=(ROOT/"docs/RELEASE_NOTES_v0.12.1_TH.md").read_text("utf-8")
        self.assertIn("Core-only",notes)
        self.assertIn("ไม่แนบน้ำหนักโมเดล",notes)
        self.assertIn("Demo Tone",notes)
        self.assertIn("ยังไม่ได้รับอนุมัติ",notes)
        self.assertIn("Windows SAPI",notes)
        self.assertTrue((ROOT/"scripts/verify_v4_core_only_stage.py").is_file())


if __name__=="__main__":
    unittest.main()
