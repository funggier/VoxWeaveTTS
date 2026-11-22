"""Core-based TikFinity localhost WebSocket; no browser or third-party WS wheel."""
import base64
import hashlib
import json
import socket
import struct
import threading
import time

import pytest

import voxweavetts.tikfinity_core as module
from voxweavetts.mode_state import ModeState
from voxweavetts.processing import InputError
from voxweavetts.source_manager import SourceManager
from voxweavetts.tikfinity_core import (
    TikFinityCoreAdapter, parse_tikfinity_chat, validate_tikfinity_endpoint
)


def frame(opcode, content, *, fin=True):
    length = len(content)
    flags = bytes([(0x80 if fin else 0) | opcode])
    if length < 126:
        return flags + bytes([length]) + content
    if length <= 65535:
        return flags + bytes([126]) + struct.pack("!H", length) + content
    return flags + bytes([127]) + struct.pack("!Q", length) + content


def test_tikfinity_url_is_loopback_only():
    for value in ("ws://localhost:21213", "ws://127.0.0.1:21213/",
                  "ws://localhost:21213/"):
        assert validate_tikfinity_endpoint(value) == "ws://127.0.0.1:21213/"
    for value in ("ws://192.168.1.1:21213", "ws://localhost:1234",
                  "ws://localhost:21213/evil", "http://localhost:21213",
                  "ws://evil@localhost:21213", "wss://localhost:21213"):
        with pytest.raises(InputError):
            validate_tikfinity_endpoint(value)


def test_tikfinity_parses_chat_only_with_metadata():
    assert parse_tikfinity_chat({"event": "gift", "data": {"comment": "x"}}, "fallback") is None
    parsed = parse_tikfinity_chat({
        "event": "chat", "data": {
            "id": "msg-9", "comment": "สวัสดีครับ 😂",
            "user": {"nickname": "ผู้ชม", "level": 18, "badges": [{"name": "VIP"}]},
        }
    }, "fallback")
    assert parsed is not None
    assert parsed.message_id == "msg-9"
    assert parsed.author == "ผู้ชม"
    assert parsed.text == "สวัสดีครับ 😂"
    assert parsed.level == "18"
    assert parsed.badges == ("VIP",)


