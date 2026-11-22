"""Remote control access tests: LAN username/password, settings and endpoint allowlist."""
from __future__ import annotations
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pathlib import Path
import pytest

from voxweavetts.network_config import load_network, save_network, public_network, check_password
from voxweavetts.remote_gateway import RemoteControlGateway
from voxweavetts.remote_client import RemoteAPI


def test_password_config_portability_and_four_character_minimum(tmp_path):
    path = tmp_path / "data" / "settings" / "network.json"
    default = load_network(path)
    assert default["username"] == "voxweave"
    assert default["remote_enabled"] is False
    assert default["control_port"] == 8776
    assert not default["password_hash"]
    saved = save_network({
        "username": "custom_user", "password": "1234",
        "remote_enabled": True, "control_host": "127.0.0.1",
        "control_port": 8821, "listener_host": "127.0.0.1", "listener_port": 8822,
        "api_port": 8820,
    }, path)
    assert "password" not in saved
    assert "1234" not in path.read_text(encoding="utf-8")
    assert check_password("1234", saved["password_hash"])
    assert not check_password("1235", saved["password_hash"])
    assert "password_hash" not in public_network(saved)
    copied = tmp_path / "relocated" / "network.json"
    copied.parent.mkdir()
    path.replace(copied)
    assert load_network(copied) == saved


@pytest.mark.parametrize("changes", [
    {"username": ""},
    {"username": "../invalid"},
    {"password": "123"},
    {"control_host": "example.com"},
    {"control_port": 70000},
    {"control_port": 0},
    {"api_port": 8800, "control_port": 8800},
    {"listener_host": "example.com"},
    {"api_port": 8800, "listener_port": 8800},
])
def test_invalid_network_settings_rejected(tmp_path, changes):
    original = public_network(load_network(tmp_path / "network.json"))
    candidate = {**original, "username":"voxweave", "password":"goodpass",
                 "remote_enabled": True, **changes}
    with pytest.raises(ValueError):
        save_network(candidate, tmp_path / "network.json")


def test_gateway_auth_and_remote_client_without_local_server(tmp_path):
    calls = []
    class InternalHandler(BaseHTTPRequestHandler):
        def respond(self, status, result):
            content = json.dumps(result).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers(); self.wfile.write(content)
        def do_GET(self):
            calls.append(("GET", self.path))
            if self.path == "/v1/runtime/state":
                self.respond(200, {"mode":"computer","listen_url":"http://private/#token=abc",
                                   "output":"default","last_error":"oops"})
            elif self.path == "/v1/jobs":
                self.respond(200, {"jobs":[{"speech_id":"a"*32,"state":"ready","display_text":"secret"}]})
            else: self.respond(404,{})
        def do_POST(self):
            data=self.rfile.read(int(self.headers.get("Content-Length","0")))
            calls.append(("POST",self.path,json.loads(data)))
            self.respond(202, {"accepted":True})
        def log_message(self,*args): pass
    local=ThreadingHTTPServer(("127.0.0.1",0),InternalHandler)
    runner=threading.Thread(target=local.serve_forever,daemon=True);runner.start()
    config=save_network({"username":"voxweave","password":"1234",
                         "remote_enabled":True,"api_port":8765,
                         "control_host":"127.0.0.1","control_port":8776,
                         "listener_host":"127.0.0.1","listener_port":8766},
                        tmp_path / "config.json")
    remote=RemoteControlGateway("127.0.0.1",0,local.server_port,config["username"],config["password_hash"])
    remote.start()
    base="http://127.0.0.1:"+str(remote.server.server_port)
    try:
        ok=RemoteAPI("127.0.0.1",remote.server.server_port,"voxweave","1234")
        state=ok.get("/v1/runtime/state")
        assert state["mode"] == "computer"
        assert "listen_url" not in state
        jobs=ok.get("/v1/jobs")
        assert jobs["jobs"][0]["state"]=="ready"
        assert "display_text" not in jobs["jobs"][0]
        assert ok.post("/v1/runtime/replay",{},"replay-computer-audio")["accepted"]
        assert calls[-1] == ("POST","/v1/runtime/replay",{})
        for u,p in (("bad","1234"),("voxweave","badp")):
            with pytest.raises(RuntimeError,match="401"):
                RemoteAPI("127.0.0.1",remote.server.server_port,u,p).get("/v1/runtime/state")
        with pytest.raises(RuntimeError,match="404"):
            ok.get("/v1/model-packages")
        with pytest.raises(RuntimeError,match="404"):
            ok.get("/v1/jobs/"+"a"*32+"/audio")
        with pytest.raises(ValueError):
            RemoteAPI("evil.invalid",80,"voxweave","1234")
    finally:
        remote.close();local.shutdown();local.server_close();runner.join(3)
