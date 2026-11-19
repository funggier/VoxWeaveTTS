"""Read-only Universal v3 Portable Doctor regression tests.

All fixtures are offline; no v2 repair APIs or destructive upgrades are used.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_v3_offline_relocatable import _fixture
from voxweavetts import portable_doctor as doctor
from voxweavetts.universal_model_packages import (
    install_model_package, make_package, installed_packages,
)
from voxweavetts.portable_runtime_v3 import runtime_folder


class PortableDoctorV3Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "Portable"
        self.root.mkdir()

    def _install(self):
        source, manifest = _fixture(self.root)
        archive = self.root / "test-v3.vwmodel"
        make_package(source, manifest, archive)
        with patch("voxweavetts.portable_runtime_v3.core_python",
                   return_value=Path(sys.executable)):
            installed = install_model_package(archive, root=self.root)
        self.assertEqual(installed["runtime_status"], "ready")
        # Doctor runs against an extracted Portable. Add its core markers
        # only AFTER installing with the real test uv and host interpreter.
        for relative in ("runtime/python/python.exe", "runtime/tools/uv.exe"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture-only")
        return manifest

    def test_empty_root_is_incomplete_and_does_not_modify_files(self):
        before = list(self.root.rglob("*"))
        result = doctor.report(self.root)
        self.assertEqual(result["format"], "voxweavetts.portable-doctor-v3")
        self.assertEqual(result["overall_state"], "incomplete")
        self.assertEqual(result["summary"]["native_models"], 0)
        self.assertTrue(result["core"]["no_operations_performed"])
        self.assertEqual(list(self.root.rglob("*")), before)

    def test_v2_assets_are_ignored_not_removed(self):
        old = self.root / "models" / "universal" / "v2" / "tts" / "legacy" / "1.0.0"
        old.mkdir(parents=True)
        legacy = old / "manifest.json"
        legacy.write_text('{"format_version":2}', encoding="utf-8")
        output = doctor.report(self.root)
        self.assertEqual(output["summary"]["native_models"], 0)
        self.assertEqual(output["summary"]["invalid_native_manifests"], 0)
        self.assertEqual(json.loads(legacy.read_text())["format_version"], 2)

    def test_ready_v3_and_deep_hash_diagnosis_are_read_only(self):
        self._install()
        before = {(p.relative_to(self.root).as_posix(), p.stat().st_size)
                  for p in self.root.rglob("*") if p.is_file()}
        result = doctor.report(self.root, verify_wheelhouse=True)
        self.assertEqual(result["overall_state"], "ready")
        self.assertEqual(result["summary"]["native_models"], 1)
        self.assertEqual(result["summary"]["runtimes_ready"], 1)
        self.assertEqual(result["models"][0]["file_hashes_checked"], "valid")
        self.assertEqual(result["runtimes"][0]["reference_count"], 1)
        after = {(p.relative_to(self.root).as_posix(), p.stat().st_size)
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_runtime_missing_detected_without_repair_or_deletion(self):
        manifest = self._install()
        shutil.rmtree(runtime_folder(self.root, manifest))
        before = len(installed_packages(self.root))
        result = doctor.report(self.root)
        self.assertEqual(before, 1)
        self.assertEqual(result["overall_state"], "needs-attention")
        self.assertEqual(result["summary"]["models_waiting_for_runtime"], 1)
        self.assertEqual(result["runtimes"][0]["recommended_action"],
                         "uninstall-model-and-reinstall-v3-package")
        self.assertEqual(len(installed_packages(self.root)), before)

    def test_deep_hash_reports_tampered_assets_without_changing_them(self):
        self._install()
        folder = installed_packages(self.root)[0][1]
        weight = folder / "voices" / "th_f_1.onnx"
        original = weight.read_bytes()
        weight.write_bytes(b"X" + original[1:])
        report = doctor.report(self.root, verify_wheelhouse=True)
        self.assertEqual(report["overall_state"], "needs-attention")
        self.assertEqual(report["models"][0]["file_hashes_checked"], "failed")
        self.assertEqual(weight.read_bytes(), b"X" + original[1:])


if __name__ == "__main__":
    unittest.main()