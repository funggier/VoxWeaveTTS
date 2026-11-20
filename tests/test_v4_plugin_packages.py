"""Universal v4 regression: unknown executable engine, one-click acceptance, safety."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from voxweavetts import universal_model_v4 as v4
from voxweavetts.package_install_v3 import preview, commit
from voxweavetts.engine_provider_catalog import all_providers

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_vwmodel_v4 import build


def fixture(base: Path, *, kind: str = "python", harmful_wheel: bool = False):
    src = base / "source"
    (src / "plugin").mkdir(parents=True)
    (src / "assets").mkdir()
    (src / "assets" / "example.txt").write_text("Original voice engine fixture\n")
    if kind == "python":
        (src / "plugin" / "worker.py").write_text(
            "import json,sys\nfor line in sys.stdin:\n"
            "  r=json.loads(line)\n"
            "  print(json.dumps({'version':1,'request_id':r['request_id'],"
            "'ok':False,'error':'synthesis_failure'}),flush=True)\n",
            encoding="utf-8")
    else:
        (src / "plugin" / "worker.exe").write_bytes(b"MZ" + b"fixture")
    wheels = []
    if harmful_wheel:
        wheel = "fixture-1.0.0-py3-none-any.whl"
        file = src / "runtime" / "wheels" / wheel
        file.parent.mkdir(parents=True)
        with zipfile.ZipFile(file, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("distutils-precedence.pth", "import malicious")
            archive.writestr("fixture-1.0.0.dist-info/WHEEL", "Wheel-Version: 1.0")
        wheels.append("runtime/wheels/" + wheel)
    spec = {
        "package": {"id": "demo-future-engine", "version": "1.0.0", "kind": "tts",
                    "title": "Future engine", "languages": ["en"]},
        "engine": {"protocol": 1, "entrypoint": (
            "plugin/worker.py" if kind == "python" else "plugin/worker.exe"),
            "language": "en", "sample_rate": 16000,
            "voices": [{"id": "new_voice", "label": "Unknown voice"}]},
        "runtime": {"python": "3.11" if kind == "python" else "native",
                    "platform": "windows-x64", "wheels": wheels},
        "rights": {"spdx": "MIT", "url": "https://opensource.org/license/mit",
                   "attribution": "Original test fixture",
                   "source": "https://github.com/funggier/VoxWeaveTTS"},
    }
    spec_file = base / "spec.json"
    spec_file.write_text(json.dumps(spec), encoding="utf-8")
    archive = base / "fixture.vwmodel"
    build(src, spec_file, archive)
    return archive


class V4PluginPackageTests(unittest.TestCase):
    def test_v4_unknown_engine_requires_no_core_adapter_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive = fixture(base)
            manifest = v4.inspect_archive(archive)
            self.assertEqual(manifest["format_version"], 4)
            self.assertEqual(manifest["engine"]["entrypoint"], "plugin/worker.py")
            with patch.object(v4, "core_python", return_value=Path(sys.executable)), patch.object(
                v4, "sys_platform", return_value="windows-x64"
            ):
                result = v4.install(archive, root=base / "portable")
                self.assertEqual(result["engine_id"], "model-demo-future-engine-1_0_0")
                self.assertTrue(result["user_trusted_plugin_code"])
                found = v4.for_engine(result["engine_id"], root=base / "portable")
                self.assertIsNotNone(found)
                profiles = all_providers(root=base / "portable")
                self.assertIn("v4-demo-future-engine-1-0-0", profiles)
                self.assertEqual(profiles["v4-demo-future-engine-1-0-0"].driver, "external")
                self.assertTrue(v4.remove("demo-future-engine", "1.0.0",
                                          root=base / "portable"))
                self.assertIsNone(v4.for_engine(result["engine_id"], root=base / "portable"))

    def test_one_click_token_can_install_v4_without_new_rights_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = fixture(Path(tmp))
            record = preview(choose_file=lambda: archive)
            self.assertEqual(record["format_version"], 4)
            self.assertTrue(record["contains_executable_plugin"])
            self.assertNotIn(str(archive), str(record))
            with patch.object(v4, "install", return_value={"format_version": 4}) as installer:
                result = commit(record["token"], accepted_rights=True)
                self.assertEqual(result["format_version"], 4)
                installer.assert_called_once_with(archive.resolve())
            with self.assertRaises(ValueError):
                commit(record["token"], accepted_rights=True)

    def test_selected_archive_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = fixture(Path(tmp))
            record = preview(choose_file=lambda: archive)
            with archive.open("ab") as file:
                file.write(b"tampered")
            with patch.object(v4, "install") as installer:
                with self.assertRaises(ValueError):
                    commit(record["token"], accepted_rights=True)
                installer.assert_not_called()

    def test_native_worker_is_a_supported_v4_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = fixture(Path(tmp), kind="native")
            manifest = v4.inspect_archive(archive)
            self.assertEqual(manifest["runtime"]["python"], "native")
            self.assertEqual(manifest["engine"]["entrypoint"], "plugin/worker.exe")

    def test_reject_unsafe_wheel_startup_hook_and_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive = fixture(base, harmful_wheel=True)
            target = base / "portable"
            with patch.object(v4, "core_python", return_value=Path(sys.executable)), patch.object(
                v4, "sys_platform", return_value="windows-x64"
            ):
                with self.assertRaisesRegex(ValueError, "startup hook"):
                    v4.install(archive, root=target)
                self.assertFalse(v4.installed_packages(target))
                self.assertFalse((target / "runtime" / "environments-v4").exists())

    def test_reject_protocol_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = fixture(Path(tmp))
            m = v4.inspect_archive(archive)
            m["engine"]["protocol"] = 2
            with self.assertRaisesRegex(v4.V4PackageError, "worker protocol"):
                v4.validate_manifest(m)

    def test_reject_native_worker_with_python_wheels(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = fixture(Path(tmp), kind="native")
            m = v4.inspect_archive(archive)
            m["runtime"]["wheels"] = ["runtime/wheels/unknown-1.0.0-py3-none-any.whl"]
            with self.assertRaises(v4.V4PackageError):
                v4.validate_manifest(m)

    def test_reject_traversal_and_extra_executable(self):
        for name in ("../escape.py", "plugin/../escape.py", "CON.txt",
                     "plugin/other.exe", "tools/start.ps1"):
            with self.subTest(name=name):
                if name.endswith(".exe") and name != "plugin/worker.exe":
                    with tempfile.TemporaryDirectory() as tmp:
                        archive = fixture(Path(tmp))
                        m = v4.inspect_archive(archive)
                        m["files"].append({"path": name, "size": 2,
                                           "sha256": hashlib.sha256(b"xx").hexdigest()})
                        with self.assertRaises(ValueError):
                            v4.validate_manifest(m)
                else:
                    with self.assertRaises(ValueError):
                        v4._path(name)


if __name__ == "__main__":
    unittest.main()
