"""Safe uninstall/reinstall for built-in MakHam and its verified .vwmodel."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import makham_package as makham
from voxweavetts import model_packages as packages


class MakhamPackageTests(unittest.TestCase):
    def test_rejects_modifications_on_removable_builtin_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"original"
            source.mkdir()
            payload={"paradee_thai_int8.onnx":b"original"*1024,
                     "config.json":b"config"*250}
            for name,data in payload.items():
                (source/name).write_bytes(data)
            pins={name:hashlib.sha256(data).hexdigest() for name,data in payload.items()}
            with patch.object(makham,"PINNED_ASSETS",pins):
                archive=root/"makham.vwmodel"
                packages.pack_local_makham(source,archive)
                base=root/"models"/"packages"
                m=packages.install_model_package(archive,base=base)
                self.assertEqual(packages.engine_id_for(m),makham.ENGINE_ID)
                installed=base/makham.PACKAGE_ID/makham.PACKAGE_VERSION
                assert installed.is_dir()
                (installed/"other.txt").write_text("user file")
                with self.assertRaisesRegex(packages.ModelPackageError,"unknown files"):
                    packages.remove_model_package(makham.PACKAGE_ID,
                                                  makham.PACKAGE_VERSION,base=base)
                self.assertTrue((installed/"other.txt").exists())
                (installed/"other.txt").unlink()
                config=installed/"config.json"
                original=config.read_bytes()
                config.write_bytes(b"tampered"*250)
                with self.assertRaisesRegex(packages.ModelPackageError,"modified"):
                    packages.remove_model_package(makham.PACKAGE_ID,
                                                  makham.PACKAGE_VERSION,base=base)
                self.assertTrue(installed.is_dir())
                config.write_bytes(original)
                self.assertTrue(packages.remove_model_package(
                    makham.PACKAGE_ID,makham.PACKAGE_VERSION,base=base))
                self.assertFalse(installed.exists())

    def test_legacy_uninstall_preserves_restorable_archive_and_user_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            legacy=makham.legacy_model_dir(root)
            legacy.mkdir(parents=True)
            weights=legacy/"paradee_thai_int8.onnx"
            with weights.open("wb") as out:
                for _ in range(128):
                    out.write(b"trusted_original" * 4096)
            config=legacy/"config.json"
            config.write_bytes(b"config"*300)
            pins={}
            for name in ("paradee_thai_int8.onnx","config.json"):
                with (legacy/name).open("rb") as source:
                    pins[name]=hashlib.file_digest(source,"sha256").hexdigest()
            unrelated=root/"data"/"settings"/"language-routes.json"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("do not change",encoding="utf-8")
            with patch.object(makham,"PINNED_ASSETS",pins):
                self.assertTrue(makham.legacy_present(root))
                self.assertTrue(makham.remove_legacy_model(root=root))
                self.assertFalse(legacy.exists())
                self.assertTrue(makham.disabled_marker(root).is_file())
                self.assertEqual(unrelated.read_text(encoding="utf-8"),"do not change")
                recovery=makham.recovery_archive(root)
                self.assertTrue(recovery.is_file())
                import zipfile
                with zipfile.ZipFile(recovery) as z:
                    data=packages.validate_manifest(json.loads(z.read("manifest.json")))
                    self.assertEqual(data["license"]["spdx"],"Apache-2.0")
                    self.assertEqual(data["package_id"],makham.PACKAGE_ID)
                self.assertFalse(makham.remove_legacy_model(root=root))
                self.assertIsNone(makham.active_model_dir(root))


if __name__=="__main__":
    unittest.main()
