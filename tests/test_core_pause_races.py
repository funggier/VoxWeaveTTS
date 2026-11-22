"""Stop during Core HTTP handoff and local TikFinity transient WS disconnect."""
from __future__ import annotations

import threading
from pathlib import Path

from voxweavetts.computer_runtime import ComputerRuntime
from voxweavetts.tikfinity_core import TikFinityCoreAdapter


class Coordinator:
    def __init__(self):
        self.jobs = [{"speech_id": "late", "source": "youtube-live", "state": "preparing"}]
        self.cancelled = []

    def list(self):
        return [dict(entry) for entry in self.jobs]

    def cancel(self, job_id):
        self.cancelled.append(job_id)
        for job in self.jobs:
            if job["speech_id"] == job_id:
                job["state"] = "cancelled"


class Sources:
    def __init__(self):
        self.messages = [("live", {"message_id": "event-1", "text": "spoken text"})]

    def take_for_runtime(self, limit):
        answer = self.messages[:limit]
        self.messages = self.messages[limit:]
        return answer

    def status(self, mode):
        return {"mode": mode, "pending": len(self.messages), "state": "idle"}


def test_global_pause_inflight_admission_preserves_pending_for_resume(tmp_path):
    sources, coordinator = Sources(), Coordinator()
    runtime = ComputerRuntime(port=8775, coordinator=coordinator,
                              source_manager=sources, playback_state=object(),
                              mode_path=tmp_path/"runtime.json",
                              initial_mode="computer")
    entered, allowed = threading.Event(), threading.Event()

    def submit(mode, msg):
        entered.set()
        assert allowed.wait(timeout=3)
        return "late"

    runtime._enqueue_via_api = submit
    worker = threading.Thread(target=runtime._drain_sources)
    worker.start()
    try:
        assert entered.wait(timeout=2)
        assert runtime.stop_audio()["playback_paused"] is True
    finally:
        allowed.set()
        worker.join(timeout=3)
    assert not worker.is_alive()
    assert coordinator.cancelled == ["late"]
    assert len(runtime._pending_messages) == 1
    assert runtime._pending_messages[0][1]["message_id"] == "event-1"
    assert runtime.resume_audio()["playback_paused"] is False


def test_tikfinity_transient_disconnect_can_reconnect_but_explicit_stop_cannot():
    adapter = TikFinityCoreAdapter("ws://localhost:21213/")
    adapter._drop_connection()
    assert not adapter._closed
    assert adapter._socket is None
    adapter.close()
    assert adapter._closed
