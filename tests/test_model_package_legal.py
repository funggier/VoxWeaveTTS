"""Provenance notices are embedded, hashed and installed with optional packs."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from voxweavetts import model_packages as packs


class ModelPackageLegalTests(unittest.TestCase):
    def test_each_pack_includes_its_real_upstream_notices(self):
        for packname, prefix in (("vachana", "vachana"), ("fastthaig2p", "fastthaig2p")):
            with self.subTest(packname=packname):
                parent=packs.ROOT/"model-packs"/packname
                self.assertTrue((parent/"LICENSE.txt").is_file())
                self.assertTrue((parent/"ATTRIBUTION.md").is_file())
                if prefix=="fastthaig2p":
                    self.assertTrue((parent/"NOTICE.txt").is_file())
                    self.assertIn("Apache License",(parent/"LICENSE.txt").read_text(encoding="utf-8"))
                    self.assertIn("Amazon",(parent/"NOTICE.txt").read_text(encoding="utf-8"))
                else:
                    self.assertIn("MIT License",(parent/"LICENSE.txt").read_text(encoding="utf-8"))

    def test_builder_integrity_and_install_with_legal_files(self):
        original=packs.ROOT
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for packname in ("vachana","fastthaig2p"):
                source=original/"model-packs"/packname
                target=root/"model-packs"/packname
                target.mkdir(parents=True)
                for filename in ("LICENSE.txt","NOTICE.txt","ATTRIBUTION.md"):
                    if (source/filename).is_file():
                        shutil.copy2(source/filename,target/filename)
            (root/"cache"/"temp").mkdir(parents=True)
            with patch.object(packs,"ROOT",root):
                src=root/"vachana"
                for name in ("speaker_config.json","voices/th_f_1.onnx",
                             "voices/th_f_2.onnx","voices/th_m_1.onnx",
                             "voices/th_m_2.onnx"):
                    file=src/name;file.parent.mkdir(parents=True,exist_ok=True)
                    file.write_bytes((b"valid-enough-fixture"*85) if name.endswith(".onnx")
                                     else b'{"audio":{"sample_rate":22050}}')
                archive=root/"vachana.vwmodel"
                packs.pack_local_vachana(src,archive)
                installed=packs.install_model_package(archive,base=root/"packages")
                self.assertEqual(installed["license"]["spdx"],"MIT")
                self._verify(archive,installed,{"legal/license.txt","legal/attribution.md"})
                self.assertTrue((root/"packages"/"vachana-thai-four-voices"/"1.0.0"/
                                 "legal"/"attribution.md").is_file())

                src=root/"fastthai";src.mkdir()
                for name in ("config.json","kokoro_thai.onnx","thai_som.npy"):
                    (src/name).write_bytes((b"fixture-bytes"*100) if name!="config.json"
                                            else b'{"lang":"th"}')
                archive=root/"fastthai.vwmodel"
                packs.pack_local_fastthai(src,archive)
                installed=packs.install_model_package(archive,base=root/"packages")
                self.assertEqual(installed["license"]["spdx"],"Apache-2.0")
                self._verify(archive,installed,{"legal/license.txt","legal/notice.txt",
                                                 "legal/attribution.md"})
                self.assertEqual(len(packs.installed_packages(base=root/"packages")),2)

    def _verify(self,archive,manifest,required):
        files={row["path"]:row for row in manifest["files"]}
        self.assertTrue(required <= set(files))
        with zipfile.ZipFile(archive) as zipped:
            self.assertEqual(set(zipped.namelist()),{"manifest.json"}|set(files))
            for name in required:
                data=zipped.read(name)
                self.assertEqual(hashlib.sha256(data).hexdigest(),files[name]["sha256"])
                self.assertIn(name.encode("utf-8"),json.dumps(manifest).encode("utf-8"))


if __name__=="__main__":
    unittest.main()
