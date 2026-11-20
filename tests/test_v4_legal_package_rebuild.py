"""An offline v4 rights bundle can add documents, never alter vendor code."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from test_v4_plugin_packages import fixture
from voxweavetts.universal_model_v4 import inspect_archive
import repackage_v4_with_legal_evidence as legal
from verify_v4_legal_packaging import assess


class V4LegalPackageTests(unittest.TestCase):
    def test_legal_docs_preserve_original_worker_and_model_license(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            example=fixture(root/"fixture")
            qa=root/"demo-future-engine-UNRELEASED-QA-format-v4.vwmodel"
            shutil.copyfile(example,qa)
            evidence=root/"evidence"
            evidence.mkdir()
            (evidence/"wheel-index.json").write_text(
                json.dumps({"unique_wheel_evidence":{}}),encoding="utf-8")
            audit=root/"audit.json"
            audit.write_text(json.dumps({"wheel_details":[]}),encoding="utf-8")
            output=root/"demo-future-engine-LEGAL-QA-format-v4.vwmodel"
            with patch.object(legal,"EVIDENCE",evidence),patch.object(
                legal,"WHEEL_LICENSE_AUDIT",audit):
                report=legal.build(qa,output)
            self.assertEqual(report["extra_original_notice_files"],1)
            self.assertFalse(report["public_release_authorized"])
            before=inspect_archive(qa)
            after=inspect_archive(output)
            result=assess(before,after)
            self.assertTrue(result["original_worker_and_all_runtime_wheels_unchanged"])
            self.assertTrue(result["original_model_weights_and_configs_unchanged"])
            self.assertEqual(before["rights"],after["rights"])
            with zipfile.ZipFile(output) as zipped:
                rights=json.loads(zipped.read("assets/legal/WHEEL_RIGHTS_INDEX.json"))
            self.assertEqual(rights["weight_license_spdx_unmodified"],"MIT")
            self.assertFalse(rights["historical_weight_hashes_identical_to_v2"])
            self.assertTrue(rights["v4_legal_review_pending"])

    def test_repack_never_overwrites_existing_qa(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            example=fixture(folder/"source")
            src=folder/"fixture-UNRELEASED-QA-format-v4.vwmodel"
            shutil.copyfile(example,src)
            target=folder/"fixture-LEGAL-QA-format-v4.vwmodel"
            target.write_bytes(b"preserve")
            with self.assertRaises(FileExistsError):
                legal.build(src,target)
            self.assertEqual(target.read_bytes(),b"preserve")


if __name__=="__main__":
    unittest.main()
