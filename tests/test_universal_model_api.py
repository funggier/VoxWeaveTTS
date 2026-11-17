"""Native v2 HTTP behavior: listing, same-origin, no implicit runtime install."""
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
from voxweavetts.universal_model_packages import (
    installed_packages, install_model_package, make_package,
)
from test_universal_model_packages import fixture


class UniversalV2ApiTests(unittest.TestCase):
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

    def post(self, endpoint, body, *, intent="install-model-package", origin=None):
        req = Request(self.base + endpoint, method="POST",
                      data=json.dumps(body).encode(), headers={
                          "Origin": origin or self.base,
                          "Content-Type": "application/json",
                          "Sec-Fetch-Site": "same-origin",
                          "X-VoxWeaveTTS-Intent": intent,
                      })
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def test_list_native_v2_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder, manifest = fixture(root, kind="stt", runtime_source="recipe-only")
            archive = root / "stt.vwmodel"
            make_package(folder, manifest, archive)
            install_model_package(archive, root=root)
            with patch("voxweavetts.server.installed_universal_packages",
                       return_value=installed_packages(root)):
                with urlopen(self.base + "/v1/model-packages", timeout=5) as response:
                    data = json.load(response)
            self.assertEqual(len(data["packages"]), 1)
            pack = data["packages"][0]
            self.assertEqual(pack["format_version"], 2)
            self.assertEqual(pack["model_kind"], "stt")
            self.assertEqual(pack["license"]["spdx"], "MIT")
            self.assertFalse(pack["adapter_trusted"])
            self.assertNotIn(str(root), json.dumps(pack))
            self.assertNotIn("universal_packages", data)

    def test_install_no_auto_dependency_action(self):
        response = {"package_id": "v2-native-test", "version": "1.0.0",
                    "package_kind": "stt", "engine_adapter": "untrusted-stt-v1",
                    "format_version": 2, "activation_supported": False,
                    "runtime_status": "runtime-not-executed"}
        with patch("voxweavetts.server.install_model_package_dialog",
                   return_value=response), patch(
            "voxweavetts.server.install_async") as runtime_installer, patch(
            "voxweavetts.server.refresh_engine_registry"
        ):
            code, body = self.post("/v1/model-packages/install-local", {})
        self.assertEqual(code, 200)
        self.assertEqual(body["format_version"], 2)
        self.assertFalse(body["activation_supported"])
        runtime_installer.assert_not_called()

    def test_ai_settings_lists_inactive_native_v2_with_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder, manifest = fixture(root, kind="translation", runtime_source="recipe-only")
            archive = root / "translation.vwmodel"
            make_package(folder, manifest, archive)
            install_model_package(archive, root=root)
            with patch("voxweavetts.server.installed_universal_packages",
                       return_value=installed_packages(root)):
                with urlopen(self.base + "/v1/ai/packages", timeout=5) as response:
                    data = json.load(response)
            self.assertFalse(data["legacy_m2m"])
            self.assertEqual(len(data["packages"]), 1)
            self.assertEqual(data["packages"][0]["key"], "v2-native-test@1.0.0")
            self.assertEqual(data["packages"][0]["runtime_state"], "runtime-recipe-pending")
            self.assertFalse(data["packages"][0]["runtime_ready"])

    def test_ai_settings_native_v2_translation_picker(self):
        selected = "T:/temp/chosen.vwmodel"
        profile = {"package": {"kind": "translation"}}
        with patch("voxweavetts.model_packages._native_model_picker",
                   return_value=selected), patch(
            "voxweavetts.universal_model_packages.inspect_archive",
            return_value=profile
        ) as inspector, patch(
            "voxweavetts.universal_model_packages.install_model_package",
            return_value={"package_id":"translation-v2", "version":"1.0.0",
                          "runtime_status":"runtime-not-executed"}
        ) as installer:
            status, body = self.post("/v1/ai/packages/install-local", {},
                                     intent="install-ai-model-package")
        self.assertEqual(status, 200)
        self.assertEqual(body["format_version"], 2)
        self.assertEqual(body["package_id"], "translation-v2")
        inspector.assert_called_once_with(selected)
        installer.assert_called_once_with(selected)

    def test_ai_legacy_remove_endpoint_retired_without_deletion(self):
        with patch("voxweavetts.server.remove_legacy_m2m") as remover:
            status, body = self.post("/v1/ai/packages/remove-legacy", {},
                                     intent="remove-legacy-ai-model")
        self.assertEqual(status, 410)
        self.assertIn("retired", body["error"])
        remover.assert_not_called()

    def test_reject_cross_origin_before_picker(self):
        with patch("voxweavetts.server.install_model_package_dialog") as picker:
            status, _ = self.post("/v1/model-packages/install-local", {},
                                   origin="https://evil.example")
            self.assertEqual(status, 403)
            picker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
