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
                       "random_queue_threshold":30,"random_queue_keep":6,
                       "prepare_ahead":mode in {"youtube_browser","tiktok_browser"},
                       "force_autoplay":mode in {"live","tiktok"}}
                saved=save_settings({"mode":mode,"expected_revision":0,"settings":value},
                                    path=path)
                self.assertEqual(saved["modes"][mode]["revision"],1)
            read=load_settings(path=path)
            self.assertEqual(len(read["modes"]),6)
            self.assertTrue(read["modes"]["youtube_browser"]["settings"]["prepare_ahead"])
            self.assertFalse(read["modes"]["discord"]["settings"]["prepare_ahead"])
            self.assertTrue(read["modes"]["live"]["settings"]["force_autoplay"])
            self.assertFalse(read["modes"]["discord"]["settings"]["force_autoplay"])
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
                {**DEFAULTS,"prepare_ahead":"yes"},
                {**DEFAULTS,"force_autoplay":"yes"},
                {**DEFAULTS,"prepare_queue_limit":0},
                {**DEFAULTS,"ready_audio_queue_limit":0},
                {**DEFAULTS,"ready_audio_queue_limit":21},
                {**DEFAULTS,"prepare_queue_limit":101},
                {**DEFAULTS,"speech_job_timeout_minutes":0},
                {**DEFAULTS,"speech_job_timeout_minutes":61},
                {**DEFAULTS,"speech_job_timeout_minutes":True},
                {**DEFAULTS,"source_id":"sensitive"},
            )
            for settings in invalid:
                with self.subTest(settings=settings),self.assertRaises(InputError):
                    save_settings({"mode":"live","expected_revision":0,"settings":settings},
                                  path=path)
                self.assertFalse(path.exists())

    def test_high_capacity_per_mode_limits_are_independent(self):
        high={**DEFAULTS,"prepare_queue_limit":100,
              "ready_audio_queue_limit":20,
              "speech_job_timeout_minutes":60}
        self.assertEqual(validate_settings(high),high)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"queue.json"
            first=save_settings({"mode":"live","expected_revision":0,
                                "settings":high},path=path)
            self.assertEqual(first["modes"]["live"]["settings"],high)
            self.assertEqual(first["modes"]["discord"]["settings"],DEFAULTS)

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
            self.assertEqual(loaded["modes"]["live"]["settings"]["speech_job_timeout_minutes"],4)
            # No implicit mutation of private/old preferences until Save.
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),document)
            settings={**loaded["modes"]["live"]["settings"],
                      "continue_on_tts_error":True}
            result=save_settings({"mode":"live","expected_revision":3,
                                  "settings":settings},path=path)
            self.assertEqual(result["modes"]["live"]["revision"],4)
            self.assertTrue(result["modes"]["live"]["settings"]["continue_on_tts_error"])
            self.assertFalse(result["modes"]["discord"]["settings"]["continue_on_tts_error"])

    def test_previous_release_settings_add_disabled_pipeline_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"source-queues.json"
            previous={k:v for k,v in DEFAULTS.items() if k!="prepare_ahead"}
            document={"schema_version":1,"modes":{
                mode:{"revision":7,"settings":{**previous,
                    "continue_on_tts_error":True}}
                for mode in SOURCE_MODES
            }}
            path.write_text(json.dumps(document),encoding="utf-8")
            loaded=load_settings(path=path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),document)
            for entry in loaded["modes"].values():
                self.assertTrue(entry["settings"]["continue_on_tts_error"])
                self.assertFalse(entry["settings"]["prepare_ahead"])
                self.assertEqual(entry["revision"],7)
            updated={**loaded["modes"]["live"]["settings"],"prepare_ahead":True}
            saved=save_settings({"mode":"live","expected_revision":7,
                                 "settings":updated},path=path)
            self.assertTrue(saved["modes"]["live"]["settings"]["prepare_ahead"])
            self.assertFalse(saved["modes"]["discord"]["settings"]["prepare_ahead"])

    def test_pre_upgrade_settings_migrate_timeout_without_overwriting_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"source-queues.json"
            old={k:v for k,v in DEFAULTS.items() if k!="speech_job_timeout_minutes"}
            old["continue_on_tts_error"]=True
            old["prepare_ahead"]=True
            old["prepare_queue_limit"]=4
            old["ready_audio_queue_limit"]=3
            document={"schema_version":1,"modes":{
                mode:{"revision":5,"settings":dict(old)} for mode in SOURCE_MODES}}
            path.write_text(json.dumps(document),encoding="utf-8")
            loaded=load_settings(path=path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),document)
            for entry in loaded["modes"].values():
                self.assertEqual(entry["settings"]["speech_job_timeout_minutes"],4)
                self.assertEqual(entry["settings"]["prepare_queue_limit"],4)
                self.assertTrue(entry["settings"]["continue_on_tts_error"])
            update={**loaded["modes"]["live"]["settings"],
                    "speech_job_timeout_minutes":17}
            saved=save_settings({"mode":"live","expected_revision":5,
                                "settings":update},path=path)
            self.assertEqual(saved["modes"]["live"]["settings"]["speech_job_timeout_minutes"],17)
            self.assertEqual(saved["modes"]["discord"]["settings"]["speech_job_timeout_minutes"],4)

    def test_previous_release_migrates_force_autoplay_disabled_without_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"source-queues.json"
            saved={key:value for key,value in DEFAULTS.items()
                   if key!="force_autoplay"}
            saved["continue_on_tts_error"]=True
            saved["prepare_queue_limit"]=100
            saved["ready_audio_queue_limit"]=20
            document={"schema_version":1,"modes":{
                mode:{"revision":11,"settings":dict(saved)} for mode in SOURCE_MODES}}
            path.write_text(json.dumps(document),encoding="utf-8")
            before=path.read_bytes()
            loaded=load_settings(path=path)
            self.assertEqual(path.read_bytes(),before)
            for mode in SOURCE_MODES:
                settings=loaded["modes"][mode]["settings"]
                self.assertIs(settings["force_autoplay"],False)
                self.assertTrue(settings["continue_on_tts_error"])
                self.assertEqual(settings["prepare_queue_limit"],100)
                self.assertEqual(settings["ready_audio_queue_limit"],20)
            updated={**loaded["modes"]["live"]["settings"],"force_autoplay":True}
            result=save_settings({"mode":"live","expected_revision":11,
                                  "settings":updated},path=path)
            self.assertTrue(result["modes"]["live"]["settings"]["force_autoplay"])
            self.assertFalse(result["modes"]["tiktok"]["settings"]["force_autoplay"])
            self.assertEqual(result["modes"]["live"]["revision"],12)

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
