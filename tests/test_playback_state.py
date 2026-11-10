"""No-model browser-clock relay and OBS-safe subtitle cue regression tests."""
from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.playback_state import PlaybackState, PlaybackConflict
from voxweavetts.processing import InputError
from voxweavetts.server import Handler

JOB_ID = "a" * 32
SESSION_ID = "b" * 32
OTHER_SESSION = "c" * 32


def fake_job():
    return {
        "state": "ready", "speech_id": JOB_ID, "engine_id": "mock-tts",
        "display_text": "เซียนผู้นี้ *** ฮ่าฮ่า",
        "audio": {
            "duration_ms": 2100, "sample_rate": 24000,
            "segments": [
                {"kind": "speech", "display_text": "เซียนผู้นี้", "start_ms": 0, "end_ms": 900},
                {"kind": "silence", "display_text": "***", "start_ms": 900, "end_ms": 1200},
                {"kind": "speech", "display_text": "ฮ่าฮ่า 🐱", "start_ms": 1200, "end_ms": 2100},
            ],
        },
    }


def event(action, position=0, sequence=1, session_id=SESSION_ID, speech_id=JOB_ID):
    return {"event": action, "position_ms": position, "sequence": sequence,
            "session_id": session_id, "speech_id": speech_id}


class PlaybackStateTests(unittest.TestCase):
    def test_real_reported_time_drives_cue_not_generated_ready(self):
        player = PlaybackState()
        self.assertEqual(player.snapshot()["state"], "idle")
        started = player.report(event("start", 10), ready_job=fake_job())
        self.assertEqual(started["state"], "playing")
        self.assertEqual(started["subtitle"], "เซียนผู้นี้")
        self.assertEqual(started["clock_basis"], "browser_html_media_current_time_reported")
        silent = player.report(event("progress", 950, 2))
        self.assertEqual(silent["subtitle"], "")
        cue = player.report(event("progress", 1500, 3))
        self.assertEqual(cue["subtitle"], "ฮ่าฮ่า 🐱")
        paused = player.report(event("paused", 1550, 4))
        self.assertEqual(paused["state"], "paused")
        self.assertEqual(paused["subtitle"], "")
        self.assertEqual(player.report(event("seeked", 300, 5))["state"], "paused")
        resumed = player.report(event("resumed", 310, 6))
        self.assertEqual(resumed["subtitle"], "เซียนผู้นี้")
        ended = player.report(event("ended", 2100, 7))
        self.assertEqual(ended["state"], "ended")
        self.assertEqual(ended["subtitle"], "")
        with self.assertRaises(PlaybackConflict):
            player.report(event("resumed", 100, 8))

    def test_stale_player_hides_subtitle_without_interpolating(self):
        player=PlaybackState(stale_after=0.5)
        player.report(event("start", 700),ready_job=fake_job())
        with player._lock:
            player._active.updated_mono -= 5
        snapshot=player.snapshot()
        self.assertEqual(snapshot["state"], "stale")
        self.assertEqual(snapshot["subtitle"], "")
        self.assertEqual(snapshot["position_ms"], 700)
        fresh=player.report(event("progress", 850, 2))
        self.assertEqual(fresh["state"], "playing")
        self.assertEqual(fresh["subtitle"], "เซียนผู้นี้")

    def test_duplicate_out_of_order_and_superseded_sessions(self):
        p=PlaybackState()
        p.report(event("start",100,1),ready_job=fake_job())
        first=p.report(event("progress",1400,3))
        self.assertEqual(first["subtitle"], "ฮ่าฮ่า 🐱")
        self.assertEqual(p.report(event("paused",200,2))["sequence"],3)
        self.assertEqual(p.snapshot()["subtitle"],"ฮ่าฮ่า 🐱")
        with self.assertRaises(PlaybackConflict):
            p.report(event("paused",200,4,session_id=OTHER_SESSION))
        new=p.report(event("start",30,1,session_id=OTHER_SESSION),ready_job=fake_job())
        self.assertEqual(new["subtitle"],"เซียนผู้นี้")
        with self.assertRaises(PlaybackConflict):
            p.report(event("stopped",1300,5))
        self.assertEqual(p.report(event("stopped",45,2,session_id=OTHER_SESSION))["subtitle"],"")

    def test_reject_invalid_and_unready_job(self):
        p=PlaybackState()
        with self.assertRaises(InputError):
            p.report(event("start",0,1),ready_job={"speech_id":JOB_ID,"state":"queued"})
        for change in (
            {"session_id":"bad"},{"speech_id":"../../../pass"},
            {"event":"unknown"},{"position_ms":True},{"position_ms":-1},
            {"position_ms":float("nan")},{"position_ms":float("inf")},
            {"sequence":False},{"sequence":0},{"sequence":2_147_483_648},
        ):
            payload=event("start",0,1)
            payload.update(change)
            with self.subTest(change=change):
                with self.assertRaises(InputError):
                    p.report(payload,ready_job=fake_job())
        bad_job=fake_job()
        bad_job["audio"]["segments"][0]["end_ms"]=3000
        with self.assertRaises(InputError):
            p.report(event("start"),ready_job=bad_job)

    def test_silence_does_not_reveal_hidden_original(self):
        p=PlaybackState()
        job=fake_job()
        job["audio"]["segments"][1]["display_text"]="PRIVATE ORIGINAL MUST BE HIDDEN"
        p.report(event("start",1000),ready_job=job)
        self.assertNotIn("PRIVATE",json.dumps(p.snapshot()))
        self.assertEqual(p.snapshot()["subtitle"],"")


