"""Wayu Paxa NC native v2: full 12 voices, pinned serialized weights and rights.

Fixtures use small fake bytes and patch the *trusted first-party* digest table,
so this test never executes untrusted pickle or downloads a model.
"""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import wayu_native_trust
from voxweavetts.engine_worker_wayu import _check_pinned_weights, _verified_package_path
from voxweavetts.personal_wayu_engine import VOICES
from voxweavetts.universal_model_packages import (
    UniversalPackageError, validate_manifest, native_adapter_profile,
    make_package, install_model_package, native_tts_packages, inspect_archive,
    remove_model_package, engine_id_for,
)


def fixture(root: Path):
    folder = root / "source"
    folder.mkdir(parents=True)
    weights = {}
    for name in wayu_native_trust.PINNED_ASSETS:
        content = ("PINNED TEST ONLY " + name).encode("utf-8") * 40
        file = folder / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content)
        weights[name] = hashlib.sha256(content).hexdigest()
    rights = {
        "license": {
            "spdx": "CC-BY-NC-4.0",
            "url": "https://creativecommons.org/licenses/by-nc/4.0/",
            "attribution": "Wayu NC / original research and 12 voice authors",
            "review_status": "hold",
        },
        "source": {"url": wayu_native_trust.SOURCE_URL,
                   "revision": wayu_native_trust.SOURCE_REVISION},
    }
    metadata = {
        "README.md": "Wayu NC test only",
        "legal/license.txt": "CC BY-NC 4.0",
        "legal/acceptable-use.txt": "NC only",
        "legal/attribution.md": "Original Wayu authors",
        "legal/rights.json": json.dumps(rights),
    }
    for name, value in metadata.items():
        file = folder / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(value, encoding="utf-8")
    original = sorted(
        [*weights, *metadata.keys() - {"legal/rights.json"}], key=str.casefold)
    (folder / "manifest-assets.json").write_text(
        json.dumps({"paths": original}), encoding="utf-8")
    all_names = sorted(
        [*original, "manifest-assets.json", "legal/rights.json"],
        key=str.casefold)
    manifest = {
        "format": "voxweavetts.model-package", "format_version": 2,
        "package": {"id": "wayu-paxa-edge-nc", "version": "1.0.0",
                    "kind": "tts", "title": "Wayu NC Test",
                    "languages": ["th", "en"]},
        "adapter": {"id": "wayu-nc-v1", "api_version": 1, "trust": "builtin"},
        "runtime": {"id": "wayu-nc", "kind": "python-venv",
                    "python": "3.11", "platform": "any", "accelerator": "cpu",
                    "source": "reuse-only", "install_policy": "reuse-only",
                    "lockfile": None},
        "assets": "manifest-assets.json", "rights": "legal/rights.json",
        "files": [{"path": name, "size": (folder / name).stat().st_size,
                   "sha256": hashlib.sha256((folder / name).read_bytes()).hexdigest()}
                  for name in all_names],
        "capabilities": {"language": "th", "sample_rate": 24000,
                         "voices": [{"id": name, "label": name,
                                     "asset": f"voices/{name}.pt"}
                                    for name, _ in VOICES]},
    }
    return folder, manifest, weights


