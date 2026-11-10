"""Standard-library document importer tests with no TTS-model requirements."""
from __future__ import annotations

import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.document_reader import (
    MAX_DOCUMENT_CHARS, _chapters, prepare_document
)
from voxweavetts.processing import InputError, process_text
from voxweavetts.server import Handler


class DocumentReaderTests(unittest.TestCase):
    def test_txt_thai_chapters_and_range_bounds(self):
        text = ("คำนำของหนังสือ\n"
                + "บทที่ ๑ กำเนิดผู้ฝึกตน\n"
                + "เซียนผู้นี้เป็นอมตะ " * 25
                + "\nตอนที่ 2 เดินทางออกเมือง\n"
                + "ฮ่า ฮ่า ฮ่า 55555 " * 25)
        doc = prepare_document(text, "txt", title="My Novel",
                               chunk_chars=125, page_size=30)
        self.assertEqual(doc["title"], "My Novel")
        self.assertEqual(doc["chapter_total"], 3)
        self.assertEqual([c["title"] for c in doc["chapters"]],
                         ["เนื้อหา", "บทที่ ๑ กำเนิดผู้ฝึกตน",
                          "ตอนที่ 2 เดินทางออกเมือง"])
        self.assertTrue(all(len(c["text"]) <= 125 for c in doc["chunks"]))
        for chunk in doc["chunks"]:
            self.assertEqual(chunk["end"] - chunk["start"], len(chunk["text"]))
        self.assertIn("55555", "".join(c["text"] for c in doc["chunks"]))

    def test_markdown_strips_non_narrated_syntax(self):
        tick = chr(96)
        text = (
            "---\ntitle: secret metadata\n---\n"
            "# บทที่ 1\n"
            "สวัสดี **ครับ** [อ่านต่อ](https://example.com/path) "
            "![รูป](https://example.com/secret.jpg)\n"
            + tick*3 + "python\nprint('DO_NOT_READ')\n" + tick*3 + "\n"
            + "~~ข้อความ~~ และ " + tick + "inlineCode" + tick + "\n"
            "<script>danger()</script>\n"
            "> เรื่องราวดำเนินต่อ\n"
            "## ตอนที่ 2\n"
            "ข้อความใหม่ <https://example.com> และ *เน้น*\n"
        )
        doc = prepare_document(text,"md")
        self.assertEqual(doc["chapter_total"],2)
        spoken="".join(c["text"] for c in doc["chunks"])
        for forbidden in ("secret metadata","https://","DO_NOT_READ",
                          "danger()","inlineCode","**","~~","!["):
            self.assertNotIn(forbidden,spoken)
        for required in ("บทที่ 1","สวัสดี ครับ อ่านต่อ",
                         "ข้อความ","เรื่องราวดำเนินต่อ","ตอนที่ 2","เน้น"):
            self.assertIn(required,spoken)

    def test_stable_hash_paging_offsets_and_no_loss(self):
        text = "# บทนำ\n" + ("กาลครั้งหนึ่ง มีชายหนุ่มออกเดินทาง.\n" * 45)
        first = prepare_document(text,"md",chunk_chars=100,page_size=3)
        second = prepare_document(text,"md",chunk_chars=100,page_size=3,
                                  page_index=1)
        self.assertEqual(first["document_id"],second["document_id"])
        self.assertEqual([c["index"] for c in first["chunks"]],[0,1,2])
        self.assertEqual([c["index"] for c in second["chunks"]],[3,4,5])
        pieces=[]
        for page in range((first["chunk_total"]+2)//3):
            result=prepare_document(text,"md",chunk_chars=100,page_size=3,
                                    page_index=page)
            pieces.extend(result["chunks"])
        canonical="".join(c["text"] for c in pieces)
        self.assertEqual(canonical,"\n".join(x[2:] if x.startswith("# ") else x for x in text.splitlines() if x))
        for c in pieces:
            self.assertEqual(canonical[c["start"]:c["end"]],c["text"])

    def test_thai_combining_marks_are_not_orphaned_at_cut(self):
        text="ก่" * 185
        doc=prepare_document(text,"txt",chunk_chars=101)
        self.assertTrue(all(not c["text"].startswith("่") for c in doc["chunks"]))
        self.assertEqual("".join(c["text"] for c in doc["chunks"]),text)

    def test_chapter_offsets(self):
        doc=prepare_document("# ตอนแรก\nหนึ่ง\n## ตอนสอง\nสอง","md")
        self.assertEqual(doc["chapters"][0]["end"]+1,
                         doc["chapters"][1]["start"])
        self.assertEqual([c["chapter_index"] for c in doc["chunks"]],[0,1])

    def test_special_characters_survive_txt_markdown_and_json_roundtrip(self):
        # Paired Thai quotation marks, symbols, escapes, emoji and astral planes.
        special = '“เซียน” • «ฮ่า» (ทดสอบ) [x] {y} 50% + @ # & $ \\ 🧑🏽‍💻 🇹🇭 ✨'
        for fmt in ("txt", "md"):
            with self.subTest(format=fmt):
                data=prepare_document("บทที่ 1\n"+special,fmt,chunk_chars=350)
                combined="".join(chunk["text"] for chunk in data["chunks"])
                self.assertIn(special,combined)
                # JSON HTTP transport must not eat backslashes, quotes or emoji.
                encoded=json.dumps({"text":special},ensure_ascii=False)
                self.assertEqual(json.loads(encoded)["text"],special)

    def test_unicode_sequences_remain_intact_at_chunk_boundaries(self):
        # A 4-codepoint family/skin-tone/ZWJ emoji and two regional indicators.
        samples=(
            "ก"*99+"👩🏽‍💻"+"ข"*140,
            "ก"*99+"🇹🇭"+"ข"*140,
            "ก"*99+"ก่"+"ข"*140,
        )
        for original in samples:
            with self.subTest(fragment=original[97:107]):
                data=prepare_document(original,"txt",chunk_chars=101)
                chunks=[chunk["text"] for chunk in data["chunks"]]
                self.assertEqual("".join(chunks),original)
                self.assertTrue(all(len(chunk)<=101 for chunk in chunks))
                self.assertFalse(any(chunk.startswith(("🏽","‍","💻","🇭","่")) for chunk in chunks))

    def test_json_settings_special_literals_and_escapes(self):
        raw_rule={
            "match":'“ฮ่า\\ฮ่า” 🌟',
            "mode":"replace",
            "spoken":'หัวเราะ "ดัง" \nซ้ำอีกครั้ง 🙂',
        }
        raw_pron={'🇹🇭':"ประเทศไทย", 'C:\\test\\voice':"ชื่อไฟล์เสียง"}
        rules=json.loads(json.dumps([raw_rule],ensure_ascii=False))
        pronunciations=json.loads(json.dumps(raw_pron,ensure_ascii=False))
        text='“ฮ่า\\ฮ่า” 🌟 และ 🇹🇭 C:\\test\\voice'
        plan=process_text(text,rules=rules,pronunciations=pronunciations)
        self.assertIn('หัวเราะ "ดัง" \nซ้ำอีกครั้ง 🙂',plan["spoken_text"])
        self.assertIn("ประเทศไทย",plan["spoken_text"])
        self.assertIn("ชื่อไฟล์เสียง",plan["spoken_text"])
        self.assertEqual(plan["display_text"],text)

    def test_invalid_data(self):
        cases=[
            {"fmt":"pdf"},{"text":""},{"text":"bad\x00data"},
            {"text":"x"*(MAX_DOCUMENT_CHARS+1)},{"chunk_chars":99},
            {"chunk_chars":451},{"chunk_chars":True},{"page_size":0},
            {"page_size":31},{"page_index":-1},{"page_index":1},
            {"page_index":True},{"title":"a"*161},
            {"text":chr(96)*3+"\nhello\n"+chr(96)*3,"fmt":"md"}
        ]
        for overrides in cases:
            with self.subTest(case=list(overrides)):
                values={"text":"สวัสดี","fmt":"txt","title":"",
                        "page_index":0,"page_size":15,"chunk_chars":350}
                values.update(overrides)
                with self.assertRaises(InputError):
                    prepare_document(**values)

    def test_document_chunk_runs_through_shared_queue_with_mock_engine(self):
        import io
        import struct
        import wave
        from voxweavetts.speech import render_wav
        from voxweavetts.speech_coordinator import SpeechCoordinator

        class OfflineEngine:
            id = "offline-document-test"
            sample_rate = 24000

            def generate(self, text, speed):
                return struct.pack("<h", 4400) * 1200

        def synth(plan, **kwargs):
            return render_wav(plan, engine=OfflineEngine(), **kwargs)

        document = prepare_document("บทที่ 1\\nอมตะ ต้องห้าม 55555", "txt")
        prepared = process_text(
            document["chunks"][0]["text"], source="document",
            rules=[{"match":"ต้องห้าม","mode":"silence","silence_ms":400}],
            pronunciations={"อมตะ":"อะ มะ ตะ"},
        )
        coordinator = SpeechCoordinator(synth)
        try:
            job = coordinator.submit(
                prepared, engine_id="fastthaig2p-cpu", voice_id="thai_som",
                render_args={"engine_id":"fastthaig2p-cpu","voice_id":"thai_som"},
            )
            complete = coordinator.wait(job["speech_id"], timeout=3)
            self.assertEqual(complete["state"], "ready")
            self.assertIn("55555", complete["display_text"])
            self.assertNotIn("ต้องห้าม", str(complete["audio"]))
            with wave.open(io.BytesIO(coordinator.audio(job["speech_id"])), "rb") as wav:
                self.assertGreater(wav.getnframes(), 9600)
                self.assertEqual(wav.getframerate(), 24000)
        finally:
            coordinator.close()

    def test_chunk_uses_existing_pronunciation_and_filter(self):
        doc=prepare_document("บทที่ 1\nอมตะ คำต้องห้าม 55555","txt")
        plan=process_text(
            doc["chunks"][0]["text"],
            rules=[
                {"match":"คำต้องห้าม","mode":"silence","silence_ms":400},
                {"match":"555","match_mode":"five_run","mode":"replace",
                 "spoken":"ฮ่า ฮ่า ฮ่า"},
            ],
            pronunciations={"อมตะ":"อะ มะ ตะ"},source="document",
        )
        self.assertIn("อะ มะ ตะ",plan["spoken_text"])
        self.assertIn("55555",plan["display_text"])
        self.assertNotIn("คำต้องห้าม",plan["spoken_text"])
        self.assertTrue(any(s["kind"]=="silence" for s in plan["segments"]))


class DocumentPreviewAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)

    def _request(self,payload,content_type="application/json"):
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
        return Request(self.base+"/v1/documents/preview",data=data,
                       headers={"Content-Type":content_type},method="POST")

    def test_preview_accepts_larger_utf8_than_regular_api(self):
        text="# บทที่ 1\n" + "สวัสดีครับ อ่านนิยายภาษาไทย\n"*1800
        self.assertGreater(len(text.encode("utf-8")),65536)
        with urlopen(self._request({"text":text,"format":"md",
                                    "page_size":4}),timeout=6) as response:
            self.assertEqual(response.status,200)
            preview=json.load(response)
        self.assertEqual(preview["chapter_total"],1)
        self.assertEqual(len(preview["chunks"]),4)
        self.assertTrue(preview["chunk_total"]>4)
        self.assertEqual(preview["offset_basis"],"normalized_narration_text")

    def test_preview_validation_and_mime(self):
        for body in (
            {"text":"สวัสดี","format":"docx"},
            {"text":"สวัสดี","format":"txt","page_size":0},
            {"text":"\x00","format":"txt"},
        ):
            with self.subTest(body=body):
                with self.assertRaises(HTTPError) as exc:
                    urlopen(self._request(body),timeout=5)
                self.assertEqual(exc.exception.code,400)
                exc.exception.close()
        with self.assertRaises(HTTPError) as exc:
            urlopen(self._request({"text":"hello","format":"txt"},"text/plain"),timeout=5)
        self.assertEqual(exc.exception.code,415)
        exc.exception.close()

    def test_http_document_keeps_unicode_quotes_slashes_and_emoji(self):
        special='“เซียน” [คำอ่าน] «ฮ่า» C:\\folder\\voice 😄 🇹🇭 👩🏽‍💻'
        with urlopen(self._request({"text":"บทที่ 1\n"+special,"format":"txt"}),
                     timeout=5) as response:
            body=json.load(response)
        self.assertEqual(body["chunk_total"],1)
        self.assertIn(special,body["chunks"][0]["text"])
        self.assertEqual(body["chapters"][0]["title"],"บทที่ 1")

    def test_preview_leaves_engine_uninitialized(self):
        with urlopen(self._request({"text":"อมตะ","format":"txt"}),
                     timeout=5) as response:
            preview=json.load(response)
        self.assertEqual(preview["chunk_total"],1)
        self.assertNotIn("engine_id",preview)
        self.assertNotIn("voice_id",preview)


if __name__=="__main__":
    unittest.main()