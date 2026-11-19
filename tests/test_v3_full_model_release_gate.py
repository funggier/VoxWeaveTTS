"""Fail-closed regression for complete Universal v3 model releases."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts.provider_rights import (
    require_first_party_wheelhouse_publication, review,
)

ROOT = Path(__file__).resolve().parents[1]


def module_from_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompleteModelReleaseGateTests(unittest.TestCase):
    def test_complete_v3_release_requires_all_eight_original_and_translation_models(self):
        m = module_from_script("verify_complete_v3_release.py")
        self.assertEqual(set(m.EXPECTED), {
            "makham-paradee", "fastthaig2p-thai-som", "vachana-thai-four-voices",
            "kokoro-multilingual-int8", "wayu-paxa-edge-nc",
            "melo-chinese-onnx", "supertonic3-multilingual-int8", "m2m100-418m",
        })
        with tempfile.TemporaryDirectory() as temp:
            result = m.inspect_release(Path(temp), ROOT)
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["missing"]), 8)

    def test_missing_v3_packaged_runtime_never_counts_as_installed(self):
        m = module_from_script("verify_complete_v3_release.py")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "faked-v3.vwmodel"
            path.write_bytes(b"not-a-zip")
            report = m.inspect_release(Path(folder), ROOT)
        self.assertFalse(report["complete"])
        self.assertEqual(report["found_model_count"], 0)
        self.assertTrue(any("invalid package" in msg for msg in report["issues"]))

    def test_app_owned_rights_holds_are_not_clearable_by_model_metadata(self):
        for provider in ("kokoro", "vachana", "wayu-nc"):
            with self.subTest(provider=provider):
                status = review(provider)
                self.assertEqual(status["publication_state"], "hold")
                self.assertIs(status["offline_wheelhouse_release_allowed"], False)
                with self.assertRaises(ValueError):
                    require_first_party_wheelhouse_publication(provider)

    def test_future_release_checksum_builder_requires_full_catalog(self):
        source = (ROOT / "scripts" / "Generate-Release-Checksums.ps1").read_text(encoding="utf-8")
        self.assertIn("verify_complete_v3_release.py", source)
        self.assertIn("Full v3 model catalog is incomplete", source)
        self.assertIn("if ($Version -ne '0.11.0')", source)

    def test_preparation_stays_in_private_cache_not_public_release(self):
        draft = module_from_script("prepare_missing_v3_candidates.py")
        self.assertTrue(draft.OUTPUT.is_relative_to(ROOT / "cache"))
        self.assertFalse(draft.OUTPUT.is_relative_to(ROOT / "dist"))
        self.assertEqual(len(draft.MODELS), 3)
        for model in draft.MODELS.values():
            self.assertIn(model["runtime"], ("vachana", "kokoro", "wayu-nc"))

    def test_candidate_wheels_cannot_be_published_by_fake_trust_flags(self):
        m = module_from_script("verify_complete_v3_release.py")
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            candidate = directory / "vachana.vwmodel"
            candidate.write_bytes(b"test")
            fake = {
                "package": {"id": "vachana-thai-four-voices", "kind": "tts"},
                "adapter": {"id": "vachana-onnx-v1"},
                "runtime": {"id": "vachana", "source": "bundled-wheels"},
            }
            with patch.object(m, "inspect_archive", return_value=fake):
                report = m.inspect_release(directory)
        self.assertFalse(report["complete"])
        self.assertIn("unresolved dependency rights HOLD: vachana", report["issues"])


if __name__ == "__main__":
    unittest.main()
