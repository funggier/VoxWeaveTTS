"""Runtime registry, shared consumer protection, and MakHam package lifecycle."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import runtime_registry as registry
from voxweavetts import makham_package as makham
from voxweavetts import model_packages as models
from voxweavetts.engine_provider_catalog import PROVIDERS


class RuntimeRegistryTests(unittest.TestCase):
    def _runtime(self, root: Path, runtime_id: str):
        provider=PROVIDERS[runtime_id]
        recipe=provider.requirements_path(root)
        recipe.parent.mkdir(parents=True, exist_ok=True)
        recipe.write_text("onnxruntime==1.0\n",encoding="utf-8")
        folder=provider.python_path(root).parent.parent
        folder.mkdir(parents=True)
        provider.python_path(root).parent.mkdir(parents=True,exist_ok=True)
        provider.python_path(root).touch()
        (folder/".voxweave-ready.json").write_text(json.dumps({
            "provider":provider.id,"backend":provider.backend,"protocol":1,
        }))
        return folder

    def test_orphan_runtime_can_be_removed_without_touching_other_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            orphan=self._runtime(root,"vachana")
            survivor=self._runtime(root,"pythaitts")
            protected=root/"models"/"personal"/"private-voice.txt"
            protected.parent.mkdir(parents=True)
            protected.write_text("do not delete")
            item=next(x for x in registry.inventory(root) if x["id"]=="vachana")
            self.assertTrue(item["can_uninstall"])
            self.assertTrue(item["ready"])
            self.assertEqual(item["reference_count"],0)
            self.assertTrue(registry.remove_unreferenced(
                "vachana",item["runtime_fingerprint"],root=root))
            self.assertFalse(orphan.exists())
            self.assertTrue(survivor.exists())
            self.assertTrue(protected.exists())

    def test_referenced_runtime_is_protected_and_model_removal_frees_it(self):
        from test_model_packages import fixture
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            folder=self._runtime(root,"vachana")
            src=root/"source"
            manifest=fixture(src)
            pkg=root/"test.vwmodel"
            models.make_package(src,manifest,pkg)
            base=root/"models"/"packages"
            models.install_model_package(pkg,base=base)
            item=next(x for x in registry.inventory(root) if x["id"]=="vachana")
            self.assertEqual(item["reference_count"],1)
            self.assertFalse(item["can_uninstall"])
            with self.assertRaisesRegex(registry.RuntimeRegistryError,"shared by installed models"):
                registry.remove_unreferenced("vachana",item["runtime_fingerprint"],root=root)
            self.assertTrue(folder.exists())
            self.assertTrue(models.remove_model_package("vachana-a","1.0.0",base=base))
            after=next(x for x in registry.inventory(root) if x["id"]=="vachana")
            self.assertTrue(after["can_uninstall"])
            self.assertTrue(registry.remove_unreferenced(
                "vachana",after["runtime_fingerprint"],root=root))
            self.assertFalse(folder.exists())

    def test_never_accept_arbitrary_path_or_stale_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            folder=self._runtime(root,"kokoro")
            info=next(x for x in registry.inventory(root) if x["id"]=="kokoro")
            for candidate in ("../../models","C:\\Windows","",None,"../wayu"):
                with self.subTest(candidate=candidate),self.assertRaises(registry.RuntimeRegistryError):
                    registry.remove_unreferenced(candidate,info["runtime_fingerprint"],root=root)
            with self.assertRaisesRegex(registry.RuntimeRegistryError,"changed"):
                registry.remove_unreferenced("kokoro","f"*64,root=root)
            self.assertTrue(folder.exists())

    def test_verified_runtime_install_requires_fingerprint_and_wheelhouse(self):
        record = {
            "id": "sherpa", "runtime_fingerprint": "a" * 64,
            "ready": False, "installed": False, "repair_required": False,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (patch.object(registry, "inventory", return_value=[record]),
                  patch("voxweavetts.offline_wheelhouse.status",
                        return_value={"ready_to_verify": False})):
                with self.assertRaisesRegex(registry.RuntimeRegistryError,
                                            "trusted verified wheelhouse"):
                    registry.install_verified_async("sherpa", "a"*64, root=root)
                with self.assertRaisesRegex(registry.RuntimeRegistryError,
                                            "recipe changed"):
                    registry.install_verified_async("sherpa", "b"*64, root=root)
                with self.assertRaises(registry.RuntimeRegistryError):
                    registry.install_verified_async("../sherpa", "a"*64, root=root)

    def test_verified_install_job_reuses_guard_and_publishes_status(self):
        import threading
        record = {
            "id": "sherpa", "runtime_fingerprint": "a"*64,
            "ready": False, "installed": False, "repair_required": False,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            key = (str(root.resolve()), "sherpa")
            with (patch.object(registry, "inventory", return_value=[record]),
                  patch("voxweavetts.offline_wheelhouse.status",
                        return_value={"ready_to_verify": True}),
                  patch("voxweavetts.verified_runtime_installer.install_verified")
                        as install):
                job = registry.install_verified_async("sherpa", "a"*64, root=root)
                self.assertEqual(job["source"], "wheelhouse")
                for _ in range(500):
                    state = registry._REPAIR_JOBS[key]["state"]
                    if state != "repairing":
                        break
                    threading.Event().wait(0.01)
                self.assertEqual(registry._REPAIR_JOBS[key]["state"], "ready")
                install.assert_called_once_with("sherpa", root=root)
            registry._REPAIR_JOBS.pop(key, None)

    def test_makham_builtin_and_package_share_one_engine_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            legacy=makham.legacy_model_dir(root)
            legacy.mkdir(parents=True)
            original={"paradee_thai_int8.onnx":b"m"*8192,
                      "config.json":b"config"*220}
            pins={name:hashlib.sha256(data).hexdigest() for name,data in original.items()}
            for name,data in original.items():
                (legacy/name).write_bytes(data)
            with patch.object(makham,"PINNED_ASSETS",pins):
                archive=root/"makham.vwmodel"
                models.pack_local_makham(legacy,archive)
                base=root/"models"/"packages"
                manifest=models.install_model_package(archive,base=base)
                self.assertEqual(models.engine_id_for(manifest),makham.ENGINE_ID)
                self.assertEqual(makham.active_model_dir(root),makham.packaged_model_dir(root))
                makham.disable_legacy_fallback(root)
                self.assertTrue(models.remove_model_package(makham.PACKAGE_ID,
                                                            makham.PACKAGE_VERSION,base=base))
                self.assertIsNone(makham.active_model_dir(root))
                self.assertTrue(legacy.exists())
                models.install_model_package(archive,base=base)
                # Legacy format reinstall must not bypass an explicit disable
                # marker after the native v2 migration.
                self.assertIsNone(makham.active_model_dir(root))
                self.assertEqual(makham.recovery_archive(root).exists(),False)


if __name__=="__main__":
    unittest.main()
