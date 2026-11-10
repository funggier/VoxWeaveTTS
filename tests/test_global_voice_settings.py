"""Global engine/voice/DSP defaults shared by all workspace modes."""
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

from voxweavetts.processing import InputError
from voxweavetts.speech import list_engine_info
from voxweavetts.server import Handler, _read_global_voice, _save_global_voice
from voxweavetts.text_settings import SettingsConflict


class GlobalVoiceSettingsTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/"data"/"settings"/"global-voice.json"
        self.patcher=patch("voxweavetts.server.GLOBAL_VOICE_SETTINGS",self.path)
        self.patcher.start()
        engine=list_engine_info()[0]
        self.payload={
            "expected_revision":0,
            "engine_id":engine.id,"voice_id":engine.voice_id,
            "speed":1.1,
            "voice_controls":{
                "gain_db":1,"pitch_semitones":0,
                "bass_db":0,"treble_db":0,
                "formant_preserve":True,
            },
        }
    def tearDown(self):
        self.patcher.stop()
        self.folder.cleanup()

    def test_round_trip_and_revision(self):
        self.assertEqual(_read_global_voice(),{"revision":0,"settings":None})
        saved=_save_global_voice(self.payload)
        self.assertEqual(saved["revision"],1)
        self.assertEqual(saved["settings"]["engine_id"],self.payload["engine_id"])
        self.assertEqual(saved["settings"]["speed"],1.1)
        self.assertTrue(self.path.is_file())
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")),saved)
        with self.assertRaises(SettingsConflict):
            _save_global_voice(self.payload)
        reread={**self.payload,"expected_revision":1,"speed":0.9}
        latest=_save_global_voice(reread)
        self.assertEqual(latest["revision"],2)
        self.assertEqual(latest["settings"]["speed"],0.9)

    def test_shared_defaults_also_apply_to_api_jobs_without_explicit_overrides(self):
        from types import SimpleNamespace
        from voxweavetts.server import Handler
        _save_global_voice(self.payload)
        info=list_engine_info()[0]
        backend_info=SimpleNamespace(
            id=info.id,voice_id=info.voice_id,
            assets_ready=True,runtime_ready=True,
        )
        handler=object.__new__(Handler)
        with patch("voxweavetts.server.get_engine_info",return_value=backend_info), patch(
            "voxweavetts.server._read_seed",return_value=100
        ):
            derived=handler._speech_params({},{"segments":[]})
            self.assertEqual(derived["engine_id"],self.payload["engine_id"])
            self.assertEqual(derived["speed"],1.1)
            self.assertEqual(derived["voice_controls"]["gain_db"],1)
            overridden=handler._speech_params({
                "engine_id":info.id,"voice_id":info.voice_id,
                "speed":0.8,"voice_controls":{"gain_db":-2}
            },{"segments":[]})
            self.assertEqual(overridden["speed"],0.8)
            self.assertEqual(overridden["voice_controls"]["gain_db"],-2)

    def test_invalid_controls_voice_and_seed_are_rejected(self):
        for update in (
            {"speed":0},
            {"speed":True},
            {"engine_id":"../../../foo"},
            {"voice_id":"other-voice"},
            {"voice_controls":{"gain_db":999}},
            {"voice_controls":{"evil":1}},
            {"expected_revision":True},
        ):
            with self.subTest(update=update), self.assertRaises(
                (InputError, ValueError, KeyError)
            ):
                _save_global_voice({**self.payload,**update})
        self.assertFalse(self.path.exists())


class GlobalVoiceHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory()
        cls.patcher=patch("voxweavetts.server.GLOBAL_VOICE_SETTINGS",
                          Path(cls.folder.name)/"config.json")
        cls.patcher.start()
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)
        cls.patcher.stop()
        cls.folder.cleanup()

    def post(self,body,intent="save-global-voice",ctype="application/json"):
        headers={"Content-Type":ctype}
        if intent:headers["X-VoxWeaveTTS-Intent"]=intent
        req=Request(self.base+"/v1/settings/global-voice",data=json.dumps(body).encode(),
                    headers=headers,method="POST")
        with urlopen(req,timeout=5) as response:
            return json.load(response)

    def test_public_get_and_write_intent(self):
        engine=list_engine_info()[0]
        with urlopen(self.base+"/v1/settings/global-voice",timeout=5) as response:
            self.assertEqual(json.load(response)["revision"],0)
        body={
            "engine_id":engine.id,"voice_id":engine.voice_id,"speed":1,
            "voice_controls":{},"expected_revision":0,
        }
        saved=self.post(body)
        self.assertEqual(saved["revision"],1)
        with urlopen(self.base+"/v1/settings/global-voice",timeout=5) as response:
            self.assertEqual(json.load(response)["settings"]["engine_id"],engine.id)
        for kwargs,status in (({"intent":None},403),({"ctype":"text/plain"},415)):
            with self.subTest(status=status), self.assertRaises(HTTPError) as error:
                self.post(body,**kwargs)
            self.assertEqual(error.exception.code,status)
            error.exception.close()
        with self.assertRaises(HTTPError) as err:
            self.post(body)
        self.assertEqual(err.exception.code,409)
        err.exception.close()


if __name__=="__main__":
    unittest.main()