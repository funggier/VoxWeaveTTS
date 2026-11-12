"""Read-only official Live/Discord adapters without network access or secrets."""
from __future__ import annotations

import json
import io
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
from unittest.mock import patch

from voxweavetts.mode_state import ModeState, ModeConflict
from voxweavetts.playback_state import PlaybackState
from voxweavetts.processing import InputError
from voxweavetts.source_adapters import (
    _normal_text, _fetch_json, DiscordChannelAdapter, PollResult, SourceFailure,
    SourceMessage, YouTubeLiveAdapter,
)
from voxweavetts.source_manager import MAX_PENDING, SourceManager
from voxweavetts.server import Handler


class AdapterTests(unittest.TestCase):
    def test_youtube_first_page_history_suppressed_then_ordered_messages(self):
        seen = []
        def get(url, headers):
            seen.append((url, headers))
            query = parse_qs(urlsplit(url).query)
            self.assertIn("key", query)
            if not query.get("pageToken"):
                return {
                    "nextPageToken":"page2", "pollingIntervalMillis":12000,
                    "items":[{"id":"historic","snippet":{"type":"textMessageEvent",
                                "textMessageDetails":{"messageText":"เก่ามาก"}}}],
                }, {}
            return {
                "nextPageToken":"page3", "pollingIntervalMillis":9000,
                "items":[
                    {"id":"new1","snippet":{"type":"textMessageEvent",
                        "textMessageDetails":{"messageText":"สวัสดีครับ 🧑🏽‍💻"}},
                     "authorDetails":{"displayName":"คุณหนึ่ง"}},
                    {"id":"event","snippet":{"type":"superChatEvent",
                        "textMessageDetails":{"messageText":"ไม่ใช่ข้อความธรรมดา"}}},
                    {"id":"new2","snippet":{"type":"textMessageEvent",
                        "textMessageDetails":{"messageText":"เพลงใหม่"}},
                     "authorDetails":{"displayName":"two"}},
                ],
            }, {}
        a=YouTubeLiveAdapter("Cg0K_livechat_id","test_api_key_12345",fetcher=get)
        self.assertEqual(a.poll().messages,())
        second=a.poll()
        self.assertEqual([x.message_id for x in second.messages],["new1","new2"])
        self.assertEqual(second.messages[0].text,"สวัสดีครับ 🧑🏽‍💻")
        self.assertEqual(second.delay_seconds,9)
        self.assertIn("pageToken=page2",seen[1][0])
        self.assertEqual(seen[0][1],{})

    def test_youtube_video_id_resolution(self):
        seen=[]
        def get(url,headers):
            seen.append(url)
            if "/videos?" in url:
                return {"items":[{"liveStreamingDetails":{
                    "activeLiveChatId":"Cg0K_real_chat_id"
                }}]},{}
            return {"nextPageToken":"p1","items":[]},{}
        a=YouTubeLiveAdapter("abcDefGhI12","test_api_key_12345",get)
        self.assertEqual(a.poll().messages,())
        self.assertEqual(a.chat_id,"Cg0K_real_chat_id")
        self.assertIn("liveChatId=Cg0K_real_chat_id",seen[-1])

    def test_external_http_error_status_actionable_without_leaking_credentials(self):
        for service,url in (
            ("YouTube","https://www.googleapis.com/youtube/v3/videos?key=SECRET_API_KEY"),
            ("Discord","https://discord.com/api/v10/channels/123456789012345678/messages"),
        ):
            for code,hint in ((400,"invalid request"),(401,"credentials"),
                              (403,"access denied"),(404,"not found")):
                with self.subTest(service=service,status=code):
                    error=HTTPError(
                        url,code,"bad request",{},
                        io.BytesIO(b'{"error":"SECRET_API_KEY or SECRET_BOT_TOKEN"}'),
                    )
                    with patch("voxweavetts.source_adapters.build_opener") as opener:
                        opener.return_value.open.side_effect=error
                        with self.assertRaises(SourceFailure) as failure:
                            _fetch_json(url,{"Authorization":"Bot SECRET_BOT_TOKEN"})
                    self.assertTrue(failure.exception.fatal)
                    self.assertIn(service,str(failure.exception))
                    self.assertIn(f"HTTP {code}",str(failure.exception))
                    self.assertIn(hint,str(failure.exception))
                    self.assertNotIn("SECRET_API_KEY",str(failure.exception))
                    self.assertNotIn("SECRET_BOT_TOKEN",str(failure.exception))

    def test_youtube_no_live_chat_is_hard_error(self):
        def get(*args):
            return {"items":[{"liveStreamingDetails":{}}]},{}
        with self.assertRaises(SourceFailure) as error:
            YouTubeLiveAdapter("abcDefGhI12","test_api_key_12345",get).poll()
        self.assertTrue(error.exception.fatal)
        self.assertNotIn("test_api_key",str(error.exception))

    def test_discord_bot_rest_order_and_first_page_skip(self):
        requests=[]
        def get(url,headers):
            requests.append((url,headers))
            messages=[
                {"id":"100000000000000006","content":"สาม",
                 "author":{"username":"user3","bot":False}},
                {"id":"100000000000000004","content":"บอต",
                 "author":{"username":"bot","bot":True}},
                {"id":"100000000000000005","content":"สอง",
                 "author":{"username":"user2"}},
            ]
            if len(requests)==1:
                return messages,{"x-ratelimit-remaining":"0",
                                 "x-ratelimit-reset-after":"8.5"}
            return [
                {"id":"100000000000000008","content":"🐱สวัสดี",
                 "author":{"username":"user4"}},
                {"id":"100000000000000007","content":"หนึ่ง",
                 "author":{"username":"user5"}},
                {"id":"100000000000000009","content":"bot",
                 "author":{"username":"b","bot":True}},
                {"id":"100000000000000010","content":"webhook",
                 "webhook_id":"123","author":{"username":"w"}},
            ],{}
        a=DiscordChannelAdapter("100000000000000001","a"*50,get)
        self.assertEqual(a.poll().messages,())
        self.assertGreaterEqual(a.poll().delay_seconds,5)
        self.assertEqual([x.text for x in a.poll().messages],["หนึ่ง","🐱สวัสดี"])
        self.assertTrue(requests[1][0].endswith("after=100000000000000006"))
        self.assertTrue(requests[2][1]["Authorization"].startswith("Bot "))
        self.assertNotIn("a"*50,requests[2][0])

    def test_invalid_ids_secrets_and_unicode_controls(self):
        for channel in ("abc","-1","https://evil.example","11111111111111111?@"):
            with self.subTest(channel=channel),self.assertRaises(InputError):
                DiscordChannelAdapter(channel,"x"*50)
        for source in ("../../etc/passwd","http://evil.example",""):
            with self.subTest(source=source),self.assertRaises(InputError):
                YouTubeLiveAdapter(source,"example_long_api_key")
        self.assertEqual(_normal_text("ก่\nข\t🧑🏽‍💻"),"ก่ ข 🧑🏽‍💻")


