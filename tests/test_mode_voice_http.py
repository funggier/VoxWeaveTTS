"""Per-workspace voice/policy settings API, loopback persistence and validation."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from voxweavetts import mode_voice_settings as voice
from voxweavetts.server import Handler


class ModeVoiceHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)

    def post(self,body,intent="save-mode-voice"):
        headers={"Content-Type":"application/json"}
        if intent:headers["X-VoxWeaveTTS-Intent"]=intent
        req=Request(self.base+"/v1/settings/mode-voices",method="POST",
                    headers=headers,data=json.dumps(body).encode("utf-8"))
        try:
            with urlopen(req,timeout=3) as response:
                return response.status,json.load(response)
        except HTTPError as error:
            with error:
                return error.code,json.load(error)

    def test_sender_name_preferences_persist_independently_and_reject_bad_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"mode-voices.json"
            with patch("voxweavetts.server.load_workspace_settings",
                       side_effect=lambda:voice.load_workspace_settings(target)),patch(
                "voxweavetts.server.save_workspace_settings",
                side_effect=lambda data:voice.save_workspace_settings(data,target)
            ):
                with urlopen(self.base+"/v1/settings/mode-voices") as response:
                    self.assertEqual(json.load(response)["sender_names"],{})
                doc=None
                for index, (mode, enabled) in enumerate((
                    ("live", True), ("discord", False),
                    ("discord_client", True), ("tiktok", True),
                )):
                    status,doc=self.post({
                        "expected_revision":index,"mode":"__sender__",
                        "settings":{"source_mode":mode,"enabled":enabled},
                    })
                    self.assertEqual(status,200)
                self.assertEqual(doc["sender_names"],{
                    "live": True, "discord": False, "discord_client": True, "tiktok": True,
                })
                with urlopen(self.base+"/v1/settings/mode-voices") as response:
                    self.assertEqual(json.load(response)["sender_names"],doc["sender_names"])
                before=voice.load_workspace_settings(target)
                for settings in ({"source_mode":"unknown","enabled":True},
                                 {"source_mode":"live","enabled":"true"},
                                 {"source_mode":"discord","enabled":1}):
                    status,_=self.post({
                        "expected_revision":4,"mode":"__sender__","settings":settings,
                    })
                    self.assertEqual(status,400)
                    self.assertEqual(voice.load_workspace_settings(target),before)
                status,_=self.post({
                    "expected_revision":3,"mode":"__sender__",
                    "settings":{"source_mode":"live","enabled":False},
                })
                self.assertEqual(status,409)

    def test_existing_voice_settings_without_sender_options_migrates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"old.json"
            path.write_text(json.dumps({"revision":5,"policy":"serial","modes":{}}),
                            encoding="utf-8")
            previous=voice.load_workspace_settings(path)
            self.assertEqual(previous["sender_names"],{})
            saved=voice.save_workspace_settings({
                "expected_revision":5,"mode":"__sender__",
                "settings":{"source_mode":"discord","enabled":True},
            },path)
            self.assertEqual(saved["revision"],6)
            self.assertEqual(voice.load_workspace_settings(path)["sender_names"],
                             {"discord":True})

    def test_http_persists_policy_and_per_mode_without_crosswriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"voices.json"
            with patch("voxweavetts.server.load_workspace_settings",
                       side_effect=lambda:voice.load_workspace_settings(target)),patch(
                "voxweavetts.server.save_workspace_settings",
                side_effect=lambda data:voice.save_workspace_settings(data,target)
            ):
                with urlopen(self.base+"/v1/settings/mode-voices") as response:
                    self.assertEqual(json.load(response)["policy"],"serial")
                payload={"expected_revision":0,"mode":"__policy__","settings":"overlap"}
                status,doc=self.post(payload)
                self.assertEqual(status,200)
                self.assertEqual(doc["policy"],"overlap")
                data={"expected_revision":1,"mode":"live",
                      "settings":{"engine_id":"makham-paradee-cpu",
                                  "voice_id":"paradee_thai","speed":1.1,
                                  "voice_controls":{"gain_db":0}}}
                status,doc=self.post(data)
                self.assertEqual(status,200)
                self.assertEqual(doc["modes"]["live"]["speed"],1.1)
                self.assertNotIn("discord",doc["modes"])
                with urlopen(self.base+"/v1/settings/mode-voices") as response:
                    restored=json.load(response)
                self.assertEqual(restored["revision"],2)
                self.assertEqual(restored["modes"]["live"]["voice_id"],"paradee_thai")
                status,_body=self.post(payload)
                self.assertEqual(status,409)
                status,_body=self.post(data,intent=None)
                self.assertEqual(status,403)
                status,_body=self.post({**data,"expected_revision":2,"mode":"evil"})
                self.assertEqual(status,400)
                self.assertEqual(voice.load_workspace_settings(target),restored)


if __name__=="__main__":
    unittest.main()
