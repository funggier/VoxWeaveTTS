"""Engine-free reading bookmarks: exact-document identity, atomic updates and API."""
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.document_reader import prepare_document
from voxweavetts.processing import InputError
from voxweavetts import reading_progress
from voxweavetts.server import Handler


DOC_ID = prepare_document(
    "# บทที่ 1\n" + "เซียนผู้นี้มีชีวิตเป็นอมตะ " * 100,
    "md", chunk_chars=150,
)["document_id"]


class ProgressStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patch=patch.object(
            reading_progress,"PROGRESS_FILE",
            Path(self.tmp.name)/"data"/"reading"/"positions.json",
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def store(self, index, revision, *, chunk_chars=150, chunk_total=30):
        return reading_progress.save_position(
            DOC_ID, chunk_chars=chunk_chars, chunk_total=chunk_total,
            next_chunk=index, expected_revision=revision,
        )

    def test_no_novel_text_or_file_paths_saved(self):
        initial=reading_progress.load_position(DOC_ID)
        self.assertIsNone(initial["progress"])
        completed=self.store(7,initial["revision"])
        self.assertEqual(completed["progress"]["next_chunk"],7)
        self.assertEqual(completed["progress"]["chunk_chars"],150)
        self.assertEqual(reading_progress.load_position(DOC_ID),completed)
        file_bytes=reading_progress.PROGRESS_FILE.read_bytes()
        self.assertNotIn("เซียน".encode("utf-8"),file_bytes)
        self.assertNotIn("บทที่".encode("utf-8"),file_bytes)
        self.assertNotIn(b"file_name",file_bytes)
        self.assertNotIn(b"voice",file_bytes)
        self.assertIn(DOC_ID.encode("ascii"),file_bytes)
        self.assertEqual(json.loads(file_bytes)["schema_version"],1)

    def test_save_resume_and_clear(self):
        start=reading_progress.load_position(DOC_ID)
        first=self.store(0,start["revision"])
        advanced=self.store(10,first["revision"])
        self.assertNotEqual(advanced["revision"],first["revision"])
        done=self.store(30,advanced["revision"])
        self.assertEqual(done["progress"]["next_chunk"],done["progress"]["chunk_total"])
        cleared=reading_progress.clear_position(DOC_ID,done["revision"])
        self.assertIsNone(cleared["progress"])
        self.assertEqual(cleared["revision"],start["revision"])
        self.assertEqual(reading_progress.load_position(DOC_ID),cleared)

    def test_stale_revision_cannot_erase_progress(self):
        initial=reading_progress.load_position(DOC_ID)
        saved=self.store(5,initial["revision"])
        with self.assertRaises(reading_progress.ProgressConflict):
            self.store(10,initial["revision"])
        with self.assertRaises(reading_progress.ProgressConflict):
            reading_progress.clear_position(DOC_ID,initial["revision"])
        self.assertEqual(reading_progress.load_position(DOC_ID),saved)

    def test_invalid_positions_ids_and_types(self):
        initial=reading_progress.load_position(DOC_ID)
        with self.assertRaises(InputError):
            reading_progress.load_position("relative/path/novel.md")
        invalid = [
            (-1,150,30), (31,150,30), (True,150,30),
            (10,99,30), (10,451,30), (10,True,30),
            (10,150,0), (10,150,2501), (10,150,3),
        ]
        for next_chunk,chunk_chars,chunk_total in invalid:
            with self.subTest(position=next_chunk,chars=chunk_chars,total=chunk_total):
                with self.assertRaises(InputError):
                    self.store(next_chunk,initial["revision"],
                               chunk_chars=chunk_chars,chunk_total=chunk_total)
        for revision in ("bad",123,None,"Z"*64):
            with self.subTest(revision=revision):
                with self.assertRaises(InputError):
                    self.store(0,revision)
        self.assertFalse(reading_progress.PROGRESS_FILE.exists())

    def test_corrupt_file_not_clobbered(self):
        path=reading_progress.PROGRESS_FILE
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('{"schema_version":1,"documents":{"bad":"foo"}}',encoding="utf-8")
        original=path.read_bytes()
        with self.assertRaises(InputError):
            reading_progress.load_position(DOC_ID)
        with self.assertRaises(InputError):
            self.store(0,"0"*64)
        self.assertEqual(path.read_bytes(),original)

    def test_multiple_documents_are_independent(self):
        other="b"*64
        state1=reading_progress.load_position(DOC_ID)
        state2=reading_progress.load_position(other)
        a=self.store(1,state1["revision"])
        b=reading_progress.save_position(
            other,chunk_chars=300,chunk_total=40,next_chunk=8,
            expected_revision=state2["revision"],
        )
        self.assertEqual(reading_progress.load_position(DOC_ID),a)
        self.assertEqual(reading_progress.load_position(other),b)

    def test_concurrent_same_revision_only_one_writer(self):
        initial=reading_progress.load_position(DOC_ID)
        def save(i):
            try:
                self.store(i,initial["revision"])
                return "saved"
            except reading_progress.ProgressConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcome=list(pool.map(save,[2,3]))
        self.assertEqual(sorted(outcome),["conflict","saved"])


class ProgressHTTPTests(unittest.TestCase):
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

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patch=patch.object(reading_progress,"PROGRESS_FILE",Path(self.tmp.name)/"progress.json")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def get(self,docid=DOC_ID):
        with urlopen(self.base+"/v1/reading/progress?document_id="+docid,timeout=5) as response:
            return json.load(response)

    def post(self,body,*,clear=False,intent=True,mime="application/json"):
        url=self.base+"/v1/reading/progress"+("/clear" if clear else "")
        header={"Content-Type":mime}
        if intent:
            header["X-VoxWeaveTTS-Intent"]=("clear-reading-progress" if clear
                                          else "save-reading-progress")
        req=Request(url,method="POST",data=json.dumps(body).encode("utf-8"),
                    headers=header)
        return urlopen(req,timeout=5)

    def test_http_resume_and_409_stale(self):
        state=self.get()
        self.assertIsNone(state["progress"])
        with self.post({
            "document_id":DOC_ID,"chunk_chars":150,"chunk_total":30,
            "next_chunk":12,"expected_revision":state["revision"],
        }) as response:
            self.assertEqual(response.status,200)
            saved=json.load(response)
        self.assertEqual(self.get()["progress"]["next_chunk"],12)
        with self.assertRaises(HTTPError) as e:
            self.post({
                "document_id":DOC_ID,"chunk_chars":150,"chunk_total":30,
                "next_chunk":13,"expected_revision":state["revision"],
            })
        self.assertEqual(e.exception.code,409)
        e.exception.close()
        with self.post({"document_id":DOC_ID,
                        "expected_revision":saved["revision"]},clear=True) as response:
            self.assertIsNone(json.load(response)["progress"])
        self.assertIsNone(self.get()["progress"])

    def test_http_input_and_intent_restrictions(self):
        original=self.get()
        body={
            "document_id":DOC_ID,"chunk_chars":150,"chunk_total":30,
            "next_chunk":0,"expected_revision":original["revision"],
        }
        for kwargs,code in [
            ({"intent":False},403),
            ({"mime":"text/plain"},415),
        ]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(HTTPError) as error:
                    self.post(body,**kwargs)
                self.assertEqual(error.exception.code,code)
                error.exception.close()
        for invalid in ("bad","X"*64,""):
            with self.subTest(document_id=invalid):
                with self.assertRaises(HTTPError) as error:
                    self.get(invalid)
                self.assertEqual(error.exception.code,400)
                error.exception.close()
        self.assertFalse(reading_progress.PROGRESS_FILE.exists())


if __name__ == "__main__":
    unittest.main()
