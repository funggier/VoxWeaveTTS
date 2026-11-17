"""Loopback HTTP persistence for per-mode queue policies; no source credentials."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.server import Handler
from voxweavetts.source_queue_settings import DEFAULTS, load_settings, save_settings


class SourceQueueSettingsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.url=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def post(self,payload,*,origin="same",intent="save-source-queue"):
        headers={"Content-Type":"application/json",
                 "Sec-Fetch-Site":"same-origin"}
        if origin=="same":
            headers["Origin"]=self.url
        elif origin:
            headers["Origin"]=origin
        if intent:
            headers["X-VoxWeaveTTS-Intent"]=intent
        req=Request(self.url+"/v1/settings/source-queues",
                    data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
                    headers=headers,method="POST")
        try:
            with urlopen(req,timeout=5) as response:
                return response.status,json.load(response)
        except HTTPError as exc:
            with exc:
                return exc.code,json.load(exc)

    def test_save_eight_thousand_and_read_other_modes_without_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"data"/"source-queues.json"
            with (patch("voxweavetts.server.load_source_queues",
                        side_effect=lambda:load_settings(path=path)),
                  patch("voxweavetts.server.save_source_queues",
                        side_effect=lambda value:save_settings(value,path=path))):
                with urlopen(self.url+"/v1/settings/source-queues",timeout=5) as response:
                    self.assertEqual(json.load(response)["modes"]["live"]["revision"],0)
                settings={**DEFAULTS,
                          "max_chars":8000,
                          "read_history_limit":2,
                          "random_queue_enabled":True,
                          "random_queue_threshold":30,
                          "random_queue_keep":5,
                          "blocked_words":"ทดสอบ"*350}
                payload={"mode":"live","expected_revision":0,"settings":settings}
                status,data=self.post(payload)
                self.assertEqual(status,200)
                self.assertEqual(data["modes"]["live"]["revision"],1)
                self.assertEqual(data["modes"]["live"]["settings"]["max_chars"],8000)
                self.assertEqual(data["modes"]["discord"]["revision"],0)
                self.assertEqual(load_settings(path=path)["modes"]["live"]["settings"],
                                 settings)
                self.assertNotIn("credential",path.read_text(encoding="utf-8"))
                status,_=self.post(payload)
                self.assertEqual(status,409)
                status,_=self.post({**payload,"settings":{**settings,"max_chars":8001},
                                    "expected_revision":1})
                self.assertEqual(status,400)
                self.assertEqual(load_settings(path=path)["modes"]["live"]["revision"],1)

    def test_same_origin_intent_and_exact_shape_protected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"settings.json"
            with patch("voxweavetts.server.save_source_queues",
                       side_effect=lambda value:save_settings(value,path=path)):
                payload={"mode":"live","expected_revision":0,
                         "settings":dict(DEFAULTS)}
                for kwargs in ({"origin":None},
                               {"origin":"https://external.example"},
                               {"intent":None}):
                    with self.subTest(kwargs=kwargs):
                        status,_=self.post(payload,**kwargs)
                        self.assertEqual(status,403)
                self.assertFalse(path.exists())
                status,_=self.post({**payload,"credential":"secret"})
                self.assertEqual(status,400)
                self.assertFalse(path.exists())


if __name__=="__main__":
    unittest.main()
