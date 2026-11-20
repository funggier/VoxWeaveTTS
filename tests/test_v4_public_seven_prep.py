"""Fail-closed invariants for the seven released V4 packages."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_v4_seven_model_release as prep
from voxweavetts.universal_model_v4 import _path, V4PackageError


class SevenV4ReleaseTests(unittest.TestCase):
    def test_exactly_seven_original_license_packages_and_no_vachana(self):
        self.assertEqual(len(prep.MODEL_TERMS), 7)
        self.assertNotIn(prep.PRIVATE_MODEL, prep.MODEL_TERMS)
        self.assertEqual(prep.MODEL_TERMS["wayu-paxa-edge-nc"], "CC-BY-NC-4.0")
        self.assertEqual(
            prep.MODEL_TERMS["supertonic3-multilingual-int8"], "OpenRAIL-M"
        )
        with self.assertRaisesRegex(ValueError, "not in seven"):
            prep.discover(prep.PRIVATE_MODEL)
        with self.assertRaisesRegex(ValueError, "not in seven"):
            prep.discover("future-private-package")

    def test_every_copyleft_and_gpl_source_name_is_a_fixed_allowed_path(self):
        versions = (
            "espeak-ng-1.52.0",
            "phonemizer-3.6.0",
            "phonemizer-fork-3.3.2",
            "gensim-4.4.0",
            "num2words-0.5.6",
        )
        for name in versions:
            path = f"assets/legal/source/{name}-source.tar.gz"
            self.assertEqual(_path(path), path)
        for untrusted in (
            "assets/legal/source/unrelated.tar.gz",
            "assets/legal/source/../gensim-4.4.0-source.tar.gz",
            "runtime/other-binary.tar.gz",
            "assets/legal/source/gensim-4.4.1-source.tar.gz",
        ):
            with self.subTest(untrusted=untrusted):
                with self.assertRaises(V4PackageError):
                    _path(untrusted)

    def test_release_preparer_refuses_any_existing_artifact_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "keep.txt").write_text("never overwrite")
            with self.assertRaises(FileExistsError):
                prep.stage(directory)
            self.assertEqual((directory / "keep.txt").read_text(), "never overwrite")

    def test_release_filename_contains_no_qa_marker(self):
        name = "VoxWeaveTTS-wayu-paxa-edge-nc-1.0.0-LEGAL-QA-format-v4.vwmodel"
        final = name.replace("-LEGAL-QA-format-v4", "-format-v4")
        self.assertEqual(
            final,
            "VoxWeaveTTS-wayu-paxa-edge-nc-1.0.0-format-v4.vwmodel",
        )
        self.assertNotIn("QA", final)


if __name__ == "__main__":
    unittest.main()
