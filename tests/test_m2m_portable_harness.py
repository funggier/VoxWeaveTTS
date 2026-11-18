"""Fast tests for the opt-in M2M Portable integration harness, not the 2 GB model."""
from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def harness():
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_portable_m2m_e2e.py"
    spec = importlib.util.spec_from_file_location("voxweavetts_portable_m2m_harness", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DisposableM2MPortableTests(unittest.TestCase):
    def test_import_does_not_launch_model_or_write_files(self):
        module = harness()
        self.assertTrue(callable(module.main))
        self.assertTrue(callable(module.cleanup_test_root))

    def test_cleanup_retries_transient_windows_file_lock(self):
        module = harness()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = root / "cache" / "temp"
            folder = work / "m2m100-fresh-portable-example"
            folder.mkdir(parents=True)
            (folder / "model.safetensors").write_bytes(b"simulated")
            actual_delete = shutil.rmtree
            calls = []
            def flaky(target):
                calls.append(target)
                if len(calls) == 1:
                    raise PermissionError("temporary file held by scanner")
                return actual_delete(target)
            with (patch.object(module, "ROOT", root),
                  patch.object(module.shutil, "rmtree", side_effect=flaky),
                  patch.object(module.time, "sleep") as sleep):
                self.assertTrue(module.cleanup_test_root(folder, attempts=3, delay=0))
            self.assertEqual(len(calls), 2)
            sleep.assert_called_once_with(0)
            self.assertFalse(folder.exists())

    def test_cleanup_refuses_any_path_outside_controlled_workspace(self):
        module = harness()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            wrong=root/"models"/"m2m100-fresh-portable-user"
            wrong.mkdir(parents=True)
            (wrong/"private.weight").write_bytes(b"do not touch")
            with patch.object(module,"ROOT",root):
                with self.assertRaisesRegex(ValueError, "controlled test workspace"):
                    module.cleanup_test_root(wrong, attempts=1, delay=0)
            self.assertEqual((wrong/"private.weight").read_bytes(),
                             b"do not touch")

    def test_permanent_lock_is_reported_separately_without_other_deletion(self):
        module = harness()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root/"cache"/"temp"/"m2m100-fresh-portable-locked"
            folder.mkdir(parents=True)
            (folder/"weight.safetensors").write_bytes(b"locked")
            with (patch.object(module, "ROOT", root),
                  patch.object(module.shutil, "rmtree",
                               side_effect=PermissionError("locked")),
                  patch.object(module.time, "sleep"),
                  patch.object(module, "log")):
                self.assertFalse(module.cleanup_test_root(folder, attempts=2, delay=0))
            self.assertEqual((folder/"weight.safetensors").read_bytes(),b"locked")


if __name__ == "__main__":
    unittest.main()
