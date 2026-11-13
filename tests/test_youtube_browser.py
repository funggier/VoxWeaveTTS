"""YouTube chat-only browser adapter: URL safety, new-only messages and lifecycle."""
import threading
import time
import unittest
from unittest.mock import patch

from voxweavetts.mode_state import ModeState
from voxweavetts.processing import InputError
from voxweavetts.source_adapters import PollResult, SourceMessage
from voxweavetts.source_manager import SourceManager
from voxweavetts.youtube_browser import YouTubeBrowserAdapter, video_id_from_input


VIDEO = "abcdefghijk"


class DummySocket:
    def close(self):
        pass


class BrowserAdapterTests(unittest.TestCase):
    def test_accept_video_id_and_safe_youtube_urls_only(self):
        for value in (VIDEO, "https://www.youtube.com/watch?v=" + VIDEO,
                      "https://youtu.be/" + VIDEO,
                      "https://youtube.com/live/" + VIDEO,
                      "https://www.youtube.com/live_chat?v=" + VIDEO):
            self.assertEqual(video_id_from_input(value), VIDEO)
        for value in ("", "not-a-video-too-long", "http://youtube.com/watch?v=" + VIDEO,
                      "https://youtube.com.evil.tld/watch?v=" + VIDEO,
                      "https://evil.tld/" + VIDEO,
                      "https://youtube.com/watch?v=" + VIDEO + "Z"):
            with self.subTest(value=value), self.assertRaises(InputError):
                video_id_from_input(value)

    def test_only_new_messages_and_duplicate_text_from_different_ids(self):
        a = YouTubeBrowserAdapter(VIDEO)
        a._ws = DummySocket()
        frames = [
            {"ready": False, "items": []},
            {"ready": True, "items": [{"id": "old", "author": "P", "text": "ก่อนเชื่อม"}]},
            {"ready": True, "items": [{"id": "old", "author": "P", "text": "ก่อนเชื่อม"},
                                      {"id": "new1", "author": "ผู้ชม A", "text": "สวัสดีครับ"}]},
            {"ready": True, "items": [{"id": "new1", "author": "ผู้ชม A", "text": "สวัสดีครับ"},
                                      {"id": "new2", "author": "ผู้ชม A", "text": "สวัสดีครับ"}]},
        ]
        with patch.object(a, "_evaluate", side_effect=frames):
            self.assertEqual(a.poll().messages, ())
            self.assertEqual(a.poll().messages, ())
            self.assertEqual([(x.author, x.text) for x in a.poll().messages],
                             [("ผู้ชม A", "สวัสดีครับ")])
            self.assertEqual([x.message_id for x in a.poll().messages], ["new2"])
        a.close()

    def test_source_manager_browser_without_api_key(self):
        instances = []

        class FakeBrowser:
            transport = "browser-dom"

            def __init__(self, source):
                self.source = source
                self.closed = False
                self.n = 0
                instances.append(self)

            def set_cancel(self, event):
                self.cancel = event

            def close(self):
                self.closed = True

            def poll(self):
                self.n += 1
                if self.n == 1:
                    return PollResult((SourceMessage("one", "ผู้ชม", "ทดสอบสด"),), 0.1)
                return PollResult((), 1)

        from voxweavetts.playback_state import PlaybackState
        states = ModeState()
        owner = states.activate("youtube_browser", PlaybackState())
        manager = SourceManager(browser_factory=FakeBrowser)
        data = {
            "mode": "youtube_browser", "mode_token": owner["mode_token"],
            "source_id": VIDEO, "credential": "", "filters": {"blocked_words": [], "max_chars": 240},
        }
        try:
            first = manager.start(data, states)
            self.assertEqual(first["mode"], "youtube_browser")
            for _ in range(30):
                if manager.status("youtube_browser")["received"] == 1:
                    break
                time.sleep(0.05)
            self.assertEqual(manager.status("youtube_browser")["transport"], "browser-dom")
            self.assertEqual(manager.status("youtube_browser")["received"], 1)
            messages = manager.drain({"mode": "youtube_browser",
                                      "mode_token": owner["mode_token"],
                                      "limit": 10}, states)["messages"]
            self.assertEqual([m["text"] for m in messages], ["ทดสอบสด"])
            self.assertEqual(instances[0].source, VIDEO)
        finally:
            manager.stop_all()
        self.assertTrue(instances[0].closed)


if __name__ == "__main__":
    unittest.main()
