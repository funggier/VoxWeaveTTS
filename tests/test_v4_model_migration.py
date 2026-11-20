"""V4-only model catalog, plugin SDK examples, and translation schema."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import universal_model_v4 as v4
from test_v4_plugin_packages import fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
from build_vwmodel_v4 import build
from verify_v4_model_inventory import EXPECTED, audit


class V4OnlyModelTests(unittest.TestCase):
    def test_only_v4_package_examples_are_exposed(self):
        names = sorted(p.name for p in (ROOT/"examples").iterdir()
                       if p.is_dir() and not p.name.startswith("__"))
        self.assertEqual(names, sorted([
            "v4-demo-tone", "v4-demo-wheel", "v4-native-worker",
            "v4-model-plugin", "v4-translation-plugin", "v4-windows-sapi",
        ]))
        self.assertFalse((ROOT/"examples/tts-provider-minimal").exists())

    def test_inventory_expects_seven_tts_and_one_translation(self):
        self.assertEqual(set(EXPECTED), {
            "makham-paradee", "fastthaig2p-thai-som",
            "melo-chinese-onnx", "supertonic3-multilingual-int8",
            "kokoro-multilingual-int8", "vachana-thai-four-voices",
            "wayu-paxa-edge-nc", "m2m100-418m",
        })
        self.assertEqual(list(EXPECTED.values()).count("tts"), 7)
        self.assertEqual(list(EXPECTED.values()).count("translation"), 1)
        with tempfile.TemporaryDirectory() as tmp:
            report = audit(Path(tmp))
        self.assertFalse(report["all_eight_present"])
        self.assertEqual(len(report["missing"]), 8)
        self.assertFalse(report["public_release_authorized"])

    def test_v3_archive_is_rejected_by_v4_only_installer(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp)/"old.vwmodel"
            import zipfile
            with zipfile.ZipFile(old, "w") as zipped:
                zipped.writestr("manifest.json", json.dumps({
                    "format":"voxweavetts.model-package", "format_version":3
                }))
            with self.assertRaises(ValueError):
                v4.inspect_archive(old)

    def test_translation_plugin_uses_v4_only_directory_and_hold_rights(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            fixture(folder)
            spec = folder/"spec.json"
            metadata = json.loads(spec.read_text(encoding="utf-8"))
            metadata["package"]["kind"] = "translation"
            metadata["package"]["id"] = "future-translation"
            metadata["engine"] = {
                "protocol":1, "entrypoint":"plugin/worker.py",
                "operation":"translate", "languages":["en","th"],
            }
            metadata["rights"]["review_status"] = "hold"
            spec.write_text(json.dumps(metadata), encoding="utf-8")
            archive = build(folder/"source",spec,folder/"translator.vwmodel")
            info = v4.inspect_archive(archive)
            self.assertEqual(info["format_version"],4)
            self.assertEqual(info["rights"]["review_status"],"hold")
            stage = folder/"portable"
            (stage/"runtime/python").mkdir(parents=True)
            (stage/"runtime/python/python.exe").write_bytes(b"test")
            installed = v4.install(archive,root=stage)
            self.assertEqual(installed["format_version"],4)
            self.assertTrue(
                (stage/"models/universal/v4/translation/future-translation/1.0.0/manifest.json").exists()
            )
            self.assertTrue(v4.remove("future-translation","1.0.0",root=stage))

    def test_translation_manifest_disallows_tts_voice_properties(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            fixture(folder)
            spec=json.loads((folder/"spec.json").read_text("utf-8"))
            spec["package"]["kind"]="translation"
            spec["engine"]={"protocol":1,"entrypoint":"plugin/worker.py",
                            "operation":"translate","languages":["th","en"],
                            "sample_rate":24000,"voices":[]}
            (folder/"spec.json").write_text(json.dumps(spec))
            with self.assertRaises(ValueError):
                build(folder/"source",folder/"spec.json",folder/"wrong.vwmodel")


if __name__ == "__main__":
    unittest.main()
