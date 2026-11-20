"""Universal v3 one-file model installer HTTP security and consent regressions."""
from __future__ import annotations
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.server import Handler
from voxweavetts.package_install_v3 import preview, commit
from voxweavetts.universal_model_packages import installed_packages
from test_v3_offline_relocatable import _fixture
from voxweavetts.universal_model_packages import make_package


class V3PackageApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.http.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(4)

    def post(self, route, body, *, intent="", origin="same"):
        headers = {"Content-Type": "application/json",
                   "Sec-Fetch-Site": "same-origin"}
        if origin == "same":
            headers["Origin"] = self.base
        elif origin:
            headers["Origin"] = origin
        if intent:
            headers["X-VoxWeaveTTS-Intent"] = intent
        request = Request(self.base + route, data=json.dumps(body).encode(),
                          headers=headers, method="POST")
        try:
            with urlopen(request, timeout=12) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def test_old_v2_install_endpoint_no_longer_exists(self):
        status, _ = self.post("/v1/model-packages/install-local", {},
                              intent="install-model-package")
        self.assertIn(status, (404, 410))

    def test_preview_is_same_origin_and_requires_explicit_intent(self):
        with patch("voxweavetts.package_install_v3.preview") as picker:
            for origin, intent in [
                ("https://evil.example", "inspect-model-package"),
                ("", "inspect-model-package"),
                ("same", ""),
                ("same", "install-model-package"),
            ]:
                status, _ = self.post("/v1/model-packages/inspect-local", {},
                                      intent=intent, origin=origin)
                self.assertEqual(status, 403)
            picker.assert_not_called()

    def test_confirm_rejects_missing_consent_before_installing(self):
        with patch("voxweavetts.package_install_v3.commit") as installer:
            for body in ({}, {"token":"x"},
                         {"token":"x","accepted_rights":False,
                          "acknowledged_noncommercial":False}):
                status, _ = self.post("/v1/model-packages/install-confirmed", body,
                                      intent="install-model-package")
                self.assertEqual(status, 400)
            installer.assert_not_called()

    def test_native_file_preview_is_no_server_and_no_path_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src, manifest=_fixture(root)
            archive=root/"selected.vwmodel"
            make_package(src,manifest,archive)
            with patch("voxweavetts.model_file_picker.pick_model_file",
                       return_value=str(archive)), patch(
                "voxweavetts.package_install_v3.install_model_package"
            ) as installer:
                code,data=self.post("/v1/model-packages/inspect-local",{},
                                    intent="inspect-model-package")
                self.assertEqual(code,200)
                self.assertEqual(data["package"]["id"],"test-vachana")
                self.assertEqual(data["license"]["spdx"],"Apache-2.0")
                self.assertTrue(data["offline"])
                self.assertNotIn(str(root),json.dumps(data))
                self.assertTrue(data["token"])
                installer.assert_not_called()

    def test_v3_preview_token_requires_consent_and_is_single_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src, manifest=_fixture(root)
            archive=root/"selected.vwmodel"
            make_package(src,manifest,archive)
            record=preview(choose_file=lambda:str(archive))
            token=record["token"]
            with self.assertRaises(Exception):
                commit(token,accepted_rights=False)
            with self.assertRaises(Exception):
                commit(token,accepted_rights=True)
            self.assertFalse(installed_packages(root))

    def test_v4_one_click_http_roundtrip_and_no_path_leak(self):
        # The browser selects a local file and immediately commits that
        # selection; no second confirmation, code approval, or license server.
        from test_v4_plugin_packages import fixture
        with tempfile.TemporaryDirectory() as tmp:
            archive = fixture(Path(tmp))
            with patch("voxweavetts.model_file_picker.pick_model_file",
                       return_value=str(archive)), patch(
                "voxweavetts.universal_model_v4.install",
                return_value={"format_version": 4,
                              "package_id": "demo-future-engine",
                              "engine_id": "model-demo-future-engine-1_0_0",
                              "runtime_status": "ready"},
            ) as installer:
                status, data = self.post("/v1/model-packages/inspect-local", {},
                                         intent="inspect-model-package")
                self.assertEqual(status, 200)
                self.assertEqual(data["format_version"], 4)
                self.assertTrue(data["contains_executable_plugin"])
                self.assertNotIn(str(archive), json.dumps(data))
                status, result = self.post(
                    "/v1/model-packages/install-confirmed",
                    {"token": data["token"], "accepted_rights": True,
                     "acknowledged_noncommercial": False},
                    intent="install-model-package",
                )
                self.assertEqual(status, 200)
                self.assertTrue(result["installed"])
                self.assertEqual(result["format_version"], 4)
                installer.assert_called_once_with(archive.resolve())

    def test_runtime_legacy_endpoints_unavailable(self):
        for path in ("/v1/runtimes/repair", "/v1/runtimes/install-verified",
                     "/v1/engine-providers/install",
                     "/v1/ai/m2m-runtime/install"):
            status, _=self.post(path, {}, intent="repair-runtime-offline")
            self.assertIn(status, (404, 410))


if __name__=="__main__":
    unittest.main()
