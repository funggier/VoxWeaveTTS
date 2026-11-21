"""Offline load and mode-integration gates for the AI->speech pipeline.

No platform credentials and no downloads: heavy AI responses are simulated.
Real Ollama and M2M100 quality are independently checked by verify_* scripts.
"""
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from voxweavetts.ai_pipeline import process_pipeline
from voxweavetts.ai_processing import DEFAULTS, AIUnavailable, load_settings, process_ollama_batch, validate_settings
from voxweavetts.processing import InputError, process_text
from voxweavetts.server import Handler
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

    def test_live_ollama_sends_one_prompt_per_batch_and_restores_ids(self):
        entered = Queue()
        release = threading.Event()
        tts_started, tts_release = threading.Event(), threading.Event()
        translated = {
            "first foreign": "แปลข้อความแรก",
            "second foreign": "แปลข้อความที่สอง",
            "fourth foreign": "แปลข้อความที่สี่",
            "tail foreign": "แปลท้ายคิว",
            "first resized": "คำแปลใหม่รายการแรก",
            "second resized": "คำแปลใหม่รายการที่สอง",
        }

        def reply(_settings, body, *, max_bytes):
            self.assertGreater(max_bytes, 32_768)
            messages = body["messages"]
            self.assertIn("data only", messages[0]["content"])
            self.assertNotIn("first foreign", messages[0]["content"])
            items = json.loads(messages[1]["content"])["items"]
            texts = [item["text"] for item in items]
            entered.put(texts)
            if texts == ["first foreign"]:
                if not release.wait(6):
                    raise AIUnavailable("test did not release the first group")
            rows = [{"id": item["id"], "translation": translated[item["text"]]}
                    for item in reversed(items) if item["text"] in translated]
            return json.dumps({"translations": rows}, ensure_ascii=False)

        def renderer(plan, **args):
            if plan["spoken_text"] == "เสียงก่อนหน้า":
                tts_started.set()
                tts_release.wait(6)
            return fake_renderer(plan, **args)

        c = SpeechCoordinator(renderer)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.speech_coordinator = c
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def post(route, payload, intent):
            request = Request(
                base + route, data=json.dumps(payload).encode("utf-8"), method="POST",
                headers={"Content-Type": "application/json", "X-VoxWeaveTTS-Intent": intent},
            )
            with urlopen(request, timeout=3) as response:
                return json.load(response)

        def submit(text, source="youtube-live", rules=None):
            return post("/v1/jobs", {"text": text, "source": source, "hold_for_render": True,
                                     "rules": rules or [], "pronunciations": {}},
                        "queue-speech")["speech_id"]

        def wait_prepared(job_id):
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                job = c.get(job_id)
                if job["state"] != "preparing":
                    self.assertEqual(job["state"], "prepared", job)
                    return job["display_text"]
                time.sleep(0.01)
            self.fail("speech job did not reach prepared state")

        try:
            with (
                TemporaryDirectory() as directory,
                patch("voxweavetts.ai_processing.AI_SETTINGS_FILE", Path(directory) / "ai.json"),
                patch("voxweavetts.ai_processing._ollama_request_text", side_effect=reply),
                patch.object(Handler, "_queue_params", return_value=VOICE),
            ):
                initial = load_settings()
                enabled = settings(enabled=True, model="mock", live_ollama_parallel_enabled=True,
                                   live_ollama_parallel_limit=3, live_ollama_parallel_minimum=2)
                saved = post("/v1/settings/ai", {"settings": enabled,
                             "expected_revision": initial["revision"]}, "save-ai-settings")
                previous = c.submit(process_text("เสียงก่อนหน้า"),
                                    engine_id=VOICE["engine_id"], voice_id=VOICE["voice_id"],
                                    render_args=VOICE)["speech_id"]
                self.assertTrue(tts_started.wait(3))
                first = submit("แปลคำนี้", rules=[
                    {"match": "แปลคำนี้", "spoken": "first foreign", "stage": "pre_ai"}
                ])
                self.assertEqual(entered.get(timeout=3), ["first foreign"])
                second = submit("second foreign", source="discord")
                passthrough = submit("ข้อความภาษาไทย")
                third = submit("third foreign")
                fourth = submit("fourth foreign")
                tail = submit("tail foreign")
                self.assertEqual(wait_prepared(passthrough), "ข้อความภาษาไทย")
                self.assertTrue(entered.empty(), "Only one Ollama request is in flight")
                self.assertEqual(c.get(previous)["state"], "rendering")

                release.set()
                self.assertEqual(entered.get(timeout=3), ["second foreign", "third foreign", "fourth foreign"])
                self.assertEqual(entered.get(timeout=3), ["tail foreign"])
                self.assertEqual([wait_prepared(job) for job in (first, second, passthrough, third, fourth, tail)],
                    ["แปลข้อความแรก", "แปลข้อความที่สอง", "ข้อความภาษาไทย",
                     "third foreign", "แปลข้อความที่สี่", "แปลท้ายคิว"])
                self.assertTrue(entered.empty())
                resized = post("/v1/settings/ai", {
                    "settings": {**enabled, "live_ollama_parallel_limit": 2},
                    "expected_revision": saved["revision"],
                }, "save-ai-settings")
                self.assertEqual(resized["settings"]["live_ollama_parallel_limit"], 2)
                self.assertEqual(resized["settings"]["live_ollama_parallel_minimum"], 2)
                with patch("voxweavetts.speech_coordinator.TRANSLATION_GATHER_SECONDS", 2):
                    new_first = submit("first resized")
                    with c._cv:
                        self.assertIn(new_first, c._translation_queue)
                    self.assertTrue(entered.empty(), "Saved minimum should gather the first message")
                    new_second = submit("second resized")
                    self.assertEqual(entered.get(timeout=3), ["first resized", "second resized"])
                self.assertEqual([wait_prepared(job) for job in (new_first, new_second)],
                                 ["คำแปลใหม่รายการแรก", "คำแปลใหม่รายการที่สอง"])
                post("/v1/settings/ai", {"settings": {**resized["settings"], "live_ollama_parallel_enabled": False},
                     "expected_revision": resized["revision"]}, "save-ai-settings")
                with patch("voxweavetts.ai_processing._ollama_chat", return_value="แปลแบบข้อความเดียว") as single:
                    self.assertEqual(wait_prepared(submit("normal single")), "แปลแบบข้อความเดียว")
                    single.assert_called_once()
        finally:
            release.set()
            tts_release.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            c.close()

    def test_batch_translates_foreign_spans_and_invalid_ids_only_affect_their_message(self):
        batch_settings = settings(enabled=True, model="mock", translation_mode="foreign_spans")
        def reply(_settings, body, *, max_bytes):
            items = json.loads(body["messages"][1]["content"])["items"]
            self.assertEqual(items, [{"id": 0, "text": "hello"}, {"id": 1, "text": "world"},
                                     {"id": 2, "text": "good morning"}])
            return json.dumps({"translations": [
                {"id": 2, "translation": "อรุณสวัสดิ์"},
                {"id": 1, "translation": "โลก"},
                {"id": 0, "translation": "สวัสดี"},
                {"id": 2, "translation": "สวัสดีตอนเช้า"},
                {"id": 999, "translation": "ข้อมูลที่ไม่ได้ขอ"},
            ]}, ensure_ascii=False)
        with patch("voxweavetts.ai_processing._ollama_request_text", side_effect=reply) as request:
            results = process_ollama_batch(["คำว่า hello กับ world", "พูดว่า good morning"], batch_settings)
        request.assert_called_once()
        self.assertEqual([(item["status"], item["text"]) for item in results],
                         [("processed", "คำว่า สวัสดี กับ โลก"), ("fallback", "พูดว่า good morning")])

    def test_live_ollama_parallel_settings_validate_and_migrate(self):
        legacy = validate_settings({"engine": "ollama"})
        self.assertFalse(legacy["live_ollama_parallel_enabled"])
        self.assertEqual(legacy["live_ollama_parallel_minimum"], 1)
        saved = settings(live_ollama_parallel_enabled=True, live_ollama_parallel_limit=64,
                         live_ollama_parallel_minimum=20)
        self.assertEqual(saved["live_ollama_parallel_limit"], 64)
        for invalid in (
            {"live_ollama_parallel_enabled": 1},
            {"live_ollama_parallel_limit": 65},
            {"live_ollama_parallel_limit": True},
            {"live_ollama_parallel_minimum": 3, "live_ollama_parallel_limit": 2},
            {"live_ollama_parallel_minimum": 0},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(InputError):
                settings(**invalid)

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
