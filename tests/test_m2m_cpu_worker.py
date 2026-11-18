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

from voxweavetts import ai_engine_registry, m2m_runtime, m2m_smoke
from voxweavetts.worker_memory_budget import MemoryHeadroom

GiB = 1024**3


class M2MCPUWorkerTests(unittest.TestCase):
    def test_torch_only_imports_inside_isolated_model_loader_and_limits_threads(self):
        fake_torch = ModuleType("torch")
        fake_torch.set_num_threads = Mock()
        fake_torch.set_num_interop_threads = Mock()
        fake_torch.set_grad_enabled = Mock()
        fake_transformers = ModuleType("transformers")

        tokenizer = object()
        model = Mock()
        model.eval.return_value = model

        class Tokenizer:
            from_pretrained = Mock(return_value=tokenizer)

        class Conditional:
            from_pretrained = Mock(return_value=model)

        fake_transformers.M2M100Tokenizer = Tokenizer
        fake_transformers.M2M100ForConditionalGeneration = Conditional
        ai_engine_registry._loaded_m2m.cache_clear()
        with (patch.dict(sys.modules, {"torch": fake_torch,
                                       "transformers": fake_transformers}),
              patch("os.cpu_count", return_value=14)):
            try:
                result = ai_engine_registry._loaded_m2m("trusted-app-model")
                self.assertEqual(result, (tokenizer, model))
                self.assertIs(ai_engine_registry._loaded_m2m("trusted-app-model"), result)
            finally:
                ai_engine_registry._loaded_m2m.cache_clear()
        fake_torch.set_num_threads.assert_called_once_with(2)
        fake_torch.set_num_interop_threads.assert_called_once_with(1)
        fake_torch.set_grad_enabled.assert_called_once_with(False)
        Tokenizer.from_pretrained.assert_called_once_with(
            "trusted-app-model", local_files_only=True)
        Conditional.from_pretrained.assert_called_once_with(
            "trusted-app-model", local_files_only=True, use_safetensors=True)

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

    def test_isolated_worker_has_offline_utf8_and_bounded_cpu_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            worker=m2m_runtime.TranslationWorkerSession(root)
            proc=Mock()
            proc.poll.return_value=0
            proc.pid=12123
            proc.stdin=io.StringIO()
            proc.stdout=io.StringIO()
            with (patch("voxweavetts.m2m_runtime.ready",return_value=True),
                  patch("voxweavetts.worker_memory_budget.memory_headroom",
                        return_value=MemoryHeadroom(8*GiB,8*GiB)),
                  patch("voxweavetts.m2m_runtime.subprocess.Popen",
                        return_value=proc) as popen,
                  patch("voxweavetts.m2m_runtime.threading.Thread") as thread,
                  patch("voxweavetts.process_ownership.register_process") as register):
                worker._start()
                args=popen.call_args.args[0]
                env=popen.call_args.kwargs["env"]
                self.assertEqual(args[2:],
                                 ["-m", "voxweavetts.m2m_worker"])
                self.assertEqual(env["OMP_NUM_THREADS"], "2")
                self.assertEqual(env["MKL_NUM_THREADS"], "2")
                self.assertEqual(env["TOKENIZERS_PARALLELISM"], "false")
                self.assertEqual(env["HF_HUB_OFFLINE"], "1")
                self.assertEqual(env["TRANSFORMERS_OFFLINE"], "1")
                self.assertEqual(env["PYTHONNOUSERSITE"], "1")
                self.assertEqual(env["PYTHONIOENCODING"], "utf-8")
                self.assertEqual(env["PYTHONPATH"], str(root/"src"))
                thread.return_value.start.assert_called_once()
                register.assert_called_once()
                worker.close()
                self.assertIsNone(worker._process)


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

