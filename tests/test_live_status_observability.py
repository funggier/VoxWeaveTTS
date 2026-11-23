"""Regression: every Core Live source must expose truthful, bounded UI status.

No browser controls or live source connections are started in these tests.
"""
from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
import threading
from urllib.request import Request, urlopen

from voxweavetts.computer_runtime import ComputerRuntime, SOURCE_NAMES
from voxweavetts.server import Handler
from voxweavetts.source_manager import SourceManager


class Coordinator:
    def __init__(self):
        self.jobs = []
        self.inspections = []

    def list(self):
        return [dict(job) for job in self.jobs]

    def staged_revision(self):
        return 7

    def get_prepared_model_inputs(self, job_id):
        self.inspections.append(("prepared", job_id))
        return {"inputs": [{"text": "ข้อความที่จะส่งเข้า TTS " + job_id,
                            "language": "th", "engine_id": "test-engine",
                            "voice_id": "test-voice"}]}

    def get_model_inputs(self, job_id):
        self.inspections.append(("ready", job_id))
        return {"inputs": [{"text": "เสียงที่สร้างจริง " + job_id,
                            "language": "th", "engine_id": "test-engine",
                            "voice_id": "test-voice", "success": True}]}

    def audio(self, job_id):
        return b"fake-wav-data"


def make_runtime(tmp_path):
    source = SourceManager()
    jobs = Coordinator()
    runtime = ComputerRuntime(
        port=8775, coordinator=jobs, source_manager=source,
        playback_state=object(), mode_path=tmp_path / "runtime.json",
        initial_mode="computer",
    )
    return runtime, source, jobs


def test_real_source_manager_core_dashboard_covers_all_live_modes(tmp_path):
    runtime, sources, coordinator = make_runtime(tmp_path)
    try:
        # This used to raise InputError for 'stt_api', breaking the entire
        # /v1/runtime/dashboard response (including YouTube and Discord).
        assert sources.preview_for_runtime("stt_api") == {
            "count": 0, "items": []}
        data = runtime.dashboard()
        assert set(data["sources"]) == set(SOURCE_NAMES)
        assert data["sources"]["stt_api"]["counts"]["queued"] == 0
        assert data["sources"]["youtube_browser"]["pipeline"] == []

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.runtime_control = runtime
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            status = json.load(urlopen(base + "/v1/runtime/state", timeout=5))
            assert "dashboard_cursor" in status
            assert "sources" in status
            req = Request(
                base + "/v1/runtime/dashboard",
                data=b"{}",
                headers={
                    "Origin": base,
                    "Content-Type": "application/json",
                    "X-VoxWeaveTTS-Intent": "inspect-runtime-dashboard",
                },
                method="POST",
            )
            with urlopen(req, timeout=5) as response:
                result = json.load(response)
                assert response.status == 200
                assert set(result["sources"]) == set(SOURCE_NAMES)
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()
    finally:
        sources.stop_all()


def test_currently_reading_stt_is_not_hidden_behind_old_pending_jobs(tmp_path):
    runtime, sources, jobs = make_runtime(tmp_path)
    try:
        for index in range(12):
            job_id = f"prior-{index}"
            jobs.jobs.append({"speech_id": job_id, "state": "prepared",
                              "error": None, "source": "voxweave-stt"})
            runtime._recent_messages["stt_api"].append({
                "message_id": str(index), "author": "STT",
                "text": "ต้นฉบับก่อนหน้า", "speech_id": job_id,
                "state": "queued", "created_at": "",
            })
        jobs.jobs.append({"speech_id": "current", "state": "ready",
                          "error": None, "source": "voxweave-stt"})
        runtime._recent_messages["stt_api"].append({
            "message_id": "latest", "author": "STT",
            "text": "ต้นฉบับกำลังอ่าน", "speech_id": "current",
            "state": "queued", "created_at": "",
        })
        runtime._active_id = "current"
        data = runtime.dashboard()["sources"]["stt_api"]
        assert data["counts"]["reading"] == 1
        assert data["pipeline"][0]["speech_id"] == "current"
        assert data["pipeline"][0]["state"] == "reading"
        assert data["pipeline"][0]["inputs"][0]["text"] == "เสียงที่สร้างจริง current"
        assert len(data["pipeline"]) <= 8

        # The active workspace is STT, not "studio". Per-source STOP should
        # therefore be able to target its current playback.
        runtime._play_audio = lambda _wav, _job, workspace, **_kwargs: workspace
        assert runtime._play_job(jobs.jobs[-1]) == "stt_api"
    finally:
        sources.stop_all()


def test_failed_jobs_keep_their_actual_outcome_after_coordinator_prunes(tmp_path):
    runtime, sources, jobs = make_runtime(tmp_path)
    try:
        runtime._recent_messages["discord"].append({
            "message_id": "failed-1", "author": "Someone",
            "text": "ข้อความทดสอบผิดพลาด", "speech_id": "missing-wav",
            "state": "queued",
        })
        runtime._remember_terminal_job({
            "speech_id": "missing-wav", "state": "failed",
            "error": "เสียงสร้างไม่สำเร็จ",
        })
        # The coordinator no longer holds the job after TTL cleanup.
        jobs.jobs.clear()
        history = runtime.dashboard()["sources"]["discord"]
        assert history["counts"]["failed"] == 1
        assert history["recent"][0]["state"] == "failed"
        assert history["recent"][0]["error"] == "เสียงสร้างไม่สำเร็จ"
        assert runtime.snapshot()["dashboard_cursor"].split(":")[1] == "1"
    finally:
        sources.stop_all()