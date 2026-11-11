"""Official Discord Desktop local RPC reader scoped to one selected text channel.

Only official consent-based RPC: HANDSHAKE -> AUTHORIZE(rpc,messages.read)
-> OAuth code exchange -> AUTHENTICATE -> SUBSCRIBE(MESSAGE_CREATE,channel_id).
No Discord user token, no self-bot, no browser cache/cookies or private API.
Requires approved Discord app or approved tester plus user consent.
"""
from __future__ import annotations

import ctypes
import json
import re
import struct
import sys
import threading
import time
import uuid
from ctypes import wintypes
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .processing import InputError
from .source_adapters import PollResult, SourceFailure, SourceMessage, _normal_text

CHANNEL_ID = re.compile(r"[0-9]{16,22}\Z")
MAX_FRAME = 65536
HANDSHAKE, FRAME, CLOSE, PING, PONG = 0, 1, 2, 3, 4


def validate_channel_id(value: object) -> str:
    if not isinstance(value, str) or not CHANNEL_ID.fullmatch(value.strip()):
        raise InputError("enter a valid Discord text Channel ID (16–22 digits)")
    return value.strip()


def validate_redirect_uri(value: object) -> str:
    if not isinstance(value, str) or len(value) > 240:
        raise InputError("registered Discord OAuth redirect URI required")
    parsed = urlsplit(value)
    host = parsed.hostname
    if (parsed.username or parsed.password or parsed.fragment or not host
        or (parsed.scheme != "https" and not (
            parsed.scheme == "http" and host in ("localhost", "127.0.0.1", "::1")
        ))):
        raise InputError("redirect URI requires HTTPS or a localhost callback")
    return value


def frame_packet(opcode: int, payload: dict) -> bytes:
    if opcode not in (HANDSHAKE, FRAME, CLOSE, PING, PONG):
        raise InputError("invalid RPC opcode")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_FRAME:
        raise InputError("RPC payload too large")
    return struct.pack("<II", opcode, len(data)) + data


def parse_frame_header(header: bytes) -> tuple[int, int]:
    if len(header) != 8:
        raise SourceFailure("incomplete Discord RPC frame", fatal=True)
    opcode, size = struct.unpack("<II", header)
    if opcode not in (HANDSHAKE, FRAME, CLOSE, PING, PONG) or size > MAX_FRAME:
        raise SourceFailure("invalid Discord RPC frame", fatal=True)
    return opcode, size


def parse_channel_event(frame: dict, selected_channel: str) -> SourceMessage | None:
    """Dispatch for selected channel only; ignore all other rooms, bots and edits."""
    if not isinstance(frame, dict) or frame.get("cmd") != "DISPATCH" or frame.get("evt") != "MESSAGE_CREATE":
        return None
    data = frame.get("data")
    if not isinstance(data, dict) or data.get("channel_id") != selected_channel:
        return None
    message = data.get("message")
    if not isinstance(message, dict) or message.get("blocked") or message.get("webhook_id"):
        return None
    author = message.get("author")
    if not isinstance(author, dict) or author.get("bot"):
        return None
    if message.get("type", 0) not in (0, 19):
        return None
    message_id = message.get("id")
    text = _normal_text(message.get("content"))
    if not isinstance(message_id, str) or not CHANNEL_ID.fullmatch(message_id) or not text:
        return None
    name = _normal_text(author.get("global_name") or author.get("username") or "", 80)
    return SourceMessage(message_id, name, text)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def oauth_exchange(client_id: str, client_secret: str,
                   redirect_uri: str, code: str) -> str:
    """Exchange a code returned by the user-consented official RPC AUTHORIZE."""
    payload = urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": redirect_uri,
    }).encode("utf-8")
    req = Request("https://discord.com/api/oauth2/token", data=payload, method="POST",
                  headers={"Content-Type":"application/x-www-form-urlencoded",
                           "Accept":"application/json"})
    try:
        with build_opener(_NoRedirect()).open(req, timeout=9) as response:
            raw = response.read(8193)
            if len(raw) > 8192:
                raise SourceFailure("Discord OAuth response too large", fatal=True)
            obj = json.loads(raw.decode("utf-8"))
            token = obj.get("access_token") if isinstance(obj, dict) else None
            if not isinstance(token, str) or not 10 <= len(token) <= 2048:
                raise SourceFailure("Discord OAuth authorization failed", fatal=True)
            return token
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise SourceFailure("Discord RPC OAuth denied; verify approved app, redirect and consent",
                            fatal=True) from None


