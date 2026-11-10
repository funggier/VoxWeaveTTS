"""Regression: never orphan Thai vowels/codas with estimated captions.

Thai character clusters are NOT Thai words. Without lexical boundaries,
estimated caption windows must not divide an unspaced Thai run.
"""
from __future__ import annotations

import hashlib
import unittest

from voxweavetts.document_reader import (
    CHUNKER_REVISION, _split_text, prepare_document
)
from voxweavetts.manual_alignment import _valid_boundary, validate_manual_cues
from voxweavetts.processing import InputError
from voxweavetts.subtitle_cues import estimated_cues
from voxweavetts.text_boundaries import (
    natural_break_positions, unsafe_unicode_boundary
)


def cues_for(text: str, duration: int = 16000):
    return estimated_cues([{
        "kind": "speech", "display_text": text,
        "start_ms": 0, "end_ms": duration,
    }])


class ThaiBoundariesTests(unittest.TestCase):
    def test_estimated_captions_do_not_slice_unspaced_thai_words(self):
        # Prior algorithm sliced every ~22 graphemes into arbitrary Thai chars.
        samples = (
            "เขาเดินทางเข้าไปในป่าเพื่อค้นหาความจริงของโลกใบนี้" * 4,
            "เพราะเหตุใดถึงมีความเปลี่ยนแปลงมากมายเกิดขึ้นในคืนวันนี้" * 4,
            "กาลครั้งหนึ่งมีหญิงสาวผู้เป็นอมตะอาศัยในหมู่บ้านเล็ก" * 5,
            "แก้วเก็บเรื่องราวเกี่ยวกับการเรียนรู้และการเปลี่ยนแปลง" * 4,
        )
        for text in samples:
            with self.subTest(start=text[:12]):
                result = cues_for(text)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["display_text"], text)

    def test_estimated_splits_only_after_real_delimiters(self):
        text = (
            "หญิงสาวเดินทางเข้าเมืองเพื่อค้นหาคำตอบ " * 4
            + "เธอพบดาบและแผนที่เก่าแก่! "
            + "หลังจากนั้นเธอจึงกลับบ้านด้วยความดีใจ " * 4
            + "🧑🏽‍💻 🇹🇭"
        )
        parts = cues_for(text, 24000)
        self.assertGreaterEqual(len(parts), 2)
        self.assertEqual("".join(x["display_text"] for x in parts), text)
        safe = natural_break_positions(text)
        boundary = 0
        for index, cue in enumerate(parts):
            boundary += len(cue["display_text"])
            if index < len(parts) - 1:
                self.assertIn(boundary, safe)
                self.assertFalse(unsafe_unicode_boundary(text, boundary))
                self.assertNotIn(cue["display_text"][-1], "เแโใไ")
            if index:
                self.assertFalse(cue["display_text"].startswith(
                    ("่", "้", "๊", "๋", "็", "์", "ำ", "🏽", "\u200d", "🇭")
                ))
        self.assertEqual(parts[0]["start_ms"], 0)
        self.assertEqual(parts[-1]["end_ms"], 24000)
        self.assertTrue(all(x["end_ms"] == y["start_ms"]
                            for x, y in zip(parts, parts[1:])))

    def test_safe_breaks_ignore_thai_leading_vowel_and_decimal_dot(self):
        text = "เก่งมากและเฝ้ารอวันใหม่ 123.45 บาท แล้วพบคำตอบ!"
        cuts = natural_break_positions(text)
        self.assertNotIn(1, cuts)  # no split after the preposed Thai vowel
        decimal = text.index(".") + 1
        self.assertNotIn(decimal, cuts)
        for cut in cuts:
            self.assertFalse(unsafe_unicode_boundary(text, cut))

    def test_document_uses_whitespace_not_random_word_cut(self):
        text = "เด็กชายเดินเข้าไปในหุบเขาเพื่อค้นหาความจริง " * 16
        doc = prepare_document(text, "txt", chunk_chars=100, page_size=30)
        chunks = doc["chunks"]
        self.assertGreater(len(chunks), 2)
        self.assertEqual("".join(x["text"] for x in chunks), text.strip())
        self.assertEqual(doc["chunker_revision"], CHUNKER_REVISION)
        self.assertEqual(chunks[1]["start_boundary_quality"], "whitespace")
        self.assertTrue(all(len(x["text"]) <= 100 for x in chunks))
        for piece in chunks[:-1]:
            self.assertEqual(piece["boundary_quality"], "whitespace")
            self.assertTrue(piece["text"].endswith(" "))
            self.assertNotIn(piece["text"][-1], "เแโใไ")

    def test_document_prefers_even_early_safe_separator_over_hard_cut(self):
        for marker in (" ", ",", "ฯ"):
            with self.subTest(marker=marker):
                text = "คำ" + marker + ("ก" * 220)
                ranges = _split_text(text, 100)
                first = ranges[0]
                self.assertEqual(first[:2], (0, len("คำ" + marker)))
                self.assertIn(first[2], ("whitespace", "punctuation"))
                self.assertEqual("".join(text[a:b] for a, b, _ in ranges), text)

    def test_document_fallback_cuts_before_thai_leading_vowel(self):
        text = "ก" * 99 + "เก่งมาก" + "ข" * 190
        ranges = _split_text(text, 100)
        self.assertEqual(ranges[0], (0, 99, "thai_preposed_vowel_hint"))
        self.assertEqual(text[ranges[1][0]], "เ")
        doc=prepare_document(text, "txt", chunk_chars=100)
        self.assertEqual(doc["chunks"][1]["start_boundary_quality"], "thai_preposed_vowel_hint")
        self.assertEqual("".join(text[a:b] for a, b, _ in ranges), text)
        self.assertTrue(all(b - a <= 100 for a, b, _ in ranges))

    def test_unavoidable_fallback_is_explicit_and_keeps_marks(self):
        text = "ก่" * 185
        doc = prepare_document(text, "txt", chunk_chars=101)
        joined = "".join(piece["text"] for piece in doc["chunks"])
        self.assertEqual(joined, text)
        self.assertTrue(any(piece["boundary_quality"] == "unicode_only_fallback"
                            for piece in doc["chunks"]))
        self.assertTrue(all(not piece["text"].startswith("่")
                            for piece in doc["chunks"]))

    def test_bookmark_id_revision_prevents_wrong_resume_offset(self):
        text = "บรรทัดแรกมีข้อความไทย " * 30
        doc = prepare_document(text, "txt", chunk_chars=100)
        old = hashlib.sha256(("txt" + "\0" + text.strip()).encode("utf-8")).hexdigest()
        self.assertNotEqual(doc["document_id"], old)

    def test_manual_cue_cannot_consist_of_orphan_preposed_vowel(self):
        self.assertFalse(_valid_boundary("เก่ง", 1))
        self.assertTrue(_valid_boundary("เก่ง", 0))
        self.assertTrue(_valid_boundary("เก่ง", len("เก่ง")))
        for text in ("แก้ว", "โคม", "ใคร", "ไกล"):
            with self.subTest(text=text):
                with self.assertRaises(InputError):
                    validate_manual_cues([{
                        "kind": "speech", "display_text": text,
                        "start_ms": 0, "end_ms": 1000,
                    }], [{
                        "segment_index": 0, "start_offset": 0,
                        "end_offset": 1, "start_ms": 0, "end_ms": 400,
                    }])


if __name__ == "__main__":
    unittest.main()