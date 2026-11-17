"""Phase B managed runtime health checks: portable moves and pinned recipes."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from voxweavetts.managed_runtime_pool import (inspect_environment, pin_fields,
    atomic_rebuild, RuntimeRebuildError)
from voxweavetts.engine_provider_catalog import PROVIDERS
from voxweavetts.engine_provider_installer import ready as provider_ready
from voxweavetts.m2m_runtime import ready as m2m_ready, REQUIREMENTS, MARKER, python_path


class ManagedRuntimeHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "app"
        self.root.mkdir()
        self.env = self.root / "runtime" / "engine-envs" / "vachana"
        self.env.mkdir(parents=True)
        self.python = self.env / "Scripts" / "python.exe"
        self.python.parent.mkdir()
        self.python.write_bytes(b"test")
        self.marker = self.env / ".voxweave-ready.json"
        (self.env / "pyvenv.cfg").write_text(
            "version_info = 3.11\nhome = " + str(self.root) + "\n",
            encoding="utf-8")
        self.hash = hashlib.sha256(b"package==1.0\n").hexdigest()

    def examine(self, *, root=None, expected_recipe=None):
        return inspect_environment(root=root or self.root, folder=self.env,
            python=self.python, marker=self.marker,
            expected_recipe_hash=expected_recipe)

    def pin(self):
        self.marker.write_text(json.dumps({
            "provider": "vachana", "backend": "vachana-v1",
            "protocol": 1, **pin_fields(self.root, self.hash)}), encoding="utf-8")

    def test_pinned_ready_relocation_and_recipe_drift(self):
        self.pin()
        ready = self.examine(expected_recipe=self.hash)
        self.assertEqual(ready["state"], "ready")
        self.assertTrue(ready["location_pinned"])
        self.assertFalse(ready["repair_required"])
        self.assertEqual(self.examine(expected_recipe="f"*64)["state"],
                         "recipe-changed")
        relocated = self.root.parent / "new-location"
        self.root.rename(relocated)
        self.root = relocated
        self.env = relocated / "runtime" / "engine-envs" / "vachana"
        self.python = self.env / "Scripts" / "python.exe"
        self.marker = self.env / ".voxweave-ready.json"
        moved = self.examine(expected_recipe=self.hash)
        self.assertEqual(moved["state"], "relocated")
        self.assertTrue(moved["repair_required"])
        self.assertFalse(moved["ready"])

    def test_wrong_abi_and_missing_base_python_are_reported(self):
        self.pin()
        cfg = self.env / "pyvenv.cfg"
        cfg.write_text("version_info = 3.12\n", encoding="utf-8")
        self.assertEqual(self.examine()["state"], "python-abi-mismatch")
        cfg.write_text("version_info = 3.11\nhome = "
                       + str(self.root / "absent") + "\n", encoding="utf-8")
        self.assertEqual(self.examine()["state"], "base-python-missing")

    def test_legacy_unpinned_is_visible_without_disabling_existing_runtime(self):
        self.marker.write_text(json.dumps({"protocol": 1}), encoding="utf-8")
        report = self.examine()
        self.assertTrue(report["ready"])
        self.assertEqual(report["state"], "legacy-unpinned")
        self.assertFalse(report["location_pinned"])

    def test_incomplete_invalid_marker_or_missing_python(self):
        self.assertEqual(self.examine()["state"], "incomplete")
        self.pin()
        self.python.unlink()
        self.assertEqual(self.examine()["state"], "incomplete")

    def test_provider_readiness_rejects_relocated_venv(self):
        profile = PROVIDERS["vachana"]
        recipe = profile.requirements_path(self.root)
        recipe.parent.mkdir(parents=True)
        recipe.write_bytes(b"package==1.0\n")
        self.pin()
        self.assertTrue(provider_ready(profile, root=self.root))
        state = json.loads(self.marker.read_text(encoding="utf-8"))
        state["installed_root"] = str(self.root / "old-drive")
        self.marker.write_text(json.dumps(state), encoding="utf-8")
        self.assertFalse(provider_ready(profile, root=self.root))

    def test_atomic_repair_preserves_old_until_validated(self):
        original = self.env / "keep.txt"
        original.write_text("old", encoding="utf-8")
        steps = []
        def build(stage):
            self.assertTrue(original.is_file())
            stage.mkdir()
            (stage / "new.txt").write_text("repaired", encoding="utf-8")
            steps.append("build")
        def verify(stage):
            self.assertTrue(original.is_file())
            steps.append("verify")
            return (stage / "new.txt").is_file()
        def quiesce():
            steps.append("quiesce")
            self.assertTrue(original.exists())
        atomic_rebuild(root=self.root, folder=self.env, build=build,
                       verify=verify, quiesce=quiesce)
        self.assertEqual(steps, ["build", "verify", "quiesce"])
        self.assertFalse(original.exists())
        self.assertEqual((self.env / "new.txt").read_text(), "repaired")
        self.assertEqual([x.name for x in self.env.parent.iterdir()], ["vachana"])

    def test_failed_repair_does_not_remove_or_mutate_original(self):
        original = self.env / "keep.txt"
        original.write_text("old", encoding="utf-8")
        def build(stage):
            stage.mkdir()
            (stage / "partial.txt").touch()
        with self.assertRaisesRegex(RuntimeRebuildError, "verification"):
            atomic_rebuild(root=self.root, folder=self.env, build=build,
                           verify=lambda stage: False)
        self.assertEqual(original.read_text(), "old")
        self.assertEqual([x.name for x in self.env.parent.iterdir()], ["vachana"])

    def test_repair_never_targets_unmanaged_folder(self):
        outside = self.root / "models" / "private"
        outside.mkdir(parents=True)
        with self.assertRaises(RuntimeRebuildError):
            atomic_rebuild(root=self.root, folder=outside,
                           build=lambda stage: None, verify=lambda stage: True)
        self.assertTrue(outside.is_dir())

    def test_m2m_readiness_rejects_relocated_venv(self):
        recipe = self.root / REQUIREMENTS
        recipe.parent.mkdir(parents=True)
        recipe.write_bytes(b"package==1.0\n")
        worker = python_path(self.root)
        worker.parent.mkdir(parents=True)
        worker.touch()
        worker_folder = worker.parent.parent
        (worker_folder / "pyvenv.cfg").write_text(
            "version_info = 3.11\nhome = " + str(self.root) + "\n", encoding="utf-8")
        marker = worker_folder / MARKER
        marker.write_text(json.dumps({"runtime": "m2m100", "protocol": 1,
            **pin_fields(self.root, self.hash)}), encoding="utf-8")
        self.assertTrue(m2m_ready(self.root))
        state = json.loads(marker.read_text(encoding="utf-8"))
        state["installed_root"] = str(self.root / "old-location")
        marker.write_text(json.dumps(state), encoding="utf-8")
        self.assertFalse(m2m_ready(self.root))


if __name__ == "__main__":
    unittest.main()
