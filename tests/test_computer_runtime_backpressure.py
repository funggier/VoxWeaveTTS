"""Computer-owned Live input must remain bounded, ordered and separate sender text."""
from __future__ import annotations
from collections import deque
import json
from types import SimpleNamespace

from voxweavetts.computer_runtime import ComputerRuntime


class Coordinator:
    def __init__(self, jobs=None):
        self.jobs = list(jobs or [])
        self.rendered = []

    def list(self):
        return [dict(item) for item in self.jobs]

    def start_render(self, speech_id):
        self.rendered.append(speech_id)


class Sources:
    def __init__(self, messages=None):
        self.messages = deque(messages or [])
        self.taken = 0

    def status(self, mode):
        return {"mode": mode, "state": "idle", "pending": len(self.messages)}

    def take_for_runtime(self, limit=10):
        self.taken += 1
        result = []
        for _ in range(min(limit, len(self.messages))):
            result.append(self.messages.popleft())
        return result


def _runtime(tmp_path, coordinator, sources):
    return ComputerRuntime(
        port=8775, coordinator=coordinator, source_manager=sources,
        playback_state=object(), mode_path=tmp_path / "runtime.json",
        initial_mode="computer",
    )


def test_computer_source_backpressure_does_not_discard_or_admit_over_limit(tmp_path):
    source = Sources([("youtube_browser", {"message_id": str(i), "text": "hello"})
                      for i in range(20)])
    coordinator = Coordinator([{"speech_id": str(i), "state": "preparing"} for i in range(20)])
    runtime = _runtime(tmp_path, coordinator, source)
    assert runtime.max_outstanding_jobs() <= 48
    assert runtime.outstanding_jobs() == 20
    runtime._drain_sources()
    assert source.taken == 0
    assert len(source.messages) == 20
    assert runtime.snapshot()["job_states"]["preparing"] == 20
    coordinator.jobs.clear()
    delivered = []
    runtime._enqueue_via_api = lambda mode, item: (delivered.append((mode, item)), True)[1]
    runtime._drain_sources()
    assert 1 <= len(delivered) <= 4
    assert len(source.messages) == 20 - len(delivered)
    assert runtime.snapshot()["max_outstanding_jobs"] <= 48


def test_core_sends_sender_separately_from_translation_and_stages_tts(monkeypatch, tmp_path):
    import voxweavetts.computer_runtime as runtime_module
    import voxweavetts.mode_voice_settings as mode_settings

    saved = {
        "modes": {"youtube_browser": {"engine_id": "engine-test", "voice_id": "voice-test"}},
        "sender_names": {"youtube_browser": True},
        "speech_formats": {"youtube_browser": {
            **mode_settings.DEFAULT_SPEECH_FORMAT,
            "read_comments": True,
            "sender_prefix": "คุณ",
            "separator": "พิมพ์ว่า",
            "read_name_at": False,
        }},
    }
    monkeypatch.setattr(mode_settings, "load_workspace_settings", lambda: saved)
    collected = []

    class Response:
        status = 202
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False

    def fake_urlopen(request, timeout):
        collected.append(json.loads(request.data.decode("utf-8")))
        return Response()

    monkeypatch.setattr(runtime_module, "urlopen", fake_urlopen)
    runtime = _runtime(tmp_path, Coordinator(), Sources())
    assert runtime._enqueue_via_api("youtube_browser", {
        "message_id": "event-1", "text": "hello", "author": "@streamer",
    })
    assert len(collected) == 1
    body = collected[0]
    assert body["source"] == "youtube-live-browser"
    assert body["source_message_id"] == "event-1"
    assert body["hold_for_render"] is True
    assert body["content_text"] == "hello"
    assert body["sender_prefix_text"] == "คุณ streamer พิมพ์ว่า"
    assert body["text"] == "คุณ streamer พิมพ์ว่า hello"
    assert body["engine_id"] == "engine-test"


def test_ready_seen_is_not_counted_against_admission(tmp_path):
    jobs = [{"speech_id": str(i), "state": "ready"} for i in range(8)]
    runtime = _runtime(tmp_path, Coordinator(jobs), Sources())
    assert runtime.outstanding_jobs() == 8
    runtime._seen.update(str(i) for i in range(8))
    assert runtime.outstanding_jobs() == 0
