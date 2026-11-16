"""NC models display their actual weight license and stay local-only."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import speech
from voxweavetts.model_packages import display_model_title
from voxweavetts.personal_wayu_engine import (
    ENGINE_ID, PersonalWayuEngine, VOICES, assets_ready, descriptor, runtime_ready,
)
from voxweavetts.processing import InputError


class PersonalNonCommercialVoiceTests(unittest.TestCase):
    def test_confirmed_nc_is_explicitly_in_model_title(self):
        def model(spdx: str, title: str = "Example Voice"):
            return {"title": title, "license": {"spdx": spdx}}
        self.assertEqual(
            display_model_title(model("CC-BY-NC-4.0")),
            "[NC / NonCommercial] Example Voice",
        )
        self.assertEqual(
            display_model_title(model("CC-BY-NC-SA-4.0")),
            "[NC / NonCommercial] Example Voice",
        )
        self.assertEqual(
            display_model_title(model("CC-BY-NC-4.0", "[NC] Custom")),
            "[NC] Custom",
        )
        self.assertEqual(display_model_title(model("MIT")), "Example Voice")
        self.assertEqual(display_model_title(model("OpenRAIL-M")), "Example Voice")
        self.assertEqual(display_model_title(model("Unknown")), "Example Voice")

    def test_wayu_descriptor_is_never_commercial_cleared(self):
        d = descriptor()
        self.assertEqual(d.id, ENGINE_ID)
        self.assertIn("[NC / NonCommercial]", d.label)
        self.assertEqual(d.commercial_status, "hold")
        self.assertEqual(d.sample_rate, 24000)
        self.assertEqual(len(VOICES), 12)
        self.assertEqual(len(d.voice_ids), 12)
        self.assertTrue(d.capabilities["seed_control"])
        self.assertFalse(d.capabilities["voice_cloning"])
        self.assertTrue(any(i.id == ENGINE_ID for i in speech.list_engine_info()))

    def test_missing_weights_do_not_download_during_synthesis(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertFalse(assets_ready(Path(temp)))
            engine = PersonalWayuEngine(model_dir=Path(temp))
            with self.assertRaises(speech.EngineUnavailable):
                engine.generate("hello", 1.0)

    def test_missing_isolated_python_disables_runtime(self):
        with patch("voxweavetts.personal_wayu_engine.gateway") as broker:
            broker.return_value.available.return_value = False
            self.assertFalse(runtime_ready())

    def test_voice_list_is_constrained(self):
        engine = PersonalWayuEngine()
        engine.select_voice("f_teen_bright")
        self.assertEqual(engine.voice_id, "f_teen_bright")
        with self.assertRaises(InputError):
            engine.select_voice("../../bad")


if __name__ == "__main__":
    unittest.main()