class WindowsDiscordPipe:
    """Official Discord named pipes, with bounded reads and cooperative cancellation."""

    def __init__(self):
        if sys.platform != "win32":
            raise SourceFailure("Discord Desktop RPC currently requires Windows", fatal=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.PeekNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                          ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        kernel.PeekNamedPipe.restype = wintypes.BOOL
        kernel.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        kernel.ReadFile.restype = wintypes.BOOL
        kernel.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                      ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        kernel.WriteFile.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        self._kernel = kernel
        self._handle = None
        invalid = ctypes.c_void_p(-1).value
        for index in range(10):
            name = rf"\\?\pipe\discord-ipc-{index}"
            handle = kernel.CreateFileW(name, 0xC0000000, 3, None, 3, 0, None)
            if handle and handle != invalid:
                self._handle = handle
                break
        if not self._handle:
            raise SourceFailure("Discord Desktop RPC not found; open Discord Desktop",
                                fatal=True)

    def close(self) -> None:
        if self._handle is not None:
            self._kernel.CloseHandle(self._handle)
            self._handle = None

    def write(self, packet: bytes) -> None:
        if not self._handle:
            raise SourceFailure("Discord RPC disconnected", retry_after=5)
        done = wintypes.DWORD()
        buf = ctypes.create_string_buffer(packet)
        if not self._kernel.WriteFile(self._handle, buf, len(packet), ctypes.byref(done), None) or done.value != len(packet):
            raise SourceFailure("Discord RPC write failed", retry_after=5)

    def read_exact(self, length: int, cancel: threading.Event, timeout: float = 20) -> bytes:
        if not 0 <= length <= MAX_FRAME:
            raise SourceFailure("Discord RPC frame too large", fatal=True)
        data = bytearray()
        deadline = time.monotonic() + timeout
        while len(data) < length and not cancel.is_set():
            if not self._handle:
                raise SourceFailure("Discord RPC disconnected", retry_after=5)
            available = wintypes.DWORD()
            if not self._kernel.PeekNamedPipe(self._handle, None, 0, None, ctypes.byref(available), None):
                raise SourceFailure("Discord RPC transport disconnected", retry_after=5)
            count = min(available.value, length-len(data))
            if not count:
                if time.monotonic() >= deadline:
                    raise SourceFailure("Discord RPC response timed out", retry_after=5)
                cancel.wait(.02)
                continue
            buf = ctypes.create_string_buffer(count)
            got = wintypes.DWORD()
            if not self._kernel.ReadFile(self._handle, buf, count, ctypes.byref(got), None) or not got.value:
                raise SourceFailure("Discord RPC read failed", retry_after=5)
            data.extend(buf.raw[:got.value])
        if len(data) != length:
            raise SourceFailure("Discord RPC stopped", retry_after=5)
        return bytes(data)


class DiscordClientRPCAdapter:
    """Subscribe to one explicit channel; message data never comes from other channels."""

    def __init__(self, source_id: str, credentials: object,
                 pipe_factory=WindowsDiscordPipe,
                 exchange=oauth_exchange):
        self.channel_id = validate_channel_id(source_id)
        if not isinstance(credentials, dict):
            raise InputError("Discord RPC needs your approved application credentials")
        client_id = credentials.get("client_id")
        secret = credentials.get("client_secret")
        redirect = credentials.get("redirect_uri")
        if not isinstance(client_id, str) or not CHANNEL_ID.fullmatch(client_id):
            raise InputError("Discord application Client ID required")
        if not isinstance(secret, str) or not 16 <= len(secret) <= 250:
            raise InputError("Discord application Client Secret required")
        if not isinstance(redirect, str):
            raise InputError("Discord application redirect URI required")
        self.client_id = client_id
        self._secret = secret
        self.redirect_uri = validate_redirect_uri(redirect)
        self._pipe_factory = pipe_factory
        self._exchange = exchange
        self._cancel = threading.Event()
        self._pipe: WindowsDiscordPipe | None = None
        self._subscribed = False
        self._connected = False

    def set_cancel(self, cancel: threading.Event) -> None:
        self._cancel = cancel

    def close(self) -> None:
        self._cancel.set()
        self._secret = ""
        if self._pipe:
            self._pipe.close()
            self._pipe = None

    def _read_frame(self, timeout: float = 20) -> tuple[int, dict]:
        if not self._pipe:
            raise SourceFailure("Discord RPC unavailable", retry_after=5)
        opcode, size = parse_frame_header(self._pipe.read_exact(8,self._cancel,timeout))
        raw = self._pipe.read_exact(size,self._cancel,timeout)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise SourceFailure("invalid Discord RPC JSON", fatal=True) from None
        if not isinstance(data, dict):
            raise SourceFailure("invalid Discord RPC frame shape", fatal=True)
        return opcode, data

    def _command(self, cmd: str, args: dict, *, event: str | None = None) -> dict:
        nonce = str(uuid.uuid4())
        obj = {"cmd":cmd,"args":args,"nonce":nonce}
        if event is not None:
            obj["evt"] = event
        self._pipe.write(frame_packet(FRAME,obj))
        deadline=time.monotonic()+35
        while time.monotonic()<deadline and not self._cancel.is_set():
            opcode,payload=self._read_frame(timeout=min(5,max(.2,deadline-time.monotonic())))
            if opcode==PING:
                self._pipe.write(frame_packet(PONG,payload))
                continue
            if opcode==CLOSE:
                raise SourceFailure("Discord RPC closed connection",fatal=True)
            if payload.get("nonce")==nonce:
                if payload.get("evt")=="ERROR" or payload.get("cmd")=="ERROR":
                    raise SourceFailure("Discord RPC command refused; verify app permission and user consent",
                                        fatal=True)
                return payload
        raise SourceFailure("Discord RPC authorization timed out",fatal=True)

    def _connect(self) -> None:
        self._pipe = self._pipe_factory()
        self._pipe.write(frame_packet(HANDSHAKE,{"v":1,"client_id":self.client_id}))
        opcode,response = self._read_frame(timeout=7)
        if opcode!=FRAME or response.get("evt")=="ERROR":
            raise SourceFailure("Discord Desktop rejected RPC handshake",fatal=True)
        auth = self._command("AUTHORIZE",{
            "client_id":self.client_id,"scopes":["rpc","messages.read"],
        })
        code = auth.get("data",{}).get("code")
        if not isinstance(code,str) or not code:
            raise SourceFailure("Discord RPC requires explicit user consent",fatal=True)
        token=self._exchange(self.client_id,self._secret,self.redirect_uri,code)
        authenticated=self._command("AUTHENTICATE",{"access_token":token})
        permissions=authenticated.get("data",{}).get("scopes",[])
        if not isinstance(permissions,list) or not {"rpc","messages.read"}.issubset(permissions):
            raise SourceFailure("Discord RPC missing messages.read permission",fatal=True)
        # Explicitly limit the subscription to the selected room.
        self._command("SUBSCRIBE",{"channel_id":self.channel_id},
                      event="MESSAGE_CREATE")
        self._subscribed=True
        self._connected=True
        self._secret=""  # no longer needed after consent/token exchange

    def poll(self) -> PollResult:
        if not self._connected:
            try:
                self._connect()
            except Exception:
                self.close()
                raise
            return PollResult((), .25)
        try:
            opcode,payload = self._read_frame(timeout=1.5)
        except SourceFailure as exc:
            if "timed out" in str(exc):
                return PollResult((), .25)
            raise
        if opcode==PING:
            self._pipe.write(frame_packet(PONG,payload))
            return PollResult((),.25)
        if opcode==CLOSE:
            raise SourceFailure("Discord Desktop RPC closed",retry_after=5)
        found = parse_channel_event(payload,self.channel_id) if opcode==FRAME else None
        return PollResult((found,) if found else (), .25)