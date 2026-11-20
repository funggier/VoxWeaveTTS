"""Published v2/v3 model weight continuity evidence for noncommercial-first v4."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from audit_legacy_v4_release_provenance import compare


class ModelWeightContinuityTests(unittest.TestCase):
    def test_all_eight_v4_weights_match_published_v2_and_five_match_v3(self):
        proof = json.loads(
            (ROOT/"docs/v4_weight_continuity_summary.json").read_text("utf-8"))
        self.assertEqual(proof["schema"],
                         "voxweavetts.v4-previously-published-weights-provenance")
        self.assertEqual(proof["historical_release_assets_verified"],13)
        self.assertEqual(proof["v4_packages_checked"],8)
        self.assertEqual(sum(m["v2_identical"] for m in proof["models"].values()),8)
        self.assertEqual(sum(m["v3_identical"] is True for m in proof["models"].values()),5)
        for name,item in proof["models"].items():
            with self.subTest(model=name):
                self.assertTrue(item["v2_identical"])
                self.assertGreater(item["weight_file_count"],0)
                self.assertEqual(item["v2_model_assets_changed"],[])
                self.assertEqual(item["v2_model_assets_added"],[])
                self.assertEqual(item["v2_model_assets_removed"],[])
                self.assertGreater(item["offline_wheel_count"],0)
        self.assertFalse(proof["first_party_model_qa_approval_granted"])

    def test_identical_weights_do_not_imply_wheel_license_clearance(self):
        proof=json.loads(
            (ROOT/"docs/v4_weight_continuity_summary.json").read_text("utf-8"))
        self.assertTrue(proof["environment_wheels_require_separate_distributable_license_evidence"])
        self.assertTrue(proof["preexisting_public_release_is_not_automatic_redistribution_license"])

    def test_comparison_identifies_asset_added_changed_and_removed(self):
        old = {
            "weights":{"model.onnx":{"size":5,"sha256":"a"},"gone.bin":{"size":2,"sha256":"b"}},
            "assets":{}, "wheels":{}, "legal":{},
        }
        new = {
            "weights":{"model.onnx":{"size":5,"sha256":"c"},"extra.npy":{"size":3,"sha256":"d"}},
            "assets":{}, "wheels":{}, "legal":{},
        }
        comp=compare(old,new)
        self.assertFalse(comp["all_legacy_weight_files_identical"])
        self.assertEqual(comp["weights"]["changed_sha256"],["model.onnx"])
        self.assertEqual(comp["weights"]["v4_added"],["extra.npy"])
        self.assertEqual(comp["weights"]["legacy_removed"],["gone.bin"])

    def test_wayu_noncommercial_in_scope_without_relicensing(self):
        from voxweavetts.provider_rights import review
        info=review("wayu-paxa-edge-nc")
        self.assertEqual(info["upstream_model_license"],"CC-BY-NC-4.0")
        self.assertEqual(info["commercial_status"],"noncommercial-only")
        self.assertFalse(info["commercial_clearance_required_for_nc_release"])
        self.assertTrue(info["original_weight_files_sha_identical_to_published_v2"])
        self.assertTrue(info["new_v4_runtime_license_review_pending"])
        self.assertFalse(info["public_release_allowed"])

    def test_new_model_not_assumed_proven_by_old_publications(self):
        from voxweavetts.provider_rights import review
        info=review("future-user-made-engine")
        self.assertFalse(info["original_weight_files_sha_identical_to_published_v2"])
        self.assertFalse(info["public_release_allowed"])


if __name__=="__main__":
    unittest.main()
