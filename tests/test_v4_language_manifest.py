"""V4-only multilingual per-voice routing contract and manifest validation."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import universal_model_v4 as v4
from voxweavetts.engine_provider_catalog import all_providers
from test_v4_plugin_packages import fixture

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from build_vwmodel_v4 import build


def multilingual(base: Path, *, incomplete: bool = False) -> Path:
    fixture(base)
    spec_file=base/"spec.json"
    spec=json.loads(spec_file.read_text(encoding="utf-8"))
    spec["package"]["languages"]=["en","ja"]
    spec["engine"]["language"]="multi"
    spec["engine"]["voices"]=[
        {"id":"en_voice","label":"English voice"},
        {"id":"ja_voice","label":"Japanese voice"},
    ]
    mapping={"en_voice":"en","ja_voice":"ja"}
    if incomplete:
        mapping.pop("ja_voice")
    spec["engine"]["voice_language_map"]=mapping
    spec_file.write_text(json.dumps(spec),encoding="utf-8")
    return build(base/"source",spec_file,base/"multilingual.vwmodel")


class V4LanguageManifestTests(unittest.TestCase):
    def test_voice_language_map_reaches_runtime_registry_without_model_specific_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            archive=multilingual(base)
            manifest=v4.inspect_archive(archive)
            self.assertEqual(manifest["engine"]["voice_language_map"],
                             {"en_voice":"en","ja_voice":"ja"})
            stage=base/"portable"
            with patch.object(v4,"core_python",return_value=Path(sys.executable)),patch.object(
                v4,"sys_platform",return_value="windows-x64"
            ):
                info=v4.install(archive,root=stage)
                self.assertEqual(info["format_version"],4)
                profiles=all_providers(root=stage)
                profile=profiles["v4-demo-future-engine-1-0-0"]
                self.assertEqual(profile.declared_engine["voice_language_map"],
                                 {"en_voice":"en","ja_voice":"ja"})
                self.assertEqual(profile.declared_engine["supported_languages"],
                                 ["en","ja"])
                self.assertTrue(v4.remove("demo-future-engine","1.0.0",root=stage))

    def test_incomplete_multilingual_mapping_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            with self.assertRaisesRegex(ValueError,"multilingual"):
                multilingual(base,incomplete=True)

    def test_a_monolingual_model_cannot_claim_an_undeclared_voice_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            fixture(base)
            spec_file=base/"spec.json"
            spec=json.loads(spec_file.read_text("utf-8"))
            spec["engine"]["voice_language_map"]={"new_voice":"ja"}
            spec_file.write_text(json.dumps(spec),encoding="utf-8")
            with self.assertRaises(ValueError):
                build(base/"source",spec_file,base/"invalid.vwmodel")


if __name__=="__main__":
    unittest.main()
