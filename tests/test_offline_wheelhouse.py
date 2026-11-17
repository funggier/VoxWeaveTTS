"""Trusted wheel inventory, strict hashes, safe snapshot and recipe provenance."""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from voxweavetts import offline_wheelhouse as wheelhouse


def wheel(directory: Path, distribution: str, version: str, *, payload=b"abc") -> Path:
    name = f"{distribution}-{version}-py3-none-any.whl"
    file = directory / name
    directory.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(file, "w", compression=zipfile.ZIP_STORED) as output:
        distinfo = f"{distribution}-{version}.dist-info/"
        output.writestr(distinfo + "METADATA",
                        "Metadata-Version: 2.1\nName: "
                        + distribution.replace("_", "-") + "\nVersion: "
                        + version + "\n\n")
        output.writestr(distinfo + "WHEEL",
                        "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\n"
                        "Tag: py3-none-any\n")
        output.writestr(distribution + "/__init__.py", payload)
    return file


class WheelhouseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "portable"
        self.root.mkdir()
        recipe = self.root / "scripts" / "engine-dependencies" / "sherpa.txt"
        recipe.parent.mkdir(parents=True)
        recipe.write_text("sherpa-onnx==2.0.1\nnumpy==2.2.6\n", encoding="utf-8")
        self.source = self.root / "candidate"
        self.source.mkdir()
        wheel(self.source, "sherpa_onnx", "2.0.1")
        wheel(self.source, "numpy", "2.2.6")
        self.draft = wheelhouse.draft_lock(self.root, "sherpa", self.source)

    def publish(self):
        lock = self.root / "scripts" / "wheelhouse-locks" / "sherpa.json"
        lock.parent.mkdir(parents=True)
        lock.write_text(json.dumps(self.draft), encoding="utf-8")
        folder = self.root / "runtime" / "wheelhouse" / "sherpa"
        folder.parent.mkdir(parents=True)
        shutil.copytree(self.source, folder)
        return folder, lock

    def test_draft_has_recipe_and_hashes_but_is_not_automatically_trusted(self):
        self.assertEqual(len(self.draft["wheels"]), 2)
        self.assertEqual(self.draft["python_abi"], "3.11")
        self.assertEqual(wheelhouse.status(self.root, "sherpa")["state"],
                         "not-published")
        with self.assertRaises(wheelhouse.WheelhouseError):
            with wheelhouse.verified_wheels(self.root, "sherpa"):
                pass

    def test_verified_wheel_copy_is_complete_and_ephemeral(self):
        self.publish()
        status = wheelhouse.status(self.root, "sherpa")
        self.assertEqual(status["state"], "present-unverified")
        self.assertTrue(status["ready_to_verify"])
        with wheelhouse.verified_wheels(self.root, "sherpa") as (folder, lock):
            self.assertEqual(len(list(folder.glob("*.whl"))), 2)
            contents = lock.read_text(encoding="utf-8")
            self.assertIn("sherpa-onnx==2.0.1 --hash=sha256:", contents)
            self.assertIn("numpy==2.2.6 --hash=sha256:", contents)
            temporary = folder.parent
            self.assertTrue(temporary.is_dir())
        self.assertFalse(temporary.exists())

    def test_same_size_tamper_rejected_before_runtime_install(self):
        folder, _ = self.publish()
        original = folder / "numpy-2.2.6-py3-none-any.whl"
        data = original.read_bytes()
        original.write_bytes(data.replace(b"abc", b"xyz", 1))
        self.assertTrue(wheelhouse.status(self.root, "sherpa")["ready_to_verify"])
        with self.assertRaisesRegex(wheelhouse.WheelhouseError, "SHA-256"):
            with wheelhouse.verified_wheels(self.root, "sherpa"):
                pass

    def test_recipe_drift_invalidates_wheelhouse(self):
        self.publish()
        recipe = self.root / "scripts" / "engine-dependencies" / "sherpa.txt"
        recipe.write_text("sherpa-onnx==2.0.2\nnumpy==2.2.6\n")
        self.assertFalse(wheelhouse.status(self.root, "sherpa")["ready_to_verify"])
        with self.assertRaises(wheelhouse.WheelhouseError):
            wheelhouse.trusted_lock(self.root, "sherpa")

    def test_unknown_files_and_missing_wheels_are_rejected(self):
        folder, _ = self.publish()
        (folder / "another.whl").write_bytes(b"unexpected")
        self.assertFalse(wheelhouse.status(self.root, "sherpa")["ready_to_verify"])
        (folder / "another.whl").unlink()
        (folder / "numpy-2.2.6-py3-none-any.whl").unlink()
        self.assertFalse(wheelhouse.status(self.root, "sherpa")["ready_to_verify"])

    def test_lock_injection_and_duplicate_distribution_are_rejected(self):
        for filename in ("../../malware.whl",
                         "C:\\malware.whl",
                         "evil-1.0-py3-none-any.whl/../../malware.whl"):
            candidate = json.loads(json.dumps(self.draft))
            candidate["wheels"][0]["filename"] = filename
            with self.subTest(filename=filename), self.assertRaises(wheelhouse.WheelhouseError):
                wheelhouse.validate_lock(candidate, root=self.root, runtime_id="sherpa")
        candidate = json.loads(json.dumps(self.draft))
        candidate["wheels"].append(candidate["wheels"][0].copy())
        with self.assertRaisesRegex(wheelhouse.WheelhouseError, "duplicate"):
            wheelhouse.validate_lock(candidate, root=self.root, runtime_id="sherpa")

    def test_untrusted_recipe_url_refused_even_if_wheels_exist(self):
        recipe = self.root / "scripts" / "engine-dependencies" / "wayu-nc.txt"
        recipe.write_text("torch==2.8.0\ngit+https://example.com/project.git\n")
        with self.assertRaisesRegex(wheelhouse.WheelhouseError, "remote dependencies"):
            wheelhouse.draft_lock(self.root, "wayu-nc", self.source)

    def test_missing_transitive_dependency_cannot_be_curated(self):
        original = self.source / "sherpa_onnx-2.0.1-py3-none-any.whl"
        original.unlink()
        with zipfile.ZipFile(original, "w") as output:
            folder = "sherpa_onnx-2.0.1.dist-info/"
            output.writestr(folder + "METADATA",
                "Metadata-Version: 2.1\nName: sherpa-onnx\nVersion: 2.0.1\n"
                "Requires-Dist: absent-helper==8.0\n\n")
            output.writestr(folder + "WHEEL",
                "Wheel-Version: 1.0\nTag: py3-none-any\n")
            output.writestr("sherpa_onnx/__init__.py", b"example")
        with self.assertRaisesRegex(wheelhouse.WheelhouseError,
                                    "missing transitive dependency"):
            wheelhouse.draft_lock(self.root, "sherpa", self.source)

    def test_metadata_spoofed_wheel_rejected(self):
        attacker = self.source / "numpy-2.2.6-py3-none-any.whl"
        attacker.unlink()
        wheel(self.source, "numpy", "2.2.7")
        (self.source / "numpy-2.2.7-py3-none-any.whl").rename(attacker)
        with self.assertRaisesRegex(wheelhouse.WheelhouseError, "metadata"):
            wheelhouse.draft_lock(self.root, "sherpa", self.source)


if __name__ == "__main__":
    unittest.main()
