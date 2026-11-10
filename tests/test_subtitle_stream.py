"""Model-free estimated-caption and bounded local SSE subtitle transport tests."""
from __future__ import annotations

import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.playback_state import PlaybackState, StreamFull
from voxweavetts.processing import InputError
from voxweavetts.server import Handler
from voxweavetts.subtitle_cues import _clusters, estimated_cues, caption_for


def ready_job(job_id: str) -> dict:
    return {
        "speech_id": job_id, "state": "ready", "engine_id": "fake-cpu",
        "audio": {
            "duration_ms": 9000,
            "segments": [
                {"kind": "speech", "display_text":
                 "เซียนผู้นี้มองเห็นดวงดาวในท้องฟ้าและเดินทางเข้าป่าใหญ่อันงดงาม 👩🏽‍💻 🇹🇭",
                 "start_ms": 0, "end_ms": 8500},
                {"kind": "silence", "display_text": "private should not leak",
                 "start_ms": 8500, "end_ms": 9000},
            ],
        },
    }


def message(event: str, session_id: str, job_id: str,
            sequence: int, pos: int) -> dict:
    return {
        "session_id": session_id, "speech_id": job_id,
        "sequence": sequence, "position_ms": pos, "event": event,
    }


class ApproximateCaptionTests(unittest.TestCase):
    def test_windows_are_disjoint_cover_segment_and_keep_unicode(self):
        source = ready_job("a"*32)["audio"]["segments"]
        cues=estimated_cues(source)
        self.assertGreater(len(cues),2)
        self.assertEqual(cues[0]["start_ms"],0)
        self.assertEqual(cues[-1]["end_ms"],9000)
        self.assertEqual(cues[-1]["display_text"],"")
        self.assertEqual("".join(c["display_text"] for c in cues if c["kind"]=="speech"),
                         source[0]["display_text"])
        self.assertTrue(all(left["end_ms"]==right["start_ms"]
                            for left,right in zip(cues,cues[1:])))
        for cue in cues:
            self.assertFalse(cue["display_text"].startswith(("🏽","‍","💻","🇭","่")))
        self.assertEqual(caption_for(source,8750,mode="estimated"),"")
        self.assertEqual(caption_for(source,100,mode="segment"),
                         source[0]["display_text"])
        self.assertNotEqual(caption_for(source,100,mode="estimated"),
                            source[0]["display_text"])

    def test_not_word_alignment_and_short_segments_unchanged(self):
        text="สวัสดีครับ"*8
        parts=[{"kind":"speech","start_ms":0,"end_ms":500,
                "display_text":text}]
        self.assertEqual(estimated_cues(parts),parts)
        self.assertEqual(caption_for(parts,600,mode="estimated"),"")
        self.assertEqual(caption_for(parts,0,mode="unknown"),"")
        self.assertEqual(_clusters("🇹🇭"),["🇹🇭"])
        self.assertEqual(_clusters("👩🏽‍💻"),["👩🏽‍💻"])

    def test_playback_snapshot_marks_estimate_not_aligned(self):
        state=PlaybackState()
        state.report(message("start","b"*32,"a"*32,1,100),ready_job=ready_job("a"*32))
        default=state.snapshot()
        approx=state.snapshot(mode="estimated")
        self.assertEqual(default["subtitle_precision"],"generated_segment")
        self.assertEqual(approx["subtitle_precision"],"estimated_grapheme_windows")
        self.assertEqual(default["revision"],approx["revision"])
        self.assertNotEqual(default["subtitle"],approx["subtitle"])
        with self.assertRaises(InputError):
            state.snapshot(mode="injected")
        state.report(message("progress","b"*32,"a"*32,2,8750))
        self.assertEqual(state.snapshot(mode="estimated")["subtitle"],"")

    def test_watchers_and_capacity(self):
        state=PlaybackState(stale_after=0.5)
        for _ in range(8):
            state.subscribe()
        with self.assertRaises(StreamFull):
            state.subscribe()
        for _ in range(8):
            state.unsubscribe()
        revision=state.snapshot()["revision"]
        self.assertIsNone(state.watch(revision,timeout=0.02))
        state.report(message("start","b"*32,"a"*32,1,10),ready_job=ready_job("a"*32))
        newer=state.watch(revision,timeout=0.02)
        self.assertEqual(newer["state"],"playing")
        with state._lock:
            state._active.updated_mono -= 5
        stale=state.watch(newer["revision"],timeout=0.02)
        self.assertEqual(stale["state"],"stale")
        self.assertEqual(stale["subtitle"],"")


