"""Regression tests: independent CPU voice/language for Chinese and Korean."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from voxweavetts.sherpa_voice_engine import (
    SherpaVoiceEngine, SUPER_FILES, SUPER_VOICES, SUPER_LANGUAGES,
)
from voxweavetts.engine_contract import EngineInfo


class FakeAudio:
    sample_rate = 44100
    samples = [0.0] * 1024


class FakeSynth:
    def __init__(self):
        self.calls = []

    def generate(self, text, *args):
        self.calls.append((text, args))
        return FakeAudio()


class SherpaRoutingTests(unittest.TestCase):
    def test_supertonic_lang_is_derived_from_each_selected_voice(self):
        engine = SherpaVoiceEngine(
            model_dir=Path("not-used"), engine_id="test-sherpa",
            adapter="sherpa-supertonic-v1", voices=SUPER_VOICES,
            sample_rate=44100)
        fake = FakeSynth()
        engine._native = fake
        with (patch.dict("sys.modules", {"sherpa_onnx": SimpleNamespace(
                GenerationConfig=lambda: SimpleNamespace(extra={}))}),
              patch("voxweavetts.speech._float32_to_pcm", return_value=b"\x00\x00")):
            for voice, text, lang in (
                ("ko_s0", "안녕하세요", "ko"),
                ("en_s1", "Hello", "en"),
                ("ja_s0", "こんにちは", "ja"),
                ("ko_s1", "반갑습니다", "ko")):
                engine.select_voice(voice)
                self.assertEqual(engine.generate(text, 1.0), b"\x00\x00")
                gen = fake.calls[-1][1][0]
                self.assertEqual(gen.extra["lang"], lang)
                self.assertEqual(gen.sid, int(voice[-1]))
        with self.assertRaises(Exception):
            engine.select_voice("zh_s0")
        with self.assertRaises(Exception):
            engine.select_voice("ko_s9")

    def test_chinese_melo_keeps_zh_voice_separate(self):
        engine = SherpaVoiceEngine(
            model_dir=Path("not-used"), engine_id="test-melo",
            adapter="sherpa-melo-zh-v1",
            voices=(("zh_melo", "Mandarin"),), sample_rate=44100)
        fake = FakeSynth()
        engine._native = fake
        with (patch.dict("sys.modules", {"sherpa_onnx": SimpleNamespace()}),
              patch("voxweavetts.speech._float32_to_pcm", return_value=b"\x00\x00")):
            engine.select_voice("zh_melo")
            self.assertEqual(engine.generate("你好", 1.2), b"\x00\x00")
            self.assertEqual(fake.calls[0], ("你好", (0, 1.2)))
        with self.assertRaises(Exception):
            engine.select_voice("ko_s0")

    def test_supertonic_has_31_languages_and_62_mapped_voices(self):
        self.assertEqual(len(SUPER_LANGUAGES), 31)
        self.assertEqual(len(SUPER_VOICES), 62)
        self.assertIn("ko", SUPER_LANGUAGES)
        self.assertNotIn("zh", SUPER_LANGUAGES)
        info = EngineInfo(
            id="test", label="Test", language="multi", voice_id="ko_s0",
            sample_rate=44100, assets_ready=True, runtime_ready=True,
            capabilities={}, voice_options=SUPER_VOICES,
            voice_language_map={v: v[:2] for v, _ in SUPER_VOICES})
        self.assertEqual(info.as_dict()["voice_language_map"]["ko_s0"], "ko")
        self.assertEqual(info.as_dict()["voice_language_map"]["en_s1"], "en")


# Universal v3 model schema and voice validation are tested independently.
if __name__ == "__main__":
    unittest.main()