class M2MRealSmokeTests(unittest.TestCase):
    def test_uses_only_fixed_two_examples_one_worker_closes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            translations=("สวัสดีเช้า", "Thank you.")
            with (patch("voxweavetts.m2m_smoke.ready",return_value=True),
                  patch("voxweavetts.m2m_smoke.native_translation_packages",
                        return_value=[({"package_id":"m2m100-418m",
                                        "version":"1.0.0"},root/"weights")]),
                  patch("voxweavetts.m2m_smoke.TranslationWorkerSession")
                        as constructor):
                session=constructor.return_value
                session.translate.side_effect=translations
                report=m2m_smoke.verify(root,timeout=30)
            constructor.assert_called_once_with(root=root, timeout=30)
            self.assertEqual([x["translation"] for x in report["samples"]],
                             list(translations))
            self.assertEqual(report["format"],
                             "voxweavetts.m2m100-inference-check-v1")
            self.assertTrue(report["offline"])
            self.assertEqual(session.translate.call_count,2)
            self.assertEqual(session.translate.call_args_list[0].args[0],
                             "Good morning.")
            self.assertEqual(session.translate.call_args_list[1].args[0],
                             "ขอบคุณครับ")
            session.close.assert_called_once()

    def test_wrong_script_or_unchanged_result_fails_and_releases_worker(self):
        root = Path("mocked-root")
        cases = (
            (("Good morning.", "Thanks."), "unchanged source"),
            (("Hello.", "Thanks."), "target-language checks"),
        )
        for answers, error in cases:
            with self.subTest(answers=answers):
                with (patch("voxweavetts.m2m_smoke.ready",return_value=True),
                      patch("voxweavetts.m2m_smoke.native_translation_packages",
                            return_value=[({"package_id":"m2m100-418m",
                                            "version":"1.0.0"},root/"model")]),
                      patch("voxweavetts.m2m_smoke.TranslationWorkerSession") as build):
                    instance = build.return_value
                    instance.translate.side_effect = answers
                    with self.assertRaisesRegex(m2m_runtime.M2MRuntimeError,error):
                        m2m_smoke.verify(root)
                    instance.close.assert_called_once()

    def test_no_runtime_fails_closed_without_loading_model(self):
        with tempfile.TemporaryDirectory() as temp:
            with (patch("voxweavetts.m2m_smoke.ready",return_value=False),
                  patch("voxweavetts.m2m_smoke.TranslationWorkerSession")
                    as constructor):
                with self.assertRaisesRegex(m2m_runtime.M2MRuntimeError,
                                            "not ready"):
                    m2m_smoke.verify(Path(temp))
                constructor.assert_not_called()

    def test_worker_closed_on_second_error(self):
        root=Path("mocked-root")
        with (patch("voxweavetts.m2m_smoke.ready",return_value=True),
              patch("voxweavetts.m2m_smoke.native_translation_packages",
                    return_value=[({"package_id":"m2m100-418m",
                                    "version":"1.0.0"},root/"model")]),
              patch("voxweavetts.m2m_smoke.TranslationWorkerSession")
                as constructor):
            session=constructor.return_value
            session.translate.side_effect=["สวัสดี",m2m_runtime.M2MRuntimeError(
                "worker timed out")]
            with self.assertRaisesRegex(m2m_runtime.M2MRuntimeError,"timed out"):
                m2m_smoke.verify(root)
            session.close.assert_called_once()

    def test_cli_json_is_ascii_and_strict_failure_exit(self):
        report={"format":"voxweavetts.m2m100-inference-check-v1",
                "samples":[{"translation":"สวัสดี"}]}
        buffer=io.StringIO()
        with (patch("voxweavetts.m2m_smoke.verify",return_value=report),
              contextlib.redirect_stdout(buffer)):
            self.assertEqual(m2m_smoke.main(["--json"]),0)
        self.assertEqual(json.loads(buffer.getvalue()),report)
        self.assertTrue(buffer.getvalue().isascii())
        with (patch("voxweavetts.m2m_smoke.ready",return_value=False),
              contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(m2m_smoke.main([]),2)

if __name__=="__main__":
    unittest.main()
