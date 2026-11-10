import unittest
from voxweavetts.processing import InputError, process_text, apply_pronunciations

class ProcessingTests(unittest.TestCase):
    def test_pronunciation_only_spoken_side(self):
        r=process_text("เขาบรรลุขั้นอมตะ",pronunciations={"อมตะ":"อะ มะ ตะ"})
        self.assertEqual(r["display_text"],"เขาบรรลุขั้นอมตะ")
        self.assertEqual(r["spoken_text"],"เขาบรรลุขั้นอะ มะ ตะ")

    def test_replacement(self):
        r=process_text("สวัสดี 55555",rules=[{"match":"55555","mode":"replace","spoken":"ฮ่า ฮ่า ฮ่า","display":"55555"}])
        self.assertEqual(r["display_text"],"สวัสดี 55555")
        self.assertEqual(r["spoken_text"],"สวัสดี ฮ่า ฮ่า ฮ่า")

    def test_repeated_fives_preserve_original_subtitle(self):
        rule={"match":"555","match_mode":"five_run","mode":"replace",
              "spoken":"ฮ่า ฮ่า ฮ่า"}
        for text in ["555", "5555", "55555", "555555555555", "สวัสดี5555ครับ"]:
            with self.subTest(text=text):
                result=process_text(text,rules=[rule])
                self.assertEqual(result["display_text"], text)
                self.assertEqual(result["spoken_text"].count("ฮ่า"), 3)
                replaced=[x for x in result["segments"] if x["spoken_text"]=="ฮ่า ฮ่า ฮ่า"]
                self.assertEqual(len(replaced),1)
                self.assertEqual(
                    text[replaced[0]["source_start"]:replaced[0]["source_end"]],
                    "5" * len(text[replaced[0]["source_start"]:replaced[0]["source_end"]])
                )

    def test_repeated_fives_ignore_numeric_literals(self):
        rule={"match":"555","match_mode":"five_run","mode":"replace",
              "spoken":"ฮ่า ฮ่า ฮ่า"}
        for text in ["15555", "55551", "2555", "5555.50", "5555,5555",
                     "5,55555", "5.55555", "55555.50", "10,55555"]:
            with self.subTest(text=text):
                result=process_text(text,rules=[rule])
                self.assertEqual(result["spoken_text"], text)

    def test_repeated_fives_rule_input_validation(self):
        for rule in [
            {"match":"555","match_mode":"arbitrary_regex","spoken":"wrong"},
            {"match":"55","match_mode":"five_run","spoken":"wrong"},
        ]:
            with self.assertRaises(InputError):
                process_text("55555",rules=[rule])
        # Rules without a pattern retain the existing literal semantics.
        self.assertEqual(
            process_text("55555",rules=[{"match":"55555","spoken":"ฮ่า"}])["spoken_text"],
            "ฮ่า"
        )

    def test_silence(self):
        r=process_text("ก่อนคำต้องห้ามหลัง",rules=[{"match":"คำต้องห้าม","mode":"silence","display":"***","silence_ms":450}])
        self.assertEqual(r["display_text"],"ก่อน***หลัง")
        self.assertEqual(r["spoken_text"],"ก่อนหลัง")
        self.assertEqual([s["kind"] for s in r["segments"]],["speech","silence","speech"])
        self.assertEqual(r["segments"][1]["silence_ms"],450)
        self.assertNotIn("คำต้องห้าม",str(r["segments"]))

    def test_skip(self):
        r=process_text("หนึ่งสองสาม",rules=[{"match":"สอง","mode":"skip","display":"[ซ่อน]"}])
        self.assertEqual(r["spoken_text"],"หนึ่งสาม")
        self.assertEqual(r["display_text"],"หนึ่ง[ซ่อน]สาม")

    def test_longest_match(self):
        r=process_text("abc",rules=[{"match":"ab","spoken":"wrong"},{"match":"abc","spoken":"right"}])
        self.assertEqual(r["spoken_text"],"right")

    def test_source_scoping(self):
        rules=[{"match":"test","spoken":"LIVE","sources":["youtube"]}]
        self.assertEqual(process_text("test",rules=rules,source="youtube")["spoken_text"],"LIVE")
        self.assertEqual(process_text("test",rules=rules,source="novel")["spoken_text"],"test")

    def test_pronunciation_non_cascading(self):
        self.assertEqual(apply_pronunciations("กข",{"ก":"ข","ข":"ค"}),"ขค")

    def test_validation(self):
        for rule in [{"match":"","mode":"silence"},{"match":"a","mode":"silence","silence_ms":-5},{"match":"a","mode":"exec"}]:
            with self.assertRaises(InputError):
                process_text("a",rules=[rule])
        with self.assertRaises(InputError):
            process_text(123)
        with self.assertRaises(InputError):
            process_text("x"*8001)

    def test_empty(self):
        r=process_text("")
        self.assertEqual(r["segments"],[])