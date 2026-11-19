"""Real offline + relocatable Universal v3 runtime tests (Windows x64)."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from voxweavetts.universal_model_packages import (
    FORMAT, UniversalPackageError, inspect_archive,
    install_model_package, installed_packages, make_package, remove_model_package,
)
from voxweavetts.portable_runtime_v3 import (
    OfflineRuntimeError, fingerprint, ready, run_command, runtime_folder,
)

PROJECT = Path(__file__).resolve().parents[1]


def _json(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")


def _fake_wheel(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as out:
        out.writestr("vwfixture.py", "print('V3_RELOCATED_WORKER_OK')\n")
        out.writestr("vwfixture-1.0.0.dist-info/WHEEL",
                     "Wheel-Version: 1.0\nGenerator: VoxWeaveTTS test\n"
                     "Root-Is-Purelib: true\nTag: py3-none-any\n")
        out.writestr("vwfixture-1.0.0.dist-info/METADATA",
                     "Metadata-Version: 2.1\nName: vwfixture\nVersion: 1.0.0\n")
        out.writestr("vwfixture-1.0.0.dist-info/RECORD", "")
    return path.read_bytes()


def _fixture(root: Path, name: str = "test-vachana") -> tuple[Path, dict]:
    folder = root / "source-" / name
    folder.mkdir(parents=True)
    files = {
        "speaker_config.json": b'{"audio":{"sample_rate":22050}}',
        "voices/th_f_1.onnx": b"\x08\x01" + b"v" * 1100,
        "legal/rights.json": _json({
            "license": {"spdx": "Apache-2.0", "url": "https://example.org/license",
                        "attribution": "Trusted V3 test", "review_status": "cleared"},
            "source": {"url": "https://example.org/model", "revision": "test"},
        }),
    }
    wheel_name = "vwfixture-1.0.0-py3-none-any.whl"
    wheel_path = root / ("tmp-" + name + ".whl")
    bytes_ = _fake_wheel(wheel_path)
    files["runtime/wheels/" + wheel_name] = bytes_
    lock = {"requirements": [{"name": "vwfixture", "version": "1.0.0"}],
            "wheels": [{"path": "runtime/wheels/" + wheel_name,
                        "sha256": hashlib.sha256(bytes_).hexdigest()}]}
    files["runtime/locks/approved.lock"] = _json(lock)
    assets = sorted(x for x in files if x not in
                    ("legal/rights.json", "runtime/locks/approved.lock"))
    files["manifest-assets.json"] = _json({"paths": assets})
    for item, content in files.items():
        dest = folder / item
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    manifest = {
        "format": FORMAT, "format_version": 3,
        "package": {"id": name, "version": "1.0.0", "kind": "tts",
                    "title": name, "languages": ["th"]},
        "adapter": {"id": "vachana-onnx-v1", "trust": "builtin",
                    "api_version": 1},
        "runtime": {"id": "vachana", "kind": "python-target",
                    "python": "3.11", "platform": "windows-x64",
                    "accelerator": "cpu", "source": "bundled-wheels",
                    "install_policy": "auto",
                    "lockfile": "runtime/locks/approved.lock"},
        "assets": "manifest-assets.json", "rights": "legal/rights.json",
        "files": [{"path": path, "size": len(content),
                   "sha256": hashlib.sha256(content).hexdigest()}
                  for path, content in files.items()],
        "capabilities": {"language": "th", "sample_rate": 22050,
                         "voices": [{"id": "th_f_1", "label": "Female 1",
                                     "asset": "voices/th_f_1.onnx"}]},
    }
    trusted = root / "scripts" / "wheelhouse-locks"
    trusted.mkdir(parents=True, exist_ok=True)
    (trusted / "vachana.json").write_bytes(_json({
        "format": "voxweavetts.trusted-wheel-lock",
        "runtime_id": "vachana", "python_abi": "3.11",
        "platform": "win_amd64",
        "wheels": [{"filename": wheel_name, "name": "vwfixture",
                    "version": "1.0.0",
                    "sha256": hashlib.sha256(bytes_).hexdigest()}],
    }))
    return folder, manifest


class V3OfflineRelocatableTests(unittest.TestCase):
    def test_v2_rejected_without_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src, manifest = _fixture(root)
            manifest["format_version"] = 2
            with self.assertRaisesRegex(UniversalPackageError, "v3"):
                make_package(src, manifest, root / "old.vwmodel")

    def test_package_creates_and_reuses_runtime_then_relocates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "a"
            root.mkdir()
            src, manifest = _fixture(root)
            archive = root / "demo.vwmodel"
            make_package(src, manifest, archive)
            self.assertEqual(inspect_archive(archive)["format_version"], 3)
            with patch("voxweavetts.portable_runtime_v3.core_python",
                       return_value=Path(sys.executable)):
                result = install_model_package(archive, root=root)
                self.assertEqual(result["runtime_status"], "ready")
                self.assertTrue(ready(root, manifest))
                self.assertEqual(installed_packages(root)[0][0]["format_version"], 3)
                clone_root = Path(td) / "b"
                shutil.copytree(root / "runtime", clone_root / "runtime")
                shutil.copytree(root / "models", clone_root / "models")
                self.assertTrue(ready(clone_root, manifest))
                cmd = run_command(clone_root, manifest, "vwfixture")
                import subprocess
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("V3_RELOCATED_WORKER_OK", proc.stdout)
                self.assertTrue(remove_model_package("test-vachana", "1.0.0", root=root))
                self.assertFalse(runtime_folder(root, manifest).exists())

    def test_shared_runtime_is_removed_only_after_last_model(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first_source, first = _fixture(root, name="first-vachana")
            second_source, second = _fixture(root, name="second-vachana")
            one, two = root / "one.vwmodel", root / "two.vwmodel"
            make_package(first_source, first, one)
            make_package(second_source, second, two)
            self.assertEqual(fingerprint(first), fingerprint(second))
            with patch("voxweavetts.portable_runtime_v3.core_python",
                       return_value=Path(sys.executable)):
                install_model_package(one, root=root)
                install_model_package(two, root=root)
                self.assertEqual(len(installed_packages(root)), 2)
                shared = runtime_folder(root, first)
                self.assertTrue(shared.is_dir())
                self.assertTrue(ready(root, first))
                for _manifest, folder in installed_packages(root):
                    self.assertFalse((folder / "runtime/wheels").exists())
                self.assertTrue(remove_model_package("first-vachana", "1.0.0", root=root))
                self.assertTrue(shared.is_dir())
                self.assertTrue(ready(root, second))
                self.assertTrue(remove_model_package("second-vachana", "1.0.0", root=root))
                self.assertFalse(shared.exists())
                self.assertEqual(installed_packages(root), [])

    def test_core_bundled_cannot_be_impersonated_by_other_model(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _source, manifest = _fixture(root)
            manifest["runtime"].update({"kind": "core", "source": "core-bundled",
                                         "install_policy": "reuse-only", "lockfile": None})
            with self.assertRaisesRegex(UniversalPackageError, "core-bundled"):
                from voxweavetts.universal_model_packages import validate_manifest
                validate_manifest(manifest)

    def test_rejects_unapproved_wheel_hash_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src, manifest = _fixture(root)
            (root / "scripts/wheelhouse-locks/vachana.json").write_text(
                '{"format":"voxweavetts.trusted-wheel-lock",'
                '"runtime_id":"vachana","python_abi":"3.11",'
                '"platform":"win_amd64","wheels":[]}', encoding="utf-8")
            archive = root / "refused.vwmodel"
            make_package(src, manifest, archive)
            with patch("voxweavetts.portable_runtime_v3.core_python",
                       return_value=Path(sys.executable)):
                with self.assertRaises(OfflineRuntimeError):
                    install_model_package(archive, root=root)
            self.assertFalse(installed_packages(root))
            self.assertFalse(runtime_folder(root, manifest).exists())


if __name__ == "__main__":
    unittest.main()
