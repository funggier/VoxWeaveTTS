"""v4-only example catalog, conversion safety and translation schema tests."""
from __future__ import annotations
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts.universal_model_v4 import (
    validate_manifest, engine_id, install, remove, installed_packages
)

ROOT = Path(__file__).resolve().parents[1]


class V4ModelMigrationTests(unittest.TestCase):
    def test_only_v4_package_author_examples_are_exposed(self):
        folders = sorted(p.name for p in (ROOT / "examples").iterdir() if p.is_dir()
                         and not p.name.startswith("__"))
        self.assertEqual(folders, sorted([
            "v4-demo-tone", "v4-demo-wheel", "v4-native-worker",
            "v4-model-plugin", "v4-translation-plugin",
        ]))
        self.assertTrue((ROOT / "tests/fixtures/legacy-provider-sdk").is_dir())

    def test_conversion_covers_every_original_model_and_translation(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import convert_all_models_to_v4 as c
        self.assertEqual(set(c.SOURCES), {
            "makham-paradee", "fastthaig2p-thai-som", "melo-chinese-onnx",
            "supertonic3-multilingual-int8", "m2m100-418m",
            "kokoro-multilingual-int8", "vachana-thai-four-voices",
            "wayu-paxa-edge-nc",
        })
        self.assertTrue(c.OUTPUT.name.endswith("V4-QA"))
        self.assertIsNone(c._asset_destination("manifest-assets.json"))
        self.assertIsNone(c._asset_destination("runtime/locks/approved.lock"))
        self.assertEqual(c._asset_destination("model.safetensors"),
                         "assets/model.safetensors")
        self.assertEqual(c._asset_destination("LICENSE"), "assets/LICENSE.txt")

    def test_v4_translation_manifest_accepts_worker_and_preserves_rights_hold(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from test_v4_plugin_packages import fixture
        from build_vwmodel_v4 import build
        from voxweavetts import universal_model_v4 as v4
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fixture(base)
            spec_path = base / "spec.json"
            data = json.loads(spec_path.read_text("utf-8"))
            data["package"]["kind"] = "translation"
            data["package"]["id"] = "future-translation"
            data["engine"] = {
                "protocol": 1, "entrypoint": "plugin/worker.py",
                "operation": "translate", "languages": ["en", "th"],
            }
            data["rights"]["review_status"] = "hold"
            spec_path.write_text(json.dumps(data), encoding="utf-8")
            archive = build(base / "source", spec_path, base / "translate.vwmodel")
            manifest = v4.inspect_archive(archive)
            self.assertEqual(manifest["package"]["kind"], "translation")
            self.assertEqual(manifest["rights"]["review_status"], "hold")
            with patch.object(v4, "core_python", return_value=Path(sys.executable)), patch.object(
                v4, "sys_platform", return_value="windows-x64"
            ):
                stage = base / "portable"
                result = v4.install(archive, root=stage)
                self.assertEqual(result["format_version"], 4)
                self.assertTrue(
                    (stage / "models/universal/v4/translation/future-translation/1.0.0/manifest.json").is_file()
                )
                self.assertEqual(len(installed_packages(stage)), 1)
                self.assertTrue(remove("future-translation", "1.0.0", root=stage))
                self.assertEqual(len(installed_packages(stage)), 0)

    def test_translation_manifest_rejects_fake_audio_voices(self):
        data = {
            "format": "voxweavetts.model-package", "format_version": 4,
            "package": {"id": "tr-model", "version": "1.0.0", "kind": "translation",
                        "title": "Test translation", "languages": ["en", "th"]},
            "engine": {"protocol": 1, "entrypoint": "plugin/worker.py",
                       "operation": "translate", "languages": ["en", "th"],
                       "voices": [{"id": "fake", "label": "not speech"}]},
            "runtime": {"python": "3.11", "platform": "windows-x64", "wheels": []},
            "rights": {"spdx": "MIT", "url": "https://example.org/license",
                       "source": "https://example.org/repo",
                       "attribution": "Example fixture"},
            "files": [
                {"path": "plugin/worker.py", "sha256": "0" * 64, "size": 12},
                {"path": "assets/model.bin", "sha256": "0" * 64, "size": 12},
            ],
        }
        with self.assertRaisesRegex(ValueError, "translation worker"):
            validate_manifest(data)


if __name__ == "__main__":
    unittest.main()
