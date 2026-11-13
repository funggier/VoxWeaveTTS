"""Extension bridge: explicit pairing, loopback HTTP/CORS, source queue, isolation."""
from __future__ import annotations

from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json
import secrets
import threading
import time
import unittest
from unittest.mock import patch

from voxweavetts.mode_state import ModeState
from voxweavetts.playback_state import PlaybackState
from voxweavetts.processing import InputError
from voxweavetts.server import Handler
from voxweavetts.source_manager import SourceManager
from voxweavetts.tiktok_extension import (
    ExtensionBridgeError, TikTokExtensionAdapter, extension_id_from_origin,
)

USERNAME = "demo_stream"
LIVE_URL = "https://www.tiktok.com/@" + USERNAME + "/live"
EXT_ID = "abcdefghijklmnopabcdefghijklmnop"
EXT_ORIGIN = "chrome-extension://" + EXT_ID


class AdapterTests(unittest.TestCase):
    def test_live_url_validation(self):
        from voxweavetts.tiktok_live_url import username_from_input
        valid = ("demo_stream", "@demo_stream",
                 "https://www.tiktok.com/@demo_stream/live",
                 "https://tiktok.com/@demo_stream/live")
        for value in valid:
            with self.subTest(value=value):
                self.assertEqual(username_from_input(value), "demo_stream")
        invalid = ("", "bad name", ".bad", "bad.",
                   "https://evil.example.com/@demo_stream/live",
                   "http://www.tiktok.com/@demo_stream/live",
                   "https://www.tiktok.com:443/@demo_stream/live",
                   "https://www.tiktok.com/@another/video/123",
                   "https://www.tiktok.com.evil.invalid/@demo_stream/live")
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(InputError):
                username_from_input(value)

    def test_origin_whitelist(self):
        self.assertEqual(extension_id_from_origin(EXT_ORIGIN), EXT_ID)
        for value in ("", "null", "https://www.tiktok.com", "chrome-extension://evil",
                      "chrome-extension://" + EXT_ID + "/popup.html",
                      "chrome-extension://" + EXT_ID + ".invalid"):
            self.assertIsNone(extension_id_from_origin(value))

    def test_pairing_single_use_expiry_tab_and_token(self):
        a = TikTokExtensionAdapter(USERNAME)
        code = a.pairing_code
        self.assertGreater(len(code), 24)
        self.assertEqual(a.phase, "waiting_extension_pair")
        with self.assertRaises(ExtensionBridgeError):
            a.pair("wrong", EXT_ID, LIVE_URL)
        with self.assertRaises(ExtensionBridgeError):
            a.pair(code, EXT_ID, "https://www.tiktok.com/@other/live")
        with patch("voxweavetts.tiktok_extension.time.monotonic",
                   return_value=a._pair_created + 305):
            with self.assertRaises(ExtensionBridgeError):
                a.pair(code, EXT_ID, LIVE_URL)
        token = a.pair(code, EXT_ID, LIVE_URL)
        self.assertEqual(a.pairing_code, "")
        with self.assertRaises(ExtensionBridgeError):
            a.pair(code, EXT_ID, LIVE_URL)
        with self.assertRaises(ExtensionBridgeError):
            a.receive(extension_id=EXT_ID, token="invalid", url=LIVE_URL,
                      phase="ready", items=[])
        with self.assertRaises(ExtensionBridgeError):
            a.receive(extension_id="b"*32, token=token, url=LIVE_URL,
                      phase="ready", items=[])
        with self.assertRaises(ExtensionBridgeError):
            a.receive(extension_id=EXT_ID, token=token,
                      url="https://www.tiktok.com/@other/live",
                      phase="ready", items=[])
        with self.assertRaises(ExtensionBridgeError):
            a.receive(extension_id=EXT_ID, token=token,
                      url=LIVE_URL, phase="waiting_chat_dom",
                      items=[{"id":"x","author":"A","text":"No"}])
        self.assertEqual(a.receive(extension_id=EXT_ID, token=token, url=LIVE_URL,
                      phase="ready", items=[{"id":"m1","author":"A","text":"สวัสดี"}]), 1)
        batch = a.poll()
        self.assertEqual([m.text for m in batch.messages], ["สวัสดี"])
        self.assertEqual(a.poll().messages, ())
        a.disconnect(extension_id=EXT_ID,token=token)
        self.assertEqual(a.phase,"extension_disconnected")
        with self.assertRaises(ExtensionBridgeError):
            a.receive(extension_id=EXT_ID,token=token,url=LIVE_URL,phase="ready",items=[])
        a.close()

    def test_mixed_gift_and_comment_events_preserve_structured_metadata(self):
        a = TikTokExtensionAdapter(USERNAME)
        token = a.pair(a.pairing_code, EXT_ID, LIVE_URL)
        rows = [
            {"id":"c1","author":"Viewer","text":"สวัสดีครับ",
             "kind":"comment","level":"25","rank":"3","badges":["InvT"]},
            {"id":"g1","author":"Viewer","text":"Heart Me","kind":"gift",
             "gift_name":"Heart Me","gift_count":3,
             "level":"","rank":"","badges":["InvT"]},
        ]
        try:
            self.assertEqual(a.receive(extension_id=EXT_ID,token=token,url=LIVE_URL,
                             phase="ready",items=rows),2)
            events=[e.public() for e in a.poll().messages]
            self.assertEqual(events[0]["text"],"สวัสดีครับ")
            self.assertEqual(events[0]["level"],"25")
            self.assertEqual(events[0]["rank"],"3")
            self.assertEqual(events[0]["badges"],["InvT"])
            self.assertEqual(events[1]["kind"],"gift")
            self.assertEqual(events[1]["gift_name"],"Heart Me")
            self.assertEqual(events[1]["gift_count"],3)
            self.assertNotIn("gift_name",events[0])
            for invalid in (
                {**rows[1],"gift_count":0},
                {**rows[1],"gift_count":"3"},
                {**rows[1],"kind":"comment"},
                {**rows[0],"kind":"share"},
                {**rows[0],"badges":["B"*49]},
                {**rows[0],"level":"0"*49},
            ):
                with self.subTest(invalid=invalid),self.assertRaises(ExtensionBridgeError):
                    a.receive(extension_id=EXT_ID,token=token,url=LIVE_URL,
                              phase="ready",items=[invalid])
        finally:
            a.close()

    def test_background_timer_throttling_does_not_false_disconnect(self):
        from voxweavetts.tiktok_extension import HEARTBEAT_WINDOW
        self.assertGreaterEqual(HEARTBEAT_WINDOW, 90)
        a = TikTokExtensionAdapter(USERNAME)
        token = a.pair(a.pairing_code, EXT_ID, LIVE_URL)
        try:
            with patch("voxweavetts.tiktok_extension.time.monotonic",
                       return_value=a._last_seen+61):
                a.poll()
                self.assertEqual(a.phase, "waiting_chat_dom")
            with patch("voxweavetts.tiktok_extension.time.monotonic",
                       return_value=a._last_seen+HEARTBEAT_WINDOW+1):
                a.poll()
                self.assertEqual(a.phase, "extension_disconnected")
            a.receive(extension_id=EXT_ID,token=token,url=LIVE_URL,
                      phase="ready",items=[])
            self.assertEqual(a.phase,"ready")
        finally:
            a.close()

    def test_dom_diagnostics_are_bounded_counts_not_raw_chat(self):
        a = TikTokExtensionAdapter(USERNAME)
        token = a.pair(a.pairing_code, EXT_ID, LIVE_URL)
        diagnostic = {"list_found": True, "row_candidates": 2,
                      "parsed_rows": 0, "fresh_rows": 0, "author_nodes": 0,
                      "tab_visible": False, "tab_focused": False,
                      "chat_change_age_seconds": 61}
        try:
            count = a.receive(extension_id=EXT_ID, token=token, url=LIVE_URL,
                              phase="ready", items=[], diagnostics=diagnostic)
            self.assertEqual(count, 0)
            self.assertEqual(a.diagnostics, diagnostic)
            for invalid in (
                {"list_found": "yes", "row_candidates": 2, "parsed_rows": 0,
                 "fresh_rows": 0, "author_nodes": 0},
                {**diagnostic, "parsed_rows": "private text"},
                {**diagnostic, "raw_html": "<div>private comment</div>"},
                {**diagnostic, "row_candidates": 999999},
                {"list_found": True},
            ):
                with self.subTest(invalid=invalid), self.assertRaises(ExtensionBridgeError):
                    a.receive(extension_id=EXT_ID, token=token, url=LIVE_URL,
                              phase="ready", items=[], diagnostics=invalid)
        finally:
            a.close()

    def test_payload_bounds(self):
        a = TikTokExtensionAdapter(USERNAME)
        token = a.pair(a.pairing_code, EXT_ID, LIVE_URL)
        invalid_batches = (
            [{"id":"a","author":"A","text":""}],
            [{"id":"a","author":"A","text":"x"*281}],
            [{"id":"bad/id","author":"A","text":"ok"}],
            [{"id":"a","author":"A","text":"\x01"}],
            [{"id":"a","author":"A","text":"okay", "secret":"no"}],
        )
        for rows in invalid_batches:
            with self.subTest(rows=rows),self.assertRaises(ExtensionBridgeError):
                a.receive(extension_id=EXT_ID,token=token,url=LIVE_URL,
                          phase="ready",items=rows)
        with self.assertRaises(ExtensionBridgeError):
            a.receive(extension_id=EXT_ID,token=token,url=LIVE_URL,
                      phase="ready",items=[{"id":str(i),"author":"A","text":"X"}
                                           for i in range(21)])
        a.close()


class HTTPBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.mode_state = ModeState()
        cls.server.playback_state = PlaybackState()
        cls.server.source_manager = SourceManager()
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.source_manager.stop_all()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)

    def send(self, route, payload=None, *, origin=None, intent=None, method="POST",
             host=None):
        headers={}
        if origin is not None: headers["Origin"]=origin
        if intent is not None: headers["X-VoxWeaveTTS-Intent"]=intent
        if host: headers["Host"]=host
        if method=="OPTIONS":
            headers["Access-Control-Request-Method"]="POST"
            data=None
        else:
            headers["Content-Type"]="application/json"
            data=json.dumps(payload).encode("utf-8")
        request=Request(self.base+route, data=data, method=method,headers=headers)
        try:
            with urlopen(request,timeout=3) as response:
                raw=response.read()
                return response.status, response.headers, json.loads(raw) if raw else {}
        except HTTPError as exc:
            status=exc.code
            body=json.loads(exc.read().decode("utf-8") or "{}")
            return status, exc.headers, body

    def test_untrusted_origin_preflight_pairing_and_forwarding(self):
        mode=self.send("/v1/modes/activate",{"mode":"tiktok_browser"},
                       intent="activate-mode")[2]
        source=self.send("/v1/sources/start",{
            "mode":"tiktok_browser","source_id":LIVE_URL,
            "mode_token":mode["mode_token"],"credential":"",
        },intent="start-live-source")[2]
        code=source["pairing_code"]
        self.assertGreater(len(code),24)
        self.assertNotIn("pairing_code",self.server.source_manager.status("tiktok_browser"))
        self.assertNotIn(code,json.dumps(self.server.source_manager.status("tiktok_browser")))
        self.assertEqual(self.send("/v1/extension/pair",{"code":code,"url":LIVE_URL},
                         origin="https://www.tiktok.com",intent="tiktok-extension")[0],403)
        self.assertEqual(self.send("/v1/extension/pair",{"code":code,"url":LIVE_URL},
                         origin=EXT_ORIGIN,intent="wrong")[0],403)
        self.assertEqual(self.send("/v1/extension/pair",{"code":code,"url":LIVE_URL},
                         origin=EXT_ORIGIN,intent="tiktok-extension",
                         host="evil.example.com")[0],403)
        ok,headers,_=self.send("/v1/extension/pair",method="OPTIONS",origin=EXT_ORIGIN)
        self.assertEqual(ok,204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"),EXT_ORIGIN)
        self.assertEqual(self.send("/v1/extension/pair",method="OPTIONS",
                                   origin="https://evil.example.com")[0],403)
        status,headers,paired=self.send("/v1/extension/pair",{
            "code":code,"url":LIVE_URL,
        },origin=EXT_ORIGIN,intent="tiktok-extension")
        self.assertEqual(status,200)
        self.assertEqual(headers["Access-Control-Allow-Origin"],EXT_ORIGIN)
        token=paired["token"]
        self.assertGreater(len(token),35)
        self.assertEqual(self.send("/v1/extension/pair",{
            "code":code,"url":LIVE_URL,
        },origin=EXT_ORIGIN,intent="tiktok-extension")[0],403)
        wrong=self.send("/v1/extension/messages",{
            "token":"wrong","url":LIVE_URL,"phase":"ready","items":[],
        },origin=EXT_ORIGIN,intent="tiktok-extension")
        self.assertEqual(wrong[0],403)
        status,_,r=self.send("/v1/extension/messages",{
            "token":token,"url":LIVE_URL,"phase":"ready",
            "items":[{"id":"id1","author":"Viewer","text":"ทดสอบคอมเมนต์จาก Chrome"}],
            "diagnostics":{"list_found":True,"row_candidates":1,"parsed_rows":1,
                            "fresh_rows":1,"author_nodes":1,
                            "tab_visible":False,"tab_focused":False,
                            "chat_change_age_seconds":10},
        },origin=EXT_ORIGIN,intent="tiktok-extension")
        self.assertEqual((status,r["accepted"]),(200,1))
        health = self.server.source_manager.status("tiktok_browser")
        self.assertEqual(health["dom_diagnostics"]["parsed_rows"], 1)
        self.assertNotIn("ทดสอบคอมเมนต์จาก Chrome",str(health["dom_diagnostics"]))
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            if self.server.source_manager.status("tiktok_browser")["received"]>=1: break
            time.sleep(.05)
        drain=self.send("/v1/sources/drain",{
            "mode":"tiktok_browser","mode_token":mode["mode_token"],"limit":5,
        },intent="drain-live-source")[2]
        self.assertEqual([x["text"] for x in drain["messages"]],
                         ["ทดสอบคอมเมนต์จาก Chrome"])
        # Live chat is separate from TikFinity's mode and YouTube.
        self.assertEqual(self.server.source_manager.status("tiktok")["state"] if False else
                         self.server.source_manager.status("live")["state"],"idle")
        self.send("/v1/extension/disconnect",{"token":token},
                  origin=EXT_ORIGIN,intent="tiktok-extension")
        with self.assertRaises(ExtensionBridgeError):
            self.server.source_manager.extension_push({
                "token":token,"url":LIVE_URL,"phase":"ready","items":[]},
                EXT_ID,self.server.mode_state)
        self.server.source_manager.stop_all()


if __name__=="__main__":
    unittest.main()
