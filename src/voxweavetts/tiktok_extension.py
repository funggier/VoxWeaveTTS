"""Opt-in, user-installed TikTok LIVE extension bridge.

No browser automation, TikTok login, cookies, or third-party API calls.
An explicitly paired browser extension sends visible comments over loopback.
The bridge is ephemeral and bound to an app source session + extension ID.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import re
import secrets
import threading
import time

from .processing import InputError
from .source_adapters import PollResult, SourceMessage
from .tiktok_live_url import username_from_input

EXTENSION_ID = re.compile(r"^[a-p]{32}$")
MESSAGE_ID = re.compile(r"^[A-Za-z0-9_.:\-]{1,160}$")
PAIR_WINDOW = 300.0
# Chrome may throttle hidden-tab timers to about one callback per minute.
# A 15-second timeout incorrectly reported a live, paired extension as lost.
HEARTBEAT_WINDOW = 90.0
DIAGNOSTIC_FIELDS = frozenset(("list_found", "row_candidates", "parsed_rows",
                              "fresh_rows", "author_nodes", "tab_visible",
                              "tab_focused", "chat_change_age_seconds"))
DIAGNOSTIC_BOOL_FIELDS = frozenset(("list_found", "tab_visible", "tab_focused"))


def extension_id_from_origin(value: str | None) -> str | None:
    if not isinstance(value, str) or not value.startswith("chrome-extension://"):
        return None
    extension_id = value[len("chrome-extension://"):]
    return extension_id if EXTENSION_ID.fullmatch(extension_id) else None


class ExtensionBridgeError(InputError):
    """Invalid/expired pairing, sender, or payload; no secret details echoed."""


class TikTokExtensionAdapter:
    transport = "extension"
    def __init__(self, source_id: str):
        self.username = username_from_input(source_id)
        self.phase = "waiting_extension_pair"
        self.dom_ready = False
        self._pairing_code: str | None = secrets.token_urlsafe(24)
        self._pair_created = time.monotonic()
        self._secret: str | None = None
        self._extension_id: str | None = None
        self._last_seen = 0.0
        self._pending: deque[SourceMessage] = deque(maxlen=150)
        self.diagnostics: dict[str, object] | None = None
        self._lock = threading.RLock()
        self._closed = False

    @property
    def pairing_code(self) -> str:
        # This is emitted only in the authenticated /sources/start reply,
        # never in /sources/status or /sources/drain.
        with self._lock:
            return self._pairing_code or ""

    def set_cancel(self, event) -> None:
        self._cancel = event

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self.phase = "stopped"
            self._pending.clear()
            self.diagnostics = None
            self._secret = None
            self._pairing_code = None
            self._extension_id = None

    def pair(self, code: object, extension_id: str, url: object) -> str:
        if not isinstance(code, str) or not isinstance(url, str):
            raise ExtensionBridgeError("invalid or expired pairing code")
        try:
            username = username_from_input(url)
        except InputError:
            raise ExtensionBridgeError("extension tab must be a TikTok LIVE URL") from None
        with self._lock:
            if (self._closed or not self._pairing_code
                or time.monotonic() - self._pair_created > PAIR_WINDOW
                or not secrets.compare_digest(self._pairing_code, code)):
                raise ExtensionBridgeError("invalid or expired pairing code")
            if username.casefold() != self.username.casefold():
                raise ExtensionBridgeError("the selected LIVE tab does not match VoxWeaveTTS")
            self._pairing_code = None
            self._extension_id = extension_id
            self._secret = secrets.token_urlsafe(32)
            self._last_seen = time.monotonic()
            self.phase = "waiting_chat_dom"
            self.dom_ready = False
            return self._secret

    def receive(self, *, extension_id: str, token: object, url: object,
                phase: object, items: object,
                diagnostics: object = None) -> int:
        if not isinstance(token, str) or not isinstance(url, str):
            raise ExtensionBridgeError("invalid extension connection")
        if not isinstance(items, list) or len(items) > 20:
            raise ExtensionBridgeError("extension batch must contain at most 20 events")
        if diagnostics is not None:
            if (not isinstance(diagnostics, dict)
                or set(diagnostics) != DIAGNOSTIC_FIELDS
                or any(type(diagnostics[key]) is not bool
                       for key in DIAGNOSTIC_BOOL_FIELDS)
                or any(type(diagnostics[key]) is not int
                       or not 0 <= diagnostics[key] <=
                       (86400 if key == "chat_change_age_seconds" else 10000)
                       for key in DIAGNOSTIC_FIELDS - DIAGNOSTIC_BOOL_FIELDS)):
                raise ExtensionBridgeError("invalid DOM diagnostic counts")
        if phase not in ("ready", "waiting_chat_dom", "comments_off"):
            raise ExtensionBridgeError("unsupported extension chat state")
        try:
            username = username_from_input(url)
        except InputError:
            raise ExtensionBridgeError("extension tab URL is not a TikTok LIVE") from None
        with self._lock:
            if (self._closed or not self._secret
                or extension_id != self._extension_id
                or not secrets.compare_digest(self._secret, token)
                or username.casefold() != self.username.casefold()):
                raise ExtensionBridgeError("extension connection is not authorized")
            batch: list[SourceMessage] = []
            for item in items:
                basic = {"id", "author", "text"}
                optional = {"kind", "level", "rank", "badges", "gift_name", "gift_count"}
                if (not isinstance(item, dict) or not basic <= set(item)
                    or set(item) - basic - optional):
                    raise ExtensionBridgeError("invalid LIVE event structure")
                mid, author, body = item["id"], item["author"], item["text"]
                kind = item.get("kind", "comment")
                level, rank = item.get("level", ""), item.get("rank", "")
                badges = item.get("badges", [])
                gift_name, gift_count = item.get("gift_name", ""), item.get("gift_count", 0)
                if (not isinstance(mid, str) or not MESSAGE_ID.fullmatch(mid)
                    or not isinstance(author, str) or len(author) > 80
                    or not isinstance(body, str) or not 1 <= len(body) <= 280
                    or any(ord(c) < 32 and c not in "\t" for c in body)
                    or kind not in ("comment", "gift")
                    or any(not isinstance(x, str) or len(x)>48 or
                           any(ord(ch)<32 for ch in x) for x in (level, rank, gift_name))
                    or not isinstance(badges, list) or len(badges) > 8
                    or any(not isinstance(b, str) or len(b)>48 for b in badges)
                    or type(gift_count) is not int or not 0 <= gift_count <= 99999):
                    raise ExtensionBridgeError("invalid LIVE event fields")
                if kind == "gift" and (not gift_name or gift_count < 1):
                    raise ExtensionBridgeError("gift event requires verified gift name and count")
                if kind == "comment" and (gift_name or gift_count):
                    raise ExtensionBridgeError("comment must not contain gift data")
                if kind == "gift":
                    # Backward compatibility: older installed extensions can
                    # still send gifts, but they are no longer queued or spoken.
                    continue
                batch.append(SourceMessage(
                    mid, author.strip(), body.strip(), kind=kind, level=level.strip(),
                    rank=rank.strip(), badges=tuple(x.strip() for x in badges if x.strip()),
                    gift_name=gift_name.strip(), gift_count=gift_count,
                ))
            if phase != "ready" and batch:
                raise ExtensionBridgeError("events require ready DOM state")
            self._last_seen = time.monotonic()
            self.phase = phase
            self.dom_ready = phase == "ready"
            self.diagnostics = dict(diagnostics) if diagnostics is not None else None
            self._pending.extend(batch)
            return len(batch)

    def poll(self) -> PollResult:
        with self._lock:
            if self._closed:
                return PollResult((), 2, online=False)
            if self._secret and time.monotonic() - self._last_seen > HEARTBEAT_WINDOW:
                self.dom_ready = False
                self.phase = "extension_disconnected"
                self.diagnostics = None
            batch = tuple(self._pending)
            self._pending.clear()
            return PollResult(batch, 1.0)

    def disconnect(self, *, extension_id: str, token: object) -> None:
        with self._lock:
            if (self._secret and isinstance(token, str)
                and secrets.compare_digest(self._secret, token)
                and extension_id == self._extension_id):
                self._secret = None
                self._extension_id = None
                self.dom_ready = False
                self.phase = "extension_disconnected"
                self.diagnostics = None
                self._pending.clear()