class _StaticCoordinator:
    def get(self, speech_id):
        from voxweavetts.speech_coordinator import JobMissing
        if speech_id != JOB_ID:
            raise JobMissing("unknown speech id")
        return fake_job()


class PlaybackHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.server.playback_state=PlaybackState()
        cls.server.speech_coordinator=_StaticCoordinator()
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def post(self,data,*,intent=True,mime="application/json"):
        headers={"Content-Type":mime}
        if intent:
            headers["X-VoxWeaveTTS-Intent"]="report-playback"
        request=Request(
            self.base+"/v1/playback/event",
            data=json.dumps(data).encode("utf-8"),method="POST",
            headers=headers,
        )
        return urlopen(request,timeout=5)

    def test_overlay_is_local_text_only_and_media_clock_reports(self):
        with urlopen(self.base+"/overlay",timeout=5) as response:
            body=response.read().decode("utf-8")
            self.assertEqual(response.status,200)
            self.assertIn("background:transparent",body)
            self.assertIn("overflow-wrap:normal",body)
            self.assertNotIn("overflow-wrap:anywhere",body)
            self.assertIn('subtitle.textContent=caption',body)
            self.assertIn('EventSource("/v1/playback/stream"',body)
            self.assertIn("/v1/playback/state",body)
        with urlopen(self.base+"/playback_clock.js",timeout=5) as response:
            self.assertIn(b"HTMLMediaElement.currentTime",response.read())
        with self.post(event("start",150,1,session_id="e"*32)) as response:
            self.assertEqual(json.load(response)["subtitle"],"เซียนผู้นี้")
        with urlopen(self.base+"/v1/playback/state",timeout=5) as response:
            self.assertEqual(json.load(response)["state"],"playing")
        with self.post(event("progress",1000,2,session_id="e"*32)) as response:
            self.assertEqual(json.load(response)["subtitle"],"")
        with self.post(event("ended",2100,3,session_id="e"*32)) as response:
            self.assertEqual(json.load(response)["state"],"ended")

    def test_auth_intent_and_mime_restrictions(self):
        for options,status in (({"intent":False},403),({"mime":"text/plain"},415)):
            with self.subTest(options=options):
                with self.assertRaises(HTTPError) as ex:
                    self.post(event("start"),**options)
                self.assertEqual(ex.exception.code,status)
                ex.exception.close()
        with self.assertRaises(HTTPError) as ex:
            self.post(event("start",session_id="3"*32,speech_id="0"*32))
        self.assertEqual(ex.exception.code,404)
        ex.exception.close()
        with self.assertRaises(HTTPError) as ex:
            self.post(event("start",position=True))
        self.assertEqual(ex.exception.code,400)
        ex.exception.close()


if __name__=="__main__":
    unittest.main()