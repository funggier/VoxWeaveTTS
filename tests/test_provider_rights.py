"""Review-only rights metadata and first-party wheelhouse release gate.

These tests never grant legal clearance and never install a wheel or model.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from voxweavetts.provider_rights import (
    review, require_first_party_wheelhouse_publication,
)


def script_module(filename: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / filename
    spec = importlib.util.spec_from_file_location(
        "provider_rights_" + filename.replace(".", "_"), path,
    )
    assert spec is not None and spec.loader is not None
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class RightsReviewTests(unittest.TestCase):
    def test_wayu_weights_nc_and_inference_code_have_separate_terms(self):
        policy = review("wayu-nc")
        self.assertEqual(policy["publication_state"], "hold")
        self.assertEqual(policy["model_license"], "CC-BY-NC-4.0")
        self.assertEqual(policy["commercial_status"], "noncommercial-only")
        self.assertIn("Apache-2.0", policy["code_license"])
        self.assertIn("remote-vcs-and-direct-url-recipe", policy["reasons"])
        self.assertFalse(policy["legal_clearance"])

    def test_vachana_and_kokoro_are_holds_for_distinct_reasons(self):
        vachana = review("vachana")
        kokoro = review("kokoro")
        self.assertEqual(vachana["publication_state"], "hold")
        self.assertEqual(kokoro["publication_state"], "hold")
        self.assertEqual(vachana["commercial_status"], "review-required")
        self.assertIn("vachanatts-wheel-no-license-declaration",
                      vachana["reasons"])
        self.assertIn("phonemizer-gpl-3-or-later-compliance-review",
                      kokoro["reasons"])
        self.assertIn("espeakng-loader-native-license-review",
                      kokoro["reasons"])
        self.assertFalse(kokoro["offline_wheelhouse_release_allowed"])

    def test_approved_external_provider_stays_review_required(self):
        with self.assertRaisesRegex(ValueError,"unknown"):
            review("my-signed-provider")
        status=review("my-signed-provider",approved_external=True)
        self.assertEqual(status["commercial_status"],"review-required")
        self.assertEqual(status["publication_state"],"review-required")
        self.assertFalse(status["legal_clearance"])
        for invalid in ("../", "bad/path", "", "a"*200):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                review(invalid,approved_external=True)

    def test_review_is_immutable_from_model_or_caller_edits(self):
        original = review("wayu-nc")
        original["legal_clearance"] = True
        original["reasons"].clear()
        reread = review("wayu-nc")
        self.assertFalse(reread["legal_clearance"])
        self.assertTrue(reread["reasons"])
        with self.assertRaisesRegex(ValueError,"unknown"):
            review("../models")
        with self.assertRaises(ValueError):
            review(None)

    def test_normal_previously_published_wheelhouse_is_not_disabled(self):
        for runtime_id in ("pythaitts", "sherpa", "m2m100"):
            with self.subTest(runtime_id=runtime_id):
                record=review(runtime_id)
                self.assertEqual(record["publication_state"], "review-required")
                self.assertFalse(record["legal_clearance"])
                self.assertIsNone(record["offline_wheelhouse_release_allowed"])
                # Gate below explicitly blocks only first-party holds, not
                # installed/upstream-published wheelhouses.
                self.assertIsNone(
                    require_first_party_wheelhouse_publication(runtime_id)
                )
        for runtime_id in ("vachana", "kokoro", "wayu-nc"):
            with self.subTest(runtime_id=runtime_id):
                with self.assertRaisesRegex(ValueError, "HOLD"):
                    require_first_party_wheelhouse_publication(runtime_id)

    def test_rights_review_keeps_distribution_holds(self):
        from voxweavetts.provider_rights import review
        self.assertEqual(review("wayu-nc")["commercial_status"], "noncommercial-only")
        self.assertEqual(review("vachana")["publication_state"], "hold")
        self.assertEqual(review("kokoro")["publication_state"], "hold")
        self.assertEqual(review("m2m100")["publication_state"], "review-required")


class ReviewedPublicationGateTests(unittest.TestCase):
    def test_even_publish_reviewed_flag_cannot_publish_a_held_runtime(self):
        script = script_module("prepare_verified_wheelhouse.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate"
            candidate.mkdir()
            fake = {
                "runtime_id": "vachana",
                "wheels": [{"filename": "vachanatts-0.0.7-py3-none-any.whl",
                            "sha256": "a"*64, "size": 1024}],
            }
            with (patch.object(script, "ROOT", root),
                  patch.object(script, "draft_lock", return_value=fake),
                  patch.object(sys, "argv", [
                      "prepare_verified_wheelhouse.py", "--runtime-id",
                      "vachana", "--source", str(candidate),
                      "--publish-reviewed",
                  ]), redirect_stdout(io.StringIO())):
                with self.assertRaisesRegex(ValueError, "HOLD"):
                    script.main()
            self.assertTrue((root/"cache"/"wheelhouse-drafts"/"vachana.json").is_file())
            self.assertFalse((root/"scripts"/"wheelhouse-locks"/"vachana.json").exists())
            self.assertFalse((root/"runtime"/"wheelhouse"/"vachana").exists())

    def test_read_only_rights_audit_does_not_promote_held_wheels(self):
        script = script_module("audit_wheelhouse_rights.py")
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            file = directory / "vachanatts-0.0.7-py3-none-any.whl"
            with zipfile.ZipFile(file, "w") as z:
                z.writestr("vachanatts-0.0.7.dist-info/METADATA",
                           "Metadata-Version: 2.1\nName: vachanatts\n"
                           "Version: 0.0.7\n")
                z.writestr("vachanatts-0.0.7.dist-info/WHEEL",
                           "Wheel-Version: 1.0\n")
            audit = script.audit_wheels(directory)
            self.assertEqual(len(audit),1)
            self.assertIn("license-not-declared", audit[0]["flags"])
            self.assertIn("license-text-not-in-wheel", audit[0]["flags"])


if __name__ == "__main__":
    unittest.main()
