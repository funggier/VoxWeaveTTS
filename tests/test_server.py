import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from voxweavetts.server import Handler
from voxweavetts.speech import engine_info

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
        self.assertEqual(data["capabilities"]["tts_audio"], engine_info().assets_ready and engine_info().runtime_ready)
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
        with patch("voxweavetts.server.render_wav",return_value=(sample,{"engine_id":"fastthaig2p-cpu","duration_ms":meta["duration_ms"]})):
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

    def test_ui(self):
        with urlopen(self.base,timeout=3) as r:
            content=r.read().decode("utf-8")
        self.assertIn("VoxWeaveTTS",content)