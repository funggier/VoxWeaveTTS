"""Universal v4 first-party rights gate; installation is independent of licensing."""
from __future__ import annotations

import unittest

from voxweavetts.provider_rights import (
    KNOWN_V4_MODELS, review, require_first_party_publication,
)


class RightsReviewV4Tests(unittest.TestCase):
    def test_eight_models_have_independent_source_licenses_and_holds(self):
        self.assertEqual(len(KNOWN_V4_MODELS),8)
        self.assertEqual(sum(note["kind"]=="tts" for note in KNOWN_V4_MODELS.values()),7)
        self.assertEqual(sum(note["kind"]=="translation" for note in KNOWN_V4_MODELS.values()),1)
        for model, note in KNOWN_V4_MODELS.items():
            with self.subTest(model=model):
                info = review(model)
                self.assertEqual(info["review_version"],4)
                self.assertEqual(info["package_kind"],note["kind"])
                self.assertEqual(info["upstream_model_license"],note["model_license"])
                self.assertIn(info["publication_state"],("review-required","hold"))
                self.assertFalse(info["public_release_allowed"])
                self.assertFalse(info["legal_clearance"])
                self.assertFalse(info["user_install_is_redistribution_clearance"])
                self.assertTrue(info["user_installs_offline_without_license_server"])
                self.assertGreater(len(info["reasons"]),0)
                with self.assertRaisesRegex(ValueError,"publication blocked"):
                    require_first_party_publication(model)

    def test_wayu_weights_remain_explicitly_noncommercial(self):
        info=review("wayu-paxa-edge-nc")
        self.assertEqual(info["publication_state"],"review-required")
        self.assertEqual(info["upstream_model_license"],"CC-BY-NC-4.0")
        self.assertEqual(info["commercial_status"],"noncommercial-only")
        self.assertIn("weights-cc-by-nc-4.0-prohibit-commercial-use",info["reasons"])

    def test_kokoro_and_vachana_have_separate_wheel_legal_blockers(self):
        kokoro=review("kokoro-multilingual-int8")
        vachana=review("vachana-thai-four-voices")
        self.assertEqual(kokoro["publication_state"],"review-required")
        self.assertEqual(vachana["publication_state"],"hold")
        self.assertIn("phonemizer-gpl-3-or-later-compliance-review",kokoro["reasons"])
        self.assertIn("espeakng-loader-native-binary-source-and-notices-review",
                      kokoro["reasons"])
        self.assertIn("vachanatts-0.0.7-wheel-no-license-declaration",
                      vachana["reasons"])
        self.assertIn("vachanatts1-nine-python-files-not-in-original-pypi-sdist",
                      vachana["reasons"])

    def test_primary_licenses_are_independent_of_core_mit_and_wheel_metadata(self):
        for package_id in KNOWN_V4_MODELS:
            with self.subTest(package_id=package_id):
                record = review(package_id)
                self.assertEqual(record["core_license"], "MIT")
                self.assertFalse(record["wheel_metadata_gap_is_automatic_conflict"])
                if package_id == "vachana-thai-four-voices":
                    self.assertEqual(record["primary_license_comparison"],
                                     "source-code-license-not-established")
                else:
                    self.assertEqual(record["primary_license_comparison"],
                                     "no-automatic-conflict-separate-original-terms")
                self.assertFalse(record["public_release_allowed"])

    def test_model_license_does_not_clear_offline_runtime_rights(self):
        for model in ("makham-paradee","m2m100-418m","melo-chinese-onnx",
                      "supertonic3-multilingual-int8"):
            with self.subTest(model=model):
                self.assertFalse(review(model)["public_release_allowed"])
        self.assertEqual(review("supertonic3-multilingual-int8")["upstream_model_license"],
                         "OpenRAIL-M")

    def test_user_installs_new_third_party_engine_without_core_whitelist(self):
        record=review("future-model-from-user")
        self.assertEqual(record["publication_state"],"review-required")
        self.assertEqual(record["upstream_model_license"],"unverified")
        self.assertEqual(record["primary_license_comparison"],"unknown")
        self.assertTrue(record["user_installs_offline_without_license_server"])
        with self.assertRaises(ValueError):
            require_first_party_publication("future-model-from-user")

    def test_read_only_result_cannot_promote_app_policy(self):
        info=review("wayu-paxa-edge-nc")
        info["public_release_allowed"]=True
        info["reasons"].clear()
        fresh=review("wayu-paxa-edge-nc")
        self.assertFalse(fresh["public_release_allowed"])
        self.assertNotEqual(fresh["reasons"],[])

    def test_invalid_ids_cannot_inject_paths_or_change_policy(self):
        for value in ("../model",r"..\model","",None,123,"bad/name",
                      "A"*100):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    review(value)


if __name__=="__main__":
    unittest.main()
