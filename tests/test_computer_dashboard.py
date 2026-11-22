"""Core-owned Browser dashboard remains real after page refresh, without side effects."""
from __future__ import annotations
from http.server import ThreadingHTTPServer
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.computer_runtime import ComputerRuntime
from voxweavetts.server import Handler


class FakeCoordinator:
    def __init__(self):
        self.inspections = 0
        self.jobs = [
            {"speech_id": "job-1", "state": "prepared", "error": None},
            {"speech_id": "job-2", "state": "ready", "error": None},
        ]

    def list(self):
        return [dict(job) for job in self.jobs]

    def staged_revision(self):
        return 3

    def get_prepared_model_inputs(self, job_id):
        self.inspections += 1
        return {"inputs": [{"text": "ข้อความหลังแปลที่ถูกต้อง",
                            "language": "th", "engine_id": "engine-test",
                            "voice_id": "voice-test"}]}

    def get_model_inputs(self, job_id):
        self.inspections += 1
        return {"inputs": [{"text": "เสียงที่สร้างจริง",
                            "language": "th", "engine_id": "engine-test",
                            "voice_id": "voice-test", "success": True}]}


class FakeSources:
    def __init__(self):
        self.drain_count = 0
        self.read_count = 0

    def status(self, mode):
        self.read_count += 1
        return {"mode": mode, "state": "running", "received": 5,
                "discarded": 0, "pending": 2, "runtime_auto_read": True}

    def preview_for_runtime(self, mode, limit=5):
        return {"count": 2, "items": [
            {"message_id": "waiting-1", "author": "A",
             "text": "ต้นทางยังรออยู่", "kind": "comment"}]}

    def take_for_runtime(self, limit=10):
        self.drain_count += 1
        return []

    def wake_all_snapshot(self):
        return {"revision": 4}


def _request(base, path, *, method="GET", data=None, intent="", origin=None):
    headers = {}
    if method == "POST":
        headers = {"Content-Type": "application/json",
                   "X-VoxWeaveTTS-Intent": intent}
        if origin is not None:
            headers["Origin"] = origin
    request = Request(base + path, method=method,
                      data=json.dumps(data).encode("utf-8") if data is not None else None,
                      headers=headers)
    with urlopen(request, timeout=5) as response:
        return response.status, json.load(response)


def test_server_owned_dashboard_is_intent_gated_and_reopen_is_readonly(tmp_path):
    sources = FakeSources()
    coordinator = FakeCoordinator()
    runtime = ComputerRuntime(port=8775, coordinator=coordinator,
                              source_manager=sources, playback_state=object(),
                              mode_path=tmp_path / "runtime.json",
                              initial_mode="computer")
    runtime._recent_messages["youtube_browser"].extend([
        {"message_id": "j1", "author": "Viewer1", "text": "raw chat secret",
         "speech_id": "job-1", "state": "queued", "created_at": ""},
        {"message_id": "j2", "author": "Viewer2", "text": "อีกข้อความ",
         "speech_id": "job-2", "state": "queued", "outcome": "read",
         "model_inputs": [{"text": "เสียงที่สร้างจริง",
                           "language": "th", "engine_id": "engine-test",
                           "voice_id": "voice-test"}],
         "created_at": ""},
    ])
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.runtime_control = runtime
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, public = _request(base, "/v1/runtime/state")
        assert status == 200 and public["mode"] == "computer"
        assert public["version"]
        with urlopen(base + "/computer_dashboard.js", timeout=4) as response:
            script = response.read().decode("utf-8")
            assert "inspect-runtime-dashboard" in script
            assert response.status == 200
        assert public["dashboard_cursor"] == "0:0:3:4"
        assert "raw chat secret" not in json.dumps(public)
        assert "เสียงที่สร้างจริง" not in json.dumps(public)
        for origin, intent in ((None, "inspect-runtime-dashboard"),
                               (base, "invalid-intent"),
                               ("http://evil.example", "inspect-runtime-dashboard")):
            try:
                _request(base, "/v1/runtime/dashboard", method="POST", data={},
                         origin=origin, intent=intent)
                assert False, "unauthorized private dashboard accepted"
            except HTTPError as exc:
                assert exc.code == 403
        for iteration in range(2):  # simulated refresh/reopen, no restart
            status, data = _request(base, "/v1/runtime/dashboard", method="POST",
                                    data={}, origin=base,
                                    intent="inspect-runtime-dashboard")
            assert status == 200 and data["mode"] == "computer"
            yt = data["sources"]["youtube_browser"]
            assert yt["counts"]["queued"] == 2  # source-owned pending
            assert yt["counts"]["prepared"] == 1
            assert yt["counts"]["read"] == 1
            assert yt["pipeline"][0]["inputs"][0]["text"] == "ข้อความหลังแปลที่ถูกต้อง"
            assert yt["model_history"][0]["inputs"][0]["text"] == "เสียงที่สร้างจริง"
            assert yt["recent"][0]["text"] == "อีกข้อความ"
            assert yt["source_pending_items"][0]["text"] == "ต้นทางยังรออยู่"
            assert sources.drain_count == 0
            assert runtime._completed == 0
        try:
            _request(base, "/v1/runtime/dashboard", method="POST",
                     data={"mode": "browser"}, origin=base,
                     intent="inspect-runtime-dashboard")
            assert False, "unexpected POST parameters accepted"
        except HTTPError as exc:
            assert exc.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_recent_history_is_bounded_and_persists_without_browser(tmp_path):
    core = ComputerRuntime(port=8775, coordinator=FakeCoordinator(),
                           source_manager=FakeSources(), playback_state=object(),
                           mode_path=tmp_path / "runtime.json",
                           initial_mode="computer")
    for index in range(200):
        core._recent_messages["discord"].append({
            "message_id": str(index), "text": "message "+str(index),
            "state": "queued", "speech_id": None})
    assert len(core._recent_messages["discord"]) == 120
    assert core.dashboard()["sources"]["discord"]["recent"][0]["message_id"] == "199"
    assert len(core.dashboard()["sources"]["discord"]["recent"]) == 80