def test_tikfinity_core_websocket_connects_receives_and_stops(monkeypatch):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    raw_connect = socket.create_connection
    seen = {"got_pong": False, "error": None}
    received_handshake = threading.Event()
    stop_server = threading.Event()

    def connect(address, timeout):
        assert address == ("127.0.0.1", 21213)
        return raw_connect(("127.0.0.1", port), timeout=timeout)

    monkeypatch.setattr(module.socket, "create_connection", connect)

    def server():
        try:
            conn, addr = listener.accept()
            conn.settimeout(2)
            with conn:
                data = bytearray()
                while b"\r\n\r\n" not in data:
                    data.extend(conn.recv(4096))
                headers = data.decode("ascii").split("\r\n")
                key = next(line.split(": ", 1)[1] for line in headers
                           if line.lower().startswith("sec-websocket-key:"))
                response_key = base64.b64encode(hashlib.sha1(
                    (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
                ).digest()).decode("ascii")
                conn.sendall((
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Connection: Upgrade\r\n"
                    "Upgrade: websocket\r\n"
                    f"Sec-WebSocket-Accept: {response_key}\r\n\r\n"
                ).encode("ascii"))
                received_handshake.set()
                msg = json.dumps({
                    "event": "chat", "data": {
                        "messageUuid": "abc456",
                        "comment": "ข้อความภาษาไทยจาก TikFinity สวัสดีครับ 😂",
                        "user": {"nickname": "ผู้ชมทดสอบ"}
                    }
                }, ensure_ascii=False).encode("utf-8")
                mid = len(msg)//2
                conn.sendall(frame(0x1, msg[:mid], fin=False))
                conn.sendall(frame(0x0, msg[mid:]))
                conn.sendall(frame(0x9, b"hi"))
                while not stop_server.is_set():
                    try:
                        raw = conn.recv(512)
                        if not raw:
                            break
                        if len(raw) >= 8 and raw[0] == 0x8A and raw[1] & 0x80:
                            payload = bytes(raw[6+i] ^ raw[2+i%4] for i in range(raw[1]&0x7F))
                            if payload == b"hi":
                                seen["got_pong"] = True
                    except socket.timeout:
                        continue
        except Exception as exc:
            seen["error"] = repr(exc)
        finally:
            listener.close()

    worker = threading.Thread(target=server, daemon=True)
    worker.start()
    adapter = TikFinityCoreAdapter("ws://localhost:21213")
    try:
        msgs = []
        for _ in range(12):
            msgs.extend(adapter.poll().messages)
            if msgs and seen["got_pong"]:
                break
        assert received_handshake.is_set()
        assert len(msgs) == 1
        assert msgs[0].message_id == "abc456"
        assert msgs[0].author == "ผู้ชมทดสอบ"
        assert "ภาษาไทย" in msgs[0].text
        assert seen["got_pong"]
    finally:
        adapter.close()
        stop_server.set()
        worker.join(timeout=3)
    assert not worker.is_alive()
    assert seen["error"] is None


def test_tikfinity_remote_close_reconnects_but_explicit_stop_does_not(monkeypatch):
    """A transient peer-close must not permanently disable the Core source."""
    from voxweavetts.source_adapters import SourceFailure

    class FakeSocket:
        def __init__(self):
            self.closed = False

        def shutdown(self, how):
            pass

        def close(self):
            self.closed = True

        def recv(self, size):
            raise socket.timeout()

    adapter = TikFinityCoreAdapter("ws://127.0.0.1:21213")
    old = FakeSocket()
    adapter._socket = old
    adapter._buffer.extend(b"\x01\x02")
    with pytest.raises(SourceFailure) as exc:
        adapter._decode_frame((True, 0x8, b""))
    assert not exc.value.fatal
    assert old.closed
    assert adapter._socket is None
    assert not adapter._closed
    assert not adapter._buffer
    connected = []

    def connect():
        connected.append(True)
        adapter._socket = FakeSocket()
        adapter._buffer = bytearray(frame(
            0x1, json.dumps({"event":"chat","data":{
                "comment":"Recovered", "nickname":"Tester",
                "messageUuid":"reconnected-1",
            }}).encode("utf-8")
        ))

    monkeypatch.setattr(adapter, "_connect", connect)
    recovered = adapter.poll()
    assert connected
    assert len(recovered.messages) == 1
    assert recovered.messages[0].text == "Recovered"
    adapter.close()
    assert adapter._closed
    with pytest.raises(SourceFailure) as stopped:
        adapter.poll()
    assert stopped.value.fatal
    assert len(connected) == 1, "explicit stop must never reconnect"


def test_tikfinity_tcp_socket_drop_does_not_mark_source_stopped(monkeypatch):
    from voxweavetts.source_adapters import SourceFailure

    class Disconnected:
        def recv(self, _size):
            return b""

        def shutdown(self, how):
            pass

        def close(self):
            pass

    adapter = TikFinityCoreAdapter("ws://localhost:21213")
    adapter._socket = Disconnected()
    with pytest.raises(SourceFailure) as error:
        adapter.poll()
    assert not error.value.fatal
    assert adapter._socket is None
    assert not adapter._closed
    adapter.close()


def test_source_manager_owns_tikfinity_queue_without_browser(tmp_path):
    from voxweavetts.source_adapters import PollResult, SourceMessage
    from collections import deque

    class StubTikFinity:
        transport = "local-websocket"
        def __init__(self, value):
            validate_tikfinity_endpoint(value)
            self.calls = 0
            self.closed = False
            self.cancel = None

        def set_cancel(self, cancel):
            self.cancel = cancel

        def poll(self):
            self.calls += 1
            return PollResult((SourceMessage("msg-01", "Viewer", "hello"),), .15)

        def close(self):
            self.closed = True

    modes = ModeState()
    owned = modes.activate("tiktok", object())
    manager = SourceManager(tikfinity_factory=StubTikFinity)
    payload = {"mode": "tiktok", "mode_token": owned["mode_token"],
               "source_id": "ws://localhost:21213", "credential": "",
               "runtime_auto_read": True}
    manager.start(payload, modes)
    deadline = time.monotonic()+3
    while manager.status("tiktok")["received"] < 1 and time.monotonic() < deadline:
        time.sleep(.03)
    assert manager.status("tiktok")["received"] == 1
    assert manager.status("tiktok")["transport"] == "local-websocket"
    chats = manager.take_for_runtime(limit=5)
    assert chats[0][0] == "tiktok"
    assert chats[0][1]["text"] == "hello"
    manager.stop_mode("tiktok")
    assert manager.status("tiktok")["state"] == "idle"
