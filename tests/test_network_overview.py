"""Web LAN overview: distinguish Browser control, listener and Desktop remote API."""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from voxweavetts.network import NetworkSettings
from voxweavetts.server import Handler, browser_network_overview


def test_web_overview_reports_actual_port_and_never_exposes_password():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.network_settings = NetworkSettings("127.0.0.1", server.server_port,
                                              "secret-123", "custom_user")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/v1/network/overview",
                     timeout=3) as response:
            overview = json.load(response)
        assert overview["web"]["port"] == server.server_port
        assert overview["web"]["bind_host"] == "127.0.0.1"
        assert overview["web"]["lan_enabled"] is False
        assert overview["web"]["username"] == "custom_user"
        assert overview["web"]["url"] == f"http://127.0.0.1:{server.server_port}/"
        assert overview["remote"]["enabled"] is False
        assert overview["listener"]["running"] is False
        raw=json.dumps(overview)
        assert "secret-123" not in raw
        assert "password_hash" not in raw
        assert "access_code" not in raw
        assert "token=" not in raw
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def test_all_ipv4_overview_has_lan_url_but_labels_it_suggested():
    overview = browser_network_overview(
        NetworkSettings("0.0.0.0",8775,"code1234","voxweave"),
        "0.0.0.0", 8775, "127.0.0.1", "192.168.1.165",
    )
    assert overview["bind_mode"] == "all_ipv4"
    assert overview["lan_enabled"] is True
    assert overview["url"] == "http://192.168.1.165:8775/"
    assert overview["url_is_estimate"] is True
    assert overview["username"] == "voxweave"


def test_selected_lan_interface_is_authoritative():
    overview = browser_network_overview(
        NetworkSettings("192.168.1.165", 9555, "code1234", "admin"),
        "192.168.1.165", 9555, "192.168.1.165", "192.168.1.165",
    )
    assert overview["url"] == "http://192.168.1.165:9555/"
    assert overview["bind_mode"] == "lan_ipv4"
    assert overview["url_is_estimate"] is False
