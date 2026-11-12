"""Local model-package HTTP UI: read-only metadata, explicit same-origin actions."""
from __future__ import annotations
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from voxweavetts.server import Handler
from test_model_packages import fixture
from pathlib import Path
import tempfile


class PackageEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(3)

    def post(self, route, body, *, origin="same", intent=None, site="same-origin"):
        headers = {"Content-Type": "application/json"}
        if origin == "same":
            headers["Origin"] = self.base
        elif isinstance(origin, str):
            headers["Origin"] = origin
        if intent:
            headers["X-VoxWeaveTTS-Intent"] = intent
        if site:
            headers["Sec-Fetch-Site"] = site
        req = Request(
            self.base + route,
            data=json.dumps(body).encode("utf-8"),
            headers=headers, method="POST",
        )
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as err:
            with err:
                return err.code, json.load(err)

    def test_list_metadata_omits_paths_and_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            sample = fixture(Path(temp))
            with patch("voxweavetts.server.installed_packages",
                       return_value=[(sample, Path(temp))]):
                with urlopen(self.base + "/v1/model-packages", timeout=3) as response:
                    body = json.load(response)
        self.assertEqual(len(body["packages"]), 1)
        item = body["packages"][0]
        self.assertEqual(item["engine_id"], "model-vachana-a-1_0_0")
        self.assertEqual(item["license"]["review_status"], "review_required")
        self.assertNotIn("folder", json.dumps(item))
        self.assertNotIn("files", json.dumps(item))

    def test_install_requires_origin_and_explicit_intent(self):
        route = "/v1/model-packages/install-local"
        with patch("voxweavetts.server.install_model_package_dialog") as dialog:
            for kwargs in (
                {"origin": "https://evil.example"},
                {"origin": None},
                {"intent": None},
                {"site": "cross-site", "intent": "install-model-package"},
            ):
                with self.subTest(kwargs=kwargs):
                    status, _body = self.post(route, {}, **kwargs)
                    self.assertEqual(status, 403)
            dialog.assert_not_called()

    def test_installs_only_native_chosen_package_and_refreshes_registry(self):
        with tempfile.TemporaryDirectory() as temp:
            sample = fixture(Path(temp))
            with patch("voxweavetts.server.install_model_package_dialog",
                       return_value=sample) as picker, patch(
                "voxweavetts.server.refresh_engine_registry"
            ) as refreshed:
                status, data = self.post(
                    "/v1/model-packages/install-local", {},
                    intent="install-model-package",
                )
                self.assertEqual(status, 200)
                self.assertEqual(data, {
                    "installed": True, "package_id": "vachana-a",
                    "version": "1.0.0",
                })
                picker.assert_called_once()
                refreshed.assert_called_once()
            with patch("voxweavetts.server.install_model_package_dialog", return_value=None):
                status, body = self.post(
                    "/v1/model-packages/install-local", {},
                    intent="install-model-package",
                )
                self.assertEqual((status, body), (200, {"cancelled": True}))

    def test_remove_requires_exact_identity_and_intent(self):
        with patch("voxweavetts.server.remove_model_package", return_value=True) as remover, patch(
            "voxweavetts.server.refresh_engine_registry"
        ) as refresh:
            status, body = self.post(
                "/v1/model-packages/remove",
                {"package_id": "vachana-a", "version": "1.0.0"},
                intent="remove-model-package",
            )
            self.assertEqual(status, 200)
            self.assertTrue(body["removed"])
            remover.assert_called_once_with("vachana-a", "1.0.0")
            refresh.assert_called_once()
        status, _body = self.post(
            "/v1/model-packages/remove",
            {"package_id": "../../secrets", "version": "1.0.0"},
            intent="remove-model-package",
        )
        self.assertEqual(status, 400)

if __name__ == "__main__":
    unittest.main()
