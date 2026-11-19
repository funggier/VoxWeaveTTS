"""Windows force-stop regression: exact ownership, PID reuse and unrelated apps."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from voxweavetts.process_ownership import (
    register_process, windows_process_created_filetime,
)

ROOT = Path(__file__).resolve().parents[1]


class StopCommandTests(unittest.TestCase):
    def test_stop_commands_and_source_are_shipped(self):
        self.assertTrue((ROOT / "Stop-VoxWeaveTTS.cmd").is_file())
        self.assertTrue((ROOT / "Stop-Dev.cmd").is_file())
        self.assertTrue((ROOT / "scripts" / "Stop-VoxWeaveTTS.ps1").is_file())
        primary = (ROOT / "scripts" / "Build-Portable.ps1").read_text(encoding="utf-8")
        self.assertIn("Build-Portable-V3.ps1", primary)
        portable_script = (ROOT / "scripts" / "Build-Portable-V3.ps1").read_text(encoding="utf-8")
        self.assertIn("Stop-Console.cmd", portable_script)
        self.assertIn("Stop-VoxWeaveTTS.cmd", portable_script)
        self.assertIn("wheelhouse-locks", portable_script)
        self.assertNotIn("Install-EngineProvider.ps1", portable_script)
        self.assertNotIn("Install-WayuWorker.ps1", portable_script)

    @unittest.skipUnless(os.name == "nt", "Windows-specific stop and FILETIME")
    def test_marker_matches_windows_process_creation_time(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertTrue(register_process("worker-host", root=Path(temp)))
            pid = os.getpid()
            marker = (Path(temp) / "runtime" / "processes"
                      / f"worker-host-{pid}.json")
            obj = json.loads(marker.read_text(encoding="utf-8"))
            self.assertEqual(obj["pid"], pid)
            self.assertEqual(obj["created_filetime"],
                             windows_process_created_filetime(pid))
            self.assertGreater(obj["created_filetime"], 0)

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"),
                         "Windows PowerShell required")
    def test_force_stop_reaps_registered_orphan_not_other_python(self):
        """Test real OS process termination, with an isolated temporary root."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stub = root / "src" / "voxweavetts"
            stub.mkdir(parents=True)
            (stub / "server.py").write_text("# fake test instance\n", encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            orphan_code = (
                "from pathlib import Path;"
                "from voxweavetts.process_ownership import register_process;"
                "import sys,time;"
                "assert register_process('worker-host',root=Path(sys.argv[1]));"
                "time.sleep(45)"
            )
            orphan = subprocess.Popen(
                [sys.executable, "-c", orphan_code, str(root)],
                cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            unrelated = subprocess.Popen(
                [sys.executable, "-c", "import time;time.sleep(45)"],
                cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                # Windows virtualenv launcher may delegate to a different
                # real Python PID. Match the exact process registry record.
                marker_dir = root / "runtime" / "processes"
                deadline = time.monotonic() + 10
                markers = []
                while not markers and time.monotonic() < deadline:
                    markers = list(marker_dir.glob("worker-host-*.json"))
                    if not markers:
                        time.sleep(0.1)
                self.assertTrue(markers, "child did not record ownership")
                marker = markers[0]
                script = str(ROOT / "scripts" / "Stop-VoxWeaveTTS.ps1")
                command = [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", script, "-ProjectRoot", str(root),
                ]
                dry = subprocess.run(
                    command + ["-DryRun"], capture_output=True, text=True,
                    errors="replace", timeout=25,
                )
                self.assertEqual(dry.returncode, 0, dry.stderr)
                self.assertIsNone(orphan.poll())
                self.assertIsNone(unrelated.poll())
                actual = subprocess.run(
                    command, capture_output=True, text=True,
                    errors="replace", timeout=25,
                )
                self.assertEqual(actual.returncode, 0, actual.stdout + actual.stderr)
                orphan.wait(timeout=5)
                self.assertIsNone(unrelated.poll(), "unrelated Python was terminated")
                self.assertFalse(marker.exists(), "stale marker was not pruned")
            finally:
                for process in (orphan, unrelated):
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=6)

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"),
                         "Windows PowerShell required")
    def test_reused_pid_marker_cannot_stop_unrelated_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = root / "src" / "voxweavetts"
            identity.mkdir(parents=True)
            (identity / "server.py").write_text("# test installation\n", encoding="utf-8")
            directory = root / "runtime" / "processes"
            directory.mkdir(parents=True)
            pid = os.getpid()
            # This is a real, unrelated live PID with a deliberately stale
            # creation time. The stop utility MUST NOT kill the test runner.
            marker = directory / f"worker-host-{pid}.json"
            marker.write_text(json.dumps({
                "format": "voxweavetts-owned-process-v1",
                "project_root": str(root.resolve()),
                "kind": "worker-host", "pid": pid,
                "created_filetime": windows_process_created_filetime(pid) - 123456789,
            }), encoding="utf-8")
            command = [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(ROOT / "scripts" / "Stop-VoxWeaveTTS.ps1"),
                "-ProjectRoot", str(root),
            ]
            stopped = subprocess.run(command, capture_output=True, text=True,
                                     errors="replace", timeout=25)
            self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
            self.assertFalse(marker.exists(), "stale marker not discarded")


if __name__ == "__main__":
    unittest.main()
