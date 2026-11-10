"""Manual, user-verified subtitle timecodes (not automatic forced alignment)."""
from __future__ import annotations

import io
import json
import threading
import time
import unittest
import wave
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.manual_alignment import validate_manual_cues, timing_metrics
from voxweavetts.playback_state import PlaybackState
from voxweavetts.processing import InputError, process_text
from voxweavetts.server import Handler
from voxweavetts.speech_coordinator import (
    SpeechCoordinator, AlignmentConflict, JobNotReady,
)

A = "นิรันดร์ 🧑🏽‍💻 ฮ่า"
B = "คำต้องห้าม"


def audio():
    data=io.BytesIO()
    with wave.open(data,"wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x30\x10"*24000)
    return data.getvalue()


def render(_plan, **_kwargs):
    return audio(), {
        "sample_rate":24000, "duration_ms":1000,
        "segments":[
            {"kind":"speech","display_text":A,"start_ms":0,"end_ms":900},
            {"kind":"silence","display_text":"***","start_ms":900,"end_ms":1000},
        ],
    }


def make_cues():
    return [
        {"segment_index":0,"start_offset":0,"end_offset":8,
         "start_ms":20,"end_ms":490},
        {"segment_index":0,"start_offset":9,"end_offset":14,
         "start_ms":500,"end_ms":850},
    ]


