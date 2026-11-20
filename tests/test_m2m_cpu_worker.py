"""M2M100 CPU-thread safety, offline subprocess and opt-in real-inference check."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from voxweavetts import m2m_runtime
from voxweavetts.worker_memory_budget import MemoryHeadroom

GiB = 1024**3


class M2MCPUWorkerTests(unittest.TestCase):
    def test_worker_memory_preflight_rejects_five_gib_commit_without_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            worker = m2m_runtime.TranslationWorkerSession(Path(temp))
            with (patch("voxweavetts.m2m_runtime.ready", return_value=True),
                  patch("voxweavetts.worker_memory_budget.memory_headroom",
                        return_value=MemoryHeadroom(8*GiB,5*GiB)),
                  patch.object(worker, "_stop"),
                  patch("voxweavetts.m2m_runtime.subprocess.Popen") as popen):
                with self.assertRaisesRegex(m2m_runtime.M2MRuntimeError,
                                            "available Windows RAM/commit"):
                    worker._start()
                popen.assert_not_called()
            self.assertFalse((Path(temp)/"logs"/"ai-runtime").exists())

class M2MGracefulShutdownTests(unittest.TestCase):
    def test_graceful_worker_eof_waits_for_normal_exit_without_taskkill(self):
        worker = m2m_runtime.TranslationWorkerSession()
        proc = Mock()
        proc.stdin = io.StringIO()
        proc.stdout = io.StringIO()
        proc.poll.return_value = None
        proc.wait.return_value = 0
        worker._process = proc
        worker._log = io.StringIO()
        with patch("voxweavetts.m2m_runtime.subprocess.run") as hard_kill:
            worker.close()
        proc.wait.assert_called_once_with(timeout=3)
        hard_kill.assert_not_called()
        self.assertTrue(proc.stdin.closed)
        self.assertTrue(proc.stdout.closed)
        self.assertIsNone(worker._process)
        self.assertIsNone(worker._log)

    @unittest.skipUnless(os.name == "nt", "Windows uses taskkill to end stalled child trees")
    def test_stalled_worker_uses_owned_tree_kill_after_eof_timeout(self):
        worker = m2m_runtime.TranslationWorkerSession()
        proc = Mock()
        proc.pid = 54321
        proc.stdin = io.StringIO()
        proc.stdout = io.StringIO()
        proc.poll.return_value = None
        proc.wait.side_effect = [subprocess.TimeoutExpired("python",3),0]
        worker._process = proc
        with patch("voxweavetts.m2m_runtime.subprocess.run") as hard_kill:
            worker.close()
        hard_kill.assert_called_once()
        command = hard_kill.call_args.args[0]
        self.assertEqual(command[:3], ["taskkill", "/PID", "54321"])
        self.assertIn("/T", command)
        self.assertIn("/F", command)
        self.assertEqual(proc.wait.call_count, 2)
        self.assertTrue(proc.stdin.closed)
        self.assertTrue(proc.stdout.closed)

if __name__=="__main__":
    unittest.main()