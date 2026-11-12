"""Model-free integration tests for the shared speech job queue and HTTP API."""
import io
import json
import struct
import threading
import time
import unittest
import wave
from dataclasses import replace
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.processing import process_text
from voxweavetts.speech import engine_info, render_wav
from voxweavetts.speech_coordinator import (
    JobMissing, JobNotReady, QueueFull, SpeechCoordinator,
)
from voxweavetts.server import Handler


class LocalFakeEngine:
    id = "fake-tts"
    sample_rate = 24000

    def generate(self, text, speed):
        return struct.pack("<h", 4200) * 1200


def fake_renderer(plan, **kwargs):
    return render_wav(plan, engine=LocalFakeEngine(), **kwargs)


def submit(coordinator, text="สวัสดี", source_message_id=None, rules=None):
    plan = process_text(text, rules=rules or [], source="test")
    return coordinator.submit(
        plan, engine_id="fastthaig2p-cpu", voice_id="thai_som",
        render_args={"engine_id": "fastthaig2p-cpu", "voice_id": "thai_som"},
        source_message_id=source_message_id,
    )


class CoordinatorTests(unittest.TestCase):
    def test_queue_ready_wav_timing_and_event_order(self):
        c = SpeechCoordinator(fake_renderer)
        try:
            job = submit(
                c, "อมตะคำลับ",
                rules=[{"match": "คำลับ", "mode": "silence", "silence_ms": 400,
                        "display": "***"}],
            )
            ready = c.wait(job["speech_id"])
            self.assertEqual(ready["state"], "ready")
            self.assertTrue(ready["audio_ready"])
            self.assertEqual(ready["display_text"], "อมตะ***")
            self.assertNotIn("คำลับ", json.dumps(ready, ensure_ascii=False))
            events = c.events(job["speech_id"])
            self.assertEqual([e["type"] for e in events],
                             ["speech.queued", "speech.rendering", "speech.ready"])
            self.assertEqual([e["sequence"] for e in events], [1, 2, 3])
            self.assertNotIn("speech.started", str(events))
            with wave.open(io.BytesIO(c.audio(job["speech_id"]))) as wav:
                self.assertEqual(wav.getnframes(), 1200 + 9600)
            self.assertEqual(ready["audio"]["segments"][1]["end_ms"] -
                             ready["audio"]["segments"][1]["start_ms"], 400)
            self.assertEqual(ready["audio"]["timing_basis"],
                             "generated_audio_samples_not_playback")
        finally:
            c.close()

    def test_source_message_dedup(self):
        c = SpeechCoordinator(fake_renderer)
        try:
            first = submit(c, "สวัสดี", "msg-42")
            duplicate = submit(c, "ข้อความอื่น", "msg-42")
            self.assertEqual(first["speech_id"], duplicate["speech_id"])
            self.assertEqual(len(c.list()), 1)
            self.assertEqual(c.wait(first["speech_id"])["state"], "ready")
        finally:
            c.close()

    def test_cancel_queued_job_does_not_render(self):
        occupied = threading.Event()
        release = threading.Event()
        calls = []

        def delayed(plan, **kwargs):
            calls.append(plan["spoken_text"])
            occupied.set()
            release.wait(5)
            return fake_renderer(plan, **kwargs)

        c = SpeechCoordinator(delayed, max_jobs=2)
        try:
            first = submit(c, "one")
            self.assertTrue(occupied.wait(3))
            second = submit(c, "two")
            cancelled = c.cancel(second["speech_id"])
            self.assertEqual(cancelled["state"], "cancelled")
            release.set()
            self.assertEqual(c.wait(first["speech_id"])["state"], "ready")
            self.assertEqual(c.get(second["speech_id"])["state"], "cancelled")
            self.assertEqual(len(calls), 1)
            with self.assertRaises(JobNotReady):
                c.audio(second["speech_id"])
        finally:
            release.set()
            c.close()

    def test_cancel_while_rendering_discards_late_audio(self):
        entered, release = threading.Event(), threading.Event()

        def slow(plan, **kwargs):
            entered.set()
            release.wait(5)
            return fake_renderer(plan, **kwargs)

        c = SpeechCoordinator(slow)
        try:
            job = submit(c)
            self.assertTrue(entered.wait(3))
            cancelled = c.cancel(job["speech_id"])
            self.assertEqual(cancelled["state"], "cancelled")
            release.set()
            time.sleep(0.07)
            self.assertEqual(c.get(job["speech_id"])["state"], "cancelled")
            self.assertNotIn("speech.ready", str(c.events(job["speech_id"])))
        finally:
            release.set()
            c.close()

    def test_bounded_queue_and_private_error(self):
        busy, release = threading.Event(), threading.Event()

        def failing(plan, **kwargs):
            busy.set()
            release.wait(5)
            raise RuntimeError("PRIVATE RAW SPOKEN CONTENT")

        c = SpeechCoordinator(failing, max_jobs=1)
        try:
            first = submit(c)
            self.assertTrue(busy.wait(3))
            with self.assertRaises(QueueFull):
                submit(c, "next")
            release.set()
            failed = c.wait(first["speech_id"])
            self.assertEqual(failed["state"], "failed")
            self.assertNotIn("PRIVATE", json.dumps(failed))
            with self.assertRaises(JobNotReady):
                c.audio(first["speech_id"])
        finally:
            release.set()
            c.close()

    def test_audio_limit_and_expiration(self):
        c = SpeechCoordinator(fake_renderer, max_total_audio_bytes=1024,
                              ttl_seconds=1.0)
        try:
            job = submit(c)
            self.assertEqual(c.wait(job["speech_id"])["state"], "failed")
            self.assertEqual(c.get(job["speech_id"])["error"],
                             "audio queue memory limit reached")
            # Simulate age instead of sleeping 20ms: scheduling on Windows CI
            # can exceed that and prune the job before we assert its error.
            with c._cv:
                c._jobs[job["speech_id"]].created_mono -= 2.0
            with self.assertRaises(JobMissing):
                c.get(job["speech_id"])
        finally:
            c.close()

    def test_validates_source_ids(self):
        c = SpeechCoordinator(fake_renderer)
        try:
            for value in ("", "x"*129, 12, {"bad": "id"}):
                with self.assertRaises(ValueError):
                    submit(c, source_message_id=value)
        finally:
            c.close()


class CoordinatorAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coordinator = SpeechCoordinator(fake_renderer)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.speech_coordinator = cls.coordinator
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)
        cls.coordinator.close()

    def test_http_queue_ready_events_audio_and_cancel(self):
        real_descriptor = engine_info()
        ready_descriptor = replace(real_descriptor, assets_ready=True, runtime_ready=True)
        payload = json.dumps({
            "text": "สวัสดี คำลับ", "source": "test",
            "source_message_id": "id-hello",
            "rules": [{"match": "คำลับ", "mode": "skip", "display": "***"}],
        }, ensure_ascii=False).encode("utf-8")
        req = Request(
            self.base + "/v1/jobs", data=payload, method="POST",
            headers={"Content-Type": "application/json",
                     "X-VoxWeaveTTS-Intent": "queue-speech"},
        )
        with patch("voxweavetts.server.get_engine_info", return_value=ready_descriptor):
            with urlopen(req, timeout=3) as response:
                self.assertEqual(response.status, 202)
                job = json.load(response)
        job_id = job["speech_id"]
        result = self.coordinator.wait(job_id)
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["display_text"], "สวัสดี ***")
        self.assertNotIn("คำลับ", json.dumps(result, ensure_ascii=False))
        self.assertFalse("spoken_text" in str(result))
        with urlopen(self.base + "/v1/jobs/" + job_id, timeout=3) as response:
            self.assertEqual(json.load(response)["state"], "ready")
        with urlopen(self.base + "/v1/jobs/" + job_id + "/events", timeout=3) as response:
            events = json.load(response)["events"]
            self.assertEqual(events[-1]["type"], "speech.ready")
        with urlopen(self.base + "/v1/jobs/" + job_id + "/audio", timeout=3) as response:
            self.assertEqual(response.headers["Content-Type"], "audio/wav")
            self.assertTrue(response.read().startswith(b"RIFF"))
        cancel = Request(
            self.base + "/v1/jobs/" + job_id + "/cancel", data=b"", method="POST",
            headers={"X-VoxWeaveTTS-Intent": "cancel-speech-job"},
        )
        with urlopen(cancel, timeout=3) as response:
            self.assertEqual(json.load(response)["state"], "cancelled")
        with self.assertRaises(HTTPError) as err:
            urlopen(self.base + "/v1/jobs/" + job_id + "/audio", timeout=3)
        self.assertEqual(err.exception.code, 409)
        err.exception.close()

    def test_mutation_requires_intent_and_bad_ids_are_404(self):
        req = Request(
            self.base + "/v1/jobs",
            data=json.dumps({"text": "hello"}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as err:
            urlopen(req, timeout=3)
        self.assertEqual(err.exception.code, 403)
        err.exception.close()
        with self.assertRaises(HTTPError) as err:
            urlopen(self.base + "/v1/jobs/" + "0"*32, timeout=3)
        self.assertEqual(err.exception.code, 404)
        err.exception.close()


if __name__ == "__main__":
    unittest.main()