class AlignmentTests(unittest.TestCase):
    def test_user_display_text_is_only_authority(self):
        segments=render(None)[1]["segments"]
        cues=[{"segment_index":0,"start_offset":0,"end_offset":8,
               "start_ms":20,"end_ms":490}]
        good=validate_manual_cues(segments,cues)
        self.assertEqual(good[0]["display_text"],A[:8])
        bad=[{**good[0],"display_text":"PRIVATE ORIGINAL"}]
        with self.assertRaises(InputError):
            validate_manual_cues(segments,bad)
        self.assertEqual(validate_manual_cues(segments,good),good)

    def test_unicode_boundary_and_mask_rejection(self):
        seg=render(None)[1]["segments"]
        emoji_start=A.index("🧑")
        for position in (emoji_start+1, emoji_start+2, emoji_start+3):
            bad={"segment_index":0,"start_offset":0,"end_offset":position,
                 "start_ms":10,"end_ms":900}
            with self.subTest(position=position):
                with self.assertRaises(InputError):
                    validate_manual_cues(seg,[bad])
        with self.assertRaises(InputError):
            validate_manual_cues(seg,[{"segment_index":1,"start_offset":0,
                                      "end_offset":1,"start_ms":900,"end_ms":960}])

    def test_invalid_timecodes_are_rejected(self):
        seg=render(None)[1]["segments"]
        base={"segment_index":0,"start_offset":0,"end_offset":3,
              "start_ms":10,"end_ms":300}
        cases=[
            {**base,"start_ms":300,"end_ms":300},
            {**base,"start_ms":900,"end_ms":1000},
            {**base,"start_ms":True},
            {**base,"start_offset":-1},
            {**base,"end_offset":len(A)+1},
            {**base,"secret":"unsafe"},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(InputError):
                validate_manual_cues(seg,[case])
        with self.assertRaises(InputError):
            validate_manual_cues(seg,[base,{**base,"start_ms":200,"end_ms":400}])
        with self.assertRaises(InputError):
            validate_manual_cues(seg,[base,{**base,"start_ms":400,"end_ms":700}])

    def test_timing_metrics_compare_exact_text_spans(self):
        ref=[{"segment_index":0,"start_offset":0,"end_offset":3,
              "start_ms":100,"end_ms":350},
             {"segment_index":0,"start_offset":3,"end_offset":6,
              "start_ms":400,"end_ms":660}]
        predicted=[{**ref[0],"start_ms":145,"end_ms":410},
                   {**ref[1],"start_ms":390,"end_ms":700}]
        score=timing_metrics(predicted,ref)
        self.assertEqual(score["matched_cues"],2)
        self.assertEqual(score["mean_absolute_boundary_error_ms"],38.75)
        self.assertEqual(score["max_absolute_boundary_error_ms"],60)
        self.assertEqual(score["boundaries_within_100ms_percent"],100.0)
        missing=timing_metrics([predicted[0]],ref)
        self.assertEqual(missing["reference_coverage_percent"],50.0)
        self.assertIsNone(timing_metrics([],ref)["mean_absolute_boundary_error_ms"])
        self.assertIsNone(timing_metrics([],[])["reference_coverage_percent"])

    def test_coordinator_job_cues_survive_snapshot_and_manual_player(self):
        coord=SpeechCoordinator(render,ttl_seconds=120)
        try:
            plan=process_text(A,source="manual")
            job=coord.submit(plan,engine_id="fake",voice_id="fake",render_args={})
            ready=coord.wait(job["speech_id"],timeout=4)
            self.assertEqual(ready["state"],"ready")
            self.assertEqual(ready["alignment_revision"],0)
            cues=validate_manual_cues(ready["audio"]["segments"],[
                {"segment_index":0,"start_offset":0,"end_offset":2,
                 "start_ms":100,"end_ms":350},
                {"segment_index":0,"start_offset":2,"end_offset":8,
                 "start_ms":450,"end_ms":700},
            ])
            saved=coord.set_manual_alignment(job["speech_id"],cues,0)
            self.assertEqual(saved["alignment_revision"],1)
            self.assertFalse(saved["audio"]["word_alignment"])
            self.assertEqual(saved["audio"]["manual_cues"],cues)
            with self.assertRaises(AlignmentConflict):
                coord.set_manual_alignment(job["speech_id"],[],0)
            playback=PlaybackState()
            session="a"*32
            playback.report({"session_id":session,"speech_id":job["speech_id"],
                             "event":"start","sequence":1,"position_ms":120},
                            ready_job=saved)
            self.assertEqual(playback.snapshot("manual")["subtitle"],A[:2])
            self.assertEqual(playback.snapshot("manual")["subtitle_precision"],
                             "manual_user_timed")
            playback.report({"session_id":session,"speech_id":job["speech_id"],
                             "event":"progress","sequence":2,"position_ms":400})
            self.assertEqual(playback.snapshot("manual")["subtitle"],"")
            playback.report({"session_id":session,"speech_id":job["speech_id"],
                             "event":"progress","sequence":3,"position_ms":500})
            self.assertEqual(playback.snapshot("manual")["subtitle"],A[2:8])
            playback.report({"session_id":session,"speech_id":job["speech_id"],
                             "event":"progress","sequence":4,"position_ms":950})
            self.assertEqual(playback.snapshot("manual")["subtitle"],"")
        finally:
            coord.close()


class AlignmentHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coord=SpeechCoordinator(render)
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.server.speech_coordinator=cls.coord
        cls.server.playback_state=PlaybackState()
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
        cls.thread.join(3)
        cls.coord.close()

    def setUp(self):
        self.plan=process_text(A,source="manual")
        created=self.coord.submit(self.plan,engine_id="fake",voice_id="fake",render_args={})
        self.id=created["speech_id"]
        self.ready=self.coord.wait(self.id,timeout=4)
        self.assertEqual(self.ready["state"],"ready")

    def post(self,path,value,intent=None,ctype="application/json"):
        headers={"Content-Type":ctype}
        if intent:headers["X-VoxWeaveTTS-Intent"]=intent
        request=Request(self.base+path,data=json.dumps(value,ensure_ascii=False).encode("utf-8"),
                        method="POST",headers=headers)
        return urlopen(request,timeout=5)

    def test_http_save_and_playback_manual_mode(self):
        cue={"segment_index":0,"start_offset":0,"end_offset":2,
             "start_ms":80,"end_ms":350}
        with self.post("/v1/jobs/"+self.id+"/alignment",
                       {"cues":[cue],"expected_revision":0},
                       "save-manual-alignment") as response:
            self.assertEqual(response.status,200)
            result=json.load(response)
        self.assertEqual(result["alignment_revision"],1)
        with urlopen(self.base+"/v1/jobs/"+self.id,timeout=5) as response:
            self.assertEqual(json.load(response)["audio"]["manual_cues"][0]["display_text"],A[:2])
        with self.post("/v1/playback/event",{
            "session_id":"d"*32,"speech_id":self.id,
            "sequence":1,"position_ms":100,"event":"start",
        },"report-playback") as response:
            self.assertEqual(json.load(response)["state"],"playing")
        with urlopen(self.base+"/v1/playback/state?mode=manual",timeout=5) as response:
            state=json.load(response)
        self.assertEqual(state["subtitle"],A[:2])
        self.assertEqual(state["subtitle_precision"],"manual_user_timed")

    def test_http_access_validation_conflicts_and_evaluation(self):
        path="/v1/jobs/"+self.id+"/alignment"
        entry={"cues":[],"expected_revision":0}
        for intent,ctype,expected in ((None,"application/json",403),
                                      ("save-manual-alignment","text/plain",415)):
            with self.subTest(expected=expected), self.assertRaises(HTTPError) as err:
                self.post(path,entry,intent,ctype)
            self.assertEqual(err.exception.code,expected);err.exception.close()
        with self.post(path,entry,"save-manual-alignment") as response:
            self.assertEqual(json.load(response)["alignment_revision"],1)
        with self.assertRaises(HTTPError) as err:
            self.post(path,entry,"save-manual-alignment")
        self.assertEqual(err.exception.code,409);err.exception.close()
        with self.assertRaises(HTTPError) as err:
            self.post(path,{"cues":[{"segment_index":1,"start_offset":0,
                                     "end_offset":1,"start_ms":900,"end_ms":950}],
                            "expected_revision":1},"save-manual-alignment")
        self.assertEqual(err.exception.code,400);err.exception.close()
        score_ref=[{"segment_index":0,"start_offset":0,"end_offset":3,
                    "start_ms":50,"end_ms":300}]
        with self.post("/v1/alignment/evaluate",
                       {"candidate":[{**score_ref[0],"start_ms":90}],
                        "reference":score_ref},
                       "evaluate-manual-alignment") as response:
            score=json.load(response)
        self.assertEqual(score["matched_cues"],1)
        self.assertEqual(score["mean_absolute_boundary_error_ms"],20.0)
        with urlopen(self.base+"/overlay?mode=manual",timeout=5) as response:
            self.assertIn(b"manual",response.read())


if __name__=="__main__":
    unittest.main()