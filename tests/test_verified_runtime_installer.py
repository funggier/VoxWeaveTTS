"""End-to-end mock installs from pinned wheels, including post-activation rollback.

All uv subprocess operations are mocked; no downloads, installed models,
actual worker processes or real OS runtime directories are modified.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import offline_wheelhouse as wh
from voxweavetts import verified_runtime_installer as installer
from voxweavetts.managed_runtime_pool import RuntimeRebuildError, pin_fields


def wheel(path: Path, name: str, version: str) -> None:
    import zipfile
    with zipfile.ZipFile(path, "w") as archive:
        info = f"{name}-{version}.dist-info/"
        archive.writestr(info + "METADATA",
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n\n")
        archive.writestr(info + "WHEEL",
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        archive.writestr(name + "/__init__.py", b"example distribution")


class VerifiedRuntimeInstallerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "portable"
        self.root.mkdir()
        recipe = self.root / "scripts" / "engine-dependencies" / "sherpa.txt"
        recipe.parent.mkdir(parents=True)
        recipe.write_text("sherpa-onnx==2.0.1\nnumpy==2.2.6\n")
        self.recipe_hash = hashlib.sha256(recipe.read_bytes()).hexdigest()
        source = self.root / "candidates"
        source.mkdir()
        for name, version in (("sherpa_onnx", "2.0.1"), ("numpy", "2.2.6")):
            wheel(source / f"{name}-{version}-py3-none-any.whl", name, version)
        draft = wh.draft_lock(self.root, "sherpa", source)
        lock_file = self.root / "scripts" / "wheelhouse-locks" / "sherpa.json"
        lock_file.parent.mkdir(parents=True)
        lock_file.write_text(json.dumps(draft))
        self.bundle = self.root / "runtime" / "wheelhouse" / "sherpa"
        self.bundle.parent.mkdir(parents=True)
        shutil.copytree(source, self.bundle)
        python = self.root / ".venv" / "Scripts" / "python.exe"
        python.parent.mkdir(parents=True)
        python.touch()
        self.runtime = self.root / "runtime" / "engine-envs" / "sherpa"
        self.commands = []

    def fake_execute(self, args, *, root, log):
        self.commands.append(args)
        if args[1:3] == ["venv", "--offline"]:
            stage = Path(args[3])
            python = stage / installer.PYTHON_NAME
            python.parent.mkdir(parents=True)
            python.touch()
            (stage / "pyvenv.cfg").write_text(
                "version_info = 3.11\nhome = " + str(self.root) + "\n")

    def deploy(self, *, failure=None):
        def runner(args, *, root, log):
            self.fake_execute(args, root=root, log=log)
            if failure is not None and failure(args):
                raise installer.VerifiedInstallError("simulated installer failure")
        with (patch("voxweavetts.verified_runtime_installer.shutil.which",
                    return_value="uv"),
              patch("voxweavetts.verified_runtime_installer._execute",
                    side_effect=runner)):
            return installer.install_verified("sherpa", root=self.root)

    def test_new_install_uses_only_verified_offline_files(self):
        self.assertEqual(self.deploy(), self.runtime)
        self.assertTrue(self.runtime.is_dir())
        self.assertEqual(len(self.commands), 5)
        install = self.commands[1]
        for flag in ("--offline", "--no-index", "--no-cache",
                     "--only-binary", "--require-hashes", "--find-links"):
            self.assertIn(flag, install)
        self.assertNotIn("https", str(install))
        self.assertEqual(self.commands[0][1:3], ["venv", "--offline"])
        self.assertEqual(self.commands[3][0],
                         str(self.runtime / installer.PYTHON_NAME))
        marker = json.loads((self.runtime / ".voxweave-ready.json").read_text())
        self.assertEqual(marker["recipe_hash"], self.recipe_hash)
        self.assertEqual(marker["installed_root"], str(self.root.resolve()))
        self.assertEqual(len(marker["wheelhouse_lock_sha256"]), 64)
        self.assertEqual(list((self.root / "cache" / "temp").iterdir()), [])

    def test_corrupt_wheel_never_launches_uv(self):
        wheel_file = self.bundle / "numpy-2.2.6-py3-none-any.whl"
        payload = wheel_file.read_bytes()
        wheel_file.write_bytes(payload.replace(b"example", b"changed", 1))
        with self.assertRaisesRegex(wh.WheelhouseError, "SHA-256"):
            self.deploy()
        self.assertEqual(self.commands, [])
        self.assertFalse(self.runtime.exists())

    def test_repair_runs_after_successful_stage_and_keeps_model_files(self):
        self.runtime.mkdir(parents=True)
        (self.runtime / "original.txt").write_text("original")
        (self.runtime / "Scripts").mkdir()
        (self.runtime / installer.PYTHON_NAME).touch()
        (self.runtime / "pyvenv.cfg").write_text(
            "version_info = 3.11\nhome = " + str(self.root) + "\n")
        marker = self.runtime / ".voxweave-ready.json"
        marker.write_text(json.dumps({
            "provider": "sherpa", "backend": "sherpa-onnx-v1", "protocol": 1,
            **pin_fields(self.root / "old-root", self.recipe_hash)}))
        protected = self.root / "models" / "private.model"
        protected.parent.mkdir(parents=True)
        protected.write_bytes(b"private weight")
        self.deploy()
        self.assertFalse((self.runtime / "original.txt").exists())
        self.assertEqual(protected.read_bytes(), b"private weight")
        self.assertEqual(len(self.commands), 5)

    def test_final_python_launch_failure_rolls_back_existing_env(self):
        self.runtime.mkdir(parents=True)
        (self.runtime / "original.txt").write_text("original")
        (self.runtime / "Scripts").mkdir()
        (self.runtime / installer.PYTHON_NAME).touch()
        (self.runtime / "pyvenv.cfg").write_text(
            "version_info = 3.11\nhome = " + str(self.root) + "\n")
        marker = self.runtime / ".voxweave-ready.json"
        marker.write_text(json.dumps({
            "provider": "sherpa", "backend": "sherpa-onnx-v1", "protocol": 1,
            **pin_fields(self.root / "old-root", self.recipe_hash)}))
        with self.assertRaisesRegex(installer.VerifiedInstallError, "simulated"):
            self.deploy(failure=lambda cmd: cmd[0] == str(
                self.runtime / installer.PYTHON_NAME))
        self.assertEqual((self.runtime / "original.txt").read_text(), "original")
        self.assertFalse(list(self.runtime.parent.glob(".sherpa.stage-*")))

    def test_wrong_runtime_or_missing_lock_never_builds(self):
        with self.assertRaises((wh.WheelhouseError, installer.VerifiedInstallError)):
            installer.install_verified("arbitrary-code", root=self.root)
        (self.root / "scripts" / "wheelhouse-locks" / "sherpa.json").unlink()
        with self.assertRaises(wh.WheelhouseError):
            self.deploy()
        self.assertEqual(self.commands, [])


if __name__ == "__main__":
    unittest.main()
