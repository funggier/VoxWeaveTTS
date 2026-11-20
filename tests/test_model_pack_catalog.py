"""V4-only QA catalog policy; no stale v3 distribution catalog is published.

The eight source models are private QA artifacts until their third-party
redistribution conditions have been independently reviewed.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from verify_v4_model_inventory import EXPECTED,audit


class V4ModelPackCatalogTests(unittest.TestCase):
    def test_inventory_is_seven_speech_and_one_translation(self):
        expected={
            "makham-paradee":"tts",
            "fastthaig2p-thai-som":"tts",
            "kokoro-multilingual-int8":"tts",
            "melo-chinese-onnx":"tts",
            "supertonic3-multilingual-int8":"tts",
            "vachana-thai-four-voices":"tts",
            "wayu-paxa-edge-nc":"tts",
            "m2m100-418m":"translation",
        }
        self.assertEqual(EXPECTED,expected)

    def test_missing_qa_assets_do_not_count_as_distributable_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=audit(Path(tmp))
        self.assertEqual(report["expected"],8)
        self.assertEqual(report["found"],0)
        self.assertFalse(report["all_eight_present"])
        self.assertFalse(report["public_release_authorized"])
        self.assertEqual(set(report["missing"]),set(EXPECTED))

    def test_v3_public_catalog_is_not_in_active_v4_project(self):
        self.assertFalse((ROOT/"model-packs/catalog.json").exists())
        self.assertTrue((ROOT/"scripts/verify_v4_model_inventory.py").is_file())
        self.assertTrue((ROOT/"docs/V4_ALL_MODEL_QA_TH.md").is_file())

    def test_public_checksum_generation_is_rights_gated(self):
        script=(ROOT/"scripts/Generate-Release-Checksums.ps1").read_text("utf-8")
        self.assertIn("verify_v4_model_inventory.py",script)
        self.assertIn("--require-cleared",script)
        self.assertIn("Public Release BLOCKED",script)
        self.assertNotIn("ModelPackagesV3",script)


if __name__=="__main__":
    unittest.main()
