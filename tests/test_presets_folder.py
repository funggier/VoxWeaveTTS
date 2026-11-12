"""Portable preset folder discovery and safe migration behavior."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import presets
from voxweavetts.speech import PARADEE_ENGINE_ID


class PresetFolderTests(unittest.TestCase):
    def test_drop_in_json_discovered_without_restart_and_filename_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            directory=root/"presets"
            with patch.object(presets, "PRESETS_DIR",directory), patch.object(
                    presets,"PRESETS_FILE",root/"legacy.json"):
                self.assertEqual(presets.load_presets(),[])
                profile={"name":"นิยายเสียง x5","engine_id":PARADEE_ENGINE_ID,
                         "voice_id":"paradee_thai","speed":5.0,
                         "voice_controls":{"gain_db":0.01,"bass_db":-2.11}}
                directory.mkdir()
                (directory/"shared-with-another-pc.json").write_text(
                    json.dumps(profile,ensure_ascii=False),encoding="utf-8")
                self.assertEqual(presets.load_presets()[0]["speed"],5.0)
                self.assertEqual(presets.load_presets()[0]["voice_controls"]["bass_db"],-2.11)
                saved=presets.save_preset({**profile,"speed":2.45})
                paths=[file for file in directory.glob("*.json")]
                self.assertEqual(len(paths),2)
                self.assertTrue(any(path.name.startswith("voice-") for path in paths))
                self.assertEqual(presets.load_presets(),[saved])
                (directory/"bad.json").write_text("{broken",encoding="utf-8")
                self.assertEqual(presets.load_presets(),[saved])
                self.assertTrue(all(file.parent==directory for file in paths))

    def test_optional_model_preset_stays_listed_before_model_install(self):
        from voxweavetts.processing import InputError
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / "presets"
            directory.mkdir()
            missing = {
                "name": "Voice from another computer",
                "engine_id": "model-optional-voice-1_0_0",
                "voice_id": "speaker_f",
                "speed": 2.35,
                "voice_controls": {"gain_db": 0.05},
            }
            (directory / "other-pc.json").write_text(
                json.dumps(missing), encoding="utf-8"
            )
            (directory / "malformed.json").write_text(
                json.dumps({**missing, "name": "Unsafe", "engine_id": "../bad"}),
                encoding="utf-8"
            )
            with patch.object(presets, "PRESETS_DIR", directory), patch.object(
                presets, "PRESETS_FILE", root / "old.json"
            ):
                entries = presets.load_presets()
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["name"], missing["name"])
                self.assertEqual(entries[0]["engine_id"], missing["engine_id"])
                self.assertEqual(entries[0]["speed"], 2.35)
                with self.assertRaises(InputError):
                    presets.save_preset(missing)  # Do not save invalid engine selections.

    def test_existing_legacy_presets_remain_readable_and_new_file_overrides(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            legacy=root/"legacy.json"
            profile={"name":"Legacy Voice","engine_id":PARADEE_ENGINE_ID,"speed":0.9}
            legacy.write_text(json.dumps([profile]),encoding="utf-8")
            with patch.object(presets,"PRESETS_DIR",root/"presets"),patch.object(
                    presets,"PRESETS_FILE",legacy):
                self.assertEqual(presets.load_presets()[0]["speed"],0.9)
                presets.save_preset({**profile,"speed":1.22})
                self.assertEqual(presets.load_presets()[0]["speed"],1.22)
                self.assertEqual(json.loads(legacy.read_text())[0]["speed"],0.9)
                with self.assertRaises(Exception):
                    presets.save_preset({"name":"../outside","engine_id":PARADEE_ENGINE_ID})
                self.assertFalse((root/"outside").exists())


if __name__=="__main__":
    unittest.main()
