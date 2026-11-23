"""Browser-reopened Core controls must affect the actual source, not tab-local state."""
from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.computer_runtime import ComputerRuntime
from voxweavetts.server import Handler
from voxweavetts.source_manager import SourceManager, _Session
from voxweavetts.source_adapters import SourceMessage


class Jobs:
    def __init__(self):
        self.jobs = []
        self.cancelled = []

    def list(self):
        return [dict(job) for job in self.jobs]

    def staged_revision(self):
        return 0

    def get_prepared_model_inputs(self, job_id):
        return {"inputs": [{"text": "ข้อความเข้าโมเดลจริง", "language": "th"}]}

    def get_model_inputs(self, job_id):
        return {"inputs": [{"text": "เสียงสร้างจริง", "language": "th", "success": True}]}

    def cancel(self, job_id):
        self.cancelled.append(job_id)


def source_setup(tmp_path):
    sources = SourceManager()
    s = _Session(
        "stt_api", "browser-owner-token-that-is-not-available-after-refresh",
        "http://127.0.0.1:8766", object(), (), 8000,
        runtime_auto_read=True,
    )
    s.state = "running"
    sources._sessions["stt_api"] = s
    jobs = Jobs()
    runtime = ComputerRuntime(
        port=8775, coordinator=jobs, source_manager=sources,
        playback_state=object(), mode_path=tmp_path / "runtime-control.json",
        initial_mode="computer",
    )
    return runtime, sources, s, jobs


def test_browser_controls_use_same_origin_core_status_after_refresh(tmp_path):
    runtime, sources, session, jobs = source_setup(tmp_path)
    session.pending.append(SourceMessage("new", "speaker", "incoming STT final"))
    runtime._pending_messages.append(
        ("stt_api", {"message_id": "buffered", "author": "speaker",
                     "text": "already taken from source"}))
    runtime._recent_messages["stt_api"].append({
        "message_id": "buffered", "text": "already taken from source",
        "state": "queued", "speech_id": None,
    })
    jobs.jobs = [{"speech_id": "accepted", "state": "ready",
                  "source": "voxweave-stt", "error": None}]
    runtime._recent_messages["stt_api"].append({
        "message_id": "accepted-1", "text": "will continue playing",
        "speech_id": "accepted", "state": "queued",
    })
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.runtime_control = runtime
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def post(path, data, intent, origin=base):
        req = Request(base + path,
                      data=json.dumps(data).encode("utf-8"),
                      method="POST", headers={
                          "Origin": origin,
                          "Content-Type": "application/json",
                          "X-VoxWeaveTTS-Intent": intent,
                      })
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as err:
            return err.code, json.load(err)

    try:
        opts = "/v1/runtime/source/options"
        reset = "/v1/runtime/source/reset"
        assert post(opts, {"mode": "stt_api", "runtime_auto_read": False},
                    "wrong-intent")[0] == 403
        assert post(opts, {"mode": "stt_api", "runtime_auto_read": False},
                    "set-core-source-options", "http://malicious.invalid")[0] == 403
        assert post(opts, {"mode": "stt_api", "runtime_auto_read": "false"},
                    "set-core-source-options")[0] == 400
        code, applied = post(opts, {"mode": "stt_api", "runtime_auto_read": False},
                             "set-core-source-options")
        assert code == 200 and applied["runtime_auto_read"] is False
        assert sources.status("stt_api")["runtime_auto_read"] is False
        # A second fresh Browser sees the same Core setting without ownership
        # transfer or a duplicate source connection.
        code, applied = post(opts, {"mode": "stt_api", "runtime_auto_read": True},
                             "set-core-source-options")
        assert code == 200 and applied["runtime_auto_read"] is True
        assert len(sources._sessions) == 1 and sources._sessions["stt_api"] is session
        assert post(reset, {"mode": "stt_api"}, "wrong-intent")[0] == 403
        assert post(reset, {"mode": "non-existent"}, "reset-core-source-queue")[0] == 400
        code, cleared = post(reset, {"mode": "stt_api"}, "reset-core-source-queue")
        assert code == 200 and cleared["cleared"] == 2
        assert cleared["connected"] is True
        assert not session.pending and not runtime._pending_messages
        assert jobs.cancelled == []
        dashboard = runtime.dashboard()["sources"]["stt_api"]
        assert dashboard["counts"]["cleared"] == 1
        assert dashboard["counts"]["ready"] == 1
        assert dashboard["pipeline"][0]["speech_id"] == "accepted"
        assert sources.status("stt_api")["state"] == "running"
        assert post(reset, {"mode": "stt_api"}, "reset-core-source-queue")[1]["cleared"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_queue_reset_cancels_only_http_admission_in_flight(tmp_path):
    runtime, sources, session, jobs = source_setup(tmp_path)
    runtime._pending_messages.append(("stt_api", {
        "message_id": "inflight", "author": "STT", "text": "still admitting"}))
    runtime._recent_messages["stt_api"].append({
        "message_id": "inflight", "text": "still admitting",
        "speech_id": None, "state": "queued",
    })
    started = threading.Event()
    release = threading.Event()

    def delayed_admission(_mode, _message):
        started.set()
        assert release.wait(4)
        return "new-unstarted-job"

    runtime._enqueue_via_api = delayed_admission
    worker = threading.Thread(target=runtime._drain_sources, daemon=True)
    worker.start()
    try:
        assert started.wait(4)
        result = runtime.reset_source_pending("stt_api")
        assert result["cleared"] == 1
    finally:
        release.set()
        worker.join(timeout=5)
    assert not worker.is_alive()
    assert jobs.cancelled == ["new-unstarted-job"]
    assert not runtime._pending_messages
    dashboard = runtime.dashboard()["sources"]["stt_api"]
    assert dashboard["counts"]["cleared"] == 1
    assert dashboard["counts"]["queued"] == 0

def test_queue_reset_ignores_messages_taken_from_source_during_reset(tmp_path):
    """Reset wins even when SourceManager had already removed a message."""
    runtime, sources, session, jobs = source_setup(tmp_path)
    session.pending.append(SourceMessage("lost-in-flight", "speaker", "one STT final"))
    taken = threading.Event()
    allow_return = threading.Event()
    original_take = sources.take_for_runtime

    def delayed_take(*, limit):
        messages = original_take(limit=limit)
        taken.set()
        assert allow_return.wait(4)
        return messages

    sources.take_for_runtime = delayed_take
    worker = threading.Thread(target=runtime._drain_sources, daemon=True)
    worker.start()
    try:
        assert taken.wait(4)
        result = runtime.reset_source_pending("stt_api")
        assert result["pending"] == 0
    finally:
        allow_return.set()
        worker.join(timeout=5)
    assert not worker.is_alive()
    assert not session.pending
    assert not runtime._pending_messages
    assert runtime.dashboard()["sources"]["stt_api"]["counts"]["queued"] == 0
    assert not jobs.cancelled
