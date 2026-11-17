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
        from dataclasses import replace
        info = replace(speech.get_engine_info("makham-paradee-cpu"),
                       assets_ready=True, runtime_ready=True)
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

    def test_worker_keeps_loaded_models_when_memory_is_healthy(self):
        from unittest.mock import Mock
        from voxweavetts.worker_memory_budget import MemoryHeadroom
        broker = EngineWorkerGateway(specs={})
        idle = Mock(last_used=7.0)
        broker._sessions["idle"] = idle
        with patch("voxweavetts.worker_memory_budget.memory_headroom",
                   return_value=MemoryHeadroom(9 * 1024**3, 10 * 1024**3)):
            self.assertEqual(broker._reclaim_idle_for_memory("new"), 0)
        idle.reclaim_if_idle.assert_not_called()

    def test_memory_pressure_reclaims_only_other_idle_models_oldest_first(self):
        from unittest.mock import Mock
        from voxweavetts.worker_memory_budget import MemoryHeadroom
        broker = EngineWorkerGateway(specs={})
        old = Mock(last_used=1.0)
        old.reclaim_if_idle.return_value = True
        recent = Mock(last_used=2.0)
        current = Mock(last_used=0.0)
        broker._sessions = {"recent": recent, "current": current, "old": old}
        low = MemoryHeadroom(4 * 1024**3, 512 * 1024**2)
        healthy = MemoryHeadroom(4 * 1024**3, 6 * 1024**3)
        with patch("voxweavetts.worker_memory_budget.memory_headroom",
                   side_effect=[low, low, healthy]):
            self.assertEqual(broker._reclaim_idle_for_memory("current"), 1)
        old.reclaim_if_idle.assert_called_once_with()
        recent.reclaim_if_idle.assert_not_called()
        current.reclaim_if_idle.assert_not_called()

    def test_busy_worker_cannot_be_reclaimed(self):
        from unittest.mock import Mock
        from voxweavetts.engine_worker_gateway import WorkerSession
        session = WorkerSession(WorkerSpec("example", "example", 24000))
        session._process = Mock()
        session._process.poll.return_value = None
        session._lock.acquire()
        outcome = []
        import threading
        t = threading.Thread(target=lambda: outcome.append(session.reclaim_if_idle()))
        t.start()
        t.join(timeout=2)
        try:
            self.assertEqual(outcome, [False])
            session._process.terminate.assert_not_called()
        finally:
            session._lock.release()
            session._process = None

    def test_host_labels_allocation_errors_without_leaking_text(self):
        class OutOfMemory:
            sample_rate = 24000
            def synthesize(self, text, *, voice_id, speed, seed):
                raise MemoryError("input is SECRET")

        request = {"version": 1, "request_id": 1, "method": "synthesize",
                   "text": "SECRET", "voice_id": "f_young_warm",
                   "speed": 1.0, "seed": 3}
        output = io.StringIO()
        with patch.object(host, "_create_backend", return_value=OutOfMemory()):
            host.serve("wayu-nc-v1",
                       reader=io.StringIO(json.dumps(request) + "\n"),
                       writer=output)
        result = json.loads(output.getvalue())
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "resource_exhausted")
        self.assertNotIn("SECRET", output.getvalue())

    def test_low_memory_never_evicts_requested_loaded_worker(self):
        from unittest.mock import Mock
        from voxweavetts.worker_memory_budget import MemoryHeadroom
        broker = EngineWorkerGateway(specs={})
        requested = Mock(last_used=5.0)
        other = Mock(last_used=1.0)
        other.reclaim_if_idle.return_value = True
        broker._sessions = {"requested": requested, "other": other}
        low = MemoryHeadroom(512 * 1024**2, 512 * 1024**2)
        with patch("voxweavetts.worker_memory_budget.memory_headroom",
                   return_value=low):
            self.assertEqual(broker._reclaim_idle_for_memory("requested"), 1)
        requested.reclaim_if_idle.assert_not_called()

    def test_windows_worker_stop_terminates_process_tree(self):
        from unittest.mock import Mock
        from voxweavetts.engine_worker_gateway import WorkerSession
        worker = WorkerSession(WorkerSpec("demo", "demo", 24000))
        process = Mock()
        process.pid = 12345
        process.poll.return_value = None
        process.wait.return_value = 0
        worker._process = process
        with patch("voxweavetts.engine_worker_gateway.os.name", "nt"), \
             patch("voxweavetts.engine_worker_gateway.subprocess.run") as kill:
            worker.close()
        self.assertEqual(kill.call_args.args[0],
                         ["taskkill", "/PID", "12345", "/T", "/F"])
        process.wait.assert_called_once_with(timeout=2)


if __name__ == "__main__":
    unittest.main()
