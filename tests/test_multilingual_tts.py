"""All engine languages are declared by v4 metadata; not old Core adapters."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts.engine_contract import EngineInfo
from voxweavetts.language_routes import (
    choose_route, detect_language, save_routes, voice_languages,
)
from voxweavetts.processing import InputError

DEFAULT="model-makham-paradee-1_0_0"
WAYU="model-wayu-paxa-edge-nc-1_0_0"


def info(engine: str, *, languages=("th", "en"), voices=("v0",)) -> EngineInfo:
    return EngineInfo(
        id=engine, label="v4 test engine", language="th",
        sample_rate=24000, voice_id=voices[0],
        voice_options=tuple((v,v) for v in voices),
        assets_ready=True, runtime_ready=True,
        capabilities={"speech":True}, supported_languages=languages,
    )


class V4LanguageRoutingTests(unittest.TestCase):
    def test_default_v4_makham_supports_thai_and_english(self):
        from voxweavetts.speech import get_engine_info
        current=get_engine_info(DEFAULT)
        self.assertEqual(set(current.supported_languages),{"th","en"})
        self.assertEqual(voice_languages(DEFAULT,"paradee_thai"),{"th","en"})

    def test_v4_nc_model_voices_keep_declared_languages(self):
        voices=("f_young_warm","m_young_clear","f_teen_bright")
        with patch("voxweavetts.speech.get_engine_info",
                   return_value=info(WAYU,voices=voices)):
            for voice in voices:
                self.assertEqual(voice_languages(WAYU,voice),{"th","en"})
            with tempfile.TemporaryDirectory() as temp:
                route={"engine_id":WAYU,"voice_id":voices[0]}
                file=Path(temp)/"routes.json"
                result=save_routes({"expected_revision":0,
                                    "routes":{"th":route,"en":route}},file)
                self.assertEqual(set(result["routes"]),{"th","en"})
                self.assertEqual(choose_route("Hello",language="en",path=file)[1],route)
                with self.assertRaises(InputError):
                    save_routes({"expected_revision":1,
                                 "routes":{"ja":route}},file)

    def test_language_is_checked_against_selected_v4_engine_not_core_catalog(self):
        with patch("voxweavetts.speech.get_engine_info",
                   return_value=info("model-custom-tts-1_0_0",
                                     languages=("ja",),voices=("j_1",))):
            self.assertEqual(voice_languages("model-custom-tts-1_0_0","j_1"),
                             {"ja"})
            with tempfile.TemporaryDirectory() as temp:
                route={"engine_id":"model-custom-tts-1_0_0","voice_id":"j_1"}
                with self.assertRaises(InputError):
                    save_routes({"expected_revision":0,
                                 "routes":{"th":route}},Path(temp)/"routes.json")

    def test_hardcoded_legacy_engine_is_not_discoverable(self):
        from voxweavetts.speech import list_engine_info
        self.assertNotIn("vachana-cpu", [x.id for x in list_engine_info()])
        self.assertNotIn("fastthaig2p-cpu", [x.id for x in list_engine_info()])
        self.assertNotIn("makham-paradee-cpu", [x.id for x in list_engine_info()])


if __name__ == "__main__":
    unittest.main()
