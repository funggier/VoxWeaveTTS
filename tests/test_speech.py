import io
import struct
import unittest
import wave

from voxweavetts.processing import InputError, process_text
from voxweavetts.speech import (
    ENGINE_ID, _chunks, engine_info, render_wav, validate_speech_request,
)


class ConstantEngine:
    id = "fake-audio"
    sample_rate = 24000

    def generate(self, text, speed):
        assert text
        assert 0.6 <= speed <= 5.0
        return struct.pack("<h", 2000) * 1000


class SpeechTests(unittest.TestCase):
    def test_speech_and_silence_are_real_pcm_frames(self):
        plan = process_text(
            "ก่อนคำต้องห้ามหลัง",
            [{"match": "คำต้องห้าม", "mode": "silence", "silence_ms": 400}],
        )
        wav, meta = render_wav(plan, engine=ConstantEngine())
        with wave.open(io.BytesIO(wav), "rb") as f:
            self.assertEqual(f.getframerate(), 24000)
            self.assertEqual(f.getnchannels(), 1)
            self.assertEqual(f.getsampwidth(), 2)
            self.assertEqual(f.getnframes(), 1000 + 9600 + 1000)
            frames = f.readframes(f.getnframes())
        self.assertEqual(frames[2000:2000+19200], bytes(19200))
        self.assertEqual(meta["segments"][1]["end_ms"] - meta["segments"][1]["start_ms"], 400)
        self.assertEqual(meta["segments"][1]["display_text"], "***")
        self.assertNotIn("คำต้องห้าม", str(meta))

    def test_replace_and_skip_not_synthesized(self):
        p = process_text(
            "อุ๊ย abc DEF",
            rules=[
                {"match": "abc", "mode": "replace", "spoken": "สวัสดี", "display": "abc"},
                {"match": "DEF", "mode": "skip", "display": "***"},
            ],
        )
        audio, meta = render_wav(p, engine=ConstantEngine())
        with wave.open(io.BytesIO(audio), "rb") as f:
            self.assertEqual(f.getnframes(), 2000)
        self.assertEqual(meta["segments"][-1]["kind"], "skip")
        self.assertEqual(meta["segments"][-1]["start_ms"], meta["segments"][-1]["end_ms"])

    def test_invalid_controls(self):
        p = process_text("สวัสดี")
        for speed in [-1, 0, 5.01, "fast", True, float("nan"), float("inf")]:
            with self.assertRaises(InputError):
                render_wav(p, speed=speed, engine=ConstantEngine())
        with self.assertRaises(InputError):
            render_wav(p, voice_id="my-voice", engine=ConstantEngine())
        with self.assertRaises(InputError):
            render_wav(process_text("x"*501), engine=ConstantEngine())

    def test_stable_seed_metadata_and_validation(self):
        from voxweavetts.speech import DEFAULT_SEED, validate_seed
        plan = process_text("ฮ่า ฮ่า ฮ่า")
        _wav, details = render_wav(plan, engine=ConstantEngine(), seed=17)
        self.assertEqual(details["seed"], 17)
        self.assertEqual(validate_seed(DEFAULT_SEED), DEFAULT_SEED)
        for value in (-1, 2147483648, 2.3, True, "100", None):
            with self.assertRaises(InputError):
                render_wav(plan, engine=ConstantEngine(), seed=value)

    def test_render_instantiates_fresh_engine_per_request(self):
        from unittest.mock import patch, call
        plan = process_text("ฮ่า ฮ่า ฮ่า")
        # Mock the generic registry-backed factory rather than one built-in
        # class: tests must not assume any particular model implementation.
        with patch("voxweavetts.speech.create_voice_engine", return_value=ConstantEngine()) as factory:
            render_wav(plan, seed=100)
            render_wav(plan, seed=100)
            self.assertEqual(factory.call_args_list, [
                call(ENGINE_ID, seed=100), call(ENGINE_ID, seed=100),
            ])

    def test_chunk_splits_do_not_discard_characters(self):
        for text in ["a"*345, "สวัสดีครับ "*50, "one, two. three! "+("four "*20)]:
            self.assertEqual("".join(_chunks(text)), text)

    def test_engine_id_and_capabilities(self):
        info = engine_info()
        self.assertEqual(info.id, ENGINE_ID)
        self.assertEqual(info.voice_id, "thai_som")
        self.assertFalse(info.capabilities["voice_cloning"])
        self.assertFalse(info.capabilities["pitch"])