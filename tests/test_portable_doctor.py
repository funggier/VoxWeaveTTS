"""Read-only Portable Doctor and bundled uv selection regression."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from voxweavetts import portable_doctor as doctor
from voxweavetts import offline_wheelhouse as wh
from voxweavetts import runtime_tools
from voxweavetts.engine_provider_installer import InstallError, repair as repair_tts
from voxweavetts.m2m_runtime import M2MRuntimeError, repair as repair_m2m


def runtime(name="pythaitts", *, ready=False, state="not-installed",
            wheels="not-ready", consumers=None):
    consumers = consumers if consumers is not None else []
    return {
        "id": name, "kind": "tts", "installed": state != "not-installed",
        "ready": ready, "health_state": state,
        "wheelhouse": {"state": wheels, "ready_to_verify": wheels == "present-unverified",
                       "wheels": 2},
        "relative_path": "runtime/engine-envs/" + name,
        "consumers": consumers, "reference_count": len(consumers),
    }


def model(package="makham-paradee", adapter="makham-paradee-onnx-v1",
          runtime_id="pythaitts"):
    return {
        "package": {"id": package, "version": "1.0.0", "kind": "tts"},
        "runtime": {"id": runtime_id},
        "adapter": {"id": adapter},
    }


def wheel(path, name, version):
    with zipfile.ZipFile(path, "w") as archive:
        info = f"{name}-{version}.dist-info/"
        archive.writestr(info + "METADATA",
                         f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n\n")
        archive.writestr(info + "WHEEL",
                         "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        archive.writestr(name + "/__init__.py", b"trusted test module")


class PortableDoctorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "Portable"
        self.root.mkdir()
        (self.root / "runtime" / "python").mkdir(parents=True)
        (self.root / "runtime" / "python" / "python.exe").write_bytes(b"base")
        (self.root / "runtime" / "tools").mkdir()
        (self.root / "runtime" / "tools" / "uv.exe").write_bytes(b"uv")

    def inspect(self, models=None, runtimes=None, *, verify_wheelhouse=False):
        models = models if models is not None else [(model(), self.root / "models")]
        runtimes = runtimes if runtimes is not None else [runtime(consumers=[
            "v2:makham-paradee@1.0.0"])]
        metadata = {"license": {"spdx": "Apache-2.0",
                                "review_status": "review_required"}}
        with (patch.object(doctor, "installed_packages", return_value=models),
              patch.object(doctor, "inventory", return_value=runtimes),
              patch.object(doctor, "native_adapter_profile", return_value=metadata),
              patch.object(doctor, "platform_compatible", return_value=True)):
            return doctor.report(self.root, verify_wheelhouse=verify_wheelhouse)

    def test_clean_portable_makham_ready_even_without_optional_worker(self):
        before = sorted(x.relative_to(self.root).as_posix()
                        for x in self.root.rglob("*"))
        result = self.inspect()
        self.assertEqual(result["overall_state"], "ready")
        self.assertEqual(result["summary"]["models_waiting_for_runtime"], 0)
        self.assertEqual(result["core"]["uv"], "bundled")
        self.assertEqual(result["runtimes"][0]["recommended_action"],
                         "supply-matching-wheelhouse")
        self.assertEqual(result["models"][0]["file_hashes_checked"], "metadata-only")
        self.assertEqual(before, sorted(x.relative_to(self.root).as_posix()
                                        for x in self.root.rglob("*")))

    def test_wayu_requires_separate_runtime_and_stays_nc(self):
        models = [(model(), self.root / "models"),
                  (model("wayu-paxa-edge-nc", "wayu-nc-v1", "wayu-nc"),
                   self.root / "wayu")]
        wheelcases = [runtime(consumers=["v2:makham-paradee@1.0.0"]),
                      runtime("wayu-nc", wheels="recipe-unsupported",
                              consumers=["v2:wayu-paxa-edge-nc@1.0.0"])]
        with patch.object(doctor, "native_adapter_profile",
                          side_effect=lambda m, _: {"license": {
                              "spdx": "CC-BY-NC-4.0" if m["package"]["id"].startswith("wayu")
                              else "Apache-2.0",
                              "review_status": "hold" if m["package"]["id"].startswith("wayu")
                              else "review_required"}}):
            with (patch.object(doctor, "installed_packages", return_value=models),
                  patch.object(doctor, "inventory", return_value=wheelcases),
                  patch.object(doctor, "platform_compatible", return_value=True)):
                data = doctor.report(self.root)
        self.assertEqual(data["overall_state"], "needs-attention")
        self.assertEqual(data["summary"]["models_waiting_for_runtime"], 1)
        self.assertEqual(data["models"][1]["license_spdx"], "CC-BY-NC-4.0")
        self.assertEqual(data["runtimes"][1]["recommended_action"],
                         "review-online-provider-recipe")

    def test_relocated_runtime_recommends_verified_rebuild(self):
        result = self.inspect(runtimes=[
            runtime("sherpa", state="relocated", wheels="present-unverified")])
        self.assertEqual(result["runtimes"][0]["recommended_action"],
                         "verify-and-rebuild-wheelhouse")

    def test_missing_core_and_bundled_uv_have_different_actions(self):
        (self.root / "runtime" / "python" / "python.exe").unlink()
        result = self.inspect(models=[(model("wayu-paxa-edge-nc", "wayu-nc-v1",
                                            "wayu-nc"), self.root / "wayu")])
        self.assertEqual(result["overall_state"], "incomplete")
        self.assertEqual(result["runtimes"][0]["recommended_action"],
                         "restore-portable-python")
        (self.root / "runtime" / "python" / "python.exe").write_bytes(b"base")
        (self.root / "runtime" / "tools" / "uv.exe").unlink()
        self.assertEqual(self.inspect()["runtimes"][0]["recommended_action"],
                         "restore-bundled-uv")

    def test_symlinked_uv_not_counted_as_portable(self):
        link = self.root / "runtime" / "tools" / "uv.exe"
        link.unlink()
        outside = self.root.parent / "uv.exe"
        outside.write_bytes(b"foreign")
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Windows symlink creation is not permitted")
        self.assertNotEqual(runtime_tools.find_uv(self.root), str(link))
        self.assertEqual(self.inspect()["core"]["uv"], "missing")
        self.assertEqual(self.inspect()["core"]["portable"], False)

    def test_strict_mode_returns_exit_two_and_json_is_parseable(self):
        with patch.object(doctor, "report", return_value={
            "overall_state": "needs-attention", "format": doctor.FORMAT,
            "summary": {}, "models": [], "runtimes": [], "core": {}}):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                exitcode = doctor.main(["--json", "--strict",
                                         "--root", str(self.root)])
        self.assertEqual(exitcode, 2)
        self.assertEqual(json.loads(out.getvalue())["format"], doctor.FORMAT)

    def test_deep_wheel_tamper_always_flags_attention_even_if_runtime_ready(self):
        records = [runtime("sherpa", ready=True, state="ready",
                           wheels="present-unverified")]
        with patch.object(doctor, "_check_wheels",
                          return_value=("hash-mismatch", 2)):
            result = self.inspect(runtimes=records, verify_wheelhouse=True)
        self.assertEqual(result["overall_state"], "needs-attention")
        self.assertEqual(result["summary"]["invalid_wheelhouses"], 1)
        self.assertEqual(result["runtimes"][0]["recommended_action"],
                         "replace-corrupt-wheelhouse")
        self.assertTrue(result["runtimes"][0]["wheelhouse_sha256_checked"])

    def test_wheelhouse_deep_check_fails_closed_when_modified(self):
        recipe = self.root / "scripts" / "engine-dependencies" / "sherpa.txt"
        recipe.parent.mkdir(parents=True)
        recipe.write_text("sherpa-onnx==2.0.1\nnumpy==2.2.6\n")
        wheel_dir = self.root / "runtime" / "wheelhouse" / "sherpa"
        wheel_dir.mkdir(parents=True)
        for name, version in (("sherpa_onnx", "2.0.1"), ("numpy", "2.2.6")):
            wheel(wheel_dir / f"{name}-{version}-py3-none-any.whl", name, version)
        lock = wh.draft_lock(self.root, "sherpa", wheel_dir)
        lock_file = self.root / "scripts" / "wheelhouse-locks" / "sherpa.json"
        lock_file.parent.mkdir()
        lock_file.write_text(json.dumps(lock))
        self.assertEqual(doctor._check_wheels(self.root, "sherpa")[0],
                         "verified-for-inspection")
        first = next(wheel_dir.iterdir())
        data = first.read_bytes()
        first.write_bytes(data.replace(b"trusted test module", b"forged! test module"))
        self.assertEqual(doctor._check_wheels(self.root, "sherpa")[0],
                         "hash-mismatch")


class BundledRepairTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "Portable"
        self.root.mkdir()
        (self.root / "runtime" / "tools").mkdir(parents=True)
        (self.root / "runtime" / "tools" / "uv.exe").write_bytes(b"trusted uv")
        (self.root / "runtime" / "python").mkdir()
        (self.root / "runtime" / "python" / "python.exe").write_bytes(b"base")

    def test_tts_repair_selects_bundled_uv_when_system_path_empty(self):
        recipe = self.root / "scripts" / "engine-dependencies" / "sherpa.txt"
        recipe.parent.mkdir(parents=True)
        recipe.write_text("sherpa-onnx==2.0.1\n")
        with patch("voxweavetts.runtime_tools.shutil.which", return_value=None) as which:
            with self.assertRaisesRegex(InstallError, "marker is missing"):
                repair_tts("sherpa", root=self.root)
            which.assert_not_called()

    def test_m2m_repair_selects_bundled_uv_when_system_path_empty(self):
        recipe = self.root / "scripts" / "ai-dependencies" / "m2m100.txt"
        recipe.parent.mkdir(parents=True)
        recipe.write_text("torch==2.8.0\n")
        with patch("voxweavetts.runtime_tools.shutil.which", return_value=None) as which:
            with self.assertRaisesRegex(M2MRuntimeError, "marker is missing"):
                repair_m2m(root=self.root)
            which.assert_not_called()


if __name__ == "__main__":
    unittest.main()
