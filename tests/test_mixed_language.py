"""Regression: user-enabled script spans synthesize in order as ONE WAV."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from voxweavetts.engine_contract import EngineInfo
from voxweavetts.mixed_language import split_language_spans
from voxweavetts.mode_voice_settings import load_workspace_settings, save_workspace_settings
from voxweavetts.processing import InputError, process_text
from voxweavetts.server import Handler
from voxweavetts.speech import render_wav


def _ready_info(engine_id):
    """Make tests independent of optional model weights installed on CI."""
    from dataclasses import replace
    from voxweavetts.speech import get_engine_info
    return replace(get_engine_info(engine_id),
                   assets_ready=True, runtime_ready=True)


class SpanTests(unittest.TestCase):
    def test_exact_user_example_is_four_spans_without_lost_characters(self):
        sample = "ผมอยากทำComputer ผม ให้มันลื่นกว่านี้ lol"
        spans = split_language_spans(sample)
        self.assertEqual(
            [(x.language, x.text) for x in spans],
            [("th", "ผมอยากทำ"), ("en", "Computer "),
             ("th", "ผม ให้มันลื่นกว่านี้ "), ("en", "lol")])
        self.assertEqual("".join(x.text for x in spans), sample)
        self.assertEqual([(x.start, x.end) for x in spans],
                         list(zip([0] + [x.end for x in spans[:-1]],
                                  [x.end for x in spans])))
        for text, langs in (
            ("多分殻ごと食ってるもんね", ["ja"]),
            ("你好 こんにちは", ["zh", "ja"]),
            ("안녕 hello", ["ko", "en"]),
            ("123?!", ["und"]),
        ):
            self.assertEqual([s.language for s in split_language_spans(text)], langs)

    def test_translation_target_does_not_override_actual_mixed_scripts(self):
        from voxweavetts.ai_pipeline import process_pipeline
        from voxweavetts.ai_processing import DEFAULTS

        plan = process_pipeline(
            "ผมอยากทำคอมพิวเตอร์",
            settings={**DEFAULTS, "enabled": True, "engine": "ollama",
                      "operation": "translate", "target_language": "zh",
                      "translation_mode": "whole_message",
                      "translation_bypass_validation": True},
            model_call=lambda *_: "你好 ผมยังไม่ได้แปลคำนี้ Computer")
        self.assertEqual(plan["processing"]["ai_status"], "processed")
        self.assertEqual(plan["processing"]["speech_language"], "zh")
        self.assertEqual([s.language for s in split_language_spans(
            plan["spoken_text"])], ["zh", "th", "en"])

    def test_workspace_switch_is_optional_per_mode_and_migrates(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text(json.dumps({
                "revision": 3, "policy": "serial", "modes": {},
                "language_routes": {"studio": True},
            }), encoding="utf-8")
            before = load_workspace_settings(path)
            self.assertEqual(before["language_splitting"], {})
            updated = save_workspace_settings({
                "expected_revision": 3, "mode": "__language_split__",
                "settings": {"source_mode": "studio", "enabled": True}}, path)
            self.assertTrue(updated["language_splitting"]["studio"])
            self.assertNotIn("reader", updated["language_splitting"])
            self.assertTrue(updated["language_routes"]["studio"])
            updated = save_workspace_settings({
                "expected_revision": 4, "mode": "__language_split__",
                "settings": {"source_mode": "studio", "enabled": False}}, path)
            self.assertFalse(updated["language_splitting"]["studio"])
            self.assertFalse(load_workspace_settings(path)["language_splitting"]["studio"])
            for value in ("true", 1, None):
                with self.assertRaises(InputError):
                    save_workspace_settings({
                        "expected_revision": 5, "mode": "__language_split__",
                        "settings": {"source_mode": "reader", "enabled": value}}, path)

    def test_server_off_preserves_normal_render_arguments(self):
        plan = process_text("สวัสดี Hello")
        with (patch("voxweavetts.server.load_workspace_settings", return_value={
            "language_routes": {}, "language_splitting": {"studio": False},
        }), patch("voxweavetts.server.get_engine_info", side_effect=_ready_info)):
            params = Handler._speech_params(None, {"mode": "studio"}, plan)
        self.assertNotIn("language_voice_routes", params)

    def test_server_on_samples_routes_without_rewriting_other_modes(self):
        plan = process_text("สวัสดี Hello")
        saved = {"th": {"engine_id": "model-makham-paradee-1_0_0", "voice_id": "paradee_thai"},
                 "en": {"engine_id": "en-fixture", "voice_id": "en_voice"}}
        with (patch("voxweavetts.server.load_workspace_settings", return_value={
                "language_routes": {}, "language_splitting": {"studio": True},
              }),
              patch("voxweavetts.server.load_routes",
                    return_value={"routes": saved}),
              patch("voxweavetts.server.get_engine_info", side_effect=_ready_info)):
            params = Handler._speech_params(None, {"mode": "studio"}, plan)
        self.assertEqual(params["language_voice_routes"], saved)


class FakeEngine:
    def __init__(self, identity, rate, events):
        self.id = identity
        self.sample_rate = rate
        self.events = events
        self.voice = None

    def select_voice(self, voice):
        self.voice = voice

    def generate(self, text, speed):
        self.events.append((self.id, self.voice, text, speed))
        return (b"\x00\x20" * round(self.sample_rate / 10))


class SynthesisTests(unittest.TestCase):
    def test_stdlib_pcm16_resample_works_without_audioop_or_numpy(self):
        import struct
        import sys
        from voxweavetts.mixed_synthesis import resample_pcm16
        source=struct.pack("<4h",0,1000,-1000,0)
        # Python 3.13 has no audioop. This test simulates that standard-library
        # environment on every supported CI version without installing NumPy.
        with patch.dict(sys.modules,{"audioop":None}):
            output=resample_pcm16(source,4,8)
            self.assertEqual(struct.unpack("<8h",output),
                             (0,500,1000,0,-1000,-500,0,0))
            self.assertEqual(resample_pcm16(source,4,4),source)
            with self.assertRaisesRegex(ValueError,"partial PCM16"):
                resample_pcm16(source+bytes([0]),4,8)

    def info(self, key):
        if key == "thai":
            return EngineInfo(
                id="thai", label="Mock Thai", language="th",
                sample_rate=24000, voice_id="thai_voice",
                assets_ready=True, runtime_ready=True,
                voice_options=(("thai_voice", "Thai"),), capabilities={})
        if key == "english":
            return EngineInfo(
                id="english", label="Mock English", language="en",
                sample_rate=44100, voice_id="en_voice",
                assets_ready=True, runtime_ready=True,
                voice_options=(("en_voice", "English"),), capabilities={})
        if key == "shared":
            return EngineInfo(
                id="shared", label="Mock shared", language="multi",
                sample_rate=24000, voice_id="thai_voice",
                assets_ready=True, runtime_ready=True,
                voice_options=(("thai_voice", "Thai"), ("en_voice", "English")),
                capabilities={})
        raise AssertionError(key)

    def test_same_wav_mixed_sample_rate_order_timeline_and_tuning(self):
        events = []
        source = "ผมอยากทำComputer ผม ให้มันลื่นกว่านี้ lol"
        plan = process_text(source)
        routes = {
            "th": {"engine_id": "thai", "voice_id": "thai_voice", "speed": 1.2},
            "en": {"engine_id": "english", "voice_id": "en_voice", "speed": 0.9},
        }
        with (patch("voxweavetts.speech.get_engine_info",
                    side_effect=self.info) as discovery,
              patch("voxweavetts.speech.create_voice_engine",
                    side_effect=lambda key, seed: FakeEngine(
                        key, self.info(key).sample_rate, events))):
            wav, metadata = render_wav(
                plan, engine_id="thai", voice_id="thai_voice",
                speed=1, seed=100, language_voice_routes=routes)
        self.assertEqual(discovery.call_count,2,
                         "four language spans should validate two engine descriptors")
        self.assertEqual([(e[0], e[2], e[3]) for e in events], [
            ("thai", "ผมอยากทำ", 1.2),
            ("english", "Computer ", 0.9),
            ("thai", "ผม ให้มันลื่นกว่านี้ ", 1.2),
            ("english", "lol", 0.9),
        ])
        with wave.open(io.BytesIO(wav), "rb") as audio:
            self.assertEqual(audio.getframerate(), 44100)
            self.assertEqual(audio.getnchannels(), 1)
            self.assertEqual(audio.getsampwidth(), 2)
            self.assertAlmostEqual(audio.getnframes() / 44100, 0.4, delta=0.005)
        self.assertEqual(metadata["duration_ms"], 400)
        self.assertEqual(len(metadata["segments"]), len(plan["segments"]))
        self.assertEqual(metadata["segments"][0]["display_text"], source)
        self.assertEqual([v["language"] for v in metadata["voices_used"]],
                         ["th", "en"])

    def test_same_engine_switches_voices_per_span_including_return(self):
        events = []
        plan = process_text("ไทย Hello อีกที bye")
        with (patch("voxweavetts.speech.get_engine_info", side_effect=self.info),
              patch("voxweavetts.speech.create_voice_engine",
                    side_effect=lambda key, seed: FakeEngine(key, 24000, events)) as factory):
            wav, metadata = render_wav(
                plan, engine_id="shared", voice_id="thai_voice",
                language_voice_routes={
                    "th": {"engine_id": "shared", "voice_id": "thai_voice"},
                    "en": {"engine_id": "shared", "voice_id": "en_voice"},
                })
        self.assertEqual([e[1] for e in events],
                         ["thai_voice", "en_voice", "thai_voice", "en_voice"])
        self.assertEqual(factory.call_count, 1)
        self.assertTrue(wav.startswith(b"RIFF"))
        self.assertEqual(metadata["sample_rate"], 24000)

    def test_missing_language_route_falls_back_and_skip_remains_masked(self):
        events = []
        plan = process_text("ไทย ABC ห้ามลับ", rules=[{
            "match": "ห้ามลับ", "mode": "skip",
        }])
        with (patch("voxweavetts.speech.get_engine_info", side_effect=self.info),
              patch("voxweavetts.speech.create_voice_engine",
                    side_effect=lambda key, seed: FakeEngine(key, 24000, events))):
            wav, metadata = render_wav(
                plan, engine_id="thai", voice_id="thai_voice",
                language_voice_routes={})
        self.assertTrue(wav.startswith(b"RIFF"))
        self.assertTrue(all(e[0] == "thai" for e in events))
        self.assertTrue(all("ห้ามลับ" not in e[2] for e in events))
        self.assertTrue(metadata["segments"][-1]["kind"] == "skip")
        self.assertEqual(metadata["segments"][-1]["display_text"], "***")

    def test_opt_out_uses_original_single_engine_once(self):
        events = []
        with (patch("voxweavetts.speech.get_engine_info", side_effect=self.info),
              patch("voxweavetts.speech.create_voice_engine",
                    side_effect=lambda key, seed: FakeEngine(key, 24000, events))):
            render_wav(process_text("สวัสดี Hello"),
                       engine_id="thai", voice_id="thai_voice")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][2], "สวัสดี Hello")


if __name__ == "__main__":
    unittest.main()
