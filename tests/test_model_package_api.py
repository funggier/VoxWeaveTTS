"""Local model-package HTTP UI: read-only metadata, explicit same-origin actions."""
from __future__ import annotations
import json
import zipfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from voxweavetts.server import Handler
from voxweavetts.model_packages import install_model_package_dialog, ModelPackageError
from voxweavetts.ai_model_packages import FORMAT as AI_PACKAGE_FORMAT, AIModelPackageError
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

    @unittest.skip("v1 HTTP package contract retired; native v2 API has replacement tests")
    def test_list_metadata_omits_paths_and_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            sample = fixture(Path(temp))
            with patch("voxweavetts.server.installed_packages",
                       return_value=[(sample, Path(temp))]):
                with urlopen(self.base + "/v1/model-packages", timeout=3) as response:
                    body = json.load(response)
        # A real local pre-v2 MakHam installation may also be listed as a
        # user-removable built-in. Only assert the mocked package under test.
        matches=[pkg for pkg in body["packages"]
                 if pkg["package_id"]=="vachana-a"]
        self.assertEqual(len(matches), 1)
        item = matches[0]
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

    @unittest.skip("v1 HTTP package contract retired; native v2 API has replacement tests")
    def test_installs_only_native_chosen_package_and_refreshes_registry(self):
        with tempfile.TemporaryDirectory() as temp:
            sample = fixture(Path(temp))
            with patch("voxweavetts.server.install_model_package_dialog",
                       return_value=sample) as picker, patch(
                "voxweavetts.server.refresh_engine_registry"
            ) as refreshed, patch("voxweavetts.server.install_async",
                                 return_value={"id": "vachana", "state": "ready", "error": None}) as setup:
                status, data = self.post(
                    "/v1/model-packages/install-local", {},
                    intent="install-model-package",
                )
                self.assertEqual(status, 200)
                self.assertEqual(data, {
                    "installed": True, "package_id": "vachana-a",
                    "version": "1.0.0",
                })
                setup.assert_called_once_with("vachana")
                picker.assert_called_once()
                refreshed.assert_called_once()
            with patch("voxweavetts.server.install_model_package_dialog", return_value=None):
                status, body = self.post(
                    "/v1/model-packages/install-local", {},
                    intent="install-model-package",
                )
                self.assertEqual((status, body), (200, {"cancelled": True}))

    @unittest.skip("v1 HTTP package contract retired; native v2 API has replacement tests")
    def test_general_model_picker_recognizes_ai_translation_package(self):
        # A user who chooses M2M100 in the general Model Packages picker
        # must be routed to the AI installer, not rejected by the TTS schema.
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/"M2M100-418M.vwmodel"
            with zipfile.ZipFile(archive,"w") as zipped:
                zipped.writestr("manifest.json",json.dumps({"format":AI_PACKAGE_FORMAT}))
                zipped.writestr("model.safetensors",b"not trusted")
            result={"package_id":"m2m100-418m","version":"1.0.0",
                    "engine_adapter":"m2m100-transformers-v1"}
            with patch("voxweavetts.ai_model_packages.install_model_package",
                       return_value=result) as install_ai:
                self.assertEqual(install_model_package_dialog(
                    choose_file=lambda: str(archive)),result)
                install_ai.assert_called_once_with(str(archive))
            with patch("voxweavetts.server.install_model_package_dialog",
                       return_value=result) as picker, patch(
                    "voxweavetts.server.refresh_engine_registry") as refreshed, patch(
                    "voxweavetts.server.install_async") as install_worker:
                status, data=self.post("/v1/model-packages/install-local",{},
                                       intent="install-model-package")
            self.assertEqual(status,200)
            self.assertEqual(data,{"installed":True,"package_kind":"ai",
                                   "package_id":"m2m100-418m","version":"1.0.0"})
            picker.assert_called_once()
            refreshed.assert_not_called()
            install_worker.assert_not_called()

    def test_general_picker_never_executes_unknown_or_malicious_package(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/"bad.vwmodel"
            with zipfile.ZipFile(archive,"w") as zipped:
                zipped.writestr("manifest.json",json.dumps({"format":"python-plugin"}))
                zipped.writestr("../malicious.py","print('no')")
            with patch("voxweavetts.ai_model_packages.install_model_package") as install_ai:
                with self.assertRaises(ModelPackageError):
                    install_model_package_dialog(choose_file=lambda: str(archive))
                install_ai.assert_not_called()

    @unittest.skip("v1 HTTP package contract retired; native v2 API has replacement tests")
    def test_general_picker_reports_ai_integrity_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/"bad-ai.vwmodel"
            with zipfile.ZipFile(archive,"w") as zipped:
                zipped.writestr("manifest.json",json.dumps({"format":AI_PACKAGE_FORMAT}))
                zipped.writestr("../evil.py","print('no')")
            with self.assertRaises(AIModelPackageError):
                install_model_package_dialog(choose_file=lambda: str(archive))

    def test_m2m_runtime_install_requires_same_origin_and_empty_request(self):
        route="/v1/ai/m2m-runtime/install"
        with patch("voxweavetts.server.install_m2m_runtime",
                   return_value={"state":"installing","error":None}) as runtime:
            for kwargs in (
                {"origin":"https://evil.example"},
                {"origin":None},
                {"intent":None},
                {"site":"cross-site","intent":"install-m2m-runtime"},
            ):
                with self.subTest(kwargs=kwargs):
                    status,_=self.post(route,{},**kwargs)
                    self.assertEqual(status,403)
            runtime.assert_not_called()
            status,_=self.post(route,{"python_path":"../../bad"},
                               intent="install-m2m-runtime")
            self.assertEqual(status,400)
            runtime.assert_not_called()
            status,body=self.post(route,{},intent="install-m2m-runtime")
            self.assertEqual(status,202)
            self.assertEqual(body,{"runtime":{"state":"installing","error":None}})
            runtime.assert_called_once_with()
        with patch("voxweavetts.server.m2m_runtime_status",
                   return_value={"state":"ready","error":None}):
            with urlopen(self.base+"/v1/ai/m2m-runtime",timeout=3) as response:
                self.assertEqual(json.load(response)["runtime"]["state"],"ready")

    @unittest.skip("v1 HTTP package contract retired; native v2 API has replacement tests")
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


    def test_runtime_registry_only_allows_orphan_cleanup_with_explicit_intent(self):
        record={"id":"sherpa","kind":"tts","runtime_fingerprint":"a"*64,
                "reference_count":0,"consumers":[],"can_uninstall":True}
        with patch("voxweavetts.server.runtime_inventory",return_value=[record]):
            with urlopen(self.base+"/v1/runtimes",timeout=3) as response:
                self.assertEqual(json.load(response)["runtimes"],[record])
        payload={"id":"sherpa","expected_fingerprint":"a"*64,
                 "confirm_uninstall":True}
        with patch("voxweavetts.server.remove_unused_runtime",
                   return_value=True) as remove_runtime:
            for invalid in (
                {"origin":"https://evil.example"},
                {"origin":None},
                {"intent":None},
                {"site":"cross-site","intent":"remove-unused-runtime"},
            ):
                with self.subTest(invalid=invalid):
                    status,_=self.post("/v1/runtimes/remove",payload,**invalid)
                    self.assertEqual(status,403)
            status,_=self.post("/v1/runtimes/remove",
                               {"id":"sherpa","expected_fingerprint":"a"*64},
                               intent="remove-unused-runtime")
            self.assertEqual(status,409)
            remove_runtime.assert_not_called()
            status,body=self.post("/v1/runtimes/remove",payload,
                                  intent="remove-unused-runtime")
            self.assertEqual((status,body),(200,{"removed":True}))
            remove_runtime.assert_called_once_with("sherpa","a"*64)

    def test_verified_wheelhouse_install_rejects_cross_origin_and_payload_extensions(self):
        payload = {"id": "sherpa", "expected_fingerprint": "a"*64,
                   "confirm_install": True}
        with patch("voxweavetts.server.install_verified_runtime_async",
                   return_value={"state": "repairing", "source": "wheelhouse",
                                 "error": None}) as installer:
            for kwargs in (
                {"origin": None, "intent": "install-verified-runtime"},
                {"origin": "https://attacker.example", "intent": "install-verified-runtime"},
                {"intent": None},
                {"site": "cross-site", "intent": "install-verified-runtime"},
            ):
                status, _ = self.post("/v1/runtimes/install-verified", payload, **kwargs)
                self.assertEqual(status, 403)
            for invalid in ({"id": "sherpa", "expected_fingerprint": "a"*64},
                            {**payload, "confirm_install": False},
                            {**payload, "find_links": "https://evil.example"},
                            {**payload, "shell": "cmd.exe"}):
                status, _ = self.post("/v1/runtimes/install-verified", invalid,
                                       intent="install-verified-runtime")
                self.assertEqual(status, 409)
            installer.assert_not_called()
            status, response = self.post("/v1/runtimes/install-verified",
                                         payload, intent="install-verified-runtime")
            self.assertEqual(status, 202)
            self.assertEqual(response["install"]["source"], "wheelhouse")
            installer.assert_called_once_with("sherpa", "a"*64)

    def test_runtime_repair_requires_origin_intent_and_exact_confirmation(self):
        record = {"id": "vachana", "expected_fingerprint": "b"*64,
                  "confirm_repair": True}
        with patch("voxweavetts.server.repair_runtime_async",
                   return_value={"state": "repairing", "error": None}) as repair:
            for kwargs in (
                {"origin": "https://attacker.example", "intent": "repair-runtime-offline"},
                {"origin": None, "intent": "repair-runtime-offline"},
                {"intent": None},
                {"site": "cross-site", "intent": "repair-runtime-offline"},
            ):
                with self.subTest(kwargs=kwargs):
                    status, _ = self.post("/v1/runtimes/repair", record, **kwargs)
                    self.assertEqual(status, 403)
            for invalid in (
                {"id": "vachana", "expected_fingerprint": "b"*64},
                {**record, "confirm_repair": False},
                {**record, "command": "powershell.exe"},
            ):
                status, _ = self.post("/v1/runtimes/repair", invalid,
                                       intent="repair-runtime-offline")
                self.assertEqual(status, 409)
            repair.assert_not_called()
            status, body = self.post("/v1/runtimes/repair", record,
                                     intent="repair-runtime-offline")
            self.assertEqual(status, 202)
            self.assertEqual(body["repair"]["state"], "repairing")
            repair.assert_called_once_with("vachana", "b"*64)

    @unittest.skip("v1 HTTP package contract retired; native v2 API has replacement tests")
    def test_user_can_uninstall_trusted_legacy_makham_without_removing_engine(self):
        with (patch("voxweavetts.server.legacy_makham_present",
                    return_value=True),
              patch("voxweavetts.server.installed_packages",return_value=[]),
              patch("voxweavetts.server.makham_recovery_archive") as recovery):
            recovery.return_value.is_file.return_value=False
            with urlopen(self.base+"/v1/model-packages",timeout=3) as response:
                packages=json.load(response)["packages"]
            self.assertEqual(len(packages),1)
            self.assertEqual(packages[0]["engine_id"],"makham-paradee-cpu")
            self.assertEqual(packages[0]["package_id"],"makham-paradee-builtin")
        with (patch("voxweavetts.server.remove_legacy_makham",return_value=True)
                  as remove_legacy,
              patch("voxweavetts.server.gateway") as broker,
              patch("voxweavetts.server.refresh_engine_registry") as refresh):
            status,body=self.post("/v1/model-packages/remove",{
                "package_id":"makham-paradee-builtin","version":"0.0.0"
            },intent="remove-model-package")
            self.assertEqual((status,body),(200,{"removed":True}))
            remove_legacy.assert_called_once_with()
            broker.return_value.reset.assert_called()
            refresh.assert_called_once_with()

    def test_provider_catalog_and_install_require_explicit_same_origin(self):
        with urlopen(self.base + "/v1/engine-providers", timeout=3) as response:
            self.assertEqual(response.status, 200)
            catalog = json.load(response)
        self.assertEqual({x["id"] for x in catalog["providers"]},
                         {"wayu-nc", "pythaitts", "vachana", "kokoro", "sherpa"})
        route = "/v1/engine-providers/install"
        with patch("voxweavetts.server.install_async",
                   return_value={"id": "kokoro", "state": "installing", "error": None}) as setup:
            for kwargs in (
                {"origin": None, "intent": "install-engine-provider"},
                {"origin": "https://malicious.example", "intent": "install-engine-provider"},
                {"site": "cross-site", "intent": "install-engine-provider"},
                {"intent": None},
            ):
                with self.subTest(kwargs=kwargs):
                    status, _ = self.post(route, {"provider_id": "kokoro"}, **kwargs)
                    self.assertEqual(status, 403)
            setup.assert_not_called()
            status, result = self.post(route, {"provider_id": "kokoro"},
                                       intent="install-engine-provider")
            self.assertEqual(status, 200)
            self.assertEqual(result["install"]["state"], "installing")
            setup.assert_called_once_with("kokoro")
        status, _ = self.post(route, {"provider_id": "../../bad"},
                              intent="install-engine-provider")
        self.assertEqual(status, 400)

if __name__ == "__main__":
    unittest.main()
