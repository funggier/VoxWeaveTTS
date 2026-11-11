"""Official Discord Desktop RPC room-specific message source — offline tests."""
from __future__ import annotations

import json
import struct
import threading
import time
import unittest

from voxweavetts.discord_client_rpc import (
    CHANNEL_ID, CLOSE, FRAME, HANDSHAKE, PING, PONG,
    DiscordClientRPCAdapter, frame_packet, parse_channel_event,
    parse_frame_header, validate_channel_id, validate_redirect_uri,
)
from voxweavetts.mode_state import ModeState, ModeConflict
from voxweavetts.playback_state import PlaybackState
from voxweavetts.processing import InputError
from voxweavetts.source_adapters import PollResult, SourceMessage
from voxweavetts.source_manager import SourceManager

CHANNEL = "100000000000000001"
OTHER = "100000000000000002"
APP_ID = "100000000000000005"
CREDS = {
    "client_id": APP_ID,
    "client_secret": "very_long_fake_secret_123",
    "redirect_uri": "http://127.0.0.1:8765/callback",
}


def dispatch(channel_id: str, text: str, message_id="100000000000000007") -> dict:
    return {
        "cmd": "DISPATCH", "evt": "MESSAGE_CREATE",
        "data": {
            "channel_id": channel_id,
            "message": {
                "id": message_id, "content": text,
                "author": {"id": "100000000000000009", "username": "ทดสอบ", "bot": False},
                "type": 0,
            },
        }
    }


class MockPipe:
    def __init__(self):
        self.buffer = bytearray()
        self.commands = []
        self.closed = False
        self.writes = []
        self.queue(FRAME, {"cmd": "DISPATCH", "evt": "READY", "data": {}})

    def queue(self, op: int, data: dict):
        self.buffer.extend(frame_packet(op, data))

    def write(self, packet: bytes) -> None:
        op, n = parse_frame_header(packet[:8])
        self.assert_packet_length = len(packet)
        assert n == len(packet) - 8
        body = json.loads(packet[8:].decode("utf-8"))
        self.writes.append((op, body))
        if op == HANDSHAKE:
            assert body["client_id"] == APP_ID
        elif op == FRAME:
            self.commands.append(body)
            cmd = body["cmd"]
            if cmd == "AUTHORIZE":
                assert body["args"]["scopes"] == ["rpc", "messages.read"]
                response = {"cmd": "AUTHORIZE", "nonce": body["nonce"], "data": {"code": "code-from-user-consent"}}
            elif cmd == "AUTHENTICATE":
                assert body["args"]["access_token"] == "approved-rpc-token-value"
                response = {"cmd": "AUTHENTICATE", "nonce": body["nonce"],
                            "data": {"scopes": ["rpc", "messages.read"]}}
            elif cmd == "SUBSCRIBE":
                assert body["evt"] == "MESSAGE_CREATE"
                response = {"cmd": "SUBSCRIBE", "nonce": body["nonce"],
                            "data": {"evt": "MESSAGE_CREATE"}}
            else:
                raise AssertionError("Unsupported RPC command "+cmd)
            self.queue(FRAME, response)

    def read_exact(self, length: int, cancel: threading.Event, timeout: float = 20) -> bytes:
        if len(self.buffer) < length:
            # No push messages yet; timeout is normal in a live session.
            from voxweavetts.source_adapters import SourceFailure
            raise SourceFailure("Discord RPC response timed out", retry_after=5)
        data = bytes(self.buffer[:length])
        del self.buffer[:length]
        return data

    def close(self):
        self.closed = True


class ClientRPCPayloadTests(unittest.TestCase):
    def test_validates_one_selected_channel_and_registered_redirect(self):
        self.assertEqual(validate_channel_id(CHANNEL), CHANNEL)
        for value in ("https://discord.com/channels/1/2", "invalid", "1234",
                      "100000000000000001;drop", "../etc/passwd", ""):
            with self.subTest(value=value), self.assertRaises(InputError):
                validate_channel_id(value)
        for good in ("https://example.test/auth", "http://localhost:8765/callback",
                     "http://127.0.0.1:8765/callback"):
            self.assertEqual(validate_redirect_uri(good), good)
        for bad in ("http://discord.example/auth", "file:///tmp/foo", "http://127.0.0.1@evil.example",
                    "javascript:alert(1)", "https://a.example/#token"):
            with self.subTest(uri=bad), self.assertRaises(InputError):
                validate_redirect_uri(bad)

    def test_decodes_only_selected_room_and_no_bot_or_blocked(self):
        self.assertIsNone(parse_channel_event(dispatch(OTHER, "ผิดห้อง"), CHANNEL))
        valid=parse_channel_event(dispatch(CHANNEL, "คำทดสอบภาษาไทย"), CHANNEL)
        self.assertIsNotNone(valid)
        self.assertEqual(valid.text, "คำทดสอบภาษาไทย")
        self.assertEqual(valid.author, "ทดสอบ")
        self.assertIsNone(parse_channel_event({"cmd":"DISPATCH","evt":"MESSAGE_UPDATE",
                                               "data":dispatch(CHANNEL,"แก้ไข")["data"]},CHANNEL))
        bot=dispatch(CHANNEL,"ข้อความจากบอต")
        bot["data"]["message"]["author"]["bot"]=True
        self.assertIsNone(parse_channel_event(bot,CHANNEL))
        blocked=dispatch(CHANNEL,"ไม่ควรอ่าน")
        blocked["data"]["message"]["blocked"]=True
        self.assertIsNone(parse_channel_event(blocked,CHANNEL))
        webhook=dispatch(CHANNEL,"เว็บฮุก")
        webhook["data"]["message"]["webhook_id"]="111"
        self.assertIsNone(parse_channel_event(webhook,CHANNEL))
        self.assertIsNone(parse_channel_event(dispatch(CHANNEL,""),CHANNEL))

    def test_binary_frames_bound_and_validated(self):
        data=frame_packet(FRAME,{"cmd":"PING","nonce":"abc"})
        self.assertEqual(parse_frame_header(data[:8]),(FRAME,len(data)-8))
        self.assertEqual(json.loads(data[8:].decode("utf-8"))["nonce"],"abc")
        from voxweavetts.source_adapters import SourceFailure
        with self.assertRaises(SourceFailure):
            parse_frame_header(struct.pack("<II",FRAME,65537))
        with self.assertRaises(SourceFailure):
            parse_frame_header(b"\0")


