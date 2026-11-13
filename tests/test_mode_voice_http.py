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

    def test_sender_speech_format_is_mode_local_and_migrates_old_files(self):
        from voxweavetts.mode_voice_settings import DEFAULT_SPEECH_FORMAT
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"formats.json"
            old={"revision":2,"policy":"serial","modes":{},
                 "sender_names":{"live":True}}
            target.write_text(json.dumps(old),encoding="utf-8")
            with patch("voxweavetts.server.load_workspace_settings",
                       side_effect=lambda:voice.load_workspace_settings(target)),patch(
                "voxweavetts.server.save_workspace_settings",
                side_effect=lambda data:voice.save_workspace_settings(data,target)
            ):
                with urlopen(self.base+"/v1/settings/mode-voices") as response:
                    doc=json.load(response)
                self.assertEqual(doc["speech_formats"],{})
                youtube={**DEFAULT_SPEECH_FORMAT,"sender_prefix":"ท่าน","separator":"กล่าวว่า",
                         "read_name_at":True}
                tiktok={**DEFAULT_SPEECH_FORMAT,"separator":"",
                        "read_gifts":True,"read_levels":True,"read_ranks":True}
                for revision,mode,fmt in ((2,"live",youtube),
                                          (3,"tiktok_browser",tiktok)):
                    status,doc=self.post({
                        "expected_revision":revision,"mode":"__speech_format__",
                        "settings":{"source_mode":mode,"format":fmt},
                    })
                    self.assertEqual(status,200)
                self.assertEqual(doc["speech_formats"]["live"]["separator"],"กล่าวว่า")
                self.assertEqual(doc["speech_formats"]["live"]["sender_prefix"],"ท่าน")
                self.assertTrue(doc["speech_formats"]["live"]["read_name_at"])
                self.assertFalse(doc["speech_formats"]["tiktok_browser"]["read_gifts"])
                self.assertEqual(doc["sender_names"],{"live":True})
                before=voice.load_workspace_settings(target)
                for invalid in (
                    {**tiktok,"read_gifts":"true"},
                    {**tiktok,"read_name_at":"false"},
                    {**tiktok,"separator":"a"*61},
                    {**tiktok,"sender_prefix":"คุณ"*61},
                    {**tiktok,"sender_prefix":"\n"},
                    {**tiktok,"separator":"\n"},
                    {**tiktok,"unknown":True},
                ):
                    status,_=self.post({
                        "expected_revision":4,"mode":"__speech_format__",
                        "settings":{"source_mode":"tiktok_browser","format":invalid},
                    })
                    self.assertEqual(status,400)
                    self.assertEqual(voice.load_workspace_settings(target),before)
                status,_=self.post({
                    "expected_revision":4,"mode":"__speech_format__",
                    "settings":{"source_mode":"unregistered","format":tiktok},
                })
                self.assertEqual(status,400)
                self.assertEqual(voice.load_workspace_settings(target),before)

    def test_older_speech_format_without_new_switch_migrates(self):
        from voxweavetts.mode_voice_settings import DEFAULT_SPEECH_FORMAT
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"old-rich-format.json"
            old={"revision":7,"policy":"serial","modes":{},
                 "speech_formats":{"tiktok_browser":{
                     "separator":"กล่าวว่า",
                     "read_gifts":True,
                     "read_badges":True,
                 }}}
            path.write_text(json.dumps(old),encoding="utf-8")
            settings=voice.load_workspace_settings(path)
            source=settings["speech_formats"]["tiktok_browser"]
            self.assertEqual(source["separator"],"กล่าวว่า")
            self.assertEqual(source["sender_prefix"],"คุณ")
            self.assertFalse(source["read_name_at"])
            self.assertFalse(source["read_gifts"])
            self.assertTrue(source["read_badges"])
            self.assertFalse(source["read_name_emojis"])
            self.assertEqual(set(source),set(DEFAULT_SPEECH_FORMAT))
            saved=voice.save_workspace_settings({
                "expected_revision":7,"mode":"__sender__",
                "settings":{"source_mode":"live","enabled":True},
            },path)
            self.assertEqual(saved["revision"],8)
            self.assertEqual(saved["speech_formats"]["tiktok_browser"],source)

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
