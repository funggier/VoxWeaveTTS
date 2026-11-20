"""Read-only v4 Portable Doctor, without any legacy runtime dependency."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import portable_doctor as doctor
from voxweavetts import universal_model_v4 as v4
from test_v4_plugin_packages import fixture


class PortableDoctorV4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "portable"

    def tearDown(self):
        self.tmp.cleanup()

    def install_fake(self):
        archive = fixture(Path(self.tmp.name) / "fixture")
        for path in ("runtime/python/python.exe", "runtime/tools/uv.exe"):
            file = self.root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"test-runtime")
        v4.install(archive, root=self.root)
        return archive

    def test_empty_root_is_read_only_and_not_ready(self):
        report = doctor.report(self.root)
        self.assertEqual(report["format"], "voxweavetts.portable-doctor-v4")
        self.assertEqual(report["overall_state"], "needs-attention")
        self.assertEqual(report["package_count"], 0)
        self.assertFalse(self.root.exists())

    def test_ready_requires_real_v4_makham_default(self):
        self.install_fake()
        report = doctor.report(self.root)
        self.assertEqual(report["package_count"], 1)
        self.assertTrue(report["offline_installer_ready"])
        self.assertFalse(report["default_model_ready"])
        self.assertEqual(report["overall_state"], "needs-attention")
        self.assertTrue(
            (self.root/"models/universal/v4/tts/demo-future-engine/1.0.0/manifest.json").exists())

    def test_v3_data_is_reported_but_never_read_or_removed(self):
        self.install_fake()
        old_dir = self.root / "models/universal/v3/tts/legacy"
        old_dir.mkdir(parents=True)
        marker = old_dir/"marker.txt"
        marker.write_text("do not touch",encoding="utf-8")
        data = doctor.report(self.root, verify_wheelhouse=True)
        self.assertTrue(data["legacy_directory_present"])
        self.assertEqual(marker.read_text(encoding="utf-8"), "do not touch")

    def test_modified_v4_worker_is_not_considered_installed(self):
        self.install_fake()
        worker = self.root / "models/universal/v4/tts/demo-future-engine/1.0.0/plugin/worker.py"
        worker.write_text("tampered executable",encoding="utf-8")
        report = doctor.report(self.root)
        self.assertEqual(report["package_count"], 0)
        self.assertFalse(report["default_model_ready"])
        self.assertEqual(worker.read_text(), "tampered executable")

    def test_strict_cli_reports_missing_runtime_without_modification(self):
        self.assertEqual(doctor.main(["--root", str(self.root), "--strict"]), 2)
        self.assertFalse(self.root.exists())


if __name__ == "__main__":
    unittest.main()
