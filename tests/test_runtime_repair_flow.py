"""Mocked offline repair integration; no downloads or local worker rebuilds."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import engine_provider_installer as tts
from voxweavetts import m2m_runtime as m2m
from voxweavetts.engine_provider_catalog import PROVIDERS
from voxweavetts.managed_runtime_pool import pin_fields


class RuntimeRepairFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "portable-project"
        self.root.mkdir()
        base = self.root / ".venv" / "Scripts" / "python.exe"
        base.parent.mkdir(parents=True)
        base.touch()
        protected = self.root / "models" / "universal" / "private-model.onnx"
        protected.parent.mkdir(parents=True)
        protected.write_bytes(b"model must not be touched")
        self.protected = protected
        self.commands = []

    def create_environment(self, relative, marker_name, marker_data):
        folder = self.root / relative
        folder.mkdir(parents=True)
        (folder / "original-state.txt").write_text("preserve on failure")
        p = folder / "Scripts" / "python.exe"
        p.parent.mkdir()
        p.touch()
        (folder / "pyvenv.cfg").write_text(
            "version_info = 3.11\nhome = " + str(self.root) + "\n")
        (folder / marker_name).write_text(json.dumps(marker_data))
        return folder

    def execute(self, cmd, *, root, log):
        self.assertEqual(root, self.root)
        self.commands.append(list(cmd))
        if len(cmd) >= 4 and cmd[1:3] == ["venv", "--offline"]:
            stage = Path(cmd[3])
            path = stage / "Scripts" / "python.exe"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"test")
            (stage / "pyvenv.cfg").write_text(
                "version_info = 3.11\nhome = " + str(self.root) + "\n")

    def test_tts_repair_stages_and_swaps_offline(self):
        profile = PROVIDERS["vachana"]
        recipe = profile.requirements_path(self.root)
        recipe.parent.mkdir(parents=True)
        recipe.write_bytes(b"onnxruntime==1\n")
        digest = hashlib.sha256(recipe.read_bytes()).hexdigest()
        folder = self.create_environment(
            Path("runtime/engine-envs/vachana"), ".voxweave-ready.json",
            {"provider": profile.id, "backend": profile.backend, "protocol": 1,
             **pin_fields(self.root / "old-location", digest)})
        with (patch("voxweavetts.engine_provider_installer.shutil.which",
                    return_value="uv"),
              patch("voxweavetts.engine_provider_installer._execute",
                    side_effect=self.execute)):
            result = tts.repair("vachana", root=self.root)
        self.assertEqual(result, folder)
        self.assertTrue(tts.ready(profile, root=self.root))
        self.assertFalse((folder / "original-state.txt").exists())
        self.assertEqual(self.protected.read_bytes(), b"model must not be touched")
        self.assertEqual(len(self.commands), 5)
        self.assertTrue(all("--offline" in cmd for cmd in self.commands[:3]))
        self.assertEqual(self.commands[3][0], str(folder / "Scripts" / "python.exe"))
        self.assertIn("--offline", self.commands[4])
        self.assertFalse(any(".backup-" in p.name or ".stage-" in p.name
                             for p in folder.parent.iterdir()))

    def test_tts_failed_offline_repair_keeps_old_runtime(self):
        profile = PROVIDERS["vachana"]
        recipe = profile.requirements_path(self.root)
        recipe.parent.mkdir(parents=True)
        recipe.write_bytes(b"onnxruntime==1\n")
        folder = self.create_environment(
            Path("runtime/engine-envs/vachana"), ".voxweave-ready.json",
            {"provider": profile.id, "backend": profile.backend, "protocol": 1})
        def unavailable(cmd, *, root, log):
            self.execute(cmd, root=root, log=log)
            if cmd[1:3] == ["pip", "install"]:
                raise tts.InstallError("required offline wheel is not cached")
        with (patch("voxweavetts.engine_provider_installer.shutil.which",
                    return_value="uv"),
              patch("voxweavetts.engine_provider_installer._execute",
                    side_effect=unavailable)):
            with self.assertRaisesRegex(tts.InstallError, "not cached"):
                tts.repair("vachana", root=self.root)
        self.assertEqual((folder / "original-state.txt").read_text(),
                         "preserve on failure")
        self.assertEqual(self.protected.read_bytes(), b"model must not be touched")
        self.assertEqual([x.name for x in folder.parent.iterdir()], ["vachana"])

    def test_m2m_repair_stages_dependencies_and_import_verification(self):
        recipe = self.root / m2m.REQUIREMENTS
        recipe.parent.mkdir(parents=True)
        recipe.write_bytes(b"torch==2.8.0\n")
        digest = hashlib.sha256(recipe.read_bytes()).hexdigest()
        folder = self.create_environment(
            Path("runtime/ai-envs/m2m100"), m2m.MARKER,
            {"runtime": "m2m100", "protocol": 1,
             **pin_fields(self.root / "old-location", digest)})
        with (patch("voxweavetts.m2m_runtime.shutil.which",
                    return_value="uv"),
              patch("voxweavetts.m2m_runtime._execute",
                    side_effect=self.execute)):
            self.assertEqual(m2m.repair(self.root), folder)
        self.assertTrue(m2m.ready(self.root))
        self.assertEqual(len(self.commands), 6)
        self.assertTrue(all("--offline" in cmd for cmd in self.commands[:3]))
        self.assertEqual(self.commands[3][1], "-c")
        self.assertEqual(self.commands[4][0], str(folder / "Scripts" / "python.exe"))
        self.assertIn("--offline", self.commands[5])
        self.assertTrue(self.protected.is_file())

    def test_final_tts_python_failure_rolls_back_to_original(self):
        profile = PROVIDERS["vachana"]
        recipe = profile.requirements_path(self.root)
        recipe.parent.mkdir(parents=True)
        recipe.write_bytes(b"onnxruntime==1\n")
        digest = hashlib.sha256(recipe.read_bytes()).hexdigest()
        folder = self.create_environment(
            Path("runtime/engine-envs/vachana"), ".voxweave-ready.json",
            {"provider": profile.id, "backend": profile.backend, "protocol": 1,
             **pin_fields(self.root / "old-location", digest)})

        def fail_final(command, *, root, log):
            self.execute(command, root=root, log=log)
            if command[0] == str(folder / "Scripts" / "python.exe"):
                raise tts.InstallError("final relocated python did not start")

        with (patch("voxweavetts.engine_provider_installer.shutil.which",
                    return_value="uv"),
              patch("voxweavetts.engine_provider_installer._execute",
                    side_effect=fail_final)):
            with self.assertRaisesRegex(tts.InstallError, "relocated python"):
                tts.repair("vachana", root=self.root)
        self.assertEqual((folder / "original-state.txt").read_text(),
                         "preserve on failure")
        self.assertTrue(self.protected.is_file())
        self.assertFalse(any(".stage-" in x.name or ".backup-" in x.name
                             for x in folder.parent.iterdir()))

    def test_final_m2m_python_failure_rolls_back_to_original(self):
        recipe = self.root / m2m.REQUIREMENTS
        recipe.parent.mkdir(parents=True)
        recipe.write_bytes(b"torch==2.8.0\n")
        digest = hashlib.sha256(recipe.read_bytes()).hexdigest()
        folder = self.create_environment(
            Path("runtime/ai-envs/m2m100"), m2m.MARKER,
            {"runtime": "m2m100", "protocol": 1,
             **pin_fields(self.root / "old-location", digest)})

        def fail_final(command, *, root, log):
            self.execute(command, root=root, log=log)
            if command[0] == str(folder / "Scripts" / "python.exe"):
                raise m2m.M2MRuntimeError("final interpreter not runnable")

        with (patch("voxweavetts.m2m_runtime.shutil.which", return_value="uv"),
              patch("voxweavetts.m2m_runtime._execute", side_effect=fail_final)):
            with self.assertRaisesRegex(m2m.M2MRuntimeError, "interpreter"):
                m2m.repair(self.root)
        self.assertEqual((folder / "original-state.txt").read_text(),
                         "preserve on failure")
        self.assertTrue(self.protected.is_file())

    def test_normal_install_refuses_relocated_runtime_before_mutation(self):
        profile = PROVIDERS["vachana"]
        recipe = profile.requirements_path(self.root)
        recipe.parent.mkdir(parents=True)
        recipe.write_bytes(b"onnxruntime==1\n")
        digest = hashlib.sha256(recipe.read_bytes()).hexdigest()
        folder = self.create_environment(
            Path("runtime/engine-envs/vachana"), ".voxweave-ready.json",
            {"provider": profile.id, "backend": profile.backend, "protocol": 1,
             **pin_fields(self.root / "old-location", digest)})
        with (patch("voxweavetts.engine_provider_installer.shutil.which",
                    return_value="uv"),
              patch("voxweavetts.engine_provider_installer._execute") as execute):
            with self.assertRaisesRegex(tts.InstallError, "offline repair"):
                tts.install("vachana", root=self.root)
        execute.assert_not_called()
        self.assertTrue((folder / ".voxweave-ready.json").exists())

    def test_normal_m2m_install_refuses_relocated_runtime_before_mutation(self):
        recipe = self.root / m2m.REQUIREMENTS
        recipe.parent.mkdir(parents=True)
        recipe.write_bytes(b"torch==2.8.0\n")
        digest = hashlib.sha256(recipe.read_bytes()).hexdigest()
        folder = self.create_environment(
            Path("runtime/ai-envs/m2m100"), m2m.MARKER,
            {"runtime": "m2m100", "protocol": 1,
             **pin_fields(self.root / "old-location", digest)})
        with (patch("voxweavetts.m2m_runtime.shutil.which",
                    return_value="uv"),
              patch("voxweavetts.m2m_runtime._execute") as execute):
            with self.assertRaisesRegex(m2m.M2MRuntimeError, "offline repair"):
                m2m.install(self.root)
        execute.assert_not_called()
        self.assertTrue((folder / m2m.MARKER).exists())


if __name__ == "__main__":
    unittest.main()
