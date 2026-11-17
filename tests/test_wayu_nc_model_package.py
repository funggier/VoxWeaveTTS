"""NonCommercial Wayu .vwmodel is data-only, SHA-pinned and separately routed."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import model_packages as pkg, speech
from voxweavetts.engine_provider_catalog import provider_for_adapter
from voxweavetts.engine_worker_proxy import ProviderVoiceEngine
from voxweavetts.engine_worker_wayu import _verified_package_path, _check_pinned_weights
from voxweavetts.personal_wayu_engine import ENGINE_ID as PERSONAL_ENGINE_ID, VOICES


def _fixture(folder: Path) -> dict[str, str]:
    files: dict[str, bytes] = {
        "config.json": b'{"sample_rate": 24000}' + b" " * 80,
        "model.pth": b"m" * 4096,
    }
    for ident, _ in VOICES:
        files[f"voices/{ident}.pt"] = ident.encode() * 150
    for name, data in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    legal = folder / "legal"
    legal.mkdir()
    for name in ("license.txt", "attribution.md", "acceptable-use.txt"):
        (legal / name).write_text("NC original, no changes. https://creativecommons.org/licenses/by-nc/4.0/")
    (folder / "README.md").write_text("Wayu-Paxa-TTS-Edge CC BY-NC 4.0")
    return {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}


class WayuNCModelPackageTests(unittest.TestCase):
    @unittest.skip("v1 Wayu Engine registration retired; new v2 package required")
    def test_pinned_wayu_package_installs_and_offers_all_voices_in_two_languages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "source"
            model.mkdir()
            pins = _fixture(model)
            with patch.object(pkg, "_WAYU_PINNED_SHA256", pins):
                manifest = pkg.create_wayu_manifest(model)
                self.assertEqual(manifest["license"]["spdx"], "CC-BY-NC-4.0")
                self.assertEqual(manifest["license"]["review_status"], "hold")
                archive = root / "wayu-nc.vwmodel"
                pkg.make_package(model, manifest, archive)
                base = root / "packages"
                installed = pkg.install_model_package(archive, base=base)
                self.assertEqual(installed, manifest)
                with patch.object(speech, "installed_packages",
                                  lambda: pkg.installed_packages(base=base)):
                    # Engine ID is separate from the existing personal/NC engine.
                    speech.refresh_engine_registry()
                    try:
                        ident = pkg.engine_id_for(manifest)
                        self.assertNotEqual(ident, PERSONAL_ENGINE_ID)
                        info = speech.get_engine_info(ident)
                        self.assertEqual(info.voice_ids, tuple(v for v, _ in VOICES))
                        self.assertEqual(info.supported_languages, ("th", "en"))
                        self.assertTrue(info.label.startswith("[NC / NonCommercial]"))
                        self.assertEqual(info.commercial_status, "hold")
                        self.assertTrue(info.assets_ready)
                        self.assertEqual(provider_for_adapter("wayu-nc-v1").id, "wayu-nc")
                        engine = speech.create_voice_engine(ident, seed=101)
                        self.assertIsInstance(engine, ProviderVoiceEngine)
                        engine.select_voice("m_young_clear")
                        self.assertEqual(engine.voice_id, "m_young_clear")
                        self.assertTrue(info.capabilities["seed_control"])
                    finally:
                        speech.refresh_engine_registry()
                self.assertTrue(pkg.remove_model_package(
                    "wayu-paxa-edge-nc", "1.0.0", base=base))

    def test_rejects_modified_serialized_weight_even_with_self_signed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            pins = _fixture(folder)
            with patch.object(pkg, "_WAYU_PINNED_SHA256", pins):
                manifest = pkg.create_wayu_manifest(folder)
                self.assertEqual(pkg.validate_manifest(manifest), manifest)
                tampered = [dict(f) for f in manifest["files"]]
                for item in tampered:
                    if item["path"] == "model.pth":
                        item["sha256"] = "0" * 64
                with self.assertRaisesRegex(pkg.ModelPackageError, "upstream"):
                    pkg.validate_manifest({**manifest, "files": tampered})
                with self.assertRaisesRegex(pkg.ModelPackageError, "vetted"):
                    pkg.validate_manifest({**manifest, "license": {
                        **manifest["license"], "spdx": "MIT",
                    }})
                with self.assertRaisesRegex(pkg.ModelPackageError, "vetted"):
                    pkg.validate_manifest({**manifest, "version": "2.0.0"})
                with self.assertRaisesRegex(pkg.ModelPackageError, "vetted"):
                    pkg.validate_manifest({**manifest, "source": {
                        **manifest["source"], "revision": "untrusted",
                    }})
                with self.assertRaisesRegex(pkg.ModelPackageError, "voice"):
                    pkg.validate_manifest({**manifest, "voices": [
                        {**manifest["voices"][0], "asset": "model.pth"},
                        *manifest["voices"][1:],
                    ]})

    def test_package_model_lookup_cannot_select_untrusted_paths(self):
        with patch("voxweavetts.model_packages.installed_packages",
                   return_value=[]):
            with self.assertRaisesRegex(ValueError, "untrusted"):
                _verified_package_path("../../other-model")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            pins = _fixture(base)
            with patch("voxweavetts.wayu_native_trust.PINNED_ASSETS", pins):
                _check_pinned_weights(base)
                (base / "model.pth").write_bytes(b"bad")
                with self.assertRaisesRegex(ValueError, "upstream"):
                    _check_pinned_weights(base)

    def test_non_wayu_packages_cannot_ship_pytorch_pickles(self):
        with tempfile.TemporaryDirectory() as directory:
            from test_model_packages import fixture
            manifest = fixture(Path(directory))
            manifest["files"].append({
                "path": "model.pth", "size": 4096, "sha256": "a" * 64,
            })
            with self.assertRaisesRegex(pkg.ModelPackageError, "PyTorch"):
                pkg.validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
