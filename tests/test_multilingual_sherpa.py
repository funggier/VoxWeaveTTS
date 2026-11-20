"""v4 multidialect voice routing uses advertised metadata, never Core Sherpa code."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts.engine_contract import EngineInfo
from voxweavetts.language_routes import voice_languages, save_routes
from voxweavetts.processing import InputError


class V4MultilingualVoiceTests(unittest.TestCase):
    def test_supertonic_voice_language_map_must_follow_each_voice(self):
        voice_map={"ko_s0":"ko","ko_s1":"ko","en_s0":"en","ja_s1":"ja"}
        info=EngineInfo(
            id="model-supertonic3-multilingual-int8-1_0_0",
            label="Supertonic v4", language="multi", sample_rate=44100,
            voice_id="ko_s0",
            voice_options=tuple((v,v) for v in voice_map),
            voice_language_map=voice_map,
            assets_ready=True,runtime_ready=True,capabilities={"speech":True})
        with patch("voxweavetts.speech.get_engine_info",return_value=info):
            for voice,lang in voice_map.items():
                self.assertEqual(voice_languages(info.id,voice),{lang})
            with tempfile.TemporaryDirectory() as tmp:
                dest=Path(tmp)/"routes.json"
                profile={"engine_id":info.id,"voice_id":"ja_s1"}
                result=save_routes({"expected_revision":0,
                                    "routes":{"ja":profile}},dest)
                self.assertEqual(result["routes"]["ja"],profile)
                with self.assertRaises(InputError):
                    save_routes({"expected_revision":1,
                                 "routes":{"zh":profile}},dest)

    def test_chinese_onnx_uses_only_declared_languages(self):
        info=EngineInfo(
            id="model-melo-chinese-onnx-1_0_0",
            label="Melo v4",language="zh",
            voice_id="zh_melo",sample_rate=44100,
            assets_ready=True,runtime_ready=True,
            supported_languages=("zh","en"),
            capabilities={"speech":True})
        with patch("voxweavetts.speech.get_engine_info",return_value=info):
            self.assertEqual(voice_languages(info.id,"zh_melo"),{"zh","en"})
            with self.assertRaises(InputError):
                voice_languages(info.id,"no-voice")


if __name__=="__main__":
    unittest.main()
