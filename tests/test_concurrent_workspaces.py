"""Concurrent source ownership, multi-clock overlay and per-channel voice prefs."""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from voxweavetts.mode_state import ModeState, ModeConflict
from voxweavetts.playback_hub import PlaybackHub
from voxweavetts.processing import InputError
from voxweavetts.source_manager import SourceManager
from voxweavetts.source_adapters import PollResult, SourceMessage
from voxweavetts.mode_voice_settings import (
    load_workspace_settings, save_workspace_settings,
)


class Source:
    def __init__(self, source_id, credential):
        self.source_id=source_id
        self.closed=False
    def poll(self):
        return PollResult((SourceMessage("test-1", "viewer", "สวัสดีครับ"),), 5.0)
    def close(self):
        self.closed=True


class ConcurrentSourcesTests(unittest.TestCase):
    def test_two_live_channels_survive_other_workspace_activations(self):
        modes=ModeState()
        hub=PlaybackHub()
        sources=SourceManager(youtube_factory=Source, discord_factory=Source)
        try:
            live=modes.activate("live",hub)
            youtube={**{"mode":"live","source_id":"youtube-live-id","credential":"test"},
                     "mode_token":live["mode_token"]}
            sources.start(youtube,modes)
            discord=modes.activate("discord",hub)
            discord_args={"mode":"discord","mode_token":discord["mode_token"],
                          "source_id":"discord-channel-id","credential":"test"}
            sources.start(discord_args,modes)
            modes.activate("studio",hub)
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                if all(sources.status(mode)["received"]>=1 for mode in ("live","discord")):
                    break
                time.sleep(.01)
            self.assertEqual(sources.status("live")["received"],1)
            self.assertEqual(sources.status("discord")["received"],1)
            self.assertEqual(len(sources.drain({**youtube,"limit":5},modes)["messages"]),1)
            self.assertEqual(len(sources.drain({**discord_args,"limit":5},modes)["messages"]),1)
            self.assertTrue(modes.is_owner("live",youtube["mode_token"]))
            modes.activate("discord",hub)
            sources.stop_mode("discord")
            with self.assertRaises(ModeConflict):
                sources.drain(discord_args,modes)
            self.assertEqual(sources.status("discord")["state"],"idle")
            self.assertNotEqual(sources.status("live")["state"],"idle")
        finally:
            sources.stop_all()


class ConcurrentPlaybackTests(unittest.TestCase):
    def test_simultaneous_sessions_and_mode_local_updates(self):
        modes=ModeState()
        hub=PlaybackHub()
        def job():
            return {"speech_id":"a"*32,"state":"ready","engine_id":"fake",
                    "audio":{"duration_ms":1000,"segments":[{
                        "kind":"speech","start_ms":0,"end_ms":1000,
                        "display_text":"สวัสดีครับ"}]}}
        tokens={mode:modes.activate(mode,hub)["mode_token"] for mode in
                ("studio","live","discord")}
        def report(mode,event,seq,position=10):
            return modes.report({
                "session_id":("b" if mode=="studio" else "c" if mode=="live" else "d")*32,
                "speech_id":"a"*32,"event":event,"sequence":seq,
                "position_ms":position,"mode":mode,"mode_token":tokens[mode]
            },job() if event=="start" else None,hub)
        for mode in ("studio","live","discord"):
            report(mode,"start",1)
        states=hub.snapshot()
        self.assertEqual(set(states["active_modes"]),{"studio","live","discord"})
        self.assertEqual(len(states["subtitles_by_mode"]),3)
        self.assertEqual(report("studio","progress",2)["state"],"playing")
        self.assertEqual(report("live","progress",2)["state"],"playing")
        report("live","ended",3,1000)
        self.assertEqual(set(hub.snapshot()["active_modes"]),{"studio","discord"})
        # Reclaiming the studio only revokes that old studio token.
        modes.activate("studio",hub)
        with self.assertRaises(ModeConflict):
            report("studio","progress",3)
        self.assertEqual(report("discord","progress",2)["state"],"playing")


class ModeVoiceSettingsTests(unittest.TestCase):
    def test_mode_profiles_persist_independently_and_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"data"/"settings.json"
            doc=load_workspace_settings(path)
            self.assertEqual(doc["policy"],"serial")
            def voice(speed):
                return {
                    "engine_id":"makham-paradee-cpu","voice_id":"paradee_thai",
                    "speed":speed,"voice_controls":{
                        "pitch_semitones":0,"gain_db":0,"bass_db":0,
                        "treble_db":0,"formant_preserve":True,
                    },
                }
            doc=save_workspace_settings({
                "expected_revision":0,"mode":"live","settings":voice(1.1)},path)
            doc=save_workspace_settings({
                "expected_revision":1,"mode":"discord","settings":voice(0.85)},path)
            doc=save_workspace_settings({
                "expected_revision":2,"mode":"__policy__","settings":"overlap"},path)
            restored=load_workspace_settings(path)
            self.assertEqual(restored["policy"],"overlap")
            self.assertEqual(restored["modes"]["live"]["speed"],1.1)
            self.assertEqual(restored["modes"]["discord"]["speed"],0.85)
            with self.assertRaisesRegex(ValueError,"changed"):
                save_workspace_settings({
                    "expected_revision":1,"mode":"live","settings":voice(1.4)},path)
            with self.assertRaises(InputError):
                save_workspace_settings({
                    "expected_revision":3,"mode":"live",
                    "settings":{**voice(1.3),"voice_id":"invalid"}},path)
            self.assertEqual(load_workspace_settings(path),restored)


if __name__=="__main__":
    unittest.main()
