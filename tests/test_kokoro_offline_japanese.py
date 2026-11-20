"""Regression: Kokoro Japanese G2P must work with bundled UniDic Lite offline."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts.kokoro_engine import KokoroOnnxEngine


class KokoroOfflineJapaneseDictionaryTests(unittest.TestCase):
    def _test_dictionary(self, *, full_installed: bool) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            full = base / "full"
            lite = base / "lite"
            full.mkdir()
            lite.mkdir()
            (lite / "mecabrc").write_text("", encoding="utf-8")
            if full_installed:
                (full / "mecabrc").write_text("", encoding="utf-8")
            unidic = types.ModuleType("unidic")
            unidic.DICDIR = str(full)
            unidic_lite = types.ModuleType("unidic_lite")
            unidic_lite.DICDIR = str(lite)
            ja = types.ModuleType("misaki.ja")
            selected: list[str] = []

            class FakeJAG2P:
                def __init__(self):
                    selected.append(unidic.DICDIR)

                def __call__(self, text):
                    return ("test-phonemes", None)

            ja.JAG2P = FakeJAG2P
            misaki = types.ModuleType("misaki")
            misaki.ja = ja
            with patch.dict(sys.modules, {
                "misaki": misaki, "misaki.ja": ja,
                "unidic": unidic, "unidic_lite": unidic_lite,
            }):
                engine = KokoroOnnxEngine(
                    model_dir=base, engine_id="qa-kokoro",
                    voices=(("jf_nezumi", "Japanese"),),
                )
                self.assertEqual(engine._japanese_phonemes("こんにちは"),
                                 "test-phonemes")
                self.assertEqual(engine._japanese_phonemes("日本語"),
                                 "test-phonemes")
            expected = full if full_installed else lite
            self.assertEqual(selected, [str(expected)])
            self.assertEqual(unidic.DICDIR, str(expected))

    def test_uses_complete_unidic_when_it_is_really_installed(self):
        self._test_dictionary(full_installed=True)

    def test_falls_back_to_bundled_unidic_lite_without_download(self):
        self._test_dictionary(full_installed=False)


if __name__ == "__main__":
    unittest.main()