class NativeWayuTests(unittest.TestCase):
    def test_wayu_native_v2_roundtrip_nc_label_and_safe_remove(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, manifest, weights = fixture(root)
            with patch.object(wayu_native_trust, "PINNED_ASSETS", weights):
                self.assertEqual(validate_manifest(manifest), manifest)
                self.assertEqual(native_adapter_profile(manifest, source)["engine_adapter"],
                                 "wayu-nc-v1")
                archive = root / "wayu-nc.vwmodel"
                make_package(source, manifest, archive)
                self.assertEqual(inspect_archive(archive)["package"]["kind"], "tts")
                installed = install_model_package(archive, root=root)
                self.assertEqual(installed["package_id"], "wayu-paxa-edge-nc")
                self.assertEqual(installed["format_version"], 2)
                self.assertTrue(installed["activation_supported"])
                entries = native_tts_packages(root)
                wayu = next(m for m, path in entries if m["package_id"] == "wayu-paxa-edge-nc")
                self.assertEqual(wayu["license"]["spdx"], "CC-BY-NC-4.0")
                self.assertEqual(wayu["license"]["review_status"], "hold")
                self.assertEqual(len(wayu["voices"]), 12)
                self.assertEqual(engine_id_for(wayu), "model-wayu-paxa-edge-nc-1_0_0")
                saved_dir = next(path for m, path in entries
                                 if m["package_id"] == "wayu-paxa-edge-nc")
                _check_pinned_weights(saved_dir)
                with patch("voxweavetts.universal_model_packages.native_tts_packages",
                           return_value=entries):
                    self.assertEqual(
                        _verified_package_path("model-wayu-paxa-edge-nc-1_0_0"),
                        saved_dir)
                    with self.assertRaisesRegex(ValueError, "untrusted"):
                        _verified_package_path("../../malicious")
                self.assertTrue(remove_model_package("wayu-paxa-edge-nc", "1.0.0",
                                                      root=root))
                self.assertFalse(saved_dir.exists())

    def test_tampered_weight_hash_or_extra_pickle_rejected_before_install(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, manifest, weights = fixture(Path(temp))
            with patch.object(wayu_native_trust, "PINNED_ASSETS", weights):
                bad = copy.deepcopy(manifest)
                next(row for row in bad["files"] if row["path"] == "model.pth")[
                    "sha256"] = "f" * 64
                with self.assertRaisesRegex(UniversalPackageError, "untrusted serialized"):
                    validate_manifest(bad)
                bad = copy.deepcopy(manifest)
                bad["files"].append({"path": "unexpected.pt",
                                     "size": 22, "sha256": "a" * 64})
                with self.assertRaisesRegex(UniversalPackageError, "untrusted serialized"):
                    validate_manifest(bad)
                bad = copy.deepcopy(manifest)
                bad["adapter"]["id"] = "vachana-onnx-v1"
                with self.assertRaisesRegex(UniversalPackageError, "serialized"):
                    validate_manifest(bad)
                bad = copy.deepcopy(manifest)
                bad["package"]["version"] = "2.0.0"
                with self.assertRaises(UniversalPackageError):
                    validate_manifest(bad)

    def test_nc_license_and_upstream_provenance_cannot_be_relabelled(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, manifest, weights = fixture(Path(temp))
            with patch.object(wayu_native_trust, "PINNED_ASSETS", weights):
                raw = json.loads((folder / "legal/rights.json").read_text())
                for changed in [
                    {"license": {**raw["license"], "spdx": "MIT"}},
                    {"license": {**raw["license"], "review_status": "cleared"}},
                    {"source": {**raw["source"], "revision": "unknown"}},
                ]:
                    modified = {**raw, **changed}
                    (folder / "legal/rights.json").write_text(
                        json.dumps(modified), encoding="utf-8")
                    with self.assertRaisesRegex(UniversalPackageError, "rights/source"):
                        native_adapter_profile(manifest, folder)
                bad = copy.deepcopy(manifest)
                bad["runtime"]["source"] = "recipe-only"
                with self.assertRaises(UniversalPackageError):
                    validate_manifest(bad)

    def test_only_pinned_wayu_weights_allowed_not_generic_pytorch(self):
        with tempfile.TemporaryDirectory() as temp:
            _, manifest, weights = fixture(Path(temp))
            with patch.object(wayu_native_trust, "PINNED_ASSETS", weights):
                bad = copy.deepcopy(manifest)
                bad["adapter"]["trust"] = "external"
                with self.assertRaises(UniversalPackageError):
                    validate_manifest(bad)
                bad = copy.deepcopy(manifest)
                bad["runtime"]["id"] = "pythaitts"
                with self.assertRaises(UniversalPackageError):
                    validate_manifest(bad)


if __name__ == "__main__":
    unittest.main()
