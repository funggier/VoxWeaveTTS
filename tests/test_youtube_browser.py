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

    def test_switches_top_chat_to_live_before_initial_message_baseline(self):
        reader = YouTubeBrowserAdapter(VIDEO)
        reader._ws = DummySocket()
        frames = [
            {"ready": True, "chat_mode": "switching", "page_visibility": "hidden",
             "items": [{"id": "old-top", "author": "A", "text": "Top only"}]},
            {"ready": True, "chat_mode": "live", "page_visibility": "hidden",
             "items": [{"id": "old-live", "author": "A", "text": "ก่อนเชื่อม"}]},
            {"ready": True, "chat_mode": "live", "page_visibility": "hidden",
             "items": [{"id": "old-live", "author": "A", "text": "ก่อนเชื่อม"},
                       {"id": "new-live", "author": "B", "text": "เห็นข้อความใหม่"}]},
        ]
        with patch.object(reader, "_evaluate", side_effect=frames):
            first = reader.poll()
            self.assertFalse(reader._initialized)
            self.assertFalse(reader.dom_ready)
            self.assertEqual(reader.phase, "switching_live_chat")
            self.assertEqual(first.messages, ())
            self.assertEqual(first.delay_seconds, 0.5)
            self.assertEqual(reader.page_visibility, "hidden")
            self.assertEqual(reader.poll().messages, ())
            self.assertTrue(reader._initialized)
            self.assertEqual(reader.chat_mode, "live")
            final = reader.poll()
            self.assertEqual([m.message_id for m in final.messages], ["new-live"])
        reader.close()

    def test_live_chat_selection_has_bounded_wait_if_youtube_changes_ui(self):
        reader = YouTubeBrowserAdapter(VIDEO)
        reader._ws = DummySocket()
        frame = {"ready": True, "chat_mode": "switching", "items": [
            {"id": "old", "author": "A", "text": "ก่อนเชื่อม"}]}
        with patch.object(reader, "_evaluate", return_value=frame):
            self.assertFalse(reader._initialized)
            self.assertEqual(reader.poll().messages, ())
            reader._live_mode_deadline = time.monotonic() - 1
            self.assertEqual(reader.poll().messages, ())
            self.assertTrue(reader._initialized)
            self.assertEqual(reader.phase, "chat_mode_unconfirmed")
        reader.close()

    def test_background_throttling_disabled_only_for_isolated_browser(self):
        import tempfile
        from pathlib import Path
        from voxweavetts import youtube_browser
        calls = []
        class FakeProcess:
            pid = 123
            def poll(self):
                return None
        with tempfile.TemporaryDirectory() as directory:
            def start(args, **kwargs):
                calls.append(args)
                portfile = Path(directory) / "data" / "browser-profiles" / "youtube-chat" / "DevToolsActivePort"
                portfile.write_text("9333\n/devtools/browser/mock\n", encoding="ascii")
                return FakeProcess()
            with patch.object(youtube_browser, "ROOT", Path(directory)), patch.object(
                youtube_browser, "find_chromium", return_value="chrome.exe"), patch.object(
                youtube_browser.subprocess, "Popen", side_effect=start):
                reader = YouTubeBrowserAdapter(VIDEO)
                reader._launch()
                self.assertEqual(reader._port, 9333)
                args = calls[0]
                for flag in ("--disable-background-timer-throttling",
                             "--disable-backgrounding-occluded-windows",
                             "--disable-renderer-backgrounding",
                             "--disable-features=CalculateNativeWinOcclusion"):
                    self.assertIn(flag, args)
                self.assertIn("--remote-debugging-address=127.0.0.1", args)
                self.assertTrue(any("--user-data-dir=" in a for a in args))
                reader._process = None
                reader.close()

    def test_source_manager_browser_without_api_key(self):
        instances = []

        class FakeBrowser:
            transport = "browser-dom"

            def __init__(self, source):
                self.source = source
                self.closed = False
                self.n = 0
                self.phase = "preparing"
                self.dom_ready = False
                self.chat_mode = "live"
                self.page_visibility = "hidden"
                instances.append(self)

            def set_cancel(self, event):
                self.cancel = event

            def close(self):
                self.closed = True

            def poll(self):
                self.phase = "ready"
                self.dom_ready = True
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
            self.assertEqual(manager.status("youtube_browser")["connection_phase"], "ready")
            self.assertEqual(manager.status("youtube_browser")["chat_mode"], "live")
            self.assertEqual(manager.status("youtube_browser")["page_visibility"], "hidden")
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
