"""Security regression: QA-only scriptless wheels keep matching RECORD hashes."""
from __future__ import annotations
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "qa_rebuild_vachana_wheel.py"


def load():
    spec = importlib.util.spec_from_file_location("qa_v3_wheel_rebuild", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WheelSanitizationTests(unittest.TestCase):
    def test_scriptless_qa_wheel_is_same_name_but_new_hash_and_no_cli(self):
        module = load()
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            original = base / module.SSG_WHEEL
            output = base / "qa" / module.SSG_WHEEL
            with zipfile.ZipFile(original, "w") as archive:
                archive.writestr("ssg/__init__.py", "__version__='0.0.8'\n")
                archive.writestr(module.SCRIPT, "#!/usr/bin/env python\nprint(42)\n")
                archive.writestr(module.RECORD, "original_record,unused,unused\n")
            before = module.sha256(original)
            result = module.strip_script(original, output,
                                          expected_source_sha256=before)
            self.assertEqual(module.sha256(original), before)
            self.assertEqual(result["original_sha256"], before)
            self.assertNotEqual(result["qa_sha256"], before)
            self.assertFalse(result["for_publication"])
            self.assertEqual(result["removed"], [module.SCRIPT])
            with zipfile.ZipFile(output) as archive:
                self.assertNotIn(module.SCRIPT, archive.namelist())
                self.assertEqual(archive.read("ssg/__init__.py"),
                                 b"__version__='0.0.8'\n")

    def test_unreviewed_wheel_and_missing_script_rejected(self):
        module = load()
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            wrong = base / "unreviewed-0.1.0-py3-none-any.whl"
            with zipfile.ZipFile(wrong, "w") as archive:
                archive.writestr("something.txt", "data")
            with self.assertRaises(ValueError):
                module.strip_script(wrong, base / "qa.whl")
            named = base / module.SSG_WHEEL
            with zipfile.ZipFile(named, "w") as archive:
                archive.writestr(module.RECORD, "")
            with self.assertRaises(ValueError):
                module.strip_script(named, base / "qa" / module.SSG_WHEEL)
            with self.assertRaises(ValueError):
                module.strip_script(named, base / "qa" / module.SSG_WHEEL,
                                    expected_source_sha256=module.sha256(named))


if __name__ == "__main__":
    unittest.main()
