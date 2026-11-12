import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from voxweavetts.server import Handler
from voxweavetts.speech import engine_info, list_engine_info

class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base="http://127.0.0.1:"+str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def test_status(self):
        with urlopen(self.base+"/v1/status",timeout=3) as r:
            data=json.load(r)
        self.assertEqual(data["app"],"VoxWeaveTTS")
        self.assertEqual(data["capabilities"]["tts_audio"], any(e.assets_ready and e.runtime_ready for e in list_engine_info()))
        self.assertTrue(data["capabilities"]["engine_registry"])
        self.assertTrue(data["capabilities"]["audio_preparation_queue"])
        self.assertFalse(data["capabilities"]["audio_playback_clock"])
        self.assertEqual(data["adapter_api_version"], 1)
        self.assertTrue(data["capabilities"]["text_filter"])

    def test_process(self):
        payload=json.dumps({"text":"อมตะต้องห้าม","pronunciations":{"อมตะ":"อะ มะ ตะ"},"rules":[{"match":"ต้องห้าม","mode":"silence","display":"*"}]},ensure_ascii=False).encode("utf-8")
        req=Request(self.base+"/v1/text/process",data=payload,headers={"Content-Type":"application/json"},method="POST")
        with urlopen(req,timeout=3) as r:
            data=json.load(r)
        self.assertEqual(data["display_text"],"อมตะ*")
        self.assertEqual(data["spoken_text"],"อะ มะ ตะ")


    def test_engine_listing(self):
        with urlopen(self.base+"/v1/engines",timeout=3) as r:
            info=json.load(r)
        self.assertEqual(info["engines"][0]["id"], "fastthaig2p-cpu")
        self.assertEqual(info["engines"][0]["language"], "th")
        self.assertFalse(info["engines"][0]["capabilities"]["voice_cloning"])
        self.assertEqual(info["engines"][0]["commercial_status"], "review_required")
        self.assertEqual(info["engines"][0]["adapter_api_version"], 1)
        with urlopen(self.base+"/v1/voices",timeout=3) as r:
            voices=json.load(r)
        self.assertEqual(voices["voices"][0]["id"], "thai_som")

    def test_speech_api_with_fake_synthesizer(self):
        from unittest.mock import patch
        from voxweavetts.processing import process_text
        from voxweavetts.speech import render_wav
        from test_speech import ConstantEngine
        plan=process_text("ทดสอบ")
        sample,meta=render_wav(plan,engine=ConstantEngine())
        payload=json.dumps({"text":"ทดสอบ"}).encode("utf-8")
        req=Request(self.base+"/v1/speech",data=payload,headers={"Content-Type":"application/json"},method="POST")
        from dataclasses import replace
        from voxweavetts.speech import get_engine_info
        ready = replace(get_engine_info("fastthaig2p-cpu"), assets_ready=True, runtime_ready=True)
        with patch("voxweavetts.server.get_engine_info", return_value=ready), patch("voxweavetts.server.render_wav",return_value=(sample,{"engine_id":"fastthaig2p-cpu","duration_ms":meta["duration_ms"],"seed":100})):
            with urlopen(req,timeout=3) as response:
                self.assertEqual(response.status,200)
                self.assertEqual(response.headers["Content-Type"],"audio/wav")
                self.assertEqual(response.read(),sample)

    def test_unknown_voice_rejected_without_model(self):
        from urllib.error import HTTPError
        payload=json.dumps({"text":"hello","voice_id":"not-a-voice"}).encode("utf-8")
        req=Request(self.base+"/v1/speech",data=payload,headers={"Content-Type":"application/json"},method="POST")
        with self.assertRaises(HTTPError) as err:
            urlopen(req,timeout=3)
        self.assertEqual(err.exception.code,400)
        err.exception.close()

    def test_seed_settings_are_saved_in_portable_data_and_used_by_speech(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from voxweavetts import server
        from voxweavetts.processing import process_text
        from voxweavetts.speech import render_wav
        from test_speech import ConstantEngine
        from urllib.error import HTTPError

        with TemporaryDirectory() as path, patch.object(
            server, "SYNTHESIS_SETTINGS", Path(path) / "data" / "settings" / "synthesis.json"
        ):
            with urlopen(self.base + "/v1/settings/synthesis", timeout=3) as response:
                self.assertEqual(json.load(response), {"seed": 100})

            payload = json.dumps({"seed": 123}).encode("utf-8")
            request = Request(
                self.base + "/v1/settings/synthesis", data=payload,
                headers={"Content-Type":"application/json",
                         "X-VoxWeaveTTS-Intent":"save-synthesis-settings"},
                method="POST"
            )
            with urlopen(request, timeout=3) as response:
                self.assertEqual(json.load(response)["seed"], 123)
            with urlopen(self.base + "/v1/settings/synthesis", timeout=3) as response:
                self.assertEqual(json.load(response)["seed"], 123)

            wav, details = render_wav(process_text("ทดสอบ"), engine=ConstantEngine(), seed=123)
            seen = {}
            def mock_audio(*args, **kwargs):
                seen["seed"] = kwargs.get("seed")
                return wav, {"engine_id": "fastthaig2p-cpu",
                             "duration_ms": details["duration_ms"], "seed":kwargs["seed"]}
            speech_request = Request(
                self.base + "/v1/speech",
                data=json.dumps({"text":"ทดสอบ"}).encode("utf-8"),
                headers={"Content-Type":"application/json"}, method="POST",
            )
            from dataclasses import replace
            from voxweavetts.speech import get_engine_info
            ready = replace(get_engine_info("fastthaig2p-cpu"), assets_ready=True, runtime_ready=True)
            with patch("voxweavetts.server.get_engine_info", return_value=ready), patch("voxweavetts.server.render_wav", side_effect=mock_audio):
                with urlopen(speech_request, timeout=3) as response:
                    self.assertEqual(response.headers["X-VoxWeaveTTS-Seed"], "123")
            self.assertEqual(seen["seed"], 123)
            self.assertTrue((Path(path) / "data/settings/synthesis.json").exists())

            missing_intent = Request(
                self.base + "/v1/settings/synthesis", data=payload,
                headers={"Content-Type":"application/json"}, method="POST"
            )
            with self.assertRaises(HTTPError) as error:
                urlopen(missing_intent, timeout=3)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()

            for seed in [-1, 2147483648, "3", True, 3.5]:
                bad = Request(
                    self.base + "/v1/settings/synthesis",
                    data=json.dumps({"seed":seed}).encode("utf-8"),
                    headers={"Content-Type":"application/json",
                             "X-VoxWeaveTTS-Intent":"save-synthesis-settings"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as err:
                    urlopen(bad, timeout=3)
                self.assertEqual(err.exception.code, 400)
                err.exception.close()

    def test_every_browser_script_tag_is_served(self):
        """Catch missing static routes before users find the page unresponsive."""
        import re
        from urllib.error import HTTPError

        with urlopen(self.base + "/", timeout=3) as response:
            html = response.read().decode("utf-8")
        paths = re.findall(r'<script\s+src="([^"]+)"', html)
        self.assertGreaterEqual(len(paths), 8)
        self.assertIn("/audio_scheduler.js", paths)
        self.assertIn("/mode_voice_settings.js", paths)
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.startswith("/"))
                with urlopen(self.base + path, timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn("javascript", response.headers.get("Content-Type", ""))
                    body = response.read()
                    self.assertGreater(len(body), 100)
                    self.assertNotIn(b"<!doctype html>", body.lower())
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base + "/not-in-static-allowlist.js", timeout=3)
        self.assertEqual(error.exception.code, 404)
        error.exception.close()

    def test_ui(self):
        with urlopen(self.base,timeout=3) as r:
            content=r.read().decode("utf-8")
        self.assertIn("VoxWeaveTTS",content)
        # The retired laughter-spelling selector was deliberately removed.
        self.assertNotIn('id="laughSpoken"', content)
        self.assertNotIn('id="testLaughSpoken"', content)
        self.assertNotIn('ทดลองคำอ่านเสียงหัวเราะจาก 55555', content)
        # Generic pronunciation rules and two-Engine Voice Studio remain.
        self.assertIn('id="rule"', content)
        self.assertIn('id="engineSelect"', content)
        self.assertIn('id="slider-pitch_semitones"', content)
        self.assertIn('id="queueSubmit"', content)
        self.assertIn('id="queueRefresh"', content)
        self.assertIn('id="queueCancel"', content)