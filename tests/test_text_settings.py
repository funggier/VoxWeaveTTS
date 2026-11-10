"""Persistent text configuration: engine-free, atomic, conflict-safe and Unicode-safe."""
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

from voxweavetts import text_settings
from voxweavetts.processing import InputError
from voxweavetts.server import Handler


class TextSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        folder=Path(self.tmp.name)
        self.rule_patch=patch.object(text_settings,"RULES_FILE",folder/"data/filters/rules.json")
        self.pron_patch=patch.object(text_settings,"PRONUNCIATIONS_FILE",folder/"data/dictionaries/pronunciations.json")
        self.rule_patch.start()
        self.pron_patch.start()

    def tearDown(self):
        self.pron_patch.stop()
        self.rule_patch.stop()
        self.tmp.cleanup()

    def test_initial_empty_and_save_preserves_unicode(self):
        initial=text_settings.load_all()
        self.assertEqual(initial["rules"],[])
        self.assertEqual(initial["pronunciations"],{})
        self.assertFalse(initial["saved"]["rules"])
        self.assertFalse(initial["saved"]["pronunciations"])
        rules=[
            {"match":'“ฮ่า\\ฮ่า” 😄',"mode":"replace","spoken":'ฮ่า "ดัง"'},
            {"match":"555","match_mode":"five_run","spoken":"ฮ่า ฮ่า ฮ่า"},
        ]
        result=text_settings.save_section("rules",rules,initial["revisions"]["rules"])
        self.assertTrue(result["saved"])
        self.assertEqual(result["value"],rules)
        self.assertEqual(json.loads(text_settings.RULES_FILE.read_text(encoding="utf-8")),rules)
        after=text_settings.load_all()
        self.assertEqual(after["rules"],rules)
        self.assertFalse(after["saved"]["pronunciations"])
        pron={'🇹🇭':"ประเทศไทย",'C:\\folder\\voice':'ชื่อไฟล์','__proto__':'ชื่อตัวแปร'}
        text_settings.save_section("pronunciations",pron,after["revisions"]["pronunciations"])
        self.assertEqual(text_settings.load_all()["pronunciations"],pron)

    def test_revision_conflict_preserves_latest_saved_file(self):
        initial=text_settings.load_section("rules")
        first=[{"match":"ฮ่า","spoken":"หัวเราะ"}]
        saved=text_settings.save_section("rules",first,initial["revision"])
        self.assertNotEqual(saved["revision"],initial["revision"])
        with self.assertRaises(text_settings.SettingsConflict):
            text_settings.save_section("rules",[{"match":"อื่น","spoken":"เสียง"}],
                                       initial["revision"])
        self.assertEqual(text_settings.load_section("rules")["value"],first)

    def test_invalid_inputs_never_change_existing_data(self):
        original=text_settings.load_section("pronunciations")
        stable={'เซียน':'เซียน'}
        text_settings.save_section("pronunciations",stable,original["revision"])
        before=text_settings.PRONUNCIATIONS_FILE.read_bytes()
        for payload in (
            ["not an object"],
            {"": "bad"},
            {"a": ""},
            {"a": 123},
            {"x"*201:"short"},
            {"a":"x"*501},
        ):
            with self.subTest(payload=str(payload)[:70]):
                with self.assertRaises(InputError):
                    text_settings.save_section("pronunciations",payload,
                        text_settings.load_section("pronunciations")["revision"])
                self.assertEqual(text_settings.PRONUNCIATIONS_FILE.read_bytes(),before)
        with self.assertRaises(InputError):
            text_settings.save_section("rules",[{"match":"a","match_mode":"regex"}],
                                       text_settings.load_section("rules")["revision"])
        with self.assertRaises(InputError):
            text_settings.save_section("pronunciations",stable,"wrong")
        self.assertEqual(text_settings.PRONUNCIATIONS_FILE.read_bytes(),before)

    def test_bounded_file_and_corrupt_data_not_overwritten(self):
        target=text_settings.RULES_FILE
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text("{not JSON",encoding="utf-8")
        with self.assertRaises(InputError):
            text_settings.load_section("rules")
        with self.assertRaises(InputError):
            text_settings.save_section("rules",[], "0"*64)
        self.assertEqual(target.read_text(encoding="utf-8"),"{not JSON")
        target.write_bytes(b" " * (text_settings.MAX_FILE_BYTES+1))
        with self.assertRaises(InputError):
            text_settings.load_section("rules")
        # Nonstandard JSON constants must fail cleanly, not raise unhandled 500.
        target.write_text('[{"match":"abc","spoken":"xyz","extra":NaN}]',encoding="utf-8")
        with self.assertRaises(InputError):
            text_settings.load_section("rules")

    def test_legacy_wrapped_rules_are_read_and_preserved_until_save(self):
        target=text_settings.RULES_FILE
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps({"rules":[{"match":"abc","spoken":"xyz"}]},
                                     ensure_ascii=False),encoding="utf-8")
        data=text_settings.load_section("rules")
        self.assertEqual(data["value"],[{"match":"abc","spoken":"xyz"}])
        self.assertTrue(data["saved"])
        self.assertTrue(target.read_text(encoding="utf-8").startswith('{"rules":'))

    def test_simultaneous_clients_only_one_can_save_stale_revision(self):
        revision=text_settings.load_section("rules")["revision"]
        candidates=[[{"match":"A","spoken":"B"}],
                    [{"match":"C","spoken":"D"}]]
        def save(item):
            try:
                text_settings.save_section("rules",item,revision)
                return "saved"
            except text_settings.SettingsConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(save,candidates))
        self.assertEqual(sorted(outcomes),["conflict","saved"])


class TextSettingsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base="http://127.0.0.1:"+str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patches=[
            patch.object(text_settings,"RULES_FILE",root/"rules.json"),
            patch.object(text_settings,"PRONUNCIATIONS_FILE",root/"pronunciations.json"),
        ]
        for handle in self.patches:
            handle.start()

    def tearDown(self):
        for handle in reversed(self.patches):
            handle.stop()
        self.tmp.cleanup()

    def get(self,url):
        with urlopen(self.base+url,timeout=5) as response:
            return json.load(response)

    def post(self,section,value,revision,*,header=True,ctype="application/json"):
        request=Request(
            self.base+"/v1/settings/text",method="POST",
            headers=({"Content-Type":ctype,"X-VoxWeaveTTS-Intent":"save-text-settings"}
                     if header else {"Content-Type":ctype}),
            data=json.dumps({"section":section,"value":value,
                             "expected_revision":revision},
                            ensure_ascii=False).encode("utf-8"))
        return urlopen(request,timeout=5)

    def test_roundtrip_and_text_processor_uses_saved_rules_without_engine(self):
        state=self.get("/v1/settings/text")
        self.assertFalse(state["saved"]["rules"])
        rules=[{"match":"555","match_mode":"five_run","mode":"replace",
                "spoken":"ฮ่า ฮ่า ฮ่า"}]
        with self.post("rules",rules,state["revisions"]["rules"]) as response:
            self.assertEqual(response.status,200)
            saved=json.load(response)
        self.assertEqual(self.get("/v1/rules"),rules)
        self.assertEqual(self.get("/v1/settings/text")["revisions"]["rules"],
                         saved["revision"])
        p={"อมตะ":"อะ มะ ตะ"}
        with self.post("pronunciations",p,state["revisions"]["pronunciations"]):
            pass
        self.assertEqual(self.get("/v1/pronunciations"),p)
        payload=json.dumps({"text":"อมตะ 55555"} ,ensure_ascii=False).encode("utf-8")
        req=Request(self.base+"/v1/text/process",data=payload,method="POST",
                    headers={"Content-Type":"application/json"})
        with urlopen(req,timeout=5) as response:
            result=json.load(response)
        self.assertIn("อะ มะ ตะ",result["spoken_text"])
        self.assertIn("ฮ่า ฮ่า ฮ่า",result["spoken_text"])
        self.assertEqual(result["display_text"],"อมตะ 55555")

    def test_intent_mime_conflict_and_invalid_rules(self):
        state=self.get("/v1/settings/text")
        revision=state["revisions"]["rules"]
        with self.assertRaises(HTTPError) as err:
            self.post("rules",[],revision,header=False)
        self.assertEqual(err.exception.code,403)
        err.exception.close()
        with self.assertRaises(HTTPError) as err:
            self.post("rules",[],revision,ctype="text/plain")
        self.assertEqual(err.exception.code,415)
        err.exception.close()
        with self.assertRaises(HTTPError) as err:
            self.post("rules",[{"match":"a","match_mode":"unsafe_regex"}],revision)
        self.assertEqual(err.exception.code,400)
        err.exception.close()
        with self.post("rules",[{"match":"hello","spoken":"สวัสดี"}],revision):
            pass
        with self.assertRaises(HTTPError) as err:
            self.post("rules",[],revision)
        self.assertEqual(err.exception.code,409)
        err.exception.close()


if __name__ == "__main__":
    unittest.main()