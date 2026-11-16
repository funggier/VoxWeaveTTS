"""Gateway regression: bounded transport, protocol isolation and NC visibility."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import engine_worker_host as host
from voxweavetts.engine_worker_gateway import (
    EngineWorkerGateway, WorkerError, WorkerSpec,
)
from voxweavetts.personal_wayu_engine import (
    ENGINE_ID, PersonalWayuEngine, runtime_ready,
)
from voxweavetts import speech


class GatewayTests(unittest.TestCase):
    def test_missing_runtime_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            gw = EngineWorkerGateway(root=Path(temp))
            self.assertFalse(gw.available("wayu-nc-v1"))
            self.assertFalse(gw.available("untrusted-entry"))
            with self.assertRaises(WorkerError):
                gw.synthesize("untrusted-entry", text="hi", voice_id="a",
                              speed=1.0, seed=1)
            with self.assertRaises(WorkerError):
                gw.synthesize("wayu-nc-v1", text="hi", voice_id="a",
                              speed=1.0, seed=1)
            gw.close()

    def test_runtime_check_only_uses_registered_gateway(self):
        with patch("voxweavetts.personal_wayu_engine.gateway") as mock:
            mock.return_value.available.return_value = False
            self.assertFalse(runtime_ready())
            mock.return_value.available.assert_called_once_with("wayu-nc-v1")

    def test_personal_adapter_calls_gateway_without_importing_model(self):
        with patch("voxweavetts.personal_wayu_engine.assets_ready", return_value=True), \
             patch("voxweavetts.personal_wayu_engine.runtime_ready", return_value=True), \
             patch("voxweavetts.personal_wayu_engine.gateway") as mock:
            mock.return_value.synthesize.return_value = b"\x00\x00" * 20
            engine = PersonalWayuEngine(seed=101)
            engine.select_voice("m_teen_bright")
            self.assertEqual(engine.generate("ทดสอบ", 1.1), b"\x00\x00" * 20)
            mock.return_value.synthesize.assert_called_once_with(
                "wayu-nc-v1", text="ทดสอบ", voice_id="m_teen_bright",
                speed=1.1, seed=101,
            )

    def test_worker_host_strict_data_only_schema(self):
        class FakeBackend:
            sample_rate = 24_000
            def synthesize(self, text, *, voice_id, speed, seed):
                return b"\x01\x00" * 5

        records = [
            {"version": 1, "request_id": 1, "method": "synthesize",
             "text": "hello", "voice_id": "f_young_warm", "speed": 1.0, "seed": 3},
            {"version": 1, "request_id": 2, "method": "execute",
             "text": "import os", "voice_id": "f_young_warm", "speed": 1.0, "seed": 3},
        ]
        input_data = io.StringIO("".join(json.dumps(r) + "\n" for r in records))
        output = io.StringIO()
        with patch.object(host, "_create_backend", return_value=FakeBackend()):
            host.serve("wayu-nc-v1", reader=input_data, writer=output)
        response = [json.loads(s) for s in output.getvalue().splitlines()]
        self.assertEqual(len(response), 2)
        self.assertTrue(response[0]["ok"])
        self.assertEqual(response[0]["sample_rate"], 24000)
        self.assertEqual(response[0]["pcm16_b64"], "AQABAAEAAQABAA==")
        self.assertFalse(response[1]["ok"])
        self.assertNotIn("import os", output.getvalue())

    def test_worker_strict_validation_rejects_untrusted_directives(self):
        with self.assertRaises(host.WorkerInputError):
            host._validate_request({"method": "shell", "command": "dir"})
        with self.assertRaises(host.WorkerInputError):
            host._validate_request({
                "version": 1, "request_id": 1, "method": "synthesize",
                "text": "ok", "voice_id": "a", "speed": float("nan"), "seed": 0,
            })
        self.assertIn(ENGINE_ID, [e.id for e in speech.list_engine_info()])


    def test_bounded_worker_output_rejects_oversized_line(self):
        import queue
        from types import SimpleNamespace
        from voxweavetts.engine_worker_gateway import WorkerSession
        session = WorkerSession(WorkerSpec("fake", "fake", 24000))
        output = queue.Queue()
        process = SimpleNamespace(stdout=io.StringIO("Z" * 80 + "\n"))
        with patch("voxweavetts.engine_worker_gateway.MAX_RESPONSE_LINE", 32):
            session._reader(process, output)
        self.assertEqual(output.get_nowait(), "")
        self.assertIsNone(output.get_nowait())

    def test_persistent_legacy_worker_refreshes_registry_for_new_model(self):
        from unittest.mock import Mock
        from voxweavetts.engine_worker_legacy import LegacyBackend
        from voxweavetts.engine_provider_catalog import PROVIDERS
        from voxweavetts.processing import InputError
        info = speech.get_engine_info("makham-paradee-cpu")
        fake_engine = Mock()
        fake_engine.generate.return_value = b"\x00\x01" * 8
        fake_registry = Mock()
        fake_registry.get.side_effect = [InputError("not loaded"), info]
        fake_registry.create.return_value = fake_engine
        with patch("voxweavetts.speech.engine_registry", return_value=fake_registry), \
             patch("voxweavetts.speech.refresh_engine_registry") as refresh:
            worker = LegacyBackend(PROVIDERS["pythaitts"])
            result = worker.synthesize(
                "สวัสดี", engine_id="makham-paradee-cpu",
                voice_id="paradee_thai", speed=1.0, seed=100,
            )
        self.assertEqual(result, b"\x00\x01" * 8)
        refresh.assert_called_once()
        fake_registry.create.assert_called_once_with("makham-paradee-cpu", 100)

if __name__ == "__main__":
    unittest.main()
