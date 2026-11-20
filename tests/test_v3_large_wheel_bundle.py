"""Ensure complex offline v3 model runtimes fit existing file-size security caps."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from voxweavetts.universal_model_packages import (
    FORMAT, VERSION, MAX_FILES, UniversalPackageError,
    validate_manifest, _validate_assets,
)


class LargeWheelBundleManifestTests(unittest.TestCase):
    def _make(self, folder: Path, *, wheel_count: int) -> dict:
        files = {}
        for name, data in {
            "model.onnx": b"fake ONNX bytes",
            "tokens.txt": b"tokens",
            "lexicon.txt": b"lexicon",
            "legal/license.txt": b"Apache-2.0 placeholder",
        }.items():
            files[name] = data
        requirements = []
        wheels = []
        for index in range(wheel_count):
            wheel = f"runtime/wheels/testpkg{index:03d}-1.0.0-py3-none-any.whl"
            files[wheel] = b"wheel payload " + str(index).encode()
            requirements.append({"name": f"testpkg{index:03d}", "version": "1.0.0"})
            wheels.append({
                "path": wheel, "sha256": hashlib.sha256(files[wheel]).hexdigest(),
            })
        lock = {"requirements": requirements, "wheels": wheels}
        files["runtime/locks/approved.lock"] = (
            json.dumps(lock, sort_keys=True).encode("utf-8")
        )
        files["legal/rights.json"] = json.dumps({
            "license": {"spdx": "MIT", "url": "https://example.org/license",
                        "attribution": "Synthetic fixture", "review_status": "review_required"},
            "source": {"url": "https://example.org/repo", "revision": "test"},
        }).encode("utf-8")
        files["manifest-assets.json"] = json.dumps({"paths": sorted(
            name for name in files
            if name not in ("manifest-assets.json", "legal/rights.json",
                            "runtime/locks/approved.lock")
        )}).encode("utf-8")
        for name, data in files.items():
            file = folder / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        return {
            "format": FORMAT, "format_version": VERSION,
            "package": {"id": "melo-fixture", "version": "1.0.0", "kind": "tts",
                        "title": "Fake model", "languages": ["zh"]},
            "adapter": {"id": "sherpa-melo-zh-v1", "api_version": 1, "trust": "builtin"},
            "runtime": {"id": "sherpa", "kind": "python-target", "python": "3.11",
                        "platform": "windows-x64", "accelerator": "cpu",
                        "source": "bundled-wheels", "install_policy": "auto",
                        "lockfile": "runtime/locks/approved.lock"},
            "capabilities": {"language": "zh", "sample_rate": 44100,
                             "voices": [{"id": "zh_melo", "label": "Chinese",
                                         "asset": "model.onnx"}]},
            "assets": "manifest-assets.json", "rights": "legal/rights.json",
            "files": [
                {"path": name, "size": len(data),
                 "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in files.items()
            ],
        }

    def test_106_wheels_can_be_declared_under_same_file_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self._make(root, wheel_count=106)
            self.assertLess(len(manifest["files"]), MAX_FILES)
            self.assertEqual(len(manifest["files"]), 113)
            validate_manifest(manifest)
            _validate_assets(root, manifest)

    def test_overall_file_cap_still_rejects_overlong_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = self._make(Path(temp), wheel_count=MAX_FILES)
            self.assertGreater(len(manifest["files"]), MAX_FILES)
            with self.assertRaises(UniversalPackageError):
                validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
