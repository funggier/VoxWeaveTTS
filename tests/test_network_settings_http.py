"""HTTP tests for the local-only LAN configuration UI API."""
from __future__ import annotations
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest

from voxweavetts import server as service
from voxweavetts.network_config import load_network, save_network


def test_network_settings_api_local_only_and_secret_not_returned(monkeypatch, tmp_path):
    settings = tmp_path / "settings" / "network.json"
    monkeypatch.setattr(service, "load_network", lambda: load_network(settings))
    monkeypatch.setattr(service, "save_network", lambda values: save_network(values, settings))

    local = ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
    thread = threading.Thread(target=local.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{local.server_port}"

    def get():
        with urlopen(base + "/v1/network/settings", timeout=4) as response:
            return json.load(response)

    def post(data, intent="save-network-settings", origin=None):
        headers = {"Content-Type": "application/json",
                   "X-VoxWeaveTTS-Intent": intent}
        headers["Origin"] = base if origin is None else origin
        request = Request(base + "/v1/network/settings",
                          method="POST", headers=headers,
                          data=json.dumps(data).encode("utf-8"))
        with urlopen(request, timeout=4) as response:
            return json.load(response)

    values = {
        "username": "stream_admin", "password": "abcd",
        "api_port": 9876, "listener_host": "127.0.0.1",
        "listener_port": 9877, "remote_enabled": True,
        "control_host": "127.0.0.1", "control_port": 9878,
    }
    try:
        assert get()["username"] == "voxweave"
        assert get()["password_configured"] is False
        with pytest.raises(HTTPError) as error:
            post(values, intent="wrong")
        assert error.value.code == 403
        with pytest.raises(HTTPError) as error:
            post(values, origin="http://evil.invalid")
        assert error.value.code == 403
        result = post(values)
        assert result["username"] == "stream_admin"
        assert result["restart_required"] is True
        assert result["password_configured"] is True
        assert "password" not in result and "password_hash" not in result
        assert "abcd" not in settings.read_text(encoding="utf-8")
        assert get()["control_port"] == 9878
        with pytest.raises(HTTPError) as error:
            post({**values, "password": "abc"})
        assert error.value.code == 400
    finally:
        local.shutdown()
        local.server_close()
        thread.join(timeout=3)
