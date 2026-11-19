"""Regression coverage for language routing, multilingual package safety and AI cleanup."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts.language_routes import (
    detect_language, load_routes, save_routes, choose_route, voice_languages,
)
from voxweavetts.processing import InputError


class LanguageRoutingTests(unittest.TestCase):
    def test_makham_paradee_voice_can_be_routed_for_thai_and_english(self):
        from voxweavetts.speech import get_engine_info
        info = get_engine_info("makham-paradee-cpu")
        self.assertEqual(info.language, "th")
        self.assertEqual(info.supported_languages, ("th", "en"))
        self.assertEqual(info.as_dict()["supported_languages"], ["th", "en"])
        self.assertEqual(voice_languages("makham-paradee-cpu", "paradee_thai"),
                         {"th", "en"})
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "language-voices.json"
            route = {"engine_id": "makham-paradee-cpu", "voice_id": "paradee_thai"}
            saved = save_routes(
                {"expected_revision": 0, "routes": {"th": route, "en": route}},
                path,
            )
            self.assertEqual(saved["routes"]["th"], saved["routes"]["en"])
            self.assertEqual(choose_route("Hello everyone", path=path),
                             ("en", route))
            self.assertEqual(choose_route("สวัสดีทุกคน", path=path),
                             ("th", route))
            with self.assertRaises(InputError):
                save_routes({"expected_revision": 1, "routes": {"ja": route}}, path)

    def test_wayu_all_twelve_voices_allow_thai_and_english_routes(self):
        from voxweavetts.personal_wayu_engine import ENGINE_ID, VOICES
        from voxweavetts.speech import get_engine_info

        descriptor = get_engine_info(ENGINE_ID)
        self.assertEqual(descriptor.language, "th")
        self.assertEqual(descriptor.supported_languages, ("th", "en"))
        self.assertEqual(descriptor.as_dict()["supported_languages"], ["th", "en"])
        self.assertEqual(len(VOICES), 12)
        for voice_id, _ in VOICES:
            with self.subTest(voice=voice_id):
                self.assertEqual(voice_languages(ENGINE_ID, voice_id), {"th", "en"})

        # Both language entries may share the same NC model and the SAME voice.
        with tempfile.TemporaryDirectory() as temp:
            profile = {"engine_id": ENGINE_ID, "voice_id": "f_young_warm"}
            path = Path(temp) / "language-voices.json"
            saved = save_routes({"expected_revision": 0,
                                 "routes": {"th": profile, "en": profile}}, path)
            self.assertEqual(set(saved["routes"]), {"th", "en"})
            self.assertEqual(choose_route("Good morning", language="en", path=path)[1],
                             profile)
            self.assertEqual(choose_route("สวัสดีครับ", language="th", path=path)[1],
                             profile)
            with self.assertRaises(InputError):
                save_routes({"expected_revision": 1,
                             "routes": {"fr": profile}}, path)

    def test_installed_tts_models_are_selectable_for_english(self):
        from voxweavetts.speech import list_engine_info
        descriptors = list_engine_info()
        self.assertTrue(descriptors)
        for info in descriptors:
            if not info.assets_ready or not info.runtime_ready:
                continue
            with self.subTest(engine=info.id):
                english_voices = [voice_id for voice_id in info.voice_ids
                                  if "en" in voice_languages(info.id, voice_id)]
                self.assertTrue(english_voices,
                                f"English must be available on ready model {info.id}")
                # Every ready model can be saved as an English route without
                # mutating the user's existing language-voices.json.
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "routes.json"
                    route = {"engine_id": info.id, "voice_id": english_voices[0]}
                    result = save_routes(
                        {"expected_revision": 0, "routes": {"en": route}}, path)
                    self.assertEqual(result["routes"]["en"], route)

    def test_other_engines_only_offer_the_languages_they_support(self):
        from voxweavetts.speech import list_engine_info
        from voxweavetts.kokoro_engine import LANGUAGE_CODES
        descriptors = {engine.id: engine for engine in list_engine_info()}
        bilingual = (
            ("fastthaig2p-cpu", "th"),
            ("makham-paradee-cpu", "th"),
            ("vachana-cpu", "th"),
            ("model-fastthaig2p-thai-som-0_3_0", "th"),
            ("model-vachana-thai-four-voices-1_0_0", "th"),
            ("model-melo-chinese-onnx-1_0_0", "zh"),
        )
        for engine_id, expected in bilingual:
            if engine_id not in descriptors:
                continue  # Optional model packs need not be installed on CI.
            for voice_id in descriptors[engine_id].voice_ids:
                with self.subTest(engine=engine_id, voice=voice_id):
                    self.assertEqual(voice_languages(engine_id, voice_id), {expected, "en"})

        kokoro = descriptors.get("model-kokoro-multilingual-int8-1_0_0")
        if kokoro:
            for voice_id in kokoro.voice_ids:
                self.assertEqual(voice_languages(kokoro.id, voice_id),
                                 {LANGUAGE_CODES[voice_id[0]]})
        supertonic = descriptors.get("model-supertonic3-multilingual-int8-1_0_0")
        if supertonic:
            for voice_id in supertonic.voice_ids:
                self.assertEqual(voice_languages(supertonic.id, voice_id),
                                 {voice_id[:2]})

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

    def test_latin_sender_name_must_not_override_japanese_voice(self):
        # A short Japanese comment with a long Latin display name used to
        # route to the English voice, producing "Japanese letter" repeatedly.
        text = "VeryLongDisplayName writes: じゃない"
        self.assertEqual(detect_language(text), "ja")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "routes.json"
            with patch("voxweavetts.language_routes.voice_languages",
                       side_effect=lambda _engine, voice: {"ja"} if voice.startswith("j") else {"en"}):
                save_routes({"expected_revision": 0, "routes": {
                    "en": {"engine_id": "shared-kokoro", "voice_id": "af_heart"},
                    "ja": {"engine_id": "shared-kokoro", "voice_id": "jf_nezumi"},
                }}, path)
            self.assertEqual(choose_route(text, path=path)[1]["voice_id"], "jf_nezumi")
            self.assertEqual(choose_route("Hello world", path=path)[1]["voice_id"], "af_heart")
            self.assertEqual(choose_route(text, language="en", path=path)[1]["voice_id"], "af_heart")

    def test_kokoro_switches_phonemizer_language_with_voice(self):
        from voxweavetts.kokoro_engine import KokoroOnnxEngine

        class RecordingNative:
            def __init__(self):
                self.calls = []

            def create(self, text, *, voice, speed, lang, is_phonemes=False):
                self.calls.append((text, voice, lang, is_phonemes))
                return [0.0], 24_000

        engine = KokoroOnnxEngine(
            model_dir=Path("unused"), engine_id="shared-kokoro",
            voices=(("jf_nezumi", "Japanese"), ("af_heart", "English")))
        native = RecordingNative()
        engine._native = native
        with (patch("voxweavetts.kokoro_engine.runtime_ready", return_value=True),
              patch.object(engine, "_japanese_phonemes", side_effect=["ɲippon", "ʥa nai"]),
              patch("voxweavetts.speech._float32_to_pcm", return_value=b"\x00\x00")):
            engine.select_voice("jf_nezumi")
            engine.generate("日本", 1.0)
            engine.select_voice("af_heart")
            engine.generate("Hello", 1.0)
            engine.select_voice("jf_nezumi")
            engine.generate("じゃない", 1.0)
        self.assertEqual(native.calls, [
            ("ɲippon", "jf_nezumi", "ja", True),
            ("Hello", "af_heart", "en-us", False),
            ("ʥa nai", "jf_nezumi", "ja", True),
        ])

    def test_real_japanese_g2p_does_not_spell_kanji_letter_names(self):
        from importlib.util import find_spec
        if not all(find_spec(name) for name in ("misaki", "fugashi", "unidic_lite")):
            self.skipTest("optional Japanese G2P is not installed")
        from voxweavetts.kokoro_engine import KokoroOnnxEngine
        engine = KokoroOnnxEngine(
            model_dir=Path("unused"), engine_id="shared-kokoro",
            voices=(("jf_nezumi", "Japanese"),))
        phones = engine._japanese_phonemes("多分殻ごと食ってるもんね")
        self.assertIn("ta", phones)
        self.assertNotIn("Chinese", phones)
        self.assertNotIn("Japanese", phones)
        self.assertNotIn("(en)", phones)
        self.assertTrue(phones.strip())

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


# v3-only package manifest/rights validation is covered by
# test_v3_offline_relocatable.py and test_model_package_api.py.
if __name__ == "__main__":
    unittest.main()
