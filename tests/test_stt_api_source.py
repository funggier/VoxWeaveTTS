"""VoxWeaveSTT final-transcript API integration: real HTTP, no STT model."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

import pytest

from voxweavetts.processing import InputError
from voxweavetts.mode_state import ModeState
from voxweavetts.source_manager import SourceManager
from voxweavetts.stt_api_source import VoxWeaveSTTAdapter


class STTMock(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), MockHandler)
        self.active_id = None
        self.events = {}
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    def start_session(self, sid):
        self.active_id = sid
        self.events.setdefault(sid, [])

    def send_final(self, text, segment=None):
        sid = self.active_id
        assert sid
        sequence = len(self.events[sid]) + 1
        self.events[sid].append({
            "type": "transcript.final", "session_id": "capture-" + sid,
            "source_id": "mic", "segment_id": segment or str(sequence),
            "revision": 0, "api_sequence": sequence, "text": text,
        })

    def close(self):
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=2)


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        from urllib.parse import urlsplit, parse_qs
        route = urlsplit(self.path)
        if route.path == "/api/status":
            sid = self.server.active_id
            active = ({
                "id": sid, "event_sequence": len(self.server.events[sid]),
                "status": "running"
            } if sid else None)
            response = {"api_version": 1, "active": active}
        elif route.path.startswith("/api/sessions/") and route.path.endswith("/events"):
            sid = route.path.split("/")[3]
            if sid not in self.server.events:
                self.send_response(404)
                self.end_headers()
                return
            cursor = int(parse_qs(route.query).get("after", ["0"])[0])
            matching = self.server.events[sid][cursor:cursor + 200]
            next_cursor = matching[-1]["api_sequence"] if matching else cursor
            response = {
                "events": matching, "last_sequence": next_cursor,
                "total_sequence": len(self.server.events[sid]),
                "has_more": next_cursor < len(self.server.events[sid]),
            }
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def stt():
    server = STTMock()
    try:
        yield server
    finally:
        server.close()


def adapter(stt):
    return VoxWeaveSTTAdapter(f"http://127.0.0.1:{stt.server_port}")


def test_new_transcript_session_and_stop_flush(stt):
    consumer = adapter(stt)
    assert consumer.poll().messages == ()
    sid = "a" * 32
    stt.start_session(sid)
    stt.send_final("สวัสดีครับ")
    first = consumer.poll()
    assert [item.text for item in first.messages] == ["สวัสดีครับ"]
    assert consumer.poll().messages == ()
    stt.send_final("Hello world")
    assert [i.text for i in consumer.poll().messages] == ["Hello world"]
    stt.send_final("ช่วงสุดท้าย")
    stt.active_id = None
    assert [i.text for i in consumer.poll().messages] == ["ช่วงสุดท้าย"]
    assert consumer.poll().messages == ()
    stt.start_session("b" * 32)
    stt.send_final("ข้อความใหม่")
    assert [i.text for i in consumer.poll().messages] == ["ข้อความใหม่"]


def test_initial_connection_skips_historical_final_events(stt):
    stt.start_session("a" * 32)
    stt.send_final("ข้อความเก่าก่อนเชื่อม")
    consumer = adapter(stt)
    assert consumer.poll().messages == ()
    stt.send_final("ข้อความหลังเชื่อม")
    assert [i.text for i in consumer.poll().messages] == ["ข้อความหลังเชื่อม"]


def test_rejects_unsafe_hosts_and_lan_without_certificate():
    for url in ("http://192.168.1.9:8766", "http://8.8.8.8:8766",
                "http://127.0.0.1:99999", "http://127.0.0.1:8766/path",
                "http://localhost@8.8.8.8:8766"):
        with pytest.raises(InputError):
            VoxWeaveSTTAdapter(url)
    with pytest.raises(InputError):
        VoxWeaveSTTAdapter("https://192.168.1.9:8768", {"pin": "12345678", "fingerprint": ""})


def test_source_manager_computer_runtime_queue_path(stt):
    states = ModeState()
    credentials = states.activate("stt_api", None)
    manager = SourceManager()
    try:
        manager.start({
            "mode": "stt_api", "mode_token": credentials["mode_token"],
            "source_id": f"http://127.0.0.1:{stt.server_port}",
            "credential": "",
            "filters": {"blocked_words": [], "max_chars": 8000},
            "runtime_auto_read": True,
        }, states)
        cutoff = time.monotonic() + 4
        while manager.status("stt_api")["polls"] == 0 and time.monotonic() < cutoff:
            time.sleep(0.02)
        assert manager.status("stt_api")["polls"] > 0
        stt.start_session("c" * 32)
        stt.send_final("สวัสดีระบบคิว")
        while manager.status("stt_api")["received"] == 0 and time.monotonic() < cutoff:
            time.sleep(0.03)
        assert manager.status("stt_api")["received"] == 1
        preview = manager.preview_for_runtime("stt_api")
        assert preview["count"] == 1
        assert len(preview["items"]) == 1
        assert preview["items"][0]["text"]  # Genuine STT final payload, not a placeholder.
        got = manager.take_for_runtime()
        assert len(got) == 1
        assert got[0][0] == "stt_api"
        assert got[0][1]["text"] == "สวัสดีระบบคิว"
        manager.stop({"mode": "stt_api", "mode_token": credentials["mode_token"]}, states)
        assert manager.status("stt_api")["state"] == "idle"
    finally:
        manager.stop_all()
