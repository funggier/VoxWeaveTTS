"""Kokoro v4 standalone Worker selects a bundled offline Japanese dictionary."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"examples/v4-model-plugin/plugin/worker.py"


def load_worker():
    spec=importlib.util.spec_from_file_location("v4_model_plugin_example",SCRIPT)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V4KokoroJapaneseTests(unittest.TestCase):
    def _run(self, full_available: bool):
        worker=load_worker()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"plugin").mkdir()
            (root/"plugin/adapter.json").write_text(json.dumps({
                "backend":"kokoro-onnx-v1",
                "sample_rate":24000,"voices":["jf_nezumi"],
            }))
            for name in ("full","lite"):
                (root/name).mkdir()
            if full_available:
                (root/"full/mecabrc").write_text("")
            (root/"lite/mecabrc").write_text("")
            unidic=types.ModuleType("unidic")
            unidic.DICDIR=str(root/"full")
            lite=types.ModuleType("unidic_lite")
            lite.DICDIR=str(root/"lite")
            selected=[]
            ja=types.ModuleType("misaki.ja")
            class G2P:
                def __init__(self):
                    selected.append(unidic.DICDIR)
                def __call__(self,text):
                    return "test-phonemes",None
            ja.JAG2P=G2P
            misaki=types.ModuleType("misaki")
            misaki.ja=ja
            kokoro=types.ModuleType("kokoro_onnx")
            class FakeKokoro:
                def __init__(self,*args):
                    self.calls=[]
                def create(self,text,**kwargs):
                    self.calls.append((text,kwargs))
                    return [0.1]*100,24000
            kokoro.Kokoro=FakeKokoro
            with patch.dict(sys.modules,{
                "unidic":unidic,"unidic_lite":lite,
                "misaki":misaki,"misaki.ja":ja,
                "kokoro_onnx":kokoro,
            }),patch.object(worker,"pcm16",return_value=b"\0\0"*100):
                engine=worker.ModelWorker(root)
                self.assertEqual(engine.synthesize("こんにちは","jf_nezumi",1.0,3),
                                 b"\0\0"*100)
                self.assertEqual(engine.synthesize("日本語","jf_nezumi",1.0,3),
                                 b"\0\0"*100)
                self.assertEqual(engine.native.calls[0][1]["lang"],"ja")
                self.assertTrue(engine.native.calls[0][1]["is_phonemes"])
                self.assertEqual(selected,[str(root/("full" if full_available else "lite"))])

    def test_falls_back_to_bundled_unidic_lite(self):
        self._run(False)

    def test_prefers_installed_full_unidic(self):
        self._run(True)


if __name__=="__main__":
    unittest.main()
