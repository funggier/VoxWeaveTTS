"""TikFinity Desktop localhost WebSocket source owned by the Core process.

No third-party dependencies, TikTok login, browser DOM or remote hosts.
Only ws://127.0.0.1:21213 and ws://localhost:21213 are accepted.
WebSocket client frames are masked; incoming JSON remains untrusted data.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import socket
import struct
import threading
import time

from .processing import InputError
from .source_adapters import PollResult, SourceFailure, SourceMessage, _normal_text

MAX_WS_PAYLOAD = 256_000
MAX_WS_BUFFER = 512_000
_MESSAGE_ID = re.compile(r"[A-Za-z0-9_.:\-]{1,160}\Z")


def validate_tikfinity_endpoint(value: object) -> str:
    if not isinstance(value, str):
        raise InputError("TikFinity endpoint must be a local WebSocket URL")
    raw = value.strip().rstrip("/")
    if raw not in ("ws://127.0.0.1:21213", "ws://localhost:21213"):
        raise InputError("only localhost:21213 TikFinity WebSocket is allowed")
    return "ws://127.0.0.1:21213/"


def parse_tikfinity_chat(value: object, fallback_id: str) -> SourceMessage | None:
    if not isinstance(value, dict) or value.get("event") != "chat":
        return None
    data = value.get("data")
    if not isinstance(data, dict):
        return None
    text = _normal_text(data.get("comment"))
    if not text:
        return None
    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    name = next(
        (raw for raw in (
            data.get("nickname"), user.get("nickname"),
            data.get("uniqueId"), user.get("uniqueId"),
        ) if isinstance(raw, str) and raw.strip()), ""
    )
    author = _normal_text(name, 80)
    raw_id = next((value for value in (
        data.get("messageUuid"), data.get("msgId"), data.get("id"))
        if (isinstance(value, (str, int)) and not isinstance(value, bool)
            and _MESSAGE_ID.fullmatch(str(value)))), fallback_id)
    level = user.get("level", data.get("level"))
    rank = user.get("topGifterRank", data.get("topGifterRank"))
    level_str = str(level) if type(level) in (str, int) and str(level).isdigit() and len(str(level)) <= 4 else ""
    rank_str = str(rank) if type(rank) in (str, int) and str(rank).isdigit() and 0 < int(rank) < 10000 else ""
    raw_badges = user.get("badges")
    badges: list[str] = []
    if isinstance(raw_badges, list):
        for item in raw_badges[:8]:
            badge = item if isinstance(item, str) else (
                item.get("name") or item.get("label") or ""
                if isinstance(item, dict) else ""
            )
            if isinstance(badge, str) and 0 < len(badge) <= 48:
                badges.append(badge)
    return SourceMessage(
        message_id=str(raw_id), author=author, text=text,
        level=level_str, rank=rank_str, badges=tuple(badges),
    )


class TikFinityCoreAdapter:
    transport = "local-websocket"

    def __init__(self, endpoint: object):
        self.endpoint = validate_tikfinity_endpoint(endpoint)
        self._socket: socket.socket | None = None
        self._buffer = bytearray()
        self._fragment = bytearray()
        self._fragmenting = False
        self._cancel = threading.Event()
        self._seq = 0
        self._lock = threading.Lock()
        self._session = os.urandom(5).hex()
        self._closed = False

    def set_cancel(self, event: threading.Event) -> None:
        self._cancel = event

    def close(self) -> None:
        """User-requested stop: permanently disable reconnect for this adapter."""
        with self._lock:
            self._closed = True
        self._drop_connection()

    def _drop_connection(self) -> None:
        """Temporary TCP/WS disconnect: reconnect remains allowed if running."""
        with self._lock:
            sock, self._socket = self._socket, None
            self._buffer.clear()
            self._fragment.clear()
            self._fragmenting = False
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def _connect(self) -> None:
        if self._cancel.is_set() or self._closed:
            raise SourceFailure("TikFinity source stopped", fatal=True)
        try:
            conn = socket.create_connection(("127.0.0.1", 21213), timeout=2)
            conn.settimeout(0.5)
            key = base64.b64encode(os.urandom(16)).decode("ascii")
            req = (
                "GET / HTTP/1.1\r\n"
                "Host: 127.0.0.1:21213\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                f"Sec-WebSocket-Key: {key}\r\n\r\n"
            )
            conn.sendall(req.encode("ascii"))
            response = bytearray()
            while b"\r\n\r\n" not in response:
                if len(response) > 8192:
                    raise OSError("oversized TikFinity handshake")
                piece = conn.recv(4096)
                if not piece:
                    raise OSError("TikFinity disconnected during handshake")
                response.extend(piece)
            head, extra = bytes(response).split(b"\r\n\r\n", 1)
            lines = head.split(b"\r\n")
            if not lines or b" 101 " not in lines[0] + b" ":
                raise OSError("TikFinity WebSocket refused upgrade")
            headers = {}
            for line in lines[1:]:
                if b":" in line:
                    name, value = line.split(b":", 1)
                    headers[name.lower().strip()] = value.strip()
            expected = base64.b64encode(hashlib.sha1(
                (key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest())
            if (headers.get(b"sec-websocket-accept") != expected
                or headers.get(b"upgrade", b"").lower() != b"websocket"):
                raise OSError("TikFinity WebSocket handshake invalid")
            with self._lock:
                if self._closed or self._cancel.is_set():
                    conn.close()
                    raise SourceFailure("TikFinity source stopped", fatal=True)
                self._socket = conn
                self._buffer = bytearray(extra)
                self._fragment.clear()
                self._fragmenting = False
        except (OSError, TimeoutError) as exc:
            try:
                conn.close()
            except (UnboundLocalError, OSError):
                pass
            raise SourceFailure(
                "TikFinity Desktop is not reachable on local port 21213",
                retry_after=5
            ) from None

    def _send_frame(self, opcode: int, data: bytes = b"") -> None:
        if len(data) > 125:
            raise ValueError("control frame too large")
        mask = os.urandom(4)
        body = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
        frame = bytes((0x80 | opcode, 0x80 | len(data))) + mask + body
        with self._lock:
            if not self._closed and self._socket:
                self._socket.sendall(frame)

    def _next_frame(self) -> tuple[bool, int, bytes] | None:
        b = self._buffer
        if len(b) < 2:
            return None
        fin, opcode = bool(b[0] & 0x80), b[0] & 0x0F
        if b[0] & 0x70:
            raise SourceFailure("unsupported TikFinity WebSocket flags", fatal=True)
        if b[1] & 0x80:
            raise SourceFailure("TikFinity server sent masked data", fatal=True)
        size = b[1] & 0x7F
        off = 2
        if size == 126:
            if len(b) < 4:
                return None
            size = struct.unpack("!H", b[2:4])[0]
            off = 4
        elif size == 127:
            if len(b) < 10:
                return None
            size = struct.unpack("!Q", b[2:10])[0]
            off = 10
        if size > MAX_WS_PAYLOAD:
            raise SourceFailure("TikFinity frame is too large", fatal=True)
        if len(b) < off + size:
            return None
        payload = bytes(b[off:off+size])
        del b[:off+size]
        return fin, opcode, payload

    def _decode_frame(self, frame: tuple[bool, int, bytes]) -> SourceMessage | None:
        fin, opcode, payload = frame
        if opcode == 0x8:
            self._drop_connection()
            raise SourceFailure("TikFinity Desktop disconnected", retry_after=5)
        if opcode == 0x9:
            self._send_frame(0xA, payload)
            return None
        if opcode == 0xA:
            return None
        if opcode == 0x1:
            self._fragment.clear()
            self._fragmenting = not fin
            self._fragment.extend(payload)
        elif opcode == 0x0 and self._fragmenting:
            self._fragment.extend(payload)
        else:
            return None
        if len(self._fragment) > MAX_WS_PAYLOAD:
            raise SourceFailure("TikFinity message too large", fatal=True)
        if not fin:
            return None
        self._fragmenting = False
        try:
            data = json.loads(self._fragment.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        self._fragment.clear()
        self._seq += 1
        return parse_tikfinity_chat(data, f"tiktok-{self._session}-{self._seq}")

    def poll(self) -> PollResult:
        if self._closed or self._cancel.is_set():
            raise SourceFailure("TikFinity source stopped", fatal=True)
        if not self._socket:
            self._connect()
        messages = []
        deadline = time.monotonic() + 0.5
        while len(messages) < 10 and not self._cancel.is_set():
            while True:
                frame = self._next_frame()
                if frame is None:
                    break
                item = self._decode_frame(frame)
                if item:
                    messages.append(item)
                if len(messages) >= 10:
                    break
            if len(messages) >= 10 or time.monotonic() >= deadline:
                break
            try:
                data = self._socket.recv(8192) if self._socket else b""
                if not data:
                    self._drop_connection()
                    raise SourceFailure("TikFinity Desktop disconnected", retry_after=5)
                self._buffer.extend(data)
                if len(self._buffer) > MAX_WS_BUFFER:
                    raise SourceFailure("TikFinity socket buffer limit", fatal=True)
            except socket.timeout:
                break
            except OSError:
                self._drop_connection()
                if self._closed or self._cancel.is_set():
                    raise SourceFailure("TikFinity source stopped", fatal=True) from None
                raise SourceFailure("TikFinity Desktop disconnected", retry_after=5) from None
        return PollResult(tuple(messages), 0.15)
