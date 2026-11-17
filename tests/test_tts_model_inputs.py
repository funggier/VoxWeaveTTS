"""Private TTS chunk diagnostics; transformed text is never in public status."""
from __future__ import annotations

import io
import json
import struct
import threading
import unittest
import wave
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from voxweavetts.processing import process_text
from voxweavetts.speech import _chunks
from voxweavetts.speech_coordinator import SpeechCoordinator, JobNotReady
from voxweavetts.server import Handler
from voxweavetts.tts_model_inputs import collect_model_inputs


def renderer(plan, **kwargs):
    audio = io.BytesIO()
    with wave.open(audio, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(24000)
        writer.writeframes(struct.pack("<h", 1000) * 240)
    return audio.getvalue(), {
        "sample_rate":24000,
        "duration_ms":10,
        "segments":[{
            "kind":"speech",
            "display_text":plan["display_text"],
            "start_ms":0,"end_ms":10,
        }],
    }


class PrivateModelInputTests(unittest.TestCase):
    def test_nonmixed_chunks_are_exactly_those_passed_to_generate(self):
        plan=process_text("hello",rules=[{
            "match":"hello","mode":"replace","spoken":"translated "+("a"*245)
        }])
        arguments={"engine_id":"makham-paradee-cpu","voice_id":"paradee_thai"}
        result=collect_model_inputs(plan,arguments)
        self.assertEqual([item["text"] for item in result],[
            part for part in _chunks(plan["spoken_text"]) if part.strip()
        ])
        self.assertGreater(len(result),1)
        self.assertEqual("".join(item["text"] for item in result),plan["spoken_text"])
        self.assertEqual({item["engine_id"] for item in result},{"makham-paradee-cpu"})

    def test_mixed_languages_exact_spans_per_engine_and_skip_silence(self):
        plan=process_text("สวัสดี Computer แล้ว 你好",source="test")
        arguments={
            "engine_id":"makham-paradee-cpu","voice_id":"paradee_thai",
            "language_voice_routes":{
                "th":{"engine_id":"makham-paradee-cpu","voice_id":"paradee_thai"},
                "en":{"engine_id":"kokoro-onnx-cpu","voice_id":"af_heart"},
                "zh":{"engine_id":"melo-zh-cpu","voice_id":"zh"},
            },
        }
        result=collect_model_inputs(plan,arguments)
        self.assertEqual("".join(item["text"] for item in result),plan["spoken_text"])
        self.assertEqual([item["language"] for item in result],["th","en","th","zh"])
        self.assertEqual(result[1]["engine_id"],"kokoro-onnx-cpu")
        self.assertEqual(result[1]["voice_id"],"af_heart")
        self.assertEqual(result[-1]["engine_id"],"melo-zh-cpu")
        separated=process_text("ABC XY",rules=[
            {"match":"XY","mode":"silence","silence_ms":50,"display":"***"},
        ])
        parts=collect_model_inputs(separated,arguments)
        self.assertEqual("".join(x["text"] for x in parts),"ABC ")
        self.assertEqual(len(parts),1)

    def test_deferred_translation_kept_private_after_plan_released(self):
        def prepare():
            return process_text("Original UI display",source="live",rules=[
                {"match":"Original UI display","mode":"replace",
                 "spoken":"English output after translation"}
            ]), {
                "engine_id":"makham-paradee-cpu","voice_id":"paradee_thai"
            }
        c=SpeechCoordinator(renderer)
        try:
            created=c.submit_deferred(prepare,source="live",source_message_id="msg-1")
            done=c.wait(created["speech_id"],timeout=5)
            self.assertEqual(done["state"],"ready")
            result=c.get_model_inputs(created["speech_id"])
            self.assertTrue(result["available"])
            self.assertEqual("".join(x["text"] for x in result["inputs"]),
                             "English output after translation")
            self.assertNotIn("English output after translation",
                             json.dumps(done,ensure_ascii=False))
            self.assertNotIn("inputs",done)
            self.assertNotIn("inputs",json.dumps(c.events(created["speech_id"])))
        finally:
            c.close()


class PrivateModelInputHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.httpd.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(3)

    def post(self,job_id,*,origin="same",intent="inspect-tts-inputs",
             site="same-origin",content_type="application/json",payload=None):
        headers={"Content-Type":content_type}
        if origin=="same":headers["Origin"]=self.base
        elif origin:headers["Origin"]=origin
        if intent:headers["X-VoxWeaveTTS-Intent"]=intent
        if site:headers["Sec-Fetch-Site"]=site
        req=Request(self.base+"/v1/jobs/"+job_id+"/tts-inputs",
                    data=json.dumps({} if payload is None else payload).encode(),
                    headers=headers,method="POST")
        try:
            with urlopen(req,timeout=3) as res:
                self.assertEqual(res.headers["Cache-Control"],"no-store")
                return res.status,json.load(res)
        except HTTPError as error:
            with error:
                return error.code,json.load(error)

    def test_guarded_explicit_post_and_no_public_get_or_events(self):
        c=SpeechCoordinator(renderer)
        try:
            transformed="English text sent into model only"
            plan=process_text("SENSITIVE_ORIGINAL",rules=[
                {"match":"SENSITIVE_ORIGINAL","spoken":transformed,"mode":"replace"}
            ],source="live")
            args={"engine_id":"makham-paradee-cpu","voice_id":"paradee_thai"}
            created=c.submit(plan,engine_id=args["engine_id"],voice_id=args["voice_id"],
                             render_args=args)
            done=c.wait(created["speech_id"],timeout=4)
            self.assertEqual(done["state"],"ready")
            job_id=created["speech_id"]
            with patch.object(Handler,"_coordinator",return_value=c):
                with urlopen(self.base+"/v1/jobs/"+job_id,timeout=3) as res:
                    public=json.load(res)
                self.assertNotIn(transformed,json.dumps(public))
                with self.assertRaises(HTTPError) as err:
                    urlopen(self.base+"/v1/jobs/"+job_id+"/tts-inputs",timeout=3)
                self.assertEqual(err.exception.code,404)
                for kwargs in (
                    {"origin":None},
                    {"origin":"https://third.party.invalid"},
                    {"intent":None},
                    {"site":"cross-site"},
                ):
                    with self.subTest(**kwargs):
                        code,body=self.post(job_id,**kwargs)
                        self.assertEqual(code,403)
                        self.assertNotIn(transformed,json.dumps(body))
                self.assertEqual(self.post(job_id,payload={"untrusted":"data"})[0],400)
                self.assertEqual(self.post(job_id,content_type="text/plain")[0],415)
                code,result=self.post(job_id)
                self.assertEqual(code,200)
                self.assertTrue(result["available"])
                self.assertEqual(result["state"],"ready")
                self.assertEqual("".join(x["text"] for x in result["inputs"]),transformed)
                self.assertEqual(self.post("0"*32)[0],404)
        finally:
            c.close()


if __name__=="__main__":
    unittest.main()
