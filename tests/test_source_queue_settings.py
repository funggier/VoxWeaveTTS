"""Portable, per-mode live queue settings; 8,000-character message boundary."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from voxweavetts.processing import InputError
from voxweavetts.source_manager import SourceManager, MAX_TEXT_CHARS, _Session
from voxweavetts.source_adapters import _normal_text, SourceMessage
from voxweavetts.source_queue_settings import (
    DEFAULTS, SOURCE_MODES, SettingsConflict, load_settings,
    save_settings, validate_settings,
)


class SourceQueueSettingsTests(unittest.TestCase):
    def test_eight_thousand_characters_allowed_for_source_and_queue_preferences(self):
        self.assertEqual(MAX_TEXT_CHARS,8000)
        self.assertEqual(SourceManager._validate_policy(
            {"blocked_words":[],"max_chars":8000})[1],8000)
        with self.assertRaises(InputError):
            SourceManager._validate_policy({"blocked_words":[],"max_chars":8001})
        self.assertEqual(len(_normal_text("ก"*8000)),8000)
        self.assertEqual(_normal_text("ข"*8001),"")
        session=_Session("live","a"*32,"stream",object(),(),8000)
        self.assertTrue(SourceManager._allowed(
            SourceMessage("id-ok","viewer","ก"*8000),session))
        self.assertFalse(SourceManager._allowed(
            SourceMessage("id-too-long","viewer","ก"*8001),session))
        self.assertEqual(validate_settings({**DEFAULTS,"max_chars":8000})["max_chars"],8000)
        with self.assertRaises(InputError):
            validate_settings({**DEFAULTS,"max_chars":8001})

    def test_atomic_independent_save_for_six_modes_without_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"data"/"settings"/"source-queues.json"
            loaded=load_settings(path=path)
            self.assertEqual(set(loaded["modes"]),set(SOURCE_MODES))
            self.assertTrue(all(record["revision"]==0 for record in loaded["modes"].values()))
            for mode in SOURCE_MODES:
                value={**DEFAULTS,"max_chars":8000,
                       "read_history_limit":2,"random_queue_enabled":True,
                       "random_queue_threshold":30,"random_queue_keep":6}
                saved=save_settings({"mode":mode,"expected_revision":0,"settings":value},
                                    path=path)
                self.assertEqual(saved["modes"][mode]["revision"],1)
            read=load_settings(path=path)
            self.assertEqual(len(read["modes"]),6)
            self.assertEqual(read["modes"]["youtube_browser"]["settings"]["max_chars"],8000)
            self.assertNotIn("credential",path.read_text(encoding="utf-8"))
            self.assertNotIn("token",path.read_text(encoding="utf-8"))
            before=path.read_bytes()
            with self.assertRaises(SettingsConflict):
                save_settings({"mode":"live","expected_revision":0,"settings":DEFAULTS},
                              path=path)
            self.assertEqual(path.read_bytes(),before)

    def test_reject_invalid_ranges_types_and_unexpected_keys_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"config.json"
            invalid=(
                {**DEFAULTS,"max_chars":8001},
                {**DEFAULTS,"max_chars":19},
                {**DEFAULTS,"max_chars":"8000"},
                {**DEFAULTS,"read_history_limit":101},
                {**DEFAULTS,"random_queue_keep":20},
                {**DEFAULTS,"auto_read":1},
                {**DEFAULTS,"source_id":"sensitive"},
            )
            for settings in invalid:
                with self.subTest(settings=settings),self.assertRaises(InputError):
                    save_settings({"mode":"live","expected_revision":0,"settings":settings},
                                  path=path)
                self.assertFalse(path.exists())

    def test_existing_saved_preferences_gain_disabled_switch_without_data_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"saved.json"
            previous={k:v for k,v in DEFAULTS.items()
                      if k!="continue_on_tts_error"}
            document={"schema_version":1,"modes":{
                mode:{"revision":3,"settings":{**previous,"max_chars":8000}}
                for mode in SOURCE_MODES
            }}
            path.write_text(json.dumps(document),encoding="utf-8")
            loaded=load_settings(path=path)
            self.assertFalse(loaded["modes"]["live"]["settings"]["continue_on_tts_error"])
            self.assertEqual(loaded["modes"]["live"]["settings"]["max_chars"],8000)
            self.assertEqual(loaded["modes"]["live"]["revision"],3)
            # No implicit mutation of private/old preferences until Save.
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),document)
            settings={**loaded["modes"]["live"]["settings"],
                      "continue_on_tts_error":True}
            result=save_settings({"mode":"live","expected_revision":3,
                                  "settings":settings},path=path)
            self.assertEqual(result["modes"]["live"]["revision"],4)
            self.assertTrue(result["modes"]["live"]["settings"]["continue_on_tts_error"])
            self.assertFalse(result["modes"]["discord"]["settings"]["continue_on_tts_error"])

    def test_corrupted_settings_do_not_silently_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"config.json"
            path.write_text("{invalid}",encoding="utf-8")
            with self.assertRaises(InputError):
                load_settings(path=path)
            with self.assertRaises(InputError):
                save_settings({"mode":"live","expected_revision":0,"settings":DEFAULTS},
                              path=path)
            self.assertEqual(path.read_text(encoding="utf-8"),"{invalid}")


if __name__=="__main__":
    unittest.main()
