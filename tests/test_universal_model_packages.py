"""Native Universal v2 regression tests (no embedded v1 manifest or bridge)."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from voxweavetts.universal_model_packages import (
    FORMAT, UniversalPackageError, native_adapter_profile,
    activation_compatible, inspect_archive, install_model_package,
    installed_packages, make_package, native_tts_packages,
    native_translation_packages, package_status, remove_model_package,
    runtime_fingerprint, validate_manifest,
)


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def fixture(folder: Path, *, kind="tts", runtime_source="reuse-only"):
    source = folder / "inputs"
    source.mkdir(parents=True, exist_ok=True)
    if kind == "tts":
        adapter_id = "vachana-onnx-v1"
        rt_id, files = "vachana", {
            "speaker_config.json": b'{"audio":{"sample_rate":22050}}',
            "voices/th_f_1.onnx": b"\x08\x01" + b"v" * 1150,
        }
        cap = {"language": "th", "sample_rate": 22050,
               "voices": [{"id": "th_f_1", "label": "Female 1",
                           "asset": "voices/th_f_1.onnx"}]}
    elif kind == "translation":
        adapter_id = "m2m100-transformers-v1"
        rt_id, files = "m2m100", {
            "config.json": b'{"model_type":"m2m_100"}',
            "vocab.json": b'{"hello":1}',
            "sentencepiece.bpe.model": b"dummy-vocabulary",
            "model.safetensors": b"dummy-checkpoint",
        }
        cap = {"model_family": "m2m100"}
    else:
        adapter_id = "untrusted-stt-v1"
        rt_id, files = "stt-worker", {"model.onnx": b"opaque-model"}
        cap = {"features": ["transcribe"]}
    for name, content in files.items():
        file = source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content)
    rights = {
        "license": {"spdx": "MIT", "url": "https://example.org/license",
                    "attribution": "Unit test model metadata", "review_status": "review_required"},
        "source": {"url": "https://example.org/model", "revision": "test"},
    }
    (source / "legal").mkdir(exist_ok=True)
    (source / "legal/rights.json").write_bytes(dump(rights))
    lock = None
    if runtime_source != "reuse-only":
        lock = "runtime/locks/win-x64-cpu.lock"
        file = source / lock
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(dump({"requirements": [{"name": "onnxruntime", "version": "1.20.1"}], "wheels": []}))
    (source / "manifest-assets.json").write_bytes(dump({"paths": sorted(files)}))
    selected = sorted(files) + ["manifest-assets.json", "legal/rights.json"] + ([lock] if lock else [])
    manifest = {
        "format": FORMAT, "format_version": 2,
        "package": {"id": "v2-native-test", "version": "1.0.0",
                    "kind": kind, "title": "Native Universal 2.0",
                    "languages": ["th", "en"] if kind == "translation" else ["th"]},
        "adapter": {"id": adapter_id, "api_version": 1,
                    "trust": "external" if kind == "stt" else "builtin"},
        "runtime": {"id": rt_id, "kind": "python-venv", "python": "3.11",
                    "platform": "any", "accelerator": "cpu",
                    "source": runtime_source,
                    "install_policy": "reuse-only" if lock is None else "reuse-or-create",
                    "lockfile": lock},
        "capabilities": cap, "assets": "manifest-assets.json",
        "rights": "legal/rights.json",
        "files": [{"path": name, "size": (source/name).stat().st_size,
                   "sha256": hashlib.sha256((source/name).read_bytes()).hexdigest()}
                  for name in selected],
    }
    return source, manifest


class NativeV2Tests(unittest.TestCase):
    def test_schema_never_embeds_v1_and_v1_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest = fixture(Path(tmp))
            self.assertNotIn("compatibility", manifest)
            self.assertEqual(validate_manifest(manifest), manifest)
            with self.assertRaises(UniversalPackageError):
                validate_manifest({**manifest, "compatibility": {"format_version": 1}})
            with self.assertRaises(UniversalPackageError):
                validate_manifest({**manifest, "format_version": 1})

    def test_native_tts_roundtrip_and_remove_only_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, manifest = fixture(root)
            a = root / "a.vwmodel"
            b = root / "b.vwmodel"
            make_package(source, manifest, a)
            for row in manifest["files"]:
                os.utime(source / row["path"], (1_600_000_000, 1_600_000_000))
            make_package(source, manifest, b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(inspect_archive(a), manifest)
            self.assertEqual(install_model_package(a, root=root)["format_version"], 2)
            stored = installed_packages(root)
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0][1].parts[-4:], ("v2", "tts", "v2-native-test", "1.0.0"))
            self.assertEqual(len(native_tts_packages(root)), 1)
            native = native_adapter_profile(*stored[0])
            self.assertEqual(native["voices"][0]["id"], "th_f_1")
            self.assertTrue(activation_compatible(manifest))
            self.assertTrue(remove_model_package("v2-native-test", "1.0.0", root=root))
            self.assertFalse(remove_model_package("v2-native-test", "1.0.0", root=root))
            self.assertEqual(installed_packages(root), [])

    def test_native_v2_registers_as_tts_engine_without_legacy_manifest(self):
        from unittest.mock import patch
        from voxweavetts import speech
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, manifest = fixture(root)
            archive = root / "native.vwmodel"
            make_package(source, manifest, archive)
            install_model_package(archive, root=root)
            native = native_tts_packages(root)
            with patch("voxweavetts.universal_model_packages.native_tts_packages",
                       return_value=native):
                speech.refresh_engine_registry()
                try:
                    engine_id = "model-v2-native-test-1_0_0"
                    item = speech.get_engine_info(engine_id)
                    self.assertEqual(item.voice_ids, ("th_f_1",))
                    self.assertTrue(item.assets_ready)
                    self.assertEqual(item.commercial_status, "review_required")
                    voice = speech.create_voice_engine(engine_id, seed=42)
                    self.assertEqual(voice.id, engine_id)
                finally:
                    speech.refresh_engine_registry()

    def test_native_v2_builder_uses_only_asset_folder_and_native_spec(self):
        from unittest.mock import patch
        import sys
        scripts = str(Path(__file__).resolve().parents[1] / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        from build_vwmodel_v2 import build
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, manifest = fixture(root)
            spec = {key: manifest[key] for key in ("package", "adapter", "runtime", "capabilities")}
            spec_file = root / "v2-spec.json"
            spec_file.write_text(json.dumps(spec), encoding="utf-8")
            output = root / "packed.vwmodel"
            build(source, spec_file, output)
            converted = inspect_archive(output)
            self.assertEqual(converted["format_version"], 2)
            self.assertNotIn("compatibility", converted)
            self.assertEqual(converted["capabilities"], spec["capabilities"])

    def test_native_translation_no_v1_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, manifest = fixture(root, kind="translation")
            archive = root / "t.vwmodel"
            make_package(source, manifest, archive)
            install_model_package(archive, root=root)
            entries = native_translation_packages(root)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0][0]["engine_adapter"], "m2m100-transformers-v1")
            self.assertEqual(entries[0][1].parts[-4:], ("v2", "translation", "v2-native-test", "1.0.0"))

    def test_unknown_stt_is_data_only_and_no_runtime_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, manifest = fixture(root, kind="stt", runtime_source="recipe-only")
            archive = root / "x.vwmodel"
            make_package(source, manifest, archive)
            result = install_model_package(archive, root=root)
            self.assertFalse(result["activation_supported"])
            self.assertEqual(len(installed_packages(root)), 1)
            self.assertFalse((root / "runtime").exists())
            status = package_status(*installed_packages(root)[0][::1], root=root) if False else package_status(
                installed_packages(root)[0][0], root=root, folder=installed_packages(root)[0][1]
            )
            self.assertFalse(status["adapter_trusted"])
            self.assertFalse(status["runtime_ready"])
            self.assertEqual(status["license"]["spdx"], "MIT")

    def test_corrupt_metadata_hash_and_extra_entry_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, manifest = fixture(root)
            archive = root / "good.vwmodel"
            make_package(source, manifest, archive)
            for change in ("hash", "extra", "traversal", "symlink"):
                with zipfile.ZipFile(archive) as src:
                    records = {f.filename: src.read(f) for f in src.infolist()}
                if change == "hash":
                    records["speaker_config.json"] = b"bad-file"
                elif change == "extra":
                    records["inject.py"] = b"print('bad')"
                elif change == "traversal":
                    records["../outside.txt"] = b"unsafe"
                malformed = root / (change + ".vwmodel")
                with zipfile.ZipFile(malformed, "w") as dst:
                    for name, content in records.items():
                        info = zipfile.ZipInfo(name)
                        if change == "symlink" and name == "speaker_config.json":
                            info.create_system = 3
                            info.external_attr = (stat.S_IFLNK | 0o644) << 16
                        dst.writestr(info, content)
                with self.subTest(change=change), self.assertRaises(UniversalPackageError):
                    install_model_package(malformed, root=root)
                self.assertEqual(installed_packages(root), [])

    def test_malicious_schema_and_unpinned_wheels_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, good = fixture(Path(tmp))
            edits = (
                lambda m: m["package"].update({"id": "../outside"}),
                lambda m: m["adapter"].update({"api_version": True}),
                lambda m: m["runtime"].update({"source": "shell-execute"}),
                lambda m: m["files"].append({"path": "scripts/run.py", "sha256": "0" * 64, "size": 1}),
                lambda m: m["files"].append({"path": "MANIFEST-assets.json", "sha256": "0" * 64, "size": 1}),
                lambda m: m["capabilities"]["voices"][0].update({"asset": "../evil.onnx"}),
                lambda m: m["files"].append({"path": "model.pth", "sha256": "0" * 64, "size": 1}),
            )
            for edit in edits:
                m = copy.deepcopy(good)
                edit(m)
                with self.subTest(edit=edit), self.assertRaises(UniversalPackageError):
                    validate_manifest(m)

    def test_package_identity_unique_across_model_kinds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a_source, tts = fixture(root / "one", kind="tts")
            b_source, stt = fixture(root / "two", kind="stt")
            a_zip = root / "a.vwmodel"
            b_zip = root / "b.vwmodel"
            make_package(a_source, tts, a_zip)
            make_package(b_source, stt, b_zip)
            install_model_package(a_zip, root=root)
            with self.assertRaisesRegex(UniversalPackageError, "already installed"):
                install_model_package(b_zip, root=root)
            self.assertEqual(len(installed_packages(root)), 1)

    def test_windows_device_and_reserved_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, original = fixture(Path(tmp))
            for bad_name in ("CON.json", "com1.txt", "notes?.txt", "NUL.onnx"):
                with self.subTest(filename=bad_name):
                    malicious = copy.deepcopy(original)
                    malicious["files"].append({
                        "path": bad_name, "size": 10, "sha256": "0" * 64,
                    })
                    with self.assertRaises(UniversalPackageError):
                        validate_manifest(malicious)

    def test_uninstall_preserves_user_added_files_and_modified_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, manifest = fixture(root)
            archive = root / "clean.vwmodel"
            make_package(source, manifest, archive)
            install_model_package(archive, root=root)
            folder = installed_packages(root)[0][1]
            extra = folder / "my-notes.txt"
            extra.write_text("keep my work", encoding="utf-8")
            with self.assertRaisesRegex(UniversalPackageError, "unmanaged"):
                remove_model_package("v2-native-test", "1.0.0", root=root)
            self.assertEqual(extra.read_text(encoding="utf-8"), "keep my work")
            extra.unlink()
            config = folder / "speaker_config.json"
            data = config.read_bytes()
            config.write_bytes(b"x" + data[1:])
            with self.assertRaisesRegex(UniversalPackageError, "modified"):
                remove_model_package("v2-native-test", "1.0.0", root=root)
            self.assertTrue(config.is_file())

    def test_builder_never_overwrites_existing_or_in_source_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, manifest = fixture(root)
            archive = root / "first.vwmodel"
            make_package(source, manifest, archive)
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaisesRegex(UniversalPackageError, "already exists"):
                make_package(source, manifest, archive)
            self.assertEqual(digest, hashlib.sha256(archive.read_bytes()).hexdigest())
            with self.assertRaisesRegex(UniversalPackageError, "inside source"):
                make_package(source, manifest, source / "nested.vwmodel")

    def test_worker_python_abi_is_checked_independently_of_core_python(self):
        from voxweavetts.universal_model_packages import runtime_compatibility
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, manifest = fixture(root)
            config = root / "runtime" / "engine-envs" / "vachana" / "pyvenv.cfg"
            config.parent.mkdir(parents=True)
            config.write_text("version_info = 3.12\n", encoding="utf-8")
            self.assertEqual(runtime_compatibility(manifest, root=root), "python-abi-mismatch")
            self.assertFalse(activation_compatible(manifest, root=root))
            config.write_text("version_info = 3.11\n", encoding="utf-8")
            self.assertTrue(activation_compatible(manifest, root=root))

    def test_runtime_fingerprint_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest = fixture(Path(tmp))
            self.assertEqual(runtime_fingerprint(manifest), runtime_fingerprint(copy.deepcopy(manifest)))


if __name__ == "__main__":
    unittest.main()
