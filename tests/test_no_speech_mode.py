"""Global Settings text-only Live mode: show AI-processed text without a WAV."""
from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
import threading
from unittest.mock import patch
from urllib.request import Request, urlopen

import pytest

from voxweavetts.ai_processing import DEFAULTS, validate_settings
from voxweavetts.processing import InputError
from voxweavetts.server import Handler
from voxweavetts.speech_coordinator import JobNotReady, SpeechCoordinator


def test_no_speech_settings_reject_unknown_duplicate_and_bad_types():
    assert validate_settings({})["no_speech_modes"] == []
    assert validate_settings({"no_speech_modes": ["discord", "stt_api"]})[
        "no_speech_modes"] == ["discord", "stt_api"]
    for bad in (None, "discord", {"discord": True}, ["discord", "discord"],
                ["studio"], ["live", 1], ["unknown"], ["live"] * 8):
        with pytest.raises(InputError):
            validate_settings({"no_speech_modes": bad})


def _ai_settings(**changes):
    return validate_settings({**DEFAULTS, "enabled": False,
                              "operation": "none",
                              "no_speech_modes": ["discord"],
                              **changes})


def test_http_live_text_only_no_tts_voice_or_audio_even_when_ai_disabled():
    renders = []
    c = SpeechCoordinator(lambda *a, **k: renders.append((a, k)))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.speech_coordinator = c
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        cfg = _ai_settings()
        base = f"http://127.0.0.1:{server.server_port}"
        def send(text, *, mode="discord", source="discord"):
            request = Request(
                base + "/v1/jobs",
                data=json.dumps({"text": text, "content_text": text,
                                 "mode": mode, "source": source,
                                 "source_message_id": "test-" + text},
                                ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "X-VoxWeaveTTS-Intent": "queue-speech"},
                method="POST",
            )
            with urlopen(request, timeout=5) as reply:
                assert reply.status == 202
                return json.load(reply)

        with (patch("voxweavetts.server.load_ai_settings", return_value={
                  "settings": cfg, "revision": "test"}),
              patch("voxweavetts.server.load_text_section",
                    side_effect=lambda kind: {"value": [] if kind == "rules" else {}}),
              patch("voxweavetts.server.Handler._queue_params",
                    side_effect=AssertionError(
                        "Text-only must never select a speech model"))):
            submitted = send("hello text")
            result = c.wait(submitted["speech_id"], timeout=6)
            assert result["state"] == "displayed", result
            assert result["display_text"] == "hello text"
            assert result["audio_ready"] is False
            assert renders == []
            assert [e["type"] for e in c.events(result["speech_id"])] == [
                "speech.preparing", "speech.displayed",
            ]
            with pytest.raises(JobNotReady):
                c.audio(result["speech_id"])
            with pytest.raises(JobNotReady):
                c.start_render(result["speech_id"])
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
        c.close()


def test_http_translation_text_only_uses_processed_text_not_raw_or_tts_input():
    renders = []
    c = SpeechCoordinator(lambda *a, **k: renders.append((a, k)))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.speech_coordinator = c
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        cfg = _ai_settings(enabled=True, operation="translate", model="test")
        base = f"http://127.0.0.1:{server.server_port}"
        data = {"text": "hello", "content_text": "hello",
                "mode": "discord", "source": "discord"}
        request = Request(base + "/v1/jobs",
                          data=json.dumps(data).encode(),
                          method="POST", headers={
                              "Content-Type": "application/json",
                              "X-VoxWeaveTTS-Intent": "queue-speech",
                          })
        with (patch("voxweavetts.server.load_ai_settings", return_value={
                  "settings": cfg, "revision": "test"}),
              patch("voxweavetts.server.load_text_section",
                    side_effect=lambda kind: {"value": [] if kind == "rules" else {}}),
              patch("voxweavetts.ai_pipeline.process_ai", return_value={
                  "text": "สวัสดี", "status": "processed", "applied": True,
              }),
              patch("voxweavetts.server.Handler._queue_params",
                    side_effect=AssertionError("Text-only must bypass TTS"))):
            with urlopen(request, timeout=5) as reply:
                accepted = json.load(reply)
            outcome = c.wait(accepted["speech_id"], timeout=6)
            assert outcome["state"] == "displayed", outcome
            assert outcome["display_text"] == "สวัสดี"
            assert "hello" not in outcome["display_text"]
            assert renders == []
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
        c.close()


def test_text_only_skipped_by_filter_never_displays_prohibited_text():
    from voxweavetts.ai_pipeline import process_pipeline
    from voxweavetts.speech_coordinator import SpeechCoordinator
    plan = process_pipeline(
        "private text", source="discord", settings=_ai_settings(),
        rules=[{"match": "private text", "mode": "skip"}],
    )
    c = SpeechCoordinator(lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("TTS may not run on skipped messages")))
    try:
        queued = c.submit_deferred(
            lambda: (plan, {"engine_id": "none", "voice_id": "none"}),
            source="discord", text_only=True,
        )
        result = c.wait(queued["speech_id"], timeout=5)
        assert result["state"] == "skipped", result
        assert "private text" not in json.dumps(result)
    finally:
        c.close()

def test_core_dashboard_shows_translation_as_text_without_model_or_audio(tmp_path):
    """Only intent-gated dashboard receives private text; public state never does."""
    import time
    from voxweavetts.ai_pipeline import process_pipeline
    from voxweavetts.computer_runtime import ComputerRuntime
    from voxweavetts.source_manager import SourceManager

    def cannot_render(*_args, **_kwargs):
        raise AssertionError("text-only job must never invoke TTS")
    c = SpeechCoordinator(cannot_render)
    sources = SourceManager()
    class Playback:
        def report(self, *args, **kwargs):
            raise AssertionError("text-only job must never report playback")
    core = ComputerRuntime(
        port=8775, coordinator=c, source_manager=sources,
        playback_state=Playback(), mode_path=tmp_path / "runtime.json",
        initial_mode="computer",
    )
    try:
        plan = process_pipeline("hello", source="discord",
                                settings=_ai_settings())
        result = c.submit_deferred(
            lambda: (plan, {"engine_id": "none", "voice_id": "none"}),
            source="discord", source_message_id="msg-1",
            hold_for_render=True, text_only=True,
        )
        core._recent_messages["discord"].append({
            "message_id": "msg-1", "author": "Speaker",
            "text": "original input", "state": "queued",
            "speech_id": result["speech_id"],
        })
        core.start()
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            dashboard = core.dashboard()["sources"]["discord"]
            if (dashboard["counts"]["displayed"] == 1
                    and result["speech_id"] in core._seen):
                break
            time.sleep(0.03)
        assert dashboard["counts"]["displayed"] == 1
        assert dashboard["read_history"][0]["processed_text"] == "hello"
        assert dashboard["read_history"][0]["state"] == "displayed"
        assert dashboard["model_history"] == []
        assert result["speech_id"] in core._seen
        assert "original input" not in json.dumps(core.snapshot())
    finally:
        core.shutdown()
        c.close()
        sources.stop_all()