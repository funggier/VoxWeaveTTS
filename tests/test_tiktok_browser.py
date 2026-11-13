"""TikTok browser reader URL safety, DOM adapter and independent source worker."""
import time
import unittest
from unittest.mock import patch

from voxweavetts.mode_state import ModeState
from voxweavetts.playback_state import PlaybackState
from voxweavetts.processing import InputError
from voxweavetts.source_adapters import PollResult, SourceMessage, SourceFailure
from voxweavetts.source_manager import SourceManager
from voxweavetts.tiktok_browser import TikTokBrowserAdapter, username_from_input

USERNAME = "test.stream_42"


class Socket:
    def close(self):
        pass


class TikTokBrowserTests(unittest.TestCase):
    def test_username_validation_and_canonical_urls(self):
        for source in (USERNAME, "@" + USERNAME,
                       "https://www.tiktok.com/@" + USERNAME + "/live",
                       "https://tiktok.com/@" + USERNAME + "/live"):
            with self.subTest(source=source):
                self.assertEqual(username_from_input(source), USERNAME)
        for source in ("", "@", "foo bar", "a"*40, ".bad", "bad.",
                       "http://www.tiktok.com/@" + USERNAME + "/live",
                       "https://www.tiktok.com.evil.invalid/@" + USERNAME + "/live",
                       "https://www.tiktok.com/@" + USERNAME,
                       "https://www.tiktok.com/@" + USERNAME + "/video/123",
                       "https://evil.example.com/@" + USERNAME + "/live",
                       "https://www.tiktok.com:8000/@" + USERNAME + "/live",
                       "https://www.tiktok.com:99999/@" + USERNAME + "/live"):
            with self.subTest(source=source), self.assertRaises(InputError):
                username_from_input(source)

    def test_adapter_isolated_profile_safe_target_and_dom_script(self):
        a = TikTokBrowserAdapter("@" + USERNAME)
        self.assertEqual(a.profile_name, "tiktok-chat")
        self.assertEqual(a.build_chat_url(a.video_id),
                         "https://www.tiktok.com/@" + USERNAME + "/live")
        self.assertTrue(a.target_matches({"type": "page",
            "url": "https://www.tiktok.com/@" + USERNAME + "/live"}))
        self.assertFalse(a.target_matches({"type": "page",
            "url": "https://www.tiktok.com.evil.invalid/@" + USERNAME + "/live"}))
        self.assertFalse(a.target_matches({"type": "page",
            "url": "https://www.tiktok.com/@" + USERNAME + "/video/1"}))
        self.assertIn("DivChatMessageList", a.chat_script)
        self.assertIn("video.muted = true", a.chat_script)
        self.assertNotIn("video.pause()", a.chat_script)
        self.assertIn('live-chat-container', a.chat_script)
        a.close()

    def test_new_comments_only_with_duplicate_dedupe(self):
        a = TikTokBrowserAdapter(USERNAME)
        a._ws = Socket()
        frames = [
            {"ready": False, "items": []},
            {"ready": True, "items": [{"id": "old", "author": "Alice", "text": "ก่อนเริ่ม"}]},
            {"ready": True, "items": [{"id": "old", "author": "Alice", "text": "ก่อนเริ่ม"},
                                      {"id": "new1", "author": "Bob", "text": "สวัสดีครับ"}]},
            {"ready": True, "items": [{"id": "new1", "author": "Bob", "text": "สวัสดีครับ"},
                                      {"id": "new2", "author": "Bob", "text": "สวัสดีครับ"}]},
        ]
        with patch.object(a, "_evaluate", side_effect=frames):
            self.assertEqual(a.poll().messages, ())
            self.assertFalse(a.dom_ready)
            self.assertEqual(a.phase, "waiting_chat_dom")
            self.assertEqual(a.poll().messages, ())
            self.assertTrue(a.dom_ready)
            self.assertEqual([x.message_id for x in a.poll().messages], ["new1"])
            self.assertEqual([(x.author, x.text) for x in a.poll().messages],
                             [("Bob", "สวัสดีครับ")])
        a.close()

    def test_comments_off_is_not_reported_as_connected_or_as_a_message(self):
        reader = TikTokBrowserAdapter(USERNAME)
        reader._ws = Socket()
        frames = [
            {"ready": False, "status": "comments_off_login_prompt", "items": []},
            {"ready": False, "status": "comments_off", "items": []},
            {"ready": True, "items": [{"id": "previous", "author": "A",
                                      "text": "ประวัติก่อนหน้า"}]},
            {"ready": True, "items": [{"id": "previous", "author": "A",
                                      "text": "ประวัติก่อนหน้า"},
                                     {"id": "latest", "author": "B",
                                      "text": "กลับมาอ่านได้แล้ว"}]},
        ]
        try:
            with patch.object(reader, "_evaluate", side_effect=frames):
                self.assertEqual(reader.poll().messages, ())
                self.assertFalse(reader.dom_ready)
                self.assertEqual(reader.phase, "comments_off_login_prompt")
                self.assertEqual(reader.poll().messages, ())
                self.assertFalse(reader.dom_ready)
                self.assertEqual(reader.phase, "comments_off")
                self.assertEqual(reader.poll().messages, ())
                self.assertTrue(reader.dom_ready)
                self.assertEqual(reader.phase, "ready")
                self.assertEqual([m.text for m in reader.poll().messages],
                                 ["กลับมาอ่านได้แล้ว"])
        finally:
            reader.close()

    def test_login_attempt_limit_is_fatal_and_not_retried(self):
        reader = TikTokBrowserAdapter(USERNAME)
        reader._ws = Socket()
        try:
            with patch.object(reader, "_evaluate", return_value={
                "ready": False, "status": "login_rate_limited", "items": [],
            }) as evaluate:
                with self.assertRaises(SourceFailure) as capture:
                    reader.poll()
                self.assertTrue(capture.exception.fatal)
                self.assertIn("temporarily limited", str(capture.exception))
                self.assertEqual(reader.phase, "login_rate_limited")
                self.assertFalse(reader.dom_ready)
                evaluate.assert_called_once()
        finally:
            reader.close()

    def test_browser_source_manager_does_not_request_api_key(self):
        created = []

        class FakeTikTok:
            transport = "browser-dom"
            phase = "ready"
            dom_ready = True

            def __init__(self, source):
                self.source = source
                self.closed = False
                self.calls = 0
                created.append(self)

            def set_cancel(self, event):
                self.cancel = event

            def close(self):
                self.closed = True

            def poll(self):
                self.calls += 1
                if self.calls == 1:
                    return PollResult((SourceMessage("m1", "Alice", "สวัสดีครับ"),), 1)
                return PollResult((), 1)

        states = ModeState()
        owner = states.activate("tiktok_browser", PlaybackState())
        manager = SourceManager(tiktok_browser_factory=FakeTikTok)
        try:
            result = manager.start({
                "mode": "tiktok_browser", "mode_token": owner["mode_token"],
                "source_id": USERNAME, "credential": "",
                "filters": {"blocked_words": [], "max_chars": 240},
            }, states)
            self.assertEqual(result["mode"], "tiktok_browser")
            for _ in range(30):
                if manager.status("tiktok_browser")["received"] == 1:
                    break
                time.sleep(.05)
            info = manager.status("tiktok_browser")
            self.assertEqual(info["state"], "running")
            self.assertEqual(info["connection_phase"], "ready")
            self.assertEqual(info["transport"], "browser-dom")
            messages = manager.drain({
                "mode": "tiktok_browser", "mode_token": owner["mode_token"], "limit": 10,
            }, states)["messages"]
            self.assertEqual([m["text"] for m in messages], ["สวัสดีครับ"])
            self.assertEqual(created[0].source, USERNAME)
        finally:
            manager.stop_all()
        self.assertTrue(created[0].closed)


if __name__ == "__main__":
    unittest.main()
