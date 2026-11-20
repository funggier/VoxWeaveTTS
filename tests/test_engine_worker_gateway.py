"""Gateway regression: bounded transport, protocol isolation and NC visibility."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts.engine_worker_gateway import (
    EngineWorkerGateway, WorkerError, WorkerSpec,
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
