"""Exclusive mode ownership with immediate OBS caption reset and stale-token rejection."""
from __future__ import annotations

import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from voxweavetts.mode_state import ModeState, ModeConflict, MODES
from voxweavetts.playback_state import PlaybackState
from voxweavetts.processing import InputError
from voxweavetts.server import Handler

SPEECH_ID="a"*32
SESSION="b"*32


def job():
    return {
        "speech_id": SPEECH_ID,
        "state":"ready",
        "engine_id":"fake-cpu",
        "audio":{"duration_ms":1000,"segments":[{
            "kind":"speech","start_ms":0,"end_ms":1000,
            "display_text":"สวัสดีครับ",
        }]}
    }


class FakeCoordinator:
    def get(self, speech_id):
        from voxweavetts.speech_coordinator import JobMissing
        if speech_id!=SPEECH_ID:raise JobMissing("unknown speech_id")
        return job()


class WorkspaceModeTests(unittest.TestCase):
    def test_atomic_switch_stops_current_session_and_stale_reports(self):
        modes=ModeState()
        playback=PlaybackState()
        first=modes.activate("reader",playback)
        self.assertEqual(first["active_mode"],"reader")
        self.assertEqual(first["revision"],1)
        self.assertEqual(len(first["mode_token"]),32)
        payload={
            "event":"start","sequence":1,"position_ms":110,
            "session_id":SESSION,"speech_id":SPEECH_ID,
            "mode":"reader","mode_token":first["mode_token"],
        }
        active=modes.report(payload,job(),playback)
        self.assertEqual(active["subtitle"],"สวัสดีครับ")
        next_mode=modes.activate("discord",playback)
        self.assertEqual(next_mode["active_mode"],"discord")
        self.assertNotEqual(first["mode_token"],next_mode["mode_token"])
        self.assertEqual(playback.snapshot()["state"],"idle")
        self.assertEqual(playback.snapshot()["subtitle"],"")
        with self.assertRaises(ModeConflict):
            modes.report({**payload,"sequence":2,"event":"progress"},None,playback)
        with self.assertRaises(ModeConflict):
            modes.report({**payload,"mode":"discord","sequence":2},None,playback)
        self.assertEqual(playback.snapshot()["state"],"idle")
        latest={
            **payload,"mode":"discord","mode_token":next_mode["mode_token"],
            "session_id":"c"*32,"sequence":1,
        }
        self.assertEqual(modes.report(latest,job(),playback)["state"],"playing")
        with self.assertRaises(InputError):
            modes.activate("unknown",playback)
        self.assertEqual(modes.snapshot()["active_mode"],"discord")
        self.assertEqual(len(MODES),7)

    def test_mode_change_notifies_sse_revision(self):
        playback=PlaybackState()
        modes=ModeState()
        modes.activate("studio",playback)
        before=playback.snapshot()["revision"]
        change=modes.activate("reader",playback)
        self.assertGreater(playback.watch(before,timeout=0.02)["revision"],before)
        self.assertNotIn("mode_token",modes.snapshot())


class WorkspaceModeHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.server.speech_coordinator=FakeCoordinator()
        cls.server.playback_state=PlaybackState()
        cls.server.mode_state=ModeState()
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def post(self,path,body,intent=None,content_type="application/json"):
        headers={"Content-Type":content_type}
        if intent:headers["X-VoxWeaveTTS-Intent"]=intent
        req=Request(self.base+path,method="POST",headers=headers,
                    data=json.dumps(body).encode("utf-8"))
        with urlopen(req,timeout=5) as response:
            return json.load(response)

    def test_http_exclusive_playback_with_cross_mode_events(self):
        initial=self.post("/v1/modes/activate",{"mode":"reader"},"activate-mode")
        self.assertEqual(initial["revision"],1)
        with urlopen(self.base+"/v1/modes/state",timeout=5) as response:
            mode_info=json.load(response)
        self.assertEqual(mode_info["active_mode"],"reader")
        self.assertNotIn("mode_token",mode_info)
        payload={"session_id":"f"*32,"speech_id":SPEECH_ID,"sequence":1,
                 "event":"start","position_ms":5,"mode":"reader",
                 "mode_token":initial["mode_token"]}
        start=self.post("/v1/playback/event",payload,"report-playback")
        self.assertEqual(start["subtitle"],"สวัสดีครับ")
        moved=self.post("/v1/modes/activate",{"mode":"live"},"activate-mode")
        self.assertEqual(moved["active_mode"],"live")
        with urlopen(self.base+"/v1/playback/state",timeout=5) as response:
            self.assertEqual(json.load(response)["subtitle"],"")
        for data in (
            {**payload,"sequence":2,"event":"progress"},
            {**payload,"mode":"live","sequence":2},
            {**payload,"mode_token":moved["mode_token"],"sequence":2},
        ):
            with self.subTest(data=data), self.assertRaises(HTTPError) as err:
                self.post("/v1/playback/event",data,"report-playback")
            self.assertEqual(err.exception.code,409)
            err.exception.close()
        new={**payload,"session_id":"c"*32,"mode":"live",
             "mode_token":moved["mode_token"]}
        self.assertEqual(self.post("/v1/playback/event",new,"report-playback")["state"],"playing")

    def test_sse_notifies_other_browser_tabs_on_mode_activation(self):
        def next_event(stream):
            event={}
            for _ in range(12):
                line=stream.readline().decode("utf-8")
                if line.startswith("event:"):
                    event["event"]=line[6:].strip()
                elif line.startswith("data:"):
                    event["data"]=json.loads(line[5:].strip())
                elif line == "\n" and "data" in event:
                    return event
            raise AssertionError("mode stream did not produce event")

        with urlopen(self.base+"/v1/modes/stream",timeout=5) as stream:
            self.assertIn("text/event-stream",stream.headers["Content-Type"])
            initial=next_event(stream)
            self.assertEqual(initial["event"],"workspace")
            self.assertNotIn("mode_token",initial["data"])
            switched=self.post("/v1/modes/activate",{"mode":"settings"},"activate-mode")
            event=next_event(stream)
            self.assertEqual(event["data"]["active_mode"],"settings")
            self.assertEqual(event["data"]["revision"],switched["revision"])

    def test_reject_invalid_modes_mime_and_intent(self):
        with self.assertRaises(HTTPError) as e:
            self.post("/v1/modes/activate",{"mode":"studio"})
        self.assertEqual(e.exception.code,403)
        e.exception.close()
        with self.assertRaises(HTTPError) as e:
            self.post("/v1/modes/activate",{"mode":"studio"},"activate-mode","text/plain")
        self.assertEqual(e.exception.code,415)
        e.exception.close()
        with self.assertRaises(HTTPError) as e:
            self.post("/v1/modes/activate",{"mode":"hacker"},"activate-mode")
        self.assertEqual(e.exception.code,400)
        e.exception.close()
        with urlopen(self.base+"/mode_workspace.js",timeout=5) as response:
            self.assertIn("javascript",response.headers["Content-Type"])
            self.assertIn(b"VoxWorkspaceModes",response.read())


if __name__=="__main__":
    unittest.main()