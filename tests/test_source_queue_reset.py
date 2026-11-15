"""Reset is a nondestructive queue purge: keep the live source and cursor."""
import unittest
from collections import deque

from voxweavetts.mode_state import ModeState
from voxweavetts.playback_state import PlaybackState
from voxweavetts.processing import InputError
from voxweavetts.source_adapters import SourceMessage
from voxweavetts.source_manager import SourceManager, _Session
from voxweavetts.mode_state import ModeConflict


class FakeAdapter:
    def close(self):
        self.closed = True


class ResetPendingTests(unittest.TestCase):
    def make_session(self):
        manager = SourceManager()
        state = ModeState()
        owner = state.activate("youtube_browser", PlaybackState())
        adapter = FakeAdapter()
        adapter.closed = False
        session = _Session(
            mode="youtube_browser", owner_token=owner["mode_token"],
            source_id="abcdefghijk", adapter=adapter,
            block_words=(), max_chars=240,
        )
        session.pending.extend([
            SourceMessage("old-a", "A", "older"),
            SourceMessage("old-b", "B", "queued"),
        ])
        session.ids.extend(["old-a", "old-b"])
        session.seen.update({"old-a", "old-b"})
        with manager._lock:
            manager._sessions["youtube_browser"] = session
        return manager, state, owner, session, adapter

    def test_reset_only_pending_and_keep_session_and_deduplication(self):
        manager, state, owner, session, adapter = self.make_session()
        try:
            before = manager.wake_snapshot("youtube_browser")["revision"]
            response = manager.reset_pending(
                {"mode": "youtube_browser", "mode_token": owner["mode_token"]}, state)
            self.assertEqual(response["cleared"], 2)
            self.assertTrue(response["connected"])
            self.assertEqual(manager.status("youtube_browser")["pending"], 0)
            self.assertIs(manager._sessions["youtube_browser"], session)
            self.assertFalse(session.cancelled.is_set())
            self.assertFalse(adapter.closed)
            self.assertEqual(session.seen, {"old-a", "old-b"})
            self.assertGreater(manager.wake_snapshot("youtube_browser")["revision"], before)
            # Messages arriving after reset remain deliverable.
            session.pending.append(SourceMessage("new", "C", "latest"))
            result = manager.drain({"mode": "youtube_browser",
                                    "mode_token": owner["mode_token"],
                                    "limit": 10}, state)
            self.assertEqual([m["message_id"] for m in result["messages"]], ["new"])
        finally:
            manager.stop_all()

    def test_http_reset_rejects_wrong_intent_and_keeps_session(self):
        import json
        import threading
        from http.server import ThreadingHTTPServer
        from unittest.mock import patch
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        from voxweavetts.server import Handler

        manager, state, owner, session, adapter = self.make_session()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/v1/sources/reset"
        def post(body, intent):
            request = Request(url, data=json.dumps(body).encode("utf-8"),
                              method="POST", headers={
                "Content-Type": "application/json",
                "X-VoxWeaveTTS-Intent": intent,
                "Origin": f"http://127.0.0.1:{server.server_port}",
            })
            try:
                with urlopen(request, timeout=4) as response:
                    return response.status, json.load(response)
            except HTTPError as error:
                with error:
                    return error.code, json.load(error)
        try:
            with (patch.object(Handler, "_source_manager", return_value=manager),
                  patch.object(Handler, "_mode_state", return_value=state)):
                payload = {"mode": "youtube_browser",
                           "mode_token": owner["mode_token"]}
                status, _ = post(payload, "stop-live-source")
                self.assertEqual(status, 403)
                self.assertEqual(len(session.pending), 2)
                status, response = post(payload, "reset-live-source-queue")
                self.assertEqual(status, 200)
                self.assertEqual(response["cleared"], 2)
                self.assertEqual(manager.status("youtube_browser")["pending"], 0)
                self.assertFalse(adapter.closed)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
            manager.stop_all()

    def test_reset_requires_current_owner_and_known_body(self):
        manager, state, owner, session, _ = self.make_session()
        try:
            with self.assertRaises(ModeConflict):
                manager.reset_pending({"mode": "youtube_browser",
                                       "mode_token": "stale"}, state)
            with self.assertRaises(InputError):
                manager.reset_pending({"mode": "youtube_browser",
                                       "mode_token": owner["mode_token"],
                                       "path": "T:/private"}, state)
            self.assertEqual(len(session.pending), 2)
        finally:
            manager.stop_all()


if __name__ == "__main__":
    unittest.main()
