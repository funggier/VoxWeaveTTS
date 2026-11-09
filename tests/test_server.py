import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from voxweavetts.server import Handler

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
        self.assertFalse(data["capabilities"]["tts_audio"])
        self.assertTrue(data["capabilities"]["text_filter"])

    def test_process(self):
        payload=json.dumps({"text":"อมตะต้องห้าม","pronunciations":{"อมตะ":"อะ มะ ตะ"},"rules":[{"match":"ต้องห้าม","mode":"silence","display":"*"}]},ensure_ascii=False).encode("utf-8")
        req=Request(self.base+"/v1/text/process",data=payload,headers={"Content-Type":"application/json"},method="POST")
        with urlopen(req,timeout=3) as r:
            data=json.load(r)
        self.assertEqual(data["display_text"],"อมตะ*")
        self.assertEqual(data["spoken_text"],"อะ มะ ตะ")

    def test_ui(self):
        with urlopen(self.base,timeout=3) as r:
            content=r.read().decode("utf-8")
        self.assertIn("VoxWeaveTTS",content)
