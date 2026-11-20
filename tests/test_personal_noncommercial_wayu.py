"""NC rights are visible in v4 manifests even before public license review."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from voxweavetts.universal_model_v4 import (
    inspect_archive, install, status, remove, ready,
)
from test_v4_plugin_packages import fixture
from scripts.build_vwmodel_v4 import build


class V4NonCommercialModelTests(unittest.TestCase):
    def test_v4_nc_rights_are_not_mislabeled_as_commercial_clearance(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            fixture(base)
            spec=base/"spec.json"
            payload=json.loads(spec.read_text("utf-8"))
            payload["package"]["id"]="qa-nc-voice"
            payload["package"]["title"]="Restricted voice"
            payload["rights"]["spdx"]="CC-BY-NC-4.0"
            payload["rights"]["review_status"]="hold"
            spec.write_text(json.dumps(payload),encoding="utf-8")
            archive=build(base/"source",spec,base/"restricted.vwmodel")
            manifest=inspect_archive(archive)
            portable=base/"portable"
            (portable/"runtime/python").mkdir(parents=True)
            (portable/"runtime/python/python.exe").write_bytes(b"test")
            install(archive,root=portable)
            detail=status(manifest,
                          portable/"models/universal/v4/tts/qa-nc-voice/1.0.0",
                          root=portable)
            self.assertTrue(detail["title"].startswith("[NC / NonCommercial]"))
            self.assertEqual(detail["license"]["review_status"],"hold")
            self.assertEqual(detail["license"]["spdx"],"CC-BY-NC-4.0")
            self.assertFalse(detail["license"].get("commercial_cleared",False))
            self.assertTrue(ready(portable,manifest))
            self.assertTrue(remove("qa-nc-voice","1.0.0",root=portable))

    def test_uninstalled_nc_package_does_not_run_or_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            from voxweavetts.universal_model_v4 import installed_packages
            self.assertFalse(installed_packages(Path(tmp)))
            self.assertFalse((Path(tmp)/"runtime/environments-v4").exists())


if __name__=="__main__":
    unittest.main()
