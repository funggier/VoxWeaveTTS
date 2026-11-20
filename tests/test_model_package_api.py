"""Universal v4-only model package picker and one-click HTTP security tests."""
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
from voxweavetts.package_install_v4 import preview, commit
from test_v4_plugin_packages import fixture


class V4PackageApiTests(unittest.TestCase):
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

    def test_no_legacy_install_endpoints(self):
        for path in ("/v1/model-packages/install-local", "/v1/runtimes/repair",
                     "/v1/runtimes/install-verified", "/v1/engine-providers/install",
                     "/v1/ai/m2m-runtime/install"):
            status, _ = self.post(path, {}, intent="install-model-package")
            self.assertIn(status, (404, 410))

    def test_preview_requires_same_origin_and_explicit_intent(self):
        with patch("voxweavetts.package_install_v4.preview") as picker:
            for origin, intent in [
                ("https://evil.example", "inspect-model-package"),
                ("", "inspect-model-package"),
                ("same", ""),
                ("same", "install-model-package"),
            ]:
                code, _ = self.post("/v1/model-packages/inspect-local", {},
                                     intent=intent, origin=origin)
                self.assertEqual(code, 403)
            picker.assert_not_called()

    def test_commit_rejects_missing_explicit_click(self):
        with patch("voxweavetts.package_install_v4.commit") as installer:
            for body in ({}, {"token":"x"},
                         {"token":"x","accepted_rights":False,
                          "acknowledged_noncommercial":False}):
                status, _ = self.post("/v1/model-packages/install-confirmed", body,
                                      intent="install-model-package")
                self.assertEqual(status, 400)
            installer.assert_not_called()

    def test_v3_archive_cannot_be_previewed_or_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "older.vwmodel"
            import zipfile
            with zipfile.ZipFile(bad, "w") as z:
                z.writestr("manifest.json", json.dumps({
                    "format":"voxweavetts.model-package", "format_version":3}))
            with self.assertRaises(ValueError):
                preview(choose_file=lambda: bad)

    def test_one_click_v4_install_and_no_selected_path_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = fixture(Path(tmp))
            with patch("voxweavetts.model_file_picker.pick_model_file",
                       return_value=str(archive)), patch(
                "voxweavetts.package_install_v4.install",
                return_value={"format_version":4,
                              "package_id":"demo-future-engine",
                              "engine_id":"model-demo-future-engine-1_0_0",
                              "runtime_status":"ready"}
            ) as installer:
                code, result = self.post("/v1/model-packages/inspect-local", {},
                                         intent="inspect-model-package")
                self.assertEqual(code, 200)
                self.assertEqual(result["format_version"], 4)
                self.assertTrue(result["contains_executable_plugin"])
                self.assertTrue(result["offline"])
                self.assertNotIn(str(archive), json.dumps(result))
                token = result["token"]
                status, installed = self.post(
                    "/v1/model-packages/install-confirmed",
                    {"token":token, "accepted_rights":True,
                     "acknowledged_noncommercial":False},
                    intent="install-model-package")
                self.assertEqual(status, 200)
                self.assertTrue(installed["installed"])
                installer.assert_called_once_with(archive.resolve())
                status, _ = self.post(
                    "/v1/model-packages/install-confirmed",
                    {"token":token, "accepted_rights":True,
                     "acknowledged_noncommercial":False},
                    intent="install-model-package")
                self.assertEqual(status, 400)

    def test_file_mutation_blocks_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = fixture(Path(tmp))
            record = preview(choose_file=lambda: archive)
            with archive.open("ab") as f:
                f.write(b"unexpected archive change")
            with patch("voxweavetts.package_install_v4.install") as installer:
                with self.assertRaises(ValueError):
                    commit(record["token"], accepted_rights=True)
                installer.assert_not_called()

    def test_package_listing_contains_only_v4(self):
        with urlopen(self.base + "/v1/model-packages", timeout=5) as response:
            listing = json.load(response)
        self.assertIsInstance(listing["packages"], list)
        self.assertTrue(all(p["format_version"] == 4
                            for p in listing["packages"]))


if __name__ == "__main__":
    unittest.main()
