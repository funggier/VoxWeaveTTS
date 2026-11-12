"""A multi-voice model is one engine with explicit selectable voice IDs."""
from __future__ import annotations

import io
import struct
import unittest
import wave

from voxweavetts.processing import InputError, process_text
from voxweavetts import speech
from voxweavetts.presets import validate_preset


class MockVachana:
    id = "vachana-cpu"
    sample_rate = 22_050

    def __init__(self):
        self.selected = None

    def select_voice(self, voice_id):
        self.selected = voice_id

    def generate(self, text, speed):
        assert self.selected == "th_m_2"
        return struct.pack("<h", 3000) * 2205


class MultiVoiceTests(unittest.TestCase):
    def test_vachana_is_one_engine_with_four_named_voices(self):
        info = speech.get_engine_info("vachana-cpu")
        self.assertEqual(info.voice_id, "th_f_1")
        expected = ["th_f_1", "th_f_2", "th_m_1", "th_m_2"]
        self.assertEqual([v["id"] for v in info.as_dict()["voices"]], expected)
        self.assertEqual(len({v["label"] for v in info.as_dict()["voices"]}), 4)
        self.assertFalse(info.capabilities["voice_cloning"])
        self.assertEqual(info.commercial_status, "hold")

    def test_voice_selection_validates_id_and_flows_into_engine(self):
        plan = process_text("สวัสดีครับ")
        for voice in ("th_f_1", "th_f_2", "th_m_1", "th_m_2"):
            speech.validate_speech_request(plan, 1.0, voice, "vachana-cpu")
        for voice in ("", "thai_som", "th_m_3", "../model.onnx"):
            with self.assertRaises(InputError):
                speech.validate_speech_request(plan, 1.0, voice, "vachana-cpu")
        engine = MockVachana()
        wav, details = speech.render_wav(
            plan, engine_id="vachana-cpu", voice_id="th_m_2", engine=engine
        )
        self.assertEqual(engine.selected, "th_m_2")
        self.assertEqual(details["voice_id"], "th_m_2")
        with wave.open(io.BytesIO(wav)) as opened:
            self.assertEqual(opened.getframerate(), 22_050)
            self.assertEqual(opened.getnframes(), 2205)

    def test_voice_preset_preserves_nondefault_voice(self):
        setting = validate_preset({
            "name": "ชาย 2", "engine_id": "vachana-cpu",
            "voice_id": "th_m_2",
        })
        self.assertEqual(setting["voice_id"], "th_m_2")
        with self.assertRaises(InputError):
            validate_preset({
                "name": "ไม่ตรง", "engine_id": "vachana-cpu",
                "voice_id": "other",
            })

    def test_existing_engines_expose_one_compatible_voice(self):
        for engine_id in (speech.ENGINE_ID, speech.PARADEE_ENGINE_ID):
            info = speech.get_engine_info(engine_id)
            self.assertEqual([v["id"] for v in info.as_dict()["voices"]], [info.voice_id])


if __name__ == "__main__":
    unittest.main()