class FakeCoordinator:
    def get(self, speech_id):
        from voxweavetts.speech_coordinator import JobMissing
        if speech_id != "a"*32:
            raise JobMissing("unknown speech id")
        return ready_job(speech_id)


class StreamHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.server.playback_state=PlaybackState()
        cls.server.speech_coordinator=FakeCoordinator()
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)

    def report(self, kind, seq, position=10):
        body=message(kind,"e"*32,"a"*32,seq,position)
        req=Request(self.base+"/v1/playback/event",
                    headers={"Content-Type":"application/json",
                             "X-VoxWeaveTTS-Intent":"report-playback"},
                    data=json.dumps(body).encode("utf-8"),method="POST")
        with urlopen(req,timeout=5) as response:
            return json.load(response)

    @staticmethod
    def next_event(response):
        result={}
        for _ in range(8):
            line=response.readline().decode("utf-8").strip()
            if not line:
                if "data" in result:
                    return result
                continue
            if line.startswith("id:"):
                result["id"]=line.split(":",1)[1].strip()
            if line.startswith("event:"):
                result["event"]=line.split(":",1)[1].strip()
            if line.startswith("data:"):
                result["data"]=json.loads(line[5:].strip())
        raise AssertionError("no SSE snapshot event")

    def test_stream_pushes_on_report_and_preserves_estimated_mode(self):
        with urlopen(self.base+"/v1/playback/stream?mode=estimated",timeout=5) as stream:
            self.assertIn("text/event-stream",stream.headers.get("Content-Type",""))
            first=self.next_event(stream)
            self.assertEqual(first["event"],"playback")
            self.assertEqual(first["data"]["subtitle_mode"],"estimated")
            started=self.report("start",1)
            pushed=self.next_event(stream)
            self.assertEqual(pushed["data"]["state"],"playing")
            self.assertEqual(pushed["data"]["revision"],started["revision"])
            self.assertEqual(pushed["data"]["subtitle_precision"],"estimated_grapheme_windows")
            paused=self.report("paused",2)
            hidden=self.next_event(stream)
            self.assertEqual(hidden["data"]["state"],"paused")
            self.assertEqual(hidden["data"]["subtitle"],"")
            self.assertGreater(int(hidden["id"]),int(first["id"]))
            self.assertEqual(paused["state"],"paused")

    def test_state_mode_and_invalid_modes(self):
        with urlopen(self.base+"/v1/playback/state?mode=estimated",timeout=5) as response:
            body=json.load(response)
        self.assertEqual(body["subtitle_mode"],"estimated")
        for route in ("/v1/playback/state?mode=html",
                      "/v1/playback/stream?mode=unsafe"):
            with self.subTest(route=route):
                with self.assertRaises(HTTPError) as result:
                    urlopen(self.base+route,timeout=5)
                self.assertEqual(result.exception.code,400)
                result.exception.close()

    def test_stream_is_bounded(self):
        state=self.server.playback_state
        for _ in range(8):
            state.subscribe()
        try:
            with self.assertRaises(HTTPError) as result:
                urlopen(self.base+"/v1/playback/stream",timeout=4)
            self.assertEqual(result.exception.code,429)
            result.exception.close()
        finally:
            for _ in range(8):
                state.unsubscribe()


if __name__=="__main__":
    unittest.main()
