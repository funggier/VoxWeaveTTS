"""Offline load and mode-integration gates for the AI->speech pipeline.

No platform credentials and no downloads: heavy AI responses are simulated.
Real Ollama and M2M100 quality are independently checked by verify_* scripts.
"""
import json
import threading
import time
import unittest

from voxweavetts.ai_pipeline import process_pipeline
from voxweavetts.ai_processing import DEFAULTS, AIUnavailable, validate_settings
from voxweavetts.processing import process_text
from voxweavetts.speech_coordinator import SpeechCoordinator, QueueFull, JobNotReady

VOICE = {"engine_id": "test-tts", "voice_id": "test"}
SOURCES = (
    "manual", "document", "youtube-live", "youtube-live-browser",
    "tiktok-live", "tiktok-live-extension", "discord",
)


def fake_renderer(plan, **kwargs):
    # A minimal valid PCM16 mono WAV and one segment of speech timing.
    import io
    import wave
    memory = io.BytesIO()
    with wave.open(memory, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 2400)
    info = {
        "duration_ms": 100, "sample_rate": 24000,
        "segments": [{"kind":"speech","display_text":plan["display_text"],
                      "start_ms":0,"end_ms":100}],
    }
    return memory.getvalue(), info


def settings(**updates):
    return validate_settings({**DEFAULTS, **updates})


class AILiveLoadTests(unittest.TestCase):
    def test_seven_sources_sender_isolation_emoji_and_rules(self):
        calls = []
        rules = [
            {"match": "GGWP", "spoken": "well played", "stage": "pre_ai"},
            {"match": "ยอดเยี่ยม", "spoken": "ดีมาก", "stage": "post_ai"},
            {"match": "@Alice", "spoken": "HACKED NAME", "stage": "post_ai"},
        ]
        for source in SOURCES:
            with self.subTest(source=source):
                plan = process_pipeline(
                    "เกม GGWP หัวเราะ", source=source, rules=rules,
                    sender_prefix_text="คุณ @Alice พิมพ์ว่า",
                    settings=settings(enabled=True,operation="translate",
                                      model="installed:test",target_language="th",
                                      auto_detect=False),
                    model_call=lambda text, *_: calls.append((source,text))
                        or "เกมยอดเยี่ยม หัวเราะ",
                )
                self.assertEqual(calls[-1], (source,"เกม well played หัวเราะ"))
                self.assertEqual(plan["spoken_text"],
                                 "คุณ @Alice พิมพ์ว่า เกมดีมาก หัวเราะ")
                self.assertTrue(plan["display_text"].startswith("คุณ @Alice พิมพ์ว่า"))
                self.assertNotIn("HACKED NAME",plan["spoken_text"])
                self.assertEqual(plan["segments"][0]["spoken_text"],
                                 "คุณ @Alice พิมพ์ว่า ")

    def test_filtered_empty_text_has_terminal_skipped_status_without_tts(self):
        calls=[]
        def renderer(plan,**args):
            calls.append(plan)
            raise AssertionError("renderer must not be called for an empty plan")
        c=SpeechCoordinator(renderer,max_jobs=3)
        try:
            pre=process_text("SECRET",source="discord",
                 rules=[{"match":"SECRET","mode":"skip"}])
            sync_job=c.submit(pre,engine_id="x",voice_id="v",render_args=VOICE)
            self.assertEqual(sync_job["state"],"skipped")
            with self.assertRaises(JobNotReady):
                c.audio(sync_job["speech_id"])
            self.assertNotIn("SECRET",json.dumps(sync_job,ensure_ascii=False))

            def prepare():
                p=process_pipeline(
                    "Hello", source="youtube-live",
                    settings=settings(enabled=True, fallback="skip",
                                      model="unavailable"),
                    model_call=lambda *_: (_ for _ in ()).throw(AIUnavailable("offline")),
                )
                return p, VOICE
            job=c.submit_deferred(prepare, source="youtube-live")
            state=c.wait(job["speech_id"],timeout=3)
            self.assertEqual(state["state"],"skipped")
            self.assertFalse(state["audio_ready"])
            self.assertNotIn("Hello",json.dumps(state))
            self.assertEqual(c.events(job["speech_id"])[-1]["type"],"speech.skipped")
            self.assertEqual(calls,[])
        finally:
            c.close()

    def test_bounded_rapid_live_submissions_cancel_without_queue_growth(self):
        held=threading.Event()
        release=threading.Event()
        generated=[]
        def blocked():
            held.set()
            release.wait(5)
            return process_text("done",source="discord"),VOICE
        def prepare():
            return process_text("queued",source="youtube-live"),VOICE
        def renderer(plan,**args):
            generated.append(plan["spoken_text"])
            return fake_renderer(plan,**args)
        c=SpeechCoordinator(renderer,max_jobs=12)
        try:
            first=c.submit_deferred(blocked,source="discord",source_message_id="blocking")
            self.assertTrue(held.wait(3))
            for i in range(250):
                name = "youtube-live" if i%2 else "discord"
                job=c.submit_deferred(prepare,source=name,source_message_id=f"rapid-{i}")
                self.assertEqual(job["state"],"preparing")
                self.assertEqual(c.cancel(job["speech_id"])["state"],"cancelled")
                # Cancelled IDs must leave the pre-AI queue immediately.
                with c._cv:
                    self.assertLessEqual(len(c._prepare_queue),12)
                    self.assertLessEqual(len(c._jobs),12)
            active=[c.submit_deferred(prepare,source="youtube-live",
                                    source_message_id=f"active-{i}") for i in range(11)]
            with self.assertRaises(QueueFull):
                c.submit_deferred(prepare,source="youtube-live",
                                  source_message_id="overflow")
            duplicate=c.submit_deferred(prepare,source="youtube-live",
                                        source_message_id="active-1")
            self.assertEqual(duplicate["speech_id"],active[1]["speech_id"])
            release.set()
            self.assertEqual(c.wait(first["speech_id"],timeout=5)["state"],"ready")
            for entry in active:
                self.assertEqual(c.wait(entry["speech_id"],timeout=5)["state"],"ready")
            self.assertEqual(len(generated),12)
            self.assertEqual(c._audio_bytes,
                             sum(len(c.audio(j["speech_id"])) for j in [first,*active]))
        finally:
            release.set()
            c.close()


if __name__=="__main__":
    unittest.main()
