"""Multi-voice v4 manifest and PCM synthesis contracts, no built-in engines."""
from __future__ import annotations

import io
import struct
import unittest
import wave
from unittest.mock import patch

from voxweavetts import speech
from voxweavetts.engine_contract import EngineInfo
from voxweavetts.presets import validate_preset
from voxweavetts.processing import InputError, process_text

V4_ID = "model-vachana-thai-four-voices-1_0_0"
VOICES = ("th_f_1", "th_f_2", "th_m_1", "th_m_2")


def v4_descriptor() -> EngineInfo:
    return EngineInfo(
        id=V4_ID, label="Vachana v4 (review pending)", language="th",
        sample_rate=22050, voice_id=VOICES[0], assets_ready=True,
        runtime_ready=True,
        voice_options=tuple((v, "V4 " + v) for v in VOICES),
        capabilities={"speech": True, "speed": True,
                      "voice_cloning": False},
        supported_languages=("th", "en"),
        commercial_status="hold",
    )


class DummyVoiceEngine:
    id = V4_ID
    sample_rate = 22050
    def select_voice(self, voice_id):
        self.selected = voice_id
    def generate(self, text, speed):
        assert self.selected == "th_m_2"
        return struct.pack("<h", 3000) * 2205


class V4MultiVoiceTests(unittest.TestCase):
    def test_four_voices_are_one_manifest_engine(self):
        info = v4_descriptor()
        self.assertEqual(info.voice_ids, VOICES)
        self.assertFalse(info.capabilities["voice_cloning"])
        self.assertEqual(info.commercial_status, "hold")

    def test_voice_selection_only_accepts_declared_ids(self):
        plan = process_text("สวัสดีครับ")
        with patch.object(speech, "get_engine_info", return_value=v4_descriptor()):
            for voice in VOICES:
                speech.validate_speech_request(plan, 1.0, voice, V4_ID)
            for voice in ("", "thai_som", "th_m_3", "../model.onnx"):
                with self.assertRaises(InputError):
                    speech.validate_speech_request(plan, 1.0, voice, V4_ID)
            engine = DummyVoiceEngine()
            wav, metadata = speech.render_wav(
                plan, engine_id=V4_ID, voice_id="th_m_2", engine=engine)
        self.assertEqual(engine.selected, "th_m_2")
        self.assertEqual(metadata["voice_id"], "th_m_2")
        with wave.open(io.BytesIO(wav)) as opened:
            self.assertEqual(opened.getframerate(), 22050)
            self.assertEqual(opened.getnframes(), 2205)

    def test_preset_preserves_nondefault_v4_voice(self):
        from voxweavetts import presets
        with patch.object(presets, "get_engine_info", return_value=v4_descriptor()):
            settings = validate_preset({
                "name":"Voice 4", "engine_id":V4_ID, "voice_id":"th_m_2"
            })
            self.assertEqual(settings["voice_id"], "th_m_2")
            with self.assertRaises(InputError):
                validate_preset({"name":"No", "engine_id":V4_ID,
                                 "voice_id":"../malicious"})

    def test_default_makham_uses_single_v4_voice(self):
        info = speech.get_engine_info(speech.ENGINE_ID)
        self.assertEqual(info.voice_ids, ("paradee_thai",))


if __name__ == "__main__":
    unittest.main()
