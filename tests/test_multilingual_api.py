"""HTTP integration for multilingual routes and safe legacy AI model removal."""
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

from voxweavetts import language_routes
from voxweavetts.server import Handler


def _ready_info(engine_id):
    """Server routing tests must not require locally installed TTS models."""
    from dataclasses import replace
    from voxweavetts.speech import get_engine_info
    return replace(get_engine_info(engine_id),
                   assets_ready=True, runtime_ready=True)


class MultilingualHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)

    def post(self, route, body, intent):
        payload = json.dumps(body).encode("utf-8")
        req = Request(self.base + route, method="POST", data=payload, headers={
            "Content-Type": "application/json",
            "X-VoxWeaveTTS-Intent": intent,
            "Origin": self.base,
        })
        try:
            with urlopen(req, timeout=4) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def test_language_routes_save_and_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "routes.json"
            with (patch("voxweavetts.server.load_routes",
                        side_effect=lambda: language_routes.load_routes(path)),
                  patch("voxweavetts.server.save_routes",
                        side_effect=lambda data: language_routes.save_routes(data, path))):
                with urlopen(self.base + "/v1/settings/language-routes", timeout=3) as res:
                    initial = json.load(res)
                self.assertEqual(initial["revision"], 0)
                self.assertIn("ja", initial["languages"])
                body = {"expected_revision": 0,
                        "routes": {"th": {
                            "engine_id": "model-makham-paradee-1_0_0",
                            "voice_id": "paradee_thai"}}}
                status, data = self.post("/v1/settings/language-routes", body,
                                         "save-language-routes")
                self.assertEqual(status, 200)
                self.assertEqual(data["revision"], 1)
                status, _ = self.post("/v1/settings/language-routes", body,
                                       "save-language-routes")
                self.assertEqual(status, 409)
                with urlopen(self.base + "/v1/settings/language-routes") as res:
                    self.assertEqual(json.load(res)["routes"], data["routes"])

    def test_routed_voice_overrides_mode_engine_for_speech(self):
        from unittest.mock import patch
        from voxweavetts.engine_contract import EngineInfo
        from voxweavetts.processing import process_text

        info = EngineInfo(
            id="model-multilingual-fixture-1_0_0", label="Test multilingual engine",
            language="multi", voice_id="af_heart", sample_rate=24000,
            voice_options=(("af_heart", "English"), ("ff_siwis", "French")),
            assets_ready=True, runtime_ready=True,
            capabilities={"speech": True},
        )
        received = {}
        def fake_render(plan, **kwargs):
            received.update(kwargs)
            return b"RIFF" + b"\\0" * 48, {
                "engine_id": kwargs["engine_id"], "duration_ms": 50,
                "seed": kwargs["seed"],
            }
        payload = {"text": "Bonjour", "language": "fr", "mode": "studio",
                   "engine_id": "model-makham-paradee-1_0_0",
                   "voice_id": "paradee_thai"}
        request = Request(
            self.base + "/v1/speech", method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        from voxweavetts.ai_processing import DEFAULTS
        with (patch("voxweavetts.server.load_workspace_settings",
                    return_value={"language_routes": {"studio": True}}),
              patch("voxweavetts.server.load_ai_settings",
                    return_value={"settings": {**DEFAULTS, "enabled": False}}),
              patch("voxweavetts.server.choose_route", return_value=(
                "fr", {"engine_id": info.id, "voice_id": "ff_siwis",
                       "speed": 1.35, "seed": 321,
                       "voice_controls": {"gain_db": 2.5, "pitch_semitones": -1.25,
                                          "bass_db": -3.0, "treble_db": 2.0,
                                          "formant_preserve": False}})),
              patch("voxweavetts.server.get_engine_info", return_value=info),
              patch("voxweavetts.speech.get_engine_info", return_value=info),
              patch("voxweavetts.server.render_wav", side_effect=fake_render)):
            with urlopen(request, timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["X-VoxWeaveTTS-Engine"], info.id)
        self.assertEqual(received["engine_id"], info.id)
        self.assertEqual(received["voice_id"], "ff_siwis")
        self.assertEqual(received["speed"], 1.35)
        self.assertEqual(received["seed"], 321)
        self.assertEqual(received["voice_controls"]["gain_db"], 2.5)
        self.assertEqual(received["voice_controls"]["pitch_semitones"], -1.25)
        self.assertFalse(received["voice_controls"]["formant_preserve"])

    def test_unconfigured_mode_does_not_use_language_route(self):
        from voxweavetts.processing import process_text
        from voxweavetts.server import Handler
        plan = process_text("Bonjour")
        data = {"mode": "reader", "language": "fr",
                "engine_id": "model-makham-paradee-1_0_0", "voice_id": "paradee_thai"}
        with patch("voxweavetts.server.load_workspace_settings",
                   return_value={"language_routes": {"studio": True, "reader": False}}), \
             patch("voxweavetts.server.choose_route") as routed, \
             patch("voxweavetts.server.get_engine_info", side_effect=_ready_info):
            params = Handler._speech_params(None, data, plan)
        routed.assert_not_called()
        self.assertEqual(params["engine_id"], data["engine_id"])
        self.assertEqual(params["voice_id"], data["voice_id"])

    def test_custom_prompt_target_language_routes_voice_only_after_ai_success(self):
        from voxweavetts.ai_processing import DEFAULTS
        from voxweavetts.server import Handler
        from voxweavetts.processing import process_text
        plan=process_text("สวัสดีครับ")
        with (patch("voxweavetts.server.load_workspace_settings",
                    return_value={"language_routes":{"studio":True}}),
              patch("voxweavetts.server.load_ai_settings",
                    return_value={"settings":{**DEFAULTS,
                        "enabled":True,"operation":"custom","target_language":"th"}}),
              patch("voxweavetts.server.choose_route",
                    return_value=("th",None)) as routed,
              patch("voxweavetts.server.get_engine_info", side_effect=_ready_info)):
            plan["processing"]={"ai_status":"processed"}
            Handler._speech_params(None,{"mode":"studio"},plan)
            self.assertEqual(routed.call_args.kwargs["language"],"th")
            plan["processing"]={"ai_status":"fallback"}
            Handler._speech_params(None,{"mode":"studio"},plan)
            self.assertIsNone(routed.call_args.kwargs["language"])

    def test_invalid_source_mode_rejected(self):
        from voxweavetts.server import Handler
        from voxweavetts.processing import process_text
        from voxweavetts.processing import InputError
        with self.assertRaises(InputError):
            Handler._speech_params(None, {"mode":"unknown", "language":"en"},
                                   process_text("Hello"))

    def test_retired_legacy_removal_endpoint_never_accepts_arbitrary_paths(self):
        # v3 deliberately has no legacy M2M remover or path-based destructive API.
        for body, intent in (
            ({}, "remove-ai-model-package"),
            ({"path": "C:/private"}, "remove-legacy-ai-model"),
            ({}, "remove-legacy-ai-model"),
        ):
            status, data = self.post("/v1/ai/packages/remove-legacy", body, intent)
            self.assertIn(status, (403, 404, 410))
            self.assertNotEqual(status, 200)


if __name__ == "__main__":
    unittest.main()