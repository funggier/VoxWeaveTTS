"""Verify first-party Windows SAPI v4 speech package and input separation."""
from __future__ import annotations

import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "examples" / "v4-windows-sapi"
sys.path.insert(0, str(ROOT / "scripts"))
from build_vwmodel_v4 import build
from voxweavetts.universal_model_v4 import inspect_archive

# Never create .pyc files inside the distributable example tree.
sys.dont_write_bytecode = True
loader = importlib.util.spec_from_file_location("windows_sapi_worker", SRC / "plugin" / "worker.py")
assert loader and loader.loader
worker = importlib.util.module_from_spec(loader)
loader.loader.exec_module(worker)


class WindowsSapiPackageTests(unittest.TestCase):
    def request(self, **changes):
        request = {
            "version": 1, "request_id": 7, "method": "synthesize",
            "text": "Safe sample", "speed": 1.0, "voice_id": "system_default",
        }
        request.update(changes)
        return request

    def test_synthetic_v4_package_has_no_third_party_binaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = build(SRC, SRC / "spec.json", Path(tmp) / "sapi.vwmodel")
            manifest = inspect_archive(archive)
            self.assertEqual(manifest["package"]["id"], "windows-sapi-desktop")
            self.assertEqual(manifest["format_version"], 4)
            self.assertEqual(manifest["runtime"]["wheels"], [])
            self.assertEqual(manifest["rights"]["spdx"], "MIT")
            self.assertEqual(manifest["package"]["languages"], ["en"])
            self.assertEqual((SRC / "assets/LICENSE.txt").read_bytes(),
                             (ROOT / "LICENSE").read_bytes())
            self.assertEqual(
                {row["path"] for row in manifest["files"]},
                {"plugin/worker.py", "spec.json", "assets/readme.txt",
                 "assets/LICENSE.txt"},
            )

    def test_user_text_never_appears_in_powershell_command(self):
        unusual = 'test \u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35 "; Start-Process calc #'
        fake = subprocess.CompletedProcess(args=[], returncode=0,
                                           stdout=base64.b64encode(b"\x01\x02" * 400).decode(),
                                           stderr="")
        with patch.object(worker, "powershell_path", return_value=Path("powershell.exe")), \
             patch.object(worker.subprocess, "run", return_value=fake) as run:
            output = worker.synthesize(self.request(text=unusual))
        self.assertTrue(output["ok"])
        self.assertEqual(output["sample_rate"], 16000)
        command = run.call_args.args[0]
        self.assertEqual(command[4], "-EncodedCommand")
        self.assertNotIn(unusual, " ".join(command))
        self.assertEqual(json.loads(run.call_args.kwargs["input"])["text"], unusual)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(run.call_args.kwargs["timeout"], 105)

    def test_rejects_invalid_voice_text_speed_and_request(self):
        for values in (
            {"voice_id": "sapi_exec"},
            {"text": " "},
            {"text": "x" * 4001},
            {"speed": float("nan")},
            {"speed": -5},
            {"method": "translate"},
            {"request_id": "bad"},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    worker.synthesize(self.request(**values))

    def test_speech_failure_is_generic(self):
        with patch.object(worker, "powershell_path", return_value=Path("powershell.exe")), \
             patch.object(worker.subprocess, "run", return_value=subprocess.CompletedProcess(
                 args=[], returncode=1, stdout="", stderr="sensitive local path"
             )):
            with self.assertRaisesRegex(RuntimeError, "Windows SAPI failed"):
                worker.synthesize(self.request())

    @unittest.skipUnless(os.name == "nt" and os.getenv("VOXWEAVE_TEST_REAL_SAPI") == "1",
                         "real Windows SAPI voice is opt-in and host dependent")
    def test_real_windows_sapi_english_voice(self):
        response = worker.synthesize(self.request(text="This is real local speech."))
        raw = base64.b64decode(response["pcm16_b64"], validate=True)
        self.assertGreater(len(raw), 20000)
        self.assertTrue(any(b != 0 for b in raw))


if __name__ == "__main__":
    unittest.main()
