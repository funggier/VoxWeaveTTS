"""Experimental chat-only browser DOM adapter (no YouTube Data API).

Launches an isolated Chromium app window and reads only visible chat messages
through the local Chrome DevTools Protocol. This is not an official YouTube
integration. No login cookies, profile data or CDP endpoint leave the PC.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from .processing import InputError
from .source_adapters import PollResult, SourceFailure, SourceMessage, _normal_text

ROOT = Path(__file__).resolve().parents[2]
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
CHAT_SCRIPT = r"""(() => {
  const list = document.querySelector("yt-live-chat-item-list-renderer #items");
  if (!list) return {ready:false, items:[]};
  const items = [...list.querySelectorAll("yt-live-chat-text-message-renderer")].slice(-100);
  return {ready:true, items: items.map(node => {
    let id = node.id || node.getAttribute("data-id") || node.getAttribute("data-vwtts-id");
    if (!id) {
      window.__vwttsChatSequence = (window.__vwttsChatSequence || 0) + 1;
      window.__vwttsPageId = window.__vwttsPageId || (Date.now() + "-" + Math.random().toString(36).slice(2));
      id = "browser-" + window.__vwttsPageId + "-" + window.__vwttsChatSequence;
      node.setAttribute("data-vwtts-id", id);
    }
    return {id, author:node.querySelector("#author-name")?.textContent || "",
            text:node.querySelector("#message")?.textContent || ""};
  })};
})()"""


def video_id_from_input(source: object) -> str:
    """Accept only public YouTube video IDs or watch/live/popout URLs."""
    if not isinstance(source, str) or len(source) > 600:
        raise InputError("YouTube video ID or URL required")
    candidate = source.strip()
    if VIDEO_ID.fullmatch(candidate):
        return candidate
    try:
        u = urlsplit(candidate)
    except ValueError:
        raise InputError("invalid YouTube video URL") from None
    if u.scheme != "https" or u.username or u.password or u.port:
        raise InputError("use a YouTube https video URL")
    host = (u.hostname or "").lower()
    if host in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if u.path in ("/watch", "/live_chat"):
            candidate = parse_qs(u.query).get("v", [""])[0]
        elif u.path.startswith(("/live/", "/shorts/")):
            candidate = u.path.split("/")[2]
    elif host == "youtu.be" and u.path.count("/") == 1:
        candidate = u.path[1:]
    if not VIDEO_ID.fullmatch(candidate):
        raise InputError("a valid YouTube video ID is required")
    return candidate


def find_chromium() -> str:
    # Chrome first; never automate the user's normal Firefox profile.
    for name in ("chrome", "msedge", "chromium"):
        path = shutil.which(name)
        if path:
            return path
    if sys.platform == "win32":
        for folder, executable in (
            (os.environ.get("PROGRAMFILES", ""), r"Google\Chrome\Application\chrome.exe"),
            (os.environ.get("PROGRAMFILES(X86)", ""), r"Google\Chrome\Application\chrome.exe"),
            (os.environ.get("PROGRAMFILES(X86)", ""), r"Microsoft\Edge\Application\msedge.exe"),
            (os.environ.get("PROGRAMFILES", ""), r"Microsoft\Edge\Application\msedge.exe"),
        ):
            if folder and (Path(folder) / executable).is_file():
                return str(Path(folder) / executable)
    raise SourceFailure("Chrome or Edge is required for Browser DOM mode", fatal=True)


class _CDPWebSocket:
    """Small RFC6455 client for local CDP, without third-party dependencies."""
    def __init__(self, address: str):
        u = urlsplit(address)
        if u.scheme != "ws" or u.hostname != "127.0.0.1" or not u.port:
            raise SourceFailure("unsafe browser debugging endpoint", fatal=True)
        sock = socket.create_connection(("127.0.0.1", u.port), timeout=5)
        sock.settimeout(5)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = u.path or "/"
        if u.query:
            path += "?" + u.query
        request = (
            f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{u.port}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        try:
            sock.sendall(request)
            reply = bytearray()
            while b"\r\n\r\n" not in reply and len(reply) < 8192:
                reply.extend(sock.recv(1024))
            expected = base64.b64encode(hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest())
            header = bytes(reply).split(b"\r\n\r\n", 1)[0]
            if (not header.startswith(b"HTTP/1.1 101") or
                b"sec-websocket-accept: " + expected.lower() not in header.lower()):
                raise OSError("CDP handshake rejected")
        except Exception:
            sock.close()
            raise
        self.sock = sock

    def close(self) -> None:
        self.sock.close()

    def _read(self, size: int) -> bytes:
        chunks = []
        while size:
            part = self.sock.recv(size)
            if not part:
                raise OSError("CDP browser socket closed")
            chunks.append(part)
            size -= len(part)
        return b"".join(chunks)

    def send(self, payload: bytes, *, opcode: int = 1) -> None:
        # Client-to-server frames MUST be masked.
        count = len(payload)
        header = bytearray([0x80 | opcode])
        if count < 126:
            header.append(0x80 | count)
        elif count < 65536:
            header.extend([0x80 | 126])
            header.extend(struct.pack("!H", count))
        else:
            header.extend([0x80 | 127])
            header.extend(struct.pack("!Q", count))
        mask = os.urandom(4)
        self.sock.sendall(bytes(header) + mask + bytes(
            b ^ mask[i % 4] for i, b in enumerate(payload)
        ))

    def receive(self) -> bytes:
        payload = bytearray()
        while True:
            a, b = self._read(2)
            opcode = a & 0x0f
            size = b & 0x7f
            if size == 126:
                size = struct.unpack("!H", self._read(2))[0]
            elif size == 127:
                size = struct.unpack("!Q", self._read(8))[0]
            if size > 1_000_000:
                raise OSError("oversized CDP frame")
            mask = self._read(4) if b & 0x80 else None
            data = self._read(size)
            if mask:
                data = bytes(v ^ mask[i % 4] for i, v in enumerate(data))
            if opcode == 9:
                self.send(data, opcode=10)
                continue
            if opcode == 8:
                raise OSError("CDP browser disconnected")
            if opcode not in (0, 1, 2):
                continue
            payload.extend(data)
            if a & 0x80:
                return bytes(payload)


class YouTubeBrowserAdapter:
    """Optional explicit-connect DOM reader; never pulls existing chat history."""

    transport = "browser-dom"
    chat_script = CHAT_SCRIPT
    profile_name = "youtube-chat"
    page_label = "YouTube"

    @staticmethod
    def parse_source(source: str) -> str:
        return video_id_from_input(source)

    @staticmethod
    def build_chat_url(identifier: str) -> str:
        return f"https://www.youtube.com/live_chat?is_popout=1&v={identifier}"

    def target_matches(self, target: dict) -> bool:
        u = urlsplit(target.get("url", ""))
        return (target.get("type") == "page"
                and u.scheme == "https" and u.hostname in ("www.youtube.com", "youtube.com")
                and u.path == "/live_chat"
                and parse_qs(u.query).get("v") == [self.video_id])

    def __init__(self, source_id: str):
        self.video_id = self.parse_source(source_id)
        self._process: subprocess.Popen | None = None
        self._port: int | None = None
        self._ws: _CDPWebSocket | None = None
        self._initialized = False
        self.dom_ready = False
        self.phase = "preparing"
        self._seen: set[str] = set()
        self._closed = False

    def set_cancel(self, event) -> None:
        self._cancel = event

    def close(self) -> None:
        self._closed = True
        self.phase = "stopped"
        if self._ws:
            self._ws.close()
            self._ws = None
        if self._process:
            try:
                if self._process.poll() is None:
                    if os.name == "nt":
                        # The isolated Chromium app may have child helper processes.
                        subprocess.run(
                            ["taskkill", "/PID", str(self._process.pid), "/T", "/F"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=5,
                        )
                    if self._process.poll() is None:
                        self._process.terminate()
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self._process.terminate()
                except OSError:
                    pass
            self._process = None

    def _launch(self) -> None:
        profile = ROOT / "data" / "browser-profiles" / self.profile_name
        profile.mkdir(parents=True, exist_ok=True)
        portfile = profile / "DevToolsActivePort"
        # Stale file after a crashed browser is not a valid endpoint.
        portfile.unlink(missing_ok=True)
        self.phase = "locating_browser"
        browser = find_chromium()
        self.phase = "starting_browser"
        url = self.build_chat_url(self.video_id)
        args = [
            browser, "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0", f"--user-data-dir={profile}",
            "--no-first-run", "--no-default-browser-check", f"--app={url}",
        ]
        try:
            self._process = subprocess.Popen(
                args, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.phase = "waiting_debugger"
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if self._closed or getattr(self, "_cancel", None) and self._cancel.is_set():
                    return
                if self._process.poll() is not None:
                    break
                if portfile.is_file():
                    rows = portfile.read_text(encoding="ascii").splitlines()
                    if rows and rows[0].isdigit():
                        self._port = int(rows[0])
                        self.phase = "finding_chat_page"
                        return
                time.sleep(0.2)
        except OSError:
            pass
        raise SourceFailure(f"could not open {self.page_label} browser window", fatal=True)

    def _connect(self) -> None:
        if self._port is None:
            self._launch()
        if self._closed:
            return
        self.phase = "finding_chat_page"
        try:
            with urlopen(f"http://127.0.0.1:{self._port}/json/list", timeout=5) as r:
                targets = json.load(r)
            target = next((t for t in targets if self.target_matches(t)), None)
            if not target:
                raise SourceFailure(f"{self.page_label} LIVE page is closed or still loading",
                                    fatal=self._initialized, retry_after=3)
            self.phase = "connecting_dom"
            self._ws = _CDPWebSocket(target["webSocketDebuggerUrl"])
        except SourceFailure:
            raise
        except (OSError, ValueError, KeyError):
            raise SourceFailure("browser DOM connection unavailable; reconnect later",
                                retry_after=5) from None

    def _evaluate(self) -> dict:
        self._ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": self.chat_script, "returnByValue": True}
        }).encode("utf-8"))
        for _ in range(20):
            response = json.loads(self._ws.receive().decode("utf-8"))
            if response.get("id") == 1:
                return response.get("result", {}).get("result", {}).get("value", {})
        raise OSError("CDP evaluation timeout")

    def poll(self) -> PollResult:
        if self._closed:
            return PollResult((), 2.0, online=False)
        if self._ws is None:
            self._connect()
        if self._closed:
            return PollResult((), 2.0, online=False)
        try:
            self.phase = "reading_dom"
            result = self._evaluate()
            if isinstance(result, dict) and result.get("status") == "login_rate_limited":
                self.dom_ready = False
                self.phase = "login_rate_limited"
                raise SourceFailure(
                    "TikTok login attempts are temporarily limited by the platform. "
                    "Stop trying to log in or reconnect; use the existing "
                    "TikTok LIVE (TikFinity) connector if available.",
                    fatal=True,
                )
            if not isinstance(result, dict) or not result.get("ready"):
                self.dom_ready = False
                status = result.get("status") if isinstance(result, dict) else None
                self.phase = (status if status in (
                    "comments_off", "comments_off_login_prompt", "login_prompt")
                    else "waiting_chat_dom")
                return PollResult((), 2.0)
            self.dom_ready = True
            self.phase = "ready"
            rows = result.get("items", [])
            if not isinstance(rows, list):
                raise ValueError("invalid chat DOM")
            parsed = []
            for row in rows[-100:]:
                if not isinstance(row, dict):
                    continue
                mid, author, msg = row.get("id"), row.get("author"), row.get("text")
                if not isinstance(mid, str) or not mid or len(mid) > 200:
                    continue
                if mid in self._seen:
                    continue
                self._seen.add(mid)
                text = _normal_text(msg)
                if text and self._initialized:
                    parsed.append(SourceMessage(mid, _normal_text(author, 80), text))
            self._initialized = True
            if len(self._seen) > 2000:
                # IDs may be reused by the remote DOM only after a reload.
                self._seen = {row.get("id") for row in rows if isinstance(row, dict)
                              and isinstance(row.get("id"), str)}
            return PollResult(tuple(parsed), 1.5)
        except (OSError, ValueError, KeyError, TimeoutError):
            self._ws.close()
            self._ws = None
            self.phase = "retrying"
            raise SourceFailure("browser chat DOM unavailable; reconnecting",
                                retry_after=5) from None
