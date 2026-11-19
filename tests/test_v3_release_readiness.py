"""Release gates that require no external accounts, network or large model assets."""
from __future__ import annotations

import importlib.util
import re
import tomllib
import unittest
from pathlib import Path

from voxweavetts import __version__

ROOT = Path(__file__).resolve().parents[1]


class UniversalV3ReleaseReadinessTests(unittest.TestCase):
    def test_version_matches_python_package_and_first_v3_release(self):
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(pyproject["project"]["version"], __version__)
        self.assertEqual(__version__, "0.11.0")

    def test_default_portable_builder_is_v3_only(self):
        wrapper = (ROOT / "scripts" / "Build-Portable.ps1").read_text(encoding="utf-8")
        builder = (ROOT / "scripts" / "Build-Portable-V3.ps1").read_text(encoding="utf-8")
        self.assertIn("Build-Portable-V3.ps1", wrapper)
        self.assertIn("models\\universal\\v3", builder)
        self.assertIn("runtime\\tools\\uv.exe", builder)
        self.assertNotIn("ModelPackagesV2", builder)
        self.assertNotIn("Install-EngineProvider.ps1", builder)

    def test_no_remaining_active_script_imports_removed_v2_package_manager(self):
        for file in (ROOT / "scripts").glob("*.py"):
            with self.subTest(script=file.name):
                source = file.read_text(encoding="utf-8")
                self.assertNotIn("from voxweavetts.model_packages import", source)
                self.assertNotIn("import voxweavetts.model_packages", source)

    def test_legacy_runtime_installers_are_not_exposed(self):
        self.assertFalse((ROOT / "scripts" / "Install-M2M100Runtime.ps1").exists())
        self.assertFalse((ROOT / "scripts" / "create_multilingual_model_packs.py").exists())

    def test_v3_release_checksum_manifest_contains_only_new_archive_formats(self):
        source = (ROOT / "scripts" / "Generate-Release-Checksums.ps1").read_text(encoding="utf-8")
        self.assertIn("ModelPackagesV3", source)
        self.assertIn("CATALOG-v3.json", source)
        self.assertIn("0.11.0", source)
        self.assertNotIn("ModelPackages/", source)
        self.assertNotIn("format-v2", source)

    def test_release_audit_has_pinned_native_assets_and_rights_warnings(self):
        path = ROOT / "scripts" / "verify_model_pack_release.py"
        spec = importlib.util.spec_from_file_location("v3_release_audit_test", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(len(module.MODELS), 5)
        for package_id, row in module.MODELS.items():
            with self.subTest(package_id=package_id):
                self.assertTrue(row["notices"])
                self.assertTrue(row["assets"])
                for digest in row["assets"].values():
                    self.assertTrue(re.fullmatch("[0-9a-f]{64}", digest))
        self.assertIn("commercial_redistribution_audited", path.read_text(encoding="utf-8"))

    def test_release_notes_require_fresh_folder_and_restrict_old_packages(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_v0.11.0.md").read_text(encoding="utf-8")
        self.assertIn("not accepted", notes)
        self.assertIn("new folder", notes)
        self.assertIn("OpenRAIL-M", notes)
        self.assertIn("memory/commit", notes)


if __name__ == "__main__":
    unittest.main()