class ClientRPCProtocolTests(unittest.TestCase):
    def test_authorize_read_scope_and_subscribe_exact_channel(self):
        mock=MockPipe()
        exchanges=[]
        def exchange(app_id, secret, uri, code):
            exchanges.append((app_id, secret, uri, code))
            return "approved-rpc-token-value"
        client=DiscordClientRPCAdapter(CHANNEL,CREDS,pipe_factory=lambda:mock,exchange=exchange)
        first=client.poll()
        self.assertEqual(first.messages, ())
        self.assertEqual([x["cmd"] for x in mock.commands],
                         ["AUTHORIZE","AUTHENTICATE","SUBSCRIBE"])
        self.assertEqual(mock.commands[2]["args"]["channel_id"],CHANNEL)
        self.assertEqual(mock.commands[2]["evt"],"MESSAGE_CREATE")
        self.assertEqual(exchanges[0][3],"code-from-user-consent")
        self.assertEqual(client._secret,"")
        mock.queue(FRAME,dispatch(OTHER,"ห้ามเข้าคิว"))
        self.assertEqual(client.poll().messages,())
        mock.queue(FRAME,dispatch(CHANNEL,"อ่านได้ครับ"))
        actual=client.poll()
        self.assertEqual(len(actual.messages),1)
        self.assertEqual(actual.messages[0].text,"อ่านได้ครับ")
        self.assertEqual(actual.messages[0].message_id,"100000000000000007")
        client.close()
        self.assertTrue(mock.closed)

    def test_rejects_missing_rpc_permission(self):
        mock=MockPipe()
        original_write=mock.write
        def custom_write(packet):
            original_write(packet)
            if mock.commands and mock.commands[-1]["cmd"]=="AUTHENTICATE":
                # Replace response with missing messages.read.
                mock.buffer.clear()
                last=mock.commands[-1]
                mock.queue(FRAME,{"cmd":"AUTHENTICATE","nonce":last["nonce"],"data":{"scopes":["rpc"]}})
        mock.write=custom_write
        from voxweavetts.source_adapters import SourceFailure
        client=DiscordClientRPCAdapter(CHANNEL,CREDS,pipe_factory=lambda:mock,
                                       exchange=lambda *args:"approved-rpc-token-value")
        with self.assertRaises(SourceFailure):
            client.poll()
        self.assertTrue(mock.closed)

    def test_manager_uses_active_owner_and_channel_id(self):
        created=[]
        class FakeClient:
            def __init__(self,source_id,credential):
                self.channel_id=source_id
                self.credential=credential
                self.event=None
                self.closed=False
                created.append(self)
            def set_cancel(self,event):self.event=event
            def poll(self):return PollResult((SourceMessage("100000000000000007","x","สวัสดี"),),.5)
            def close(self):self.closed=True
        modes=ModeState()
        playback=PlaybackState()
        active=modes.activate("discord_client",playback)
        manager=SourceManager(client_factory=FakeClient)
        args={"mode":"discord_client","mode_token":active["mode_token"],
              "source_id":CHANNEL,"credential":dict(CREDS)}
        try:
            started=manager.start(args,modes)
            self.assertEqual(started["source_id"],CHANNEL)
            self.assertNotIn("client_secret",str(started))
            deadline=time.monotonic()+2
            while manager.status("discord_client").get("polls",0)<1 and time.monotonic()<deadline:
                time.sleep(.01)
            results=manager.drain({**args,"limit":1},modes)
            self.assertEqual(results["messages"][0]["text"],"สวัสดี")
            modes.activate("studio",playback)
            with self.assertRaises(ModeConflict):
                manager.drain({**args,"limit":1},modes)
            manager.stop_all()
            self.assertTrue(created[0].closed)
            self.assertTrue(created[0].event.is_set())
        finally:
            manager.stop_all()


if __name__=="__main__":
    unittest.main()
