import base64
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from voxweavetts.network import NetworkAccess, NetworkSettings, load_network_settings
from voxweavetts.server import Handler


ACCESS_CODE = "test-code-with-24-characters"
AUTHORIZATION = "Basic " + base64.b64encode(f"voxweave:{ACCESS_CODE}".encode()).decode()


class NetworkSettingsTests(unittest.TestCase):
    def test_defaults_saved_settings_and_launch_overrides(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {}, clear=True):
            file = Path(root) / "network.json"
            self.assertEqual(load_network_settings(path=file), NetworkSettings())
            file.write_text(
                '{"host":"100.84.6.5","port":8775,"access_code":"' + ACCESS_CODE + '"}',
                encoding="utf-8",
            )
            self.assertEqual(load_network_settings(path=file), NetworkSettings("100.84.6.5", 8775, ACCESS_CODE))
            self.assertEqual(load_network_settings("192.168.1.10", 9000, path=file),
                             NetworkSettings("192.168.1.10", 9000, ACCESS_CODE))
            with patch.dict(os.environ, {"VOXWEAVETTS_NETWORK_PASSWORD": "another-offline-access-code"}):
                self.assertEqual(load_network_settings(path=file).access_code, "another-offline-access-code")

    def test_invalid_values_and_wildcard_without_access_code_are_rejected(self):
        for host, port, access_code in (
            ("localhost", 8765, ""), ("::1", 8765, ""), ("0.0.0.0", 8765, ""),
            ("127.0.0.1", 0, ""), ("127.0.0.1", 65536, ""), ("127.0.0.1", True, ""),
            ("239.1.2.3", 8765, ACCESS_CODE), ("127.0.0.1", 8765, "\né"),
        ):
            with self.subTest(host=host, port=port), self.assertRaises(ValueError):
                NetworkSettings(host, port, access_code)


@contextmanager
def network_server(handler):
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as http:
        http.network_access = NetworkAccess(NetworkSettings("0.0.0.0", 8765, ACCESS_CODE))
        worker = threading.Thread(target=http.serve_forever, kwargs={"poll_interval": 0.03})
        worker.start()
        try:
            yield http.server_port
        finally:
            http.shutdown()
            worker.join()


class RemoteHandler(Handler):
    def _is_host_machine(self):
        return False


class NetworkHTTPTests(unittest.TestCase):
    def request(self, port, path, headers=None, data=None):
        client = HTTPConnection("127.0.0.1", port, timeout=4)
        try:
            client.request("POST" if data is not None else "GET", path, data, headers or {})
            response = client.getresponse()
            response.read()
            return response.status, response.getheader("WWW-Authenticate")
        finally:
            client.close()

    def test_remote_request_authenticates_before_serving_html_overlay_and_api(self):
        with network_server(RemoteHandler) as port:
            for path in ("/", "/overlay", "/v1/modes/state"):
                with self.subTest(path=path):
                    self.assertEqual(self.request(port, path), (401, 'Basic realm="VoxWeaveTTS"'))
                    self.assertEqual(self.request(port, path, {"Authorization": "Basic wrong"})[0], 401)
                    self.assertEqual(self.request(port, path, {"Authorization": AUTHORIZATION})[0], 200)

    def test_host_origin_and_admin_actions(self):
        with network_server(RemoteHandler) as port:
            self.assertEqual(self.request(port, "/", {
                "Host": f"unrelated.example:{port}", "Authorization": AUTHORIZATION,
            })[0], 403)
            path = "/v1/jobs/" + "0" * 32 + "/start-render"
            headers = {
                "Authorization": AUTHORIZATION,
                "Content-Type": "application/json",
                "X-VoxWeaveTTS-Intent": "start-staged-speech-render",
            }
            self.assertEqual(self.request(port, path, {**headers, "Origin": "http://elsewhere"}, "{}")[0], 403)
            headers["Origin"] = f"http://127.0.0.1:{port}"
            self.assertEqual(self.request(port, path, headers, "{}")[0], 404)
            headers["X-VoxWeaveTTS-Intent"] = "inspect-model-package"
            self.assertEqual(self.request(port, "/v1/model-packages/inspect-local", headers, "{}")[0], 403)

    def test_owner_keeps_basic_access_without_access_code(self):
        with network_server(Handler) as port:
            self.assertEqual(self.request(port, "/v1/modes/state"), (200, None))


if __name__ == "__main__":
    unittest.main()