class FakeReadyAdapter:
    def __init__(self,source_id,credential):
        self.source_id=source_id
        self.credential=credential
        self.polls=0
    def poll(self):
        self.polls+=1
        return PollResult(tuple(
            [SourceMessage(str(i),"tester",("blocked message" if i==1 else f"คำใหม่ {i}"))
             for i in range(52)]
            + [SourceMessage("10","tester","คำใหม่ 10")]
            + [SourceMessage("duplicate-link","tester","https://bad.example/a")]
        ),5.0)


class FakeRateLimitAdapter:
    def __init__(self,*args):
        pass
    def poll(self):
        raise SourceFailure("source rate limit; retry later",retry_after=65)


class FakeUnexpectedAdapter:
    def __init__(self,*args):
        pass
    def poll(self):
        raise RuntimeError("fake transport failed with SECRET_CREDENTIAL")


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.modes=ModeState()
        self.playback=PlaybackState()
        self.owner=self.modes.activate("live",self.playback)
        self.manager=SourceManager(youtube_factory=FakeReadyAdapter)

    def tearDown(self):
        self.manager.stop_all()

    def test_owner_required_and_bounded_queue_moderation(self):
        base={"mode":"live","mode_token":self.owner["mode_token"],
              "source_id":"Cg0K_livechat_id","credential":"test_api_key_12345",
              "filters":{"blocked_words":["blocked"]}}
        with self.assertRaises(ModeConflict):
            self.manager.start({**base,"mode_token":"x"*32},self.modes)
        result=self.manager.start(base,self.modes)
        self.assertNotIn("credential",result)
        self.assertNotIn("test_api_key",str(result))
        deadline=time.monotonic()+2
        while self.manager.status("live").get("polls",0)<1 and time.monotonic()<deadline:
            time.sleep(.01)
        status=self.manager.status("live")
        self.assertEqual(status["polls"],1)
        self.assertEqual(status["pending"],MAX_PENDING)
        self.assertGreaterEqual(status["discarded"],2)
        self.assertEqual(status["duplicates"],1)
        messages=self.manager.drain({**base,"limit":20},self.modes)
        self.assertEqual(len(messages["messages"]),20)
        self.assertEqual(messages["messages"][0]["message_id"], "0",
                         "overflow must not evict oldest unread message")
        self.assertEqual(messages["messages"][1]["message_id"], "2")
        self.assertNotIn("blocked message",str(messages))
        self.assertNotIn("https://",str(messages))
        with self.assertRaises(ModeConflict):
            self.manager.drain({**base,"mode_token":"0"*32},self.modes)
        self.modes.activate("studio",self.playback)
        self.assertTrue(self.modes.is_owner("live",base["mode_token"]))
        self.manager.drain(base,self.modes)  # Other tab/Studio cannot stop LIVE.
        self.modes.activate("live",self.playback)
        with self.assertRaises(ModeConflict):
            self.manager.drain(base,self.modes)
        self.manager.stop_all()
        self.assertEqual(self.manager.status("live")["state"],"idle")

    def test_unexpected_source_exception_retries_without_worker_crash_or_secret_leak(self):
        manager=SourceManager(youtube_factory=FakeUnexpectedAdapter)
        try:
            manager.start({"mode":"live","mode_token":self.owner["mode_token"],
                           "source_id":"Cg0K_livechat_id",
                           "credential":"test_api_key_12345"},self.modes)
            deadline=time.monotonic()+2
            while manager.status("live")["state"]=="connecting" and time.monotonic()<deadline:
                time.sleep(.01)
            status=manager.status("live")
            self.assertEqual(status["state"],"retrying")
            self.assertGreaterEqual(status["next_poll_seconds"],5)
            self.assertNotIn("SECRET_CREDENTIAL",str(status))
            self.assertTrue(manager._sessions["live"].thread.is_alive())
        finally:
            manager.stop_all()

    def test_source_rate_limit_does_not_spin(self):
        manager=SourceManager(youtube_factory=FakeRateLimitAdapter)
        try:
            manager.start({"mode":"live","mode_token":self.owner["mode_token"],
                           "source_id":"Cg0K_livechat_id",
                           "credential":"test_api_key_12345"},self.modes)
            deadline=time.monotonic()+2
            while manager.status("live")["state"]=="connecting" and time.monotonic()<deadline:
                time.sleep(.01)
            state=manager.status("live")
            self.assertEqual(state["state"],"retrying")
            self.assertGreaterEqual(state["next_poll_seconds"],65)
            self.assertNotIn("test_api_key",str(state))
        finally:
            manager.stop_all()


class SourceHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.server.mode_state=ModeState()
        cls.server.playback_state=PlaybackState()
        cls.server.source_manager=SourceManager(youtube_factory=FakeReadyAdapter)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.source_manager.stop_all()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)

    def post(self,path,body,intent=None):
        headers={"Content-Type":"application/json"}
        if intent: headers["X-VoxWeaveTTS-Intent"]=intent
        req=Request(self.base+path,method="POST",headers=headers,
                    data=json.dumps(body).encode("utf-8"))
        with urlopen(req,timeout=5) as response:
            return json.load(response)

    def test_http_read_only_source_lifecycle(self):
        with self.assertRaises(HTTPError) as error:
            self.post("/v1/sources/start",{"mode":"live"},None)
        self.assertEqual(error.exception.code,403)
        error.exception.close()
        activated=self.post("/v1/modes/activate",{"mode":"live"},"activate-mode")
        payload={"mode":"live","mode_token":activated["mode_token"],
                 "source_id":"Cg0K_livechat_id",
                 "credential":"test_api_key_12345"}
        started=self.post("/v1/sources/start",payload,"start-live-source")
        self.assertEqual(started["mode"],"live")
        self.assertNotIn("credential",started)
        with urlopen(self.base+"/v1/sources/status?mode=live",timeout=5) as response:
            snapshot=json.load(response)
        self.assertNotIn("mode_token",snapshot)
        self.assertNotIn("test_api_key",str(snapshot))
        deadline=time.monotonic()+2
        while self.server.source_manager.status("live").get("polls",0)<1 and time.monotonic()<deadline:
            time.sleep(.01)
        drained=self.post("/v1/sources/drain",{**payload,"limit":4},"drain-live-source")
        self.assertEqual(len(drained["messages"]),4)
        # Switching to Settings must not disconnect YouTube LIVE. Only
        # reclaiming YouTube itself from another tab invalidates its token.
        restarted=self.post("/v1/sources/start",payload,"start-live-source")
        self.assertEqual(restarted["mode"],"live")
        changed=self.post("/v1/modes/activate",{"mode":"settings"},"activate-mode")
        self.assertEqual(changed["active_mode"],"settings")
        self.assertNotEqual(self.server.source_manager.status("live")["state"],"idle")
        self.post("/v1/sources/drain",payload,"drain-live-source")
        refreshed=self.post("/v1/modes/activate",{"mode":"live"},"activate-mode")
        self.assertEqual(self.server.source_manager.status("live")["state"],"idle")
        with self.assertRaises(HTTPError) as stale:
            self.post("/v1/sources/drain",payload,"drain-live-source")
        self.assertEqual(stale.exception.code,409)
        stale.exception.close()
        payload["mode_token"]=refreshed["mode_token"]
        self.post("/v1/sources/start",payload,"start-live-source")
        stopped=self.post("/v1/sources/stop",payload,"stop-live-source")
        self.assertEqual(stopped["state"],"stopped")
        with self.assertRaises(HTTPError) as error:
            self.post("/v1/sources/drain",payload,"drain-live-source")
        self.assertEqual(error.exception.code,409)
        error.exception.close()


if __name__=="__main__":
    unittest.main()