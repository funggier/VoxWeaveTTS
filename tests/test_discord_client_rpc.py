"""Official Discord Desktop RPC room-specific message source — offline tests."""
from __future__ import annotations

import io
import json
import struct
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs

from voxweavetts.discord_client_rpc import (
    CHANNEL_ID, CLOSE, FRAME, HANDSHAKE, PING, PONG,
    DiscordClientRPCAdapter, DISCORD_HTTP_USER_AGENT,
    frame_packet, parse_channel_event, oauth_exchange,
    rpc_oauth_error_hint,
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
                assert "redirect_uri" not in body["args"]  # official AUTHORIZE schema
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
    def test_rpc_oauth_5000_allowlisted_diagnostics(self):
        from voxweavetts.source_adapters import SourceFailure
        for code, hint in (("invalid_scope", "authorized tester"),
                           ("invalid_request", "invalid_request"),
                           ("invalid_client", "invalid_client"),
                           ("unauthorized_client", "unauthorized_client")):
            with self.subTest(code=code):
                details = {"code": 5000, "message":
                           "OAuth2 Error: " + code + ": private-user-secret-do-not-echo"}
                message = rpc_oauth_error_hint(details)
                self.assertIn(code, message)
                self.assertNotIn("private-user-secret", message)
        for invalid in ("OAuth2 Error: unexpected_new_error: SECRET",
                        "arbitrary SECRET with invalid_scope inside",
                        "OAuth2 Error: invalid_scope: " + "SECRET" * 500):
            with self.subTest(invalid=invalid[:32]):
                self.assertEqual(rpc_oauth_error_hint({"code": 5000, "message": invalid}),
                                 "OAuth2 error (5000); details unavailable")
        self.assertEqual(rpc_oauth_error_hint(None),
                         "OAuth2 error (5000); details unavailable")

        mock = MockPipe()
        original_write = mock.write
        def denied(packet):
            original_write(packet)
            if mock.commands and mock.commands[-1]["cmd"] == "AUTHORIZE":
                mock.buffer.clear()
                mock.queue(FRAME, {
                    "cmd": "AUTHORIZE", "evt": "ERROR",
                    "nonce": mock.commands[-1]["nonce"],
                    "data": {"code": 5000,
                             "message": "OAuth2 Error: invalid_scope: SECRET-PROVIDER-DATA"},
                })
        mock.write = denied
        client = DiscordClientRPCAdapter(
            CHANNEL, CREDS, pipe_factory=lambda: mock,
            exchange=lambda *args: "not_used",
        )
        with self.assertRaises(SourceFailure) as failure:
            client.poll()
        self.assertIn("invalid_scope", str(failure.exception))
        self.assertIn("5000", str(failure.exception))
        self.assertNotIn("SECRET-PROVIDER-DATA", str(failure.exception))
        self.assertTrue(failure.exception.fatal)
        self.assertTrue(mock.closed)

    def test_oauth_token_request_and_safe_http_error_diagnostics(self):
        from voxweavetts.source_adapters import SourceFailure
        for error_id in ("invalid_grant", "invalid_client", "unknown-error"):
            with self.subTest(error_id=error_id):
                class ErrorOpener:
                    def open(self, request, timeout):
                        self.assert_payload = parse_qs(request.data.decode("utf-8"))
                        self.req_url = request.full_url
                        self.req_headers = request.headers
                        body = json.dumps({
                            "error": error_id,
                            "error_description": "SECRET_IN_PROVIDER_DESCRIPTION",
                            "access_token": "SECRET_IN_PROVIDER_TOKEN",
                        }).encode("utf-8")
                        raise HTTPError(request.full_url, 400, "Bad Request",
                                        {}, io.BytesIO(body))
                opener = ErrorOpener()
                with patch("voxweavetts.discord_client_rpc.build_opener", return_value=opener):
                    with self.assertRaises(SourceFailure) as failure:
                        oauth_exchange(APP_ID, "SECRET_IN_CLIENT", "http://127.0.0.1:8765",
                                       "SECRET_IN_CODE")
                self.assertEqual(opener.req_url, "https://discord.com/api/v10/oauth2/token")
                self.assertEqual(opener.req_headers["User-agent"], DISCORD_HTTP_USER_AGENT)
                self.assertIn("VoxWeaveTTS (https://github.com/funggier/VoxWeaveTTS,", DISCORD_HTTP_USER_AGENT)
                self.assertEqual(opener.assert_payload["redirect_uri"], ["http://127.0.0.1:8765"])
                self.assertEqual(opener.assert_payload["grant_type"], ["authorization_code"])
                self.assertEqual(opener.assert_payload["code"], ["SECRET_IN_CODE"])
                message = str(failure.exception)
                self.assertTrue(failure.exception.fatal)
                self.assertIn("HTTP 400", message)
                for private in ("SECRET_IN_PROVIDER_DESCRIPTION", "SECRET_IN_PROVIDER_TOKEN",
                                "SECRET_IN_CLIENT", "SECRET_IN_CODE", "unknown-error"):
                    self.assertNotIn(private, message)
                if error_id in ("invalid_grant", "invalid_client"):
                    self.assertIn(error_id, message)

    def test_oauth_rejects_non_json_server_error_without_disclosing_html(self):
        from voxweavetts.source_adapters import SourceFailure
        class HtmlOpener:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 502, "Bad Gateway", {},
                                io.BytesIO(b"<html>SECRET_HTML</html>"))
        with patch("voxweavetts.discord_client_rpc.build_opener", return_value=HtmlOpener()):
            with self.assertRaises(SourceFailure) as failure:
                oauth_exchange(APP_ID, CREDS["client_secret"], CREDS["redirect_uri"], "TEST_CODE")
        self.assertIn("HTTP 502", str(failure.exception))
        self.assertNotIn("SECRET_HTML", str(failure.exception))

    def test_http_403_is_reported_as_api_block_without_leaking_html(self):
        from voxweavetts.source_adapters import SourceFailure
        class Forbidden:
            def open(self, request, timeout):
                self.user_agent = request.headers.get("User-agent")
                raise HTTPError(request.full_url, 403, "Forbidden", {},
                                io.BytesIO(b"<html>SECRET_NO_LEAK</html>"))
        opener = Forbidden()
        with patch("voxweavetts.discord_client_rpc.build_opener", return_value=opener):
            with self.assertRaises(SourceFailure) as error:
                oauth_exchange(APP_ID, "PRIVATE_CLIENT_SECRET",
                               "http://127.0.0.1:8765", "PRIVATE_AUTHORIZATION_CODE")
        self.assertEqual(opener.user_agent, DISCORD_HTTP_USER_AGENT)
        self.assertIn("HTTP 403", str(error.exception))
        for secret in ("PRIVATE_CLIENT_SECRET", "PRIVATE_AUTHORIZATION_CODE", "SECRET_NO_LEAK"):
            self.assertNotIn(secret, str(error.exception))

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
        self.assertEqual(client.phase,"subscribed")
        self.assertNotIn("redirect_uri", mock.commands[0]["args"])
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

    def test_handshake_timeout_needs_fresh_consent_and_keeps_manager_alive(self):
        from voxweavetts.source_adapters import SourceFailure
        mock = MockPipe()
        mock.buffer.clear()  # Discord Desktop never replies to handshake.
        client = DiscordClientRPCAdapter(
            CHANNEL, CREDS, pipe_factory=lambda: mock,
            exchange=lambda *args: "approved-rpc-token-value",
        )
        with self.assertRaises(SourceFailure) as error:
            client.poll()
        self.assertTrue(error.exception.fatal)
        self.assertTrue(mock.closed)
        self.assertTrue(client._terminal)
        self.assertEqual(client._secret, "")
        self.assertFalse(client._cancel.is_set())
        client.close()

    def test_delayed_discord_consent_does_not_fail_on_empty_idle_frames(self):
        from voxweavetts.source_adapters import SourceFailure
        class DelayedAuthorize(MockPipe):
            def __init__(self):
                super().__init__()
                self.pending_authorize = b""
                self.empty_reads = 0
            def write(self, packet):
                super().write(packet)
                if self.commands and self.commands[-1]["cmd"] == "AUTHORIZE":
                    self.pending_authorize = bytes(self.buffer)
                    self.buffer.clear()
            def read_exact(self, length, cancel, timeout=20):
                if self.pending_authorize:
                    if self.empty_reads < 2:
                        self.empty_reads += 1
                        raise SourceFailure("Discord RPC response timed out", retry_after=5)
                    self.buffer.extend(self.pending_authorize)
                    self.pending_authorize = b""
                return super().read_exact(length, cancel, timeout)
        mock = DelayedAuthorize()
        client = DiscordClientRPCAdapter(
            CHANNEL, CREDS, pipe_factory=lambda: mock,
            exchange=lambda *args: "approved-rpc-token-value",
        )
        self.assertFalse(client.poll().messages)
        self.assertEqual(mock.empty_reads, 2)
        self.assertEqual(client.phase, "subscribed")
        client.close()

    def test_discord_permission_error_uses_safe_code_not_raw_server_message(self):
        from voxweavetts.source_adapters import SourceFailure
        mock = MockPipe()
        original_write = mock.write
        def denied(packet):
            original_write(packet)
            if mock.commands and mock.commands[-1]["cmd"] == "AUTHORIZE":
                mock.buffer.clear()
                mock.queue(FRAME, {
                    "cmd": "AUTHORIZE", "evt": "ERROR",
                    "nonce": mock.commands[-1]["nonce"],
                    "data": {"code": 4006, "message": "private-secret-must-not-appear"},
                })
        mock.write = denied
        client = DiscordClientRPCAdapter(
            CHANNEL, CREDS, pipe_factory=lambda: mock,
            exchange=lambda *args: "approved-rpc-token-value",
        )
        with self.assertRaises(SourceFailure) as error:
            client.poll()
        self.assertTrue(error.exception.fatal)
        self.assertIn("approved app/tester", str(error.exception))
        self.assertNotIn("private-secret", str(error.exception))
        self.assertTrue(mock.closed)

    def test_manager_retains_failed_oauth_phase_for_diagnostics(self):
        from voxweavetts.source_adapters import SourceFailure
        modes = ModeState()
        playback = PlaybackState()
        active = modes.activate("discord_client", playback)
        manager = SourceManager(client_factory=lambda source, cred: DiscordClientRPCAdapter(
            source, cred, pipe_factory=MockPipe,
            exchange=lambda *args: (_ for _ in ()).throw(
                SourceFailure("Discord OAuth token exchange: invalid_grant (HTTP 400)", fatal=True)
            ),
        ))
        try:
            manager.start({"mode": "discord_client", "mode_token": active["mode_token"],
                           "source_id": CHANNEL, "credential": dict(CREDS)}, modes)
            deadline = time.monotonic() + 3
            while manager.status("discord_client")["state"] != "error" and time.monotonic() < deadline:
                time.sleep(.01)
            status = manager.status("discord_client")
            self.assertEqual(status["state"], "error")
            self.assertEqual(status["connection_phase"], "disconnected")
            self.assertEqual(status["failed_phase"], "exchanging_oauth_code")
            self.assertIn("invalid_grant", status["info"])
            self.assertNotIn(CREDS["client_secret"], str(status))
        finally:
            manager.stop_all()

    def test_idle_timeout_keeps_authorized_channel_alive(self):
        mock = MockPipe()
        client = DiscordClientRPCAdapter(
            CHANNEL, CREDS, pipe_factory=lambda: mock,
            exchange=lambda *args: "approved-rpc-token-value",
        )
        client.poll()
        self.assertEqual(client.poll().messages, ())
        self.assertTrue(client._connected)
        self.assertFalse(mock.closed)
        mock.queue(FRAME, dispatch(CHANNEL, "ข้อความใหม่"))
        self.assertEqual(client.poll().messages[0].text, "ข้อความใหม่")
        client.close()

    def test_disconnect_and_close_frame_require_explicit_reconnect(self):
        from voxweavetts.source_adapters import SourceFailure
        for disconnected in (False, True):
            with self.subTest(disconnected=disconnected):
                mock = MockPipe()
                client = DiscordClientRPCAdapter(
                    CHANNEL, CREDS, pipe_factory=lambda: mock,
                    exchange=lambda *args: "approved-rpc-token-value",
                )
                client.poll()
                if disconnected:
                    def failed_read(*args):
                        raise SourceFailure("Discord RPC transport disconnected", retry_after=5)
                    mock.read_exact = failed_read
                else:
                    mock.queue(CLOSE, {"message": "closed"})
                with self.assertRaises(SourceFailure) as error:
                    client.poll()
                self.assertTrue(error.exception.fatal)
                self.assertIn("reconnect", str(error.exception))
                self.assertTrue(mock.closed)
                self.assertFalse(client._connected)
                self.assertFalse(client._cancel.is_set(),
                                 "adapter must let SourceManager publish fatal error")
                with self.assertRaises(SourceFailure):
                    client.poll()
                client.close()

    def test_manager_reports_terminal_rpc_error_instead_of_retrying(self):
        from voxweavetts.source_adapters import SourceFailure
        class DisconnectAfterSubscribe(MockPipe):
            def write(self, packet):
                super().write(packet)
                if self.commands and self.commands[-1]["cmd"] == "SUBSCRIBE":
                    self.queue(CLOSE, {"message": "closed"})
        modes = ModeState()
        playback = PlaybackState()
        active = modes.activate("discord_client", playback)
        manager = SourceManager(client_factory=lambda source, cred: DiscordClientRPCAdapter(
            source, cred, pipe_factory=DisconnectAfterSubscribe,
            exchange=lambda *args: "approved-rpc-token-value",
        ))
        try:
            manager.start({"mode": "discord_client", "mode_token": active["mode_token"],
                           "source_id": CHANNEL, "credential": dict(CREDS)}, modes)
            deadline = time.monotonic() + 3
            while manager.status("discord_client")["state"] != "error" and time.monotonic() < deadline:
                time.sleep(.01)
            status = manager.status("discord_client")
            self.assertEqual(status["state"], "error")
            self.assertIn("reconnect", status["info"])
            self.assertEqual(status["next_poll_seconds"], 0)
            self.assertEqual(status["connection_phase"], "disconnected")
            self.assertEqual(status["failed_phase"], "subscribed")
        finally:
            manager.stop_all()

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
