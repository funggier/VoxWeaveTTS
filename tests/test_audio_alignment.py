"""Signal-derived speech activity timing; no neural model or external weights."""
from __future__ import annotations

import io
import math
import struct
import unittest
import wave

from voxweavetts.audio_alignment import PCMActivityProvider
from voxweavetts.playback_state import PlaybackState
from voxweavetts.processing import process_text, InputError
from voxweavetts.speech_coordinator import SpeechCoordinator
from voxweavetts.subtitle_cues import caption_for


RATE = 24000


def make_wav(runs: list[tuple[int, int]], *, channels: int = 1) -> bytes:
    """(duration_ms, PCM amplitude); 1000Hz square-modulated audible signal."""
    samples = bytearray()
    phase = 0
    for duration, amp in runs:
        for _ in range(round(duration * RATE / 1000)):
            value = amp if phase % 24 < 12 else -amp
            for _channel in range(channels):
                samples.extend(struct.pack("<h", value))
            phase += 1
    buffer = io.BytesIO()
    with wave.open(buffer,"wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(RATE)
        writer.writeframes(samples)
    return buffer.getvalue()


class SignalActivityTests(unittest.TestCase):
    def setUp(self):
        self.provider = PCMActivityProvider()
        self.wav = make_wav([
            (220,0),(380,9500),(300,0),(360,9500),(180,0),
        ])
        self.segment=[{
            "kind":"speech","display_text":"สวัสดีครับ 55555 🐱",
            "start_ms":0,"end_ms":1440,
        }]

    def test_audible_runs_recovered_from_pcm_not_letter_counts(self):
        result=self.provider.analyze(self.wav,self.segment)
        self.assertEqual(len(result),1)
        self.assertEqual(len(result[0]),2)
        first,second=result[0]
        self.assertTrue(180 <= first["start_ms"] <= 240, first)
        self.assertTrue(580 <= first["end_ms"] <= 650,first)
        self.assertTrue(860 <= second["start_ms"] <= 930,second)
        self.assertTrue(1240 <= second["end_ms"] <= 1300,second)
        self.assertEqual(caption_for([
            {**self.segment[0],"activity_intervals":result[0]}],100,"activity"),"")
        self.assertEqual(caption_for([
            {**self.segment[0],"activity_intervals":result[0]}],350,"activity"),
                         self.segment[0]["display_text"])
        self.assertEqual(caption_for([
            {**self.segment[0],"activity_intervals":result[0]}],740,"activity"),"")
        self.assertEqual(caption_for([
            {**self.segment[0],"activity_intervals":result[0]}],1080,"activity"),
                         self.segment[0]["display_text"])
        self.assertEqual(caption_for(self.segment,740,"segment"),
                         self.segment[0]["display_text"])

    def test_silence_only_produces_no_audible_intervals(self):
        wav=make_wav([(1100,0)])
        result=self.provider.analyze(wav,[{"kind":"speech","start_ms":0,"end_ms":1100}])
        self.assertEqual(result,[[]])

    def test_mask_and_non_speech_do_not_leak(self):
        wav=make_wav([(400,9000),(250,0),(390,9000)])
        segments=[
            {"kind":"speech","start_ms":0,"end_ms":400,"display_text":"ก่อน"},
            {"kind":"silence","start_ms":400,"end_ms":650,"display_text":"PRIVATE ORIGINAL"},
            {"kind":"speech","start_ms":650,"end_ms":1040,"display_text":"หลัง"},
        ]
        result=self.provider.analyze(wav,segments)
        self.assertEqual(result[1],[])
        self.assertTrue(result[0])
        self.assertTrue(result[2])
        meta=[{**part,"activity_intervals":intervals}
              for part, intervals in zip(segments,result)]
        self.assertEqual(caption_for(meta,510,"activity"),"")
        self.assertEqual(caption_for(meta,800,"activity"),"หลัง")

    def test_reject_unsupported_without_failing_wav(self):
        stereo=make_wav([(500,9000)],channels=2)
        self.assertIsNone(self.provider.analyze(stereo,self.segment))
        self.assertIsNone(self.provider.analyze(b"not a wave",self.segment))
        self.assertIsNone(self.provider.analyze(self.wav,[{
            **self.segment[0],"end_ms":4000000,
        }]))


class AlignmentIntegrationTests(unittest.TestCase):
    def test_fake_renderer_queue_emits_public_activity_metadata(self):
        wav=make_wav([(200,0),(850,8500),(250,0)])
        plan=process_text("นิยายผู้ฝึกตนเดินทางสู่ป่าใหญ่",source="document")
        def render(_plan,**kwargs):
            return wav,{
                "sample_rate":RATE,"duration_ms":1300,
                "segments":[{
                    "kind":"speech","display_text":_plan["display_text"],
                    "start_ms":0,"end_ms":1300,
                    "source_start":0,"source_end":len(_plan["display_text"]),
                }],
            }
        coord=SpeechCoordinator(render)
        try:
            job=coord.submit(plan,engine_id="fake",voice_id="fake",render_args={})
            ready=coord.wait(job["speech_id"],timeout=3)
            self.assertEqual(ready["state"],"ready")
            meta=ready["audio"]
            self.assertFalse(meta["word_alignment"])
            self.assertIn("pcm16",meta["activity_basis"])
            self.assertEqual(len(meta["segments"][0]["activity_intervals"]),1)
            self.assertNotIn("source_start",str(meta))
            self.assertNotIn("spoken_text",str(meta))
            state=PlaybackState()
            state.report({
                "session_id":"a"*32,"speech_id":job["speech_id"],
                "sequence":1,"event":"start","position_ms":50,
            },ready_job=ready)
            self.assertEqual(state.snapshot("activity")["subtitle"],"")
            state.report({
                "session_id":"a"*32,"speech_id":job["speech_id"],
                "sequence":2,"event":"progress","position_ms":420,
            })
            self.assertEqual(state.snapshot("activity")["subtitle"],plan["display_text"])
            self.assertEqual(state.snapshot("activity")["subtitle_precision"],
                             "pcm16_energy_activity_heuristic")
        finally:
            coord.close()

    def test_missing_activity_metadata_has_explicit_fallback_label(self):
        job={
            "speech_id":"b"*32,"state":"ready","engine_id":"mock",
            "audio":{"duration_ms":1000,"segments":[{
                "kind":"speech","start_ms":0,"end_ms":1000,
                "display_text":"สวัสดี",
            }]},
        }
        state=PlaybackState()
        state.report({
            "session_id":"a"*32,"speech_id":"b"*32,
            "sequence":1,"event":"start","position_ms":500,
        },ready_job=job)
        snapshot=state.snapshot("activity")
        self.assertEqual(snapshot["subtitle_precision"],
                         "generated_segment_fallback_no_activity")
        self.assertEqual(snapshot["subtitle"],"สวัสดี")

    def test_provider_metadata_allowlist_and_failing_provider_fallback(self):
        wav=make_wav([(500,9000)])
        plan=process_text("สวัสดี")
        def render(_plan,**_args):
            return wav,{
                "sample_rate":RATE,"duration_ms":500,
                "segments":[{"kind":"speech","display_text":"สวัสดี",
                             "start_ms":0,"end_ms":500}],
            }
        class LeakyProvider:
            id="test-leaky"
            def analyze(self,wav,segments):
                return [[{"start_ms":0,"end_ms":500,
                          "secret_text":"PRIVATE SHOULD NOT LEAK"}]]
        class BrokenProvider:
            id="test-broken"
            def analyze(self,wav,segments):
                raise RuntimeError("engine-independent analysis failure")
        for provider in (LeakyProvider(),BrokenProvider()):
            with self.subTest(provider=provider.id):
                coordinator=SpeechCoordinator(render,alignment_provider=provider)
                try:
                    job=coordinator.submit(plan,engine_id="fake",voice_id="fake",render_args={})
                    ready=coordinator.wait(job["speech_id"],timeout=3)
                    self.assertEqual(ready["state"],"ready")
                    self.assertNotIn("PRIVATE SHOULD NOT LEAK",str(ready))
                    self.assertFalse(ready["audio"]["word_alignment"])
                    if provider.id=="test-broken":
                        self.assertEqual(ready["audio"]["activity_basis"],"unavailable")
                        self.assertNotIn("activity_intervals",ready["audio"]["segments"][0])
                    else:
                        self.assertEqual(ready["audio"]["segments"][0]["activity_intervals"],
                                         [{"start_ms":0,"end_ms":500}])
                finally:
                    coordinator.close()

    def test_audio_activity_intervals_strictly_validated(self):
        job={
            "speech_id":"b"*32,"state":"ready","engine_id":"mock",
            "audio":{"duration_ms":1000,"segments":[{
                "kind":"speech","start_ms":0,"end_ms":1000,
                "display_text":"สวัสดี",
                "activity_intervals":[{"start_ms":150,"end_ms":600}],
            }]},
        }
        PlaybackState().report({
            "session_id":"c"*32,"speech_id":"b"*32,
            "sequence":1,"event":"start","position_ms":100,
        },ready_job=job)
        for intervals in (
            [{"start_ms":150,"end_ms":1001}],
            [{"start_ms":150,"end_ms":600},{"start_ms":500,"end_ms":700}],
            [{"start_ms":True,"end_ms":400}],
            [{"start_ms":800,"end_ms":700}],
            [{}],
            "invalid",
        ):
            bad={**job,"audio":{**job["audio"],"segments":[
                {**job["audio"]["segments"][0],"activity_intervals":intervals}
            ]}}
            with self.subTest(intervals=intervals):
                with self.assertRaises(InputError):
                    PlaybackState().report({
                        "session_id":"d"*32,"speech_id":"b"*32,
                        "sequence":1,"event":"start","position_ms":10,
                    },ready_job=bad)


if __name__=="__main__":
    unittest.main()