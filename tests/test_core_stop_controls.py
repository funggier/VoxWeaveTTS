"""Core stop controls must survive Browser refresh and never auto-resume."""
from __future__ import annotations
from collections import deque
from http.server import ThreadingHTTPServer
import json
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from voxweavetts.computer_runtime import ComputerRuntime, read_mode
from voxweavetts.server import Handler


class FakeSources:
    def __init__(self):
        self.stopped = []
        self.pending = []

    def stop_mode(self, mode):
        self.stopped.append(mode)
        self.pending = [x for x in self.pending if x[0] != mode]

    def status(self, mode):
        return {"state": "idle" if mode in self.stopped else "running",
                "mode": mode, "pending": sum(1 for x in self.pending if x[0] == mode)}

    def take_for_runtime(self, limit):
        out = self.pending[:limit]
        self.pending = self.pending[limit:]
        return out


class FakeCoordinator:
    def __init__(self, jobs=()):
        self.jobs = list(jobs)
        self.cancelled = []
        self.rendered = []
        self.read = []

    def list(self):
        return [dict(job) for job in self.jobs]

    def cancel(self, speech_id):
        self.cancelled.append(speech_id)
        for job in self.jobs:
            if job["speech_id"] == speech_id:
                job["state"] = "cancelled"
                break

    def start_render(self, speech_id):
        self.rendered.append(speech_id)


class FakePlayback:
    def report(self, *args, **kwargs):
        pass


def make_core(tmp_path, *, coordinator=None, sources=None):
    return ComputerRuntime(port=8775,
            coordinator=coordinator or FakeCoordinator(),
            source_manager=sources or FakeSources(), playback_state=FakePlayback(),
            mode_path=tmp_path / "runtime-control.json",
            initial_mode="computer")


def test_fresh_install_defaults_to_core_but_preserves_explicit_browser(tmp_path):
    path = tmp_path / "runtime-control.json"
    assert read_mode(path) == "computer"
    path.write_text('{"mode": "browser"}', encoding="utf-8")
    assert read_mode(path) == "browser"


def test_stop_audio_pauses_all_dispatch_until_explicit_resume(tmp_path):
    core = make_core(tmp_path)
    assert not core.snapshot()["playback_paused"]
    core._replays.append((b"audio", {"source": "youtube-live"}))
    result = core.stop_audio()
    assert result["playback_paused"] is True
    assert result["audio_state"] == "paused"
    assert core._stop_audio.is_set()
    assert not core._replays
    core._pending_messages.append(("live", {"message_id": "m1", "text": "hello"}))
    core._enqueue_via_api = lambda *args: pytest.fail("paused Core must not submit")
    core._drain_sources()
    assert len(core._pending_messages) == 1
    assert core.resume_audio()["playback_paused"] is False
    assert core.snapshot()["audio_state"] == "idle"


def test_stop_source_cancels_only_that_live_mode_and_stops_playback(tmp_path):
    jobs = [
        {"speech_id": "live-1", "source": "youtube-live", "state": "prepared"},
        {"speech_id": "live-2", "source": "youtube-live", "state": "ready"},
        {"speech_id": "discord-1", "source": "discord", "state": "ready"},
        {"speech_id": "client-1", "source": "discord-client", "state": "prepared"},
    ]
    coordinator = FakeCoordinator(jobs)
    sources = FakeSources()
    core = make_core(tmp_path, coordinator=coordinator, sources=sources)
    core._pending_messages.extend([
        ("live", {"message_id": "one", "text": "1"}),
        ("discord", {"message_id": "two", "text": "2"}),
    ])
    core._recent_messages["live"].append({
        "message_id": "one", "text": "1", "speech_id": "live-1",
        "state": "prepared"
    })
    core._active_workspace = "live"
    core._active_id = "live-2"
    assert core.stop_source("live")["cancelled_jobs"] == 2
    assert sources.stopped == ["live"]
    assert core._stop_audio.is_set()
    assert coordinator.cancelled == ["live-1", "live-2"]
    assert list(core._pending_messages) == [
        ("discord", {"message_id": "two", "text": "2"})]
    assert core._recent_messages["live"][0]["outcome"] == "stopped"
    assert not core._playback_paused
    assert "live" in core.snapshot()["stopped_sources"]
    core.resume_source("live")
    assert "live" not in core.snapshot()["stopped_sources"]
    assert "discord" not in sources.stopped


def test_stop_client_does_not_cancel_discord(tmp_path):
    jobs = [
        {"speech_id": "bot", "source": "discord", "state": "ready"},
        {"speech_id": "client", "source": "discord-client", "state": "ready"},
    ]
    coordinator = FakeCoordinator(jobs)
    core = make_core(tmp_path, coordinator=coordinator)
    core.stop_source("discord_client")
    assert coordinator.cancelled == ["client"]


def test_stop_during_source_submission_cancels_late_job(tmp_path):
    jobs = [{"speech_id": "late-job", "source": "youtube-live", "state": "preparing"}]
    coordinator = FakeCoordinator(jobs)
    sources = FakeSources()
    core = make_core(tmp_path, coordinator=coordinator, sources=sources)
    sources.pending = [("live", {"message_id": "m1", "text": "slow request"})]
    entered, proceed = threading.Event(), threading.Event()

    def submit(mode, msg):
        entered.set()
        assert proceed.wait(3), "test submission must be released"
        return "late-job"

    core._enqueue_via_api = submit
    worker = threading.Thread(target=core._drain_sources)
    worker.start()
    try:
        assert entered.wait(2)
        core.stop_source("live")
    finally:
        proceed.set()
        worker.join(3)
    assert not worker.is_alive()
    assert coordinator.cancelled.count("late-job") >= 1
    assert core._recent_messages["live"][0]["outcome"] == "stopped"
    assert not core._pending_messages


def test_browser_can_stop_core_source_after_refresh_and_resume_only_by_request(tmp_path):
    coordinator = FakeCoordinator([
        {"speech_id": "job1", "source": "youtube-live", "state": "ready"}])
    core = make_core(tmp_path, coordinator=coordinator)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.runtime_control = core
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def post(path, payload, intent, origin=base):
        headers = {"Content-Type": "application/json",
                   "X-VoxWeaveTTS-Intent": intent,
                   "Origin": origin}
        request = Request(base + path, method="POST",
                          data=json.dumps(payload).encode("utf-8"),
                          headers=headers)
        with urlopen(request, timeout=3) as response:
            return response.status, json.load(response)

    try:
        with pytest.raises(HTTPError) as invalid:
            post("/v1/runtime/source/stop", {"mode": "live"},
                 "wrong-intent")
        assert invalid.value.code == 403
        with pytest.raises(HTTPError) as foreign:
            post("/v1/runtime/source/stop", {"mode": "live"},
                 "stop-core-source", origin="http://evil.example")
        assert foreign.value.code == 403
        code, stopped = post("/v1/runtime/source/stop",
                             {"mode": "live"}, "stop-core-source")
        assert code == 200 and stopped["cancelled_jobs"] == 1
        assert coordinator.cancelled == ["job1"]
        code, paused = post("/v1/runtime/playback",
                             {"action": "stop"}, "control-computer-playback")
        assert code == 200 and paused["playback_paused"]
        code, resumed = post("/v1/runtime/playback",
                              {"action": "resume"}, "control-computer-playback")
        assert code == 200 and not resumed["playback_paused"]
        assert "live" in resumed["stopped_sources"], (
            "resuming audio must NOT restart an explicitly stopped source")
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(3)

def test_stop_before_worker_start_blocks_ready_audio_until_resume(tmp_path):
    import time
    class ReadyCoordinator(FakeCoordinator):
        def audio(self, speech_id):
            return b"pcm-payload"
    class RecordingOutput:
        def __init__(self):
            self.played = []
        def play(self, wav, duration_ms, stop, progress, target):
            self.played.append(wav)
            progress(duration_ms)
            return not stop.is_set()
    jobs = [{"speech_id": "ready-1", "source": "youtube-live",
             "state": "ready", "audio": {"duration_ms": 70}}]
    coordinator = ReadyCoordinator(jobs)
    output = RecordingOutput()
    core = ComputerRuntime(
        port=8775, coordinator=coordinator,
        source_manager=FakeSources(), playback_state=FakePlayback(),
        output=output, mode_path=tmp_path / "runtime.json",
        initial_mode="computer",
    )
    core.stop_audio()
    core.start()
    try:
        time.sleep(0.15)
        assert output.played == [], "stop must park worker without replaying queued WAV"
        assert coordinator.rendered == []
        core.resume_audio()
        deadline = time.monotonic() + 2
        while not output.played and time.monotonic() < deadline:
            time.sleep(0.01)
        assert output.played == [b"pcm-payload"]
        assert core.snapshot()["completed"] == 1
    finally:
        core.shutdown()
