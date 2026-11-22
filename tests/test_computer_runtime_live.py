"""Regression tests for server-owned live audio and API-controlled replay."""
from __future__ import annotations
import io
import json
from pathlib import Path
import threading
import time
from unittest.mock import Mock
import wave

from voxweavetts.computer_runtime import ComputerRuntime, persist_mode, read_mode, read_output
from voxweavetts.live_audio import LiveAudioHub, decode_wav, FRAME_MS
from voxweavetts.listener_gateway import ListeningGateway


def pcm_wav(seconds=0.3, rate=16000):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\x00\x00" * int(rate * seconds))
    return stream.getvalue()


class StubSources:
    def status(self, mode):
        return {"mode": mode, "pending": 0, "state": "idle"}

    def take_for_runtime(self, limit):
        return []


class StubCoordinator:
    def list(self):
        return []


class StubPlayback:
    def __init__(self):
        self.events = []

    def report(self, data, *, ready_job, workspace, clock_basis):
        self.events.append((data["event"], workspace, clock_basis))


def test_live_broadcast_delivers_short_chunks_only_without_history():
    hub = LiveAudioHub()
    listener = hub.subscribe()
    stop = threading.Event()
    times = []
    assert hub.broadcast(pcm_wav(0.3), stop, times.append)
    packets = []
    while True:
        packet = listener.take(0.001)
        if packet is None:
            break
        packets.append(packet)
    assert packets[0]["event"] == "begin"
    assert packets[-1]["event"] == "end"
    assert any(x["event"] == "pcm" for x in packets)
    assert len([x for x in packets if x["event"] == "pcm"]) <= 4
    assert not hasattr(hub, "replay_history")
    hub.unsubscribe(listener)
    late_listener = hub.subscribe()
    assert late_listener.take(0.001) is None  # late clients never receive old audio
    hub.unsubscribe(late_listener)


def test_computer_mode_live_output_and_api_replay(tmp_path):
    playback = StubPlayback()
    runtime = ComputerRuntime(
        port=9999, coordinator=StubCoordinator(), source_manager=StubSources(),
        playback_state=playback, mode_path=tmp_path / "runtime.json",
        initial_mode="computer",
    )
    runtime.configure_output("live")
    speech = {"speech_id": "1" * 32, "source": "manual",
              "audio": {"duration_ms": 300}}
    listener = runtime.audio_hub.subscribe()
    runtime._play_audio(pcm_wav(0.3), speech, "studio")
    assert runtime.snapshot()["completed"] == 1
    assert runtime.snapshot()["last_completed_speech_id"] == "1" * 32
    assert any(x[0] == "start" for x in playback.events)
    assert any(x[0] == "ended" for x in playback.events)
    assert all(x[2] == "computer_monotonic_estimate" for x in playback.events)
    assert runtime.replay_latest()["accepted"]
    assert len(runtime._replays) == 1
    assert read_mode(tmp_path / "runtime.json") == "computer"
    assert read_output(tmp_path / "runtime.json") == "live"
    runtime.audio_hub.unsubscribe(listener)


def test_lan_gateway_requires_bearer_and_never_exposes_wav(tmp_path):
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    runtime = ComputerRuntime(
        port=9999, coordinator=StubCoordinator(), source_manager=StubSources(),
        playback_state=StubPlayback(), mode_path=tmp_path / "runtime.json",
        initial_mode="computer",
    )
    gateway = ListeningGateway(runtime, port=port, host="127.0.0.1")
    gateway.start()
    try:
        assert gateway.server is not None
        base = f"http://127.0.0.1:{port}"
        with urlopen(base + "/listen", timeout=3) as response:
            page = response.read()
        assert b"VoxWeaveTTS" in page
        assert b"/v1/live/stream" in page
        assert b"/v1/jobs/" not in page
        try:
            urlopen(base + "/v1/live/status", timeout=3)
            assert False, "unauthorized status was accepted"
        except HTTPError as error:
            assert error.code == 401
        request = Request(base + "/v1/live/status", headers={
            "Authorization": "Bearer " + gateway.token,
        })
        with urlopen(request, timeout=3) as response:
            result = json.load(response)
        assert result["output"] == "default"
        try:
            urlopen(Request(base + "/v1/jobs/" + "a" * 32 + "/audio",
                            headers={"Authorization": "Bearer " + gateway.token}),
                    timeout=3)
            assert False, "WAV leaked from listening gateway"
        except HTTPError as error:
            assert error.code == 404
    finally:
        gateway.close()
