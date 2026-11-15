"""Regression coverage for language routing, multilingual package safety and AI cleanup."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts.language_routes import (
    detect_language, load_routes, save_routes, choose_route,
)
from voxweavetts.model_packages import validate_manifest, ModelPackageError
from voxweavetts.ai_model_packages import (
    remove_legacy_m2m, legacy_model_installed, AIModelPackageError,
)
from voxweavetts.processing import InputError


class LanguageRoutingTests(unittest.TestCase):
    def test_script_detection(self):
        samples = [
            ("สวัสดีค่ะ", "th"), ("Hello world", "en"),
            ("こんにちは", "ja"), ("你好世界", "zh"),
            ("안녕하세요", "ko"), ("नमस्ते", "hi"),
            ("Привет", "ru"), ("123!", "und"),
        ]
        for text, expected in samples:
            with self.subTest(text=text):
                self.assertEqual(detect_language(text), expected)

    def test_save_reload_revision_and_route(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "voices.json"
            with patch("voxweavetts.language_routes.voice_languages",
                       return_value={"en"}):
                saved = save_routes({
                    "expected_revision": 0,
                    "routes": {"en": {
                        "engine_id": "model-kokoro-multilingual-int8-1_0_0",
                        "voice_id": "af_heart",
                        "speed": 1.35, "seed": 321,
                        "voice_controls": {"gain_db": 2.5, "pitch_semitones": -1.25,
                                           "bass_db": -3.0, "treble_db": 2.0,
                                           "formant_preserve": False},
                    }}
                }, path)
            self.assertEqual(saved["revision"], 1)
            self.assertNotIn("enabled", saved)
            self.assertEqual(load_routes(path), saved)
            language, voice = choose_route("Hello", path=path)
            self.assertEqual(language, "en")
            self.assertEqual(voice["voice_id"], "af_heart")
            self.assertEqual(voice["speed"], 1.35)
            self.assertEqual(voice["seed"], 321)
            self.assertEqual(voice["voice_controls"]["pitch_semitones"], -1.25)
            self.assertFalse(voice["voice_controls"]["formant_preserve"])
            with self.assertRaises(ValueError):
                save_routes({"expected_revision": 0, "routes": {}}, path)
            with self.assertRaises(InputError):
                choose_route("Hello", language=[], path=path)

    def test_reject_invalid_language_voice_tuning(self):
        base = {"engine_id": "test-tts", "voice_id": "af_heart"}
        invalid = [
            {"speed": 0.59}, {"speed": 5.01}, {"speed": float("nan")},
            {"speed": True}, {"seed": -1}, {"seed": 1.5},
            {"voice_controls": {"gain_db": 99}},
            {"voice_controls": {"pitch_semitones": float("inf")}},
            {"unexpected": "field"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            with patch("voxweavetts.language_routes.voice_languages",
                       return_value={"en"}):
                for bad in invalid:
                    with self.subTest(bad=bad), self.assertRaises(InputError):
                        save_routes({"expected_revision": 0,
                                     "routes": {"en": {**base, **bad}}},
                                    Path(temp) / "language-routes.json")

    def test_old_model_voice_only_route_remains_usable(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "language-routes.json"
            path.write_text('{"revision":2,"routes":{"en":{"engine_id":"test-tts",'
                            '"voice_id":"af_heart"}}}', encoding="utf-8")
            loaded = load_routes(path)
            self.assertEqual(loaded["routes"]["en"],
                             {"engine_id": "test-tts", "voice_id": "af_heart"})

    def test_reject_wrong_language_voice(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("voxweavetts.language_routes.voice_languages",
                       return_value={"th"}):
                with self.assertRaises(InputError):
                    save_routes({"expected_revision": 0,
                                 "routes": {"fr": {"engine_id": "thai",
                                                    "voice_id": "thai_som"}}},
                                Path(temp) / "voices.json")


class KokoroPackageManifestTests(unittest.TestCase):
    def test_data_only_manifest_allows_shared_voice_archive(self):
        data = {
            "format": "voxweavetts.model-package", "format_version": 1,
            "package_id": "kokoro-test-onnx", "version": "1.0.0",
            "title": "Kokoro CPU test", "engine_adapter": "kokoro-onnx-v1",
            "language": "multi", "sample_rate": 24000,
            "voices": [
                {"id": name, "label": name, "asset": "voices-v1.0.bin"}
                for name in ("af_heart", "ff_siwis", "jf_alpha")
            ],
            "files": [
                {"path": name, "size": 2048, "sha256": "a" * 64}
                for name in ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")
            ],
            "license": {
                "spdx": "Apache-2.0", "url": "https://example.org",
                "attribution": "Kokoro authors", "review_status": "review_required"
            },
            "source": {"url": "https://example.org", "revision": "test"},
            "dependencies": ["kokoro-onnx==0.6.0"],
        }
        self.assertIs(validate_manifest(data), data)
        bad = {**data, "language": "th"}
        with self.assertRaises(ModelPackageError):
            validate_manifest(bad)
        bad = {**data, "voices": [{"id": "invalid",
                                  "label": "Unsupported",
                                  "asset": "voices-v1.0.bin"}]}
        with self.assertRaises(ModelPackageError):
            validate_manifest(bad)


class LegacyAIUninstallTests(unittest.TestCase):
    def test_only_known_fixed_folder_can_be_removed(self):
        from voxweavetts.ai_engine_registry import _M2M_FILES
        with tempfile.TemporaryDirectory() as tmp:
            location = Path(tmp) / "m2m100_418m"
            location.mkdir()
            for filename in _M2M_FILES:
                (location / filename).write_bytes(b"dummy")
            extra = location / "private.txt"
            extra.write_text("do not delete")
            with patch("voxweavetts.ai_engine_registry.MODEL_DIR", location):
                self.assertTrue(legacy_model_installed())
                with self.assertRaises(AIModelPackageError):
                    remove_legacy_m2m()
                self.assertTrue(extra.exists(), "unknown data must survive")
                extra.unlink()
                self.assertTrue(remove_legacy_m2m())
                self.assertFalse(location.exists())
                self.assertFalse(remove_legacy_m2m())


if __name__ == "__main__":
    unittest.main()
