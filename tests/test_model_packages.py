"""Data-only .vwmodel package installation and multiple coexistence tests."""
from __future__ import annotations
import hashlib
import io
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from voxweavetts import speech
from voxweavetts.model_packages import (
    FORMAT, ModelPackageError, make_package, install_model_package,
    installed_packages, remove_model_package, engine_id_for, validate_manifest,
)


def fixture(source: Path, *, package_id="vachana-a", version="1.0.0"):
    names = ["th_f_1", "th_f_2"]
    payloads = {"speaker_config.json": b'{"audio":{"sample_rate":22050}}'}
    for name in names:
        payloads["voices/" + name + ".onnx"] = b"\x08\x01" + (name.encode() * 512)
    for name, data in payloads.items():
        file = source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
    return {
        "format": FORMAT, "format_version": 1,
        "package_id": package_id, "version": version,
        "title": "Thai Test Multiple Voices",
        "engine_adapter": "vachana-onnx-v1", "language": "th",
        "sample_rate": 22_050,
        "voices": [{"id": name, "label": "เสียง " + name,
                    "asset": "voices/" + name + ".onnx"} for name in names],
        "files": [{"path": path, "size": len(data),
                   "sha256": hashlib.sha256(data).hexdigest()}
                  for path, data in payloads.items()],
        "license": {"spdx": "MIT", "url": "https://example.org/voice",
                    "attribution": "Example testing attribution",
                    "review_status": "review_required"},
        "source": {"url": "https://example.org/source", "revision": "test"},
        "dependencies": ["vachanatts==0.0.7"],
    }


class ModelPackagesTests(unittest.TestCase):
    def test_install_two_versions_and_another_model_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "packages"
            for package_id, version in [
                ("vachana-a", "1.0.0"), ("vachana-a", "1.1.0"),
                ("vachana-b", "1.0.0"),
            ]:
                src = Path(temp) / "src" / package_id / version
                profile = fixture(src, package_id=package_id, version=version)
                archive = Path(temp) / (package_id + "-" + version + ".vwmodel")
                make_package(src, profile, archive)
                self.assertEqual(install_model_package(archive, base=base), profile)
            found = installed_packages(base=base)
            self.assertEqual(len(found), 3)
            self.assertEqual(len({engine_id_for(m) for m, _ in found}), 3)
            self.assertEqual([len(m["voices"]) for m, _ in found], [2, 2, 2])
            first = base / "vachana-a" / "1.0.0"
            self.assertTrue(first.is_dir())
            with self.assertRaisesRegex(ModelPackageError, "already installed"):
                install_model_package(Path(temp) / "vachana-a-1.0.0.vwmodel", base=base)
            self.assertTrue(remove_model_package("vachana-a", "1.1.0", base=base))
            self.assertTrue(first.is_dir())
            self.assertEqual(len(installed_packages(base=base)), 2)
            self.assertFalse(remove_model_package("vachana-a", "1.1.0", base=base))

    def test_incompatible_manifest_and_code_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "src"
            manifest = fixture(src)
            cases = [
                ("no provenance", {"license": {}}),
                ("adapter injection", {"engine_adapter": "python-plugin"}),
                ("unknown file", {"files": manifest["files"] + [{"path": "../evil.py", "size": 1, "sha256": "0" * 64}]}),
                ("malicious voice", {"voices": [{"id": "../bad", "label": "BAD", "asset": "voices/th_f_1.onnx"}]}),
                ("bad version", {"version": "../0.1"}),
            ]
            for case, edit in cases:
                with self.subTest(case=case), self.assertRaises(ModelPackageError):
                    validate_manifest({**manifest, **edit})
            # Explicit reject ZIP members not declared in the manifest.
            archive = Path(temp) / "extra.vwmodel"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("manifest.json", json.dumps(manifest))
                for row in manifest["files"]:
                    zipped.write(src / row["path"], row["path"])
                zipped.writestr("../evil.py", "print('malicious')")
            with self.assertRaises(ModelPackageError):
                install_model_package(archive, base=Path(temp) / "installed")
            self.assertFalse((Path(temp) / "evil.py").exists())

    def test_corruption_sha_rejected_and_atomic(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "src"
            manifest = fixture(src)
            archive = Path(temp) / "corrupt.vwmodel"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("manifest.json", json.dumps(manifest))
                for row in manifest["files"]:
                    content = (src / row["path"]).read_bytes()
                    if row["path"] == "voices/th_f_2.onnx":
                        content = bytes([content[0] ^ 1]) + content[1:]
                    zipped.writestr(row["path"], content)
            with self.assertRaisesRegex(ModelPackageError, "SHA-256"):
                install_model_package(archive, base=Path(temp) / "installed")
            self.assertFalse((Path(temp) / "installed" / "vachana-a" / "1.0.0").exists())

    def test_package_registered_with_existing_trusted_adapter(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "models"
            source = Path(temp) / "source"
            m = fixture(source)
            a = Path(temp) / "voice.vwmodel"
            make_package(source, m, a)
            install_model_package(a, base=base)
            with patch.object(speech, "installed_packages", lambda: installed_packages(base=base)):
                speech.refresh_engine_registry()
                try:
                    info = speech.get_engine_info(engine_id_for(m))
                    self.assertEqual(info.voice_ids, ("th_f_1", "th_f_2"))
                    self.assertEqual(info.commercial_status, "review_required")
                    self.assertTrue(info.assets_ready)
                    engine = speech.create_voice_engine(info.id, seed=100)
                    self.assertEqual(engine.id, info.id)
                    self.assertEqual(engine.model_dir, base / "vachana-a" / "1.0.0")
                    speech.validate_speech_request(
                        {"segments": []}, 1.0, "th_f_2", info.id
                    )
                    self.assertIn("makham-paradee-cpu",
                                  [entry.id for entry in speech.list_engine_info()])
                finally:
                    speech.refresh_engine_registry()


if __name__ == "__main__":
    unittest.main()
