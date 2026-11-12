"""Voice Engine registry, safe DSP, portable preset and HTTP contract tests."""
import io
import json
import math
import struct
import tempfile
import unittest
import wave
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.processing import InputError, process_text
from voxweavetts import presets
from voxweavetts.speech import (
    PARADEE_ENGINE_ID, ENGINE_ID, engine_info, get_engine_info,
    list_engine_info, render_wav
)
from voxweavetts.voice_controls import (
    apply_voice_controls, control_schema, ffmpeg_path, validate_controls
)


class FakeEngine:
    id = PARADEE_ENGINE_ID
    sample_rate = 24000

    def generate(self, text, speed):
        return struct.pack("<h", 8000) * 1000


class VoiceStudioTests(unittest.TestCase):
    def test_builtin_engine_descriptors_never_claim_voice_cloning(self):
        info = list_engine_info()
        self.assertEqual([x.id for x in info][:3], [ENGINE_ID, PARADEE_ENGINE_ID, "vachana-cpu"])
        self.assertEqual(info[0].voice_id, "thai_som")
        self.assertEqual(info[1].voice_id, "paradee_thai")
        self.assertTrue(all(not item.capabilities["voice_cloning"] for item in info))
        self.assertFalse(info[1].capabilities["seed_control"])

    def test_paradee_voice_id_and_wav_metadata(self):
        plan = process_text("สวัสดี")
        with self.assertRaises(InputError):
            render_wav(plan, voice_id="thai_som", engine_id=PARADEE_ENGINE_ID,
                       engine=FakeEngine())
        wav, meta = render_wav(plan, voice_id="paradee_thai",
                               engine_id=PARADEE_ENGINE_ID, engine=FakeEngine())
        self.assertEqual(meta["engine_id"], PARADEE_ENGINE_ID)
        self.assertIsNone(meta["seed"])
        with wave.open(io.BytesIO(wav)) as reader:
            self.assertEqual(reader.getframerate(), 24000)
            self.assertEqual(reader.getnframes(), 1000)

    def test_default_dsp_is_identity(self):
        pcm = struct.pack("<h", 1234) * 300
        self.assertEqual(apply_voice_controls(pcm, 24000, {}), pcm)

    def test_gain_dsp_amplifies_and_clips_correctly(self):
        pcm = struct.pack("<hhhh", 1000, -1000, 22000, -22000)
        output = apply_voice_controls(pcm, 24000, {"gain_db": 6.0})
        samples = struct.unpack("<hhhh", output)
        self.assertTrue(1900 <= samples[0] <= 2100)
        self.assertTrue(-2100 <= samples[1] <= -1900)
        self.assertEqual(samples[2], 32767)
        self.assertEqual(samples[3], -32768)

    def test_controls_reject_unsupported_or_unsafe_values(self):
        for raw in (
            {"gain_db": float("nan")},
            {"gain_db": True},
            {"gain_db": 999},
            {"pitch_semitones": -999},
            {"bass_db": 13},
            {"treble_db": "3"},
            {"formant_preserve": "false"},
            {"arbitrary_filter": "subprocess"},
            [],
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(InputError):
                    validate_controls(raw)
        data = validate_controls({"gain_db": 4})
        self.assertEqual(data["gain_db"], 4)
        self.assertTrue(data["formant_preserve"])
        schema = control_schema()
        self.assertEqual(schema["post"]["pitch_semitones"]["max"], 4)
        self.assertFalse(schema["independent_formant_shift_supported"])

    def test_preset_json_is_stored_private_with_safe_names(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            presets, "PRESETS_FILE", Path(tmp) / "data" / "presets" / "voice-presets.json"
        ):
            saved = presets.save_preset({
                "name": "นิยายเสียงนุ่ม",
                "engine_id": PARADEE_ENGINE_ID,
                "voice_id": "paradee_thai",
                "speed": 0.9,
                "voice_controls": {"gain_db": 3.0, "bass_db": 2.0}
            })
            self.assertEqual(saved["name"], "นิยายเสียงนุ่ม")
            self.assertEqual(presets.load_presets(), [saved])
            revised = presets.save_preset({
                "name": "นิยายเสียงนุ่ม",
                "engine_id": PARADEE_ENGINE_ID,
                "voice_controls": {"gain_db": -3},
            })
            self.assertEqual(len(presets.load_presets()), 1)
            self.assertEqual(presets.load_presets()[0], revised)
            for invalid in ("../secrets", "voice/name", "", " "):
                with self.assertRaises(InputError):
                    presets.save_preset({"name": invalid, "engine_id": PARADEE_ENGINE_ID})

    def test_render_applies_dsp_to_speech_but_not_silence(self):
        plan = process_text(
            "ฮ่าคำต้องห้าม",
            rules=[{"match":"คำต้องห้าม","mode":"silence","silence_ms":400}],
        )
        with patch("voxweavetts.speech.apply_voice_controls", side_effect=lambda b, *_: b) as dsp:
            wav, meta = render_wav(
                plan, engine_id=PARADEE_ENGINE_ID, voice_id="paradee_thai",
                engine=FakeEngine(), voice_controls={"gain_db":2}
            )
        self.assertEqual(dsp.call_count, 1)
        with wave.open(io.BytesIO(wav)) as reader:
            values = reader.readframes(reader.getnframes())
            self.assertEqual(reader.getnframes(), 10600)
            self.assertEqual(values[2000:], bytes(19200))
        self.assertEqual(meta["segments"][1]["end_ms"] - meta["segments"][1]["start_ms"], 400)


class VoiceStudioServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import ThreadingHTTPServer
        from voxweavetts.server import Handler
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def test_engine_schema_and_multivoice_registry(self):
        with urlopen(self.base+"/v1/engines",timeout=3) as response:
            data=json.load(response)
        self.assertGreaterEqual(len(data["engines"]), 3)
        self.assertIn("pitch_semitones",data["control_schema"]["post"])
        with urlopen(self.base+"/v1/voices",timeout=3) as response:
            voices=json.load(response)["voices"]
        self.assertEqual([x["id"] for x in voices][:2], ["thai_som","paradee_thai"])
        self.assertTrue(all(x in [v["id"] for v in voices] for x in
                            ["th_f_1", "th_f_2", "th_m_1", "th_m_2"]))

    def test_presets_round_trip_and_header_protection(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            presets, "PRESETS_FILE", Path(tmp)/"presets.json"
        ):
            payload=json.dumps({
                "name":"โปรไฟล์ทดสอบ", "engine_id":PARADEE_ENGINE_ID,
                "speed":1.15, "voice_controls":{"pitch_semitones":1}
            },ensure_ascii=False).encode("utf-8")
            req=Request(self.base+"/v1/presets",data=payload,
                        headers={"Content-Type":"application/json",
                                 "X-VoxWeaveTTS-Intent":"save-voice-preset"},
                        method="POST")
            with urlopen(req,timeout=3) as response:
                self.assertEqual(json.load(response)["preset"]["engine_id"],PARADEE_ENGINE_ID)
            with urlopen(self.base+"/v1/presets",timeout=3) as response:
                stored=json.load(response)["presets"]
            self.assertEqual(len(stored),1)
            self.assertEqual(stored[0]["voice_controls"]["pitch_semitones"],1)
            bad=Request(self.base+"/v1/presets",data=payload,
                        headers={"Content-Type":"application/json"},method="POST")
            with self.assertRaises(HTTPError) as err:
                urlopen(bad,timeout=3)
            self.assertEqual(err.exception.code,403)
            err.exception.close()


if __name__ == "__main__":
    unittest.main()
