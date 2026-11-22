"""HTTP integration for shared computer-runtime controls (no installed model needed)."""
from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.computer_runtime import ComputerRuntime, read_mode, read_output
from voxweavetts.server import Handler


class EmptyCoordinator:
    def list(self):
        return []


class EmptySources:
    def status(self, mode):
        return {"mode": mode, "state": "idle", "pending": 0}


def test_runtime_http_settings_replay_and_security(tmp_path):
    runtime = ComputerRuntime(
        port=8765, coordinator=EmptyCoordinator(), source_manager=EmptySources(),
        playback_state=object(), mode_path=tmp_path / "data" / "settings" / "runtime-control.json",
        initial_mode="browser",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.runtime_control = runtime
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def get(path):
        with urlopen(base + path, timeout=3) as response:
            return response.status, json.load(response)

    def post(path, value, intent=""):
        request = Request(base + path,
                          data=json.dumps(value).encode("utf-8"),
                          method="POST",
                          headers={"Content-Type": "application/json",
                                   "X-VoxWeaveTTS-Intent": intent})
        with urlopen(request, timeout=3) as response:
            return response.status, json.load(response)

    try:
        status, initial = get("/v1/runtime/state")
        assert status == 200 and initial["mode"] == "browser"
        assert initial["output"] == "default"
        try:
            post("/v1/runtime/mode", {"mode": "computer"})
            assert False, "missing intent accepted"
        except HTTPError as exc:
            assert exc.code == 403
        assert post("/v1/runtime/mode", {"mode": "computer"},
                    "set-runtime-mode")[1]["mode"] == "computer"
        assert post("/v1/runtime/output", {"output": "live"},
                    "set-runtime-output")[1]["output"] == "live"
        audio = {"sample_rate": 192000, "channels": 2, "buffer_ms": 100}
        assert post("/v1/runtime/audio", audio,
                    "set-runtime-audio")[1]["audio_settings"] == audio
        assert get("/v1/runtime/state")[1]["audio_settings"] == audio
        assert json.loads(runtime.mode_path.read_text())["audio_settings"] == audio
        try:
            post("/v1/runtime/audio", {"sample_rate": 4000, "channels": 2,
                                        "buffer_ms": 100},
                 "set-runtime-audio")
            assert False, "out of range rate was accepted"
        except HTTPError as exc:
            assert exc.code == 400
        try:
            post("/v1/runtime/audio", audio, "wrong-intent")
            assert False, "missing audio intent was accepted"
        except HTTPError as exc:
            assert exc.code == 403
        assert read_mode(runtime.mode_path) == "computer"
        assert read_output(runtime.mode_path) == "live"
        try:
            post("/v1/runtime/output", {"output": "wasapi:not-present"},
                 "set-runtime-output")
            assert False, "nonexistent output accepted"
        except HTTPError as exc:
            assert exc.code == 400
        try:
            post("/v1/runtime/replay", {}, "replay-computer-audio")
            assert False, "replay without audio accepted"
        except HTTPError as exc:
            assert exc.code == 409
        assert post("/v1/runtime/playback", {"action": "stop"},
                    "control-computer-playback")[0] == 200
        assert get("/v1/runtime/state")[1]["mode"] == "computer"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        runtime.shutdown()
