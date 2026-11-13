"""Independent bounded opt-in YouTube/Discord source monitors per workspace.

Credentials never leave this manager through status, logs or exceptions.
Backend polling is read-only. Browser playback (with a real HTMLMediaElement)
remains the sole authority for the unified OBS subtitle clock.
"""
from __future__ import annotations

import os
import re
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from .mode_state import ModeConflict, ModeState
from .processing import InputError
from .discord_client_rpc import DiscordClientRPCAdapter
from .youtube_browser import YouTubeBrowserAdapter
from .tiktok_browser import TikTokBrowserAdapter
from .source_adapters import (
    DiscordChannelAdapter, PollResult, SourceFailure, SourceMessage,
    YouTubeLiveAdapter,
)

MAX_PENDING = 40
MAX_SEEN = 512
MAX_BLOCKED_WORDS = 20
MAX_TEXT_CHARS = 280
URL_PATTERN = re.compile(r"https?://|www\.|discord\.gg/", re.IGNORECASE)


@dataclass
class _Session:
    mode: str
    owner_token: str
    source_id: str
    adapter: Any
    block_words: tuple[str, ...]
    max_chars: int
    pending: deque[SourceMessage] = field(default_factory=lambda: deque(maxlen=MAX_PENDING))
    ids: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_SEEN))
    seen: set[str] = field(default_factory=set)
    cancelled: threading.Event = field(default_factory=threading.Event)
    state: str = "connecting"
    info: str = "connecting to source"
    received: int = 0
    discarded: int = 0
    duplicates: int = 0
    polls: int = 0
    next_poll_seconds: float = 0
    thread: threading.Thread | None = None

    def public(self) -> dict[str, Any]:
        return {
            "mode": self.mode, "source_id": self.source_id,
            "state": self.state, "info": self.info,
            "pending": len(self.pending),
            "received": self.received,
            "discarded": self.discarded,
            "duplicates": self.duplicates,
            "polls": self.polls,
            "next_poll_seconds": self.next_poll_seconds,
            "temporary_credentials": True,
            **({"transport": self.adapter.transport}
               if self.mode in ("live", "youtube_browser", "tiktok_browser") and getattr(self.adapter, "transport", None)
               in ("streamList", "polling", "browser-dom") else {}),
            **({"connection_phase": self.adapter.phase}
               if self.mode in ("discord_client", "youtube_browser", "tiktok_browser")
               and isinstance(getattr(self.adapter, "phase", None), str)
               else {}),
            **({"failed_phase": self.adapter.failed_phase}
               if self.mode == "discord_client" and self.state == "error"
               and isinstance(getattr(self.adapter, "failed_phase", None), str)
               else {}),
        }


class SourceManager:
    def __init__(self, *,
                 youtube_factory: Callable[..., Any] = YouTubeLiveAdapter,
                 discord_factory: Callable[..., Any] = DiscordChannelAdapter,
                 client_factory: Callable[..., Any] = DiscordClientRPCAdapter,
                 browser_factory: Callable[..., Any] = YouTubeBrowserAdapter,
                 tiktok_browser_factory: Callable[..., Any] = TikTokBrowserAdapter):
        self._lock = threading.RLock()
        self._sessions: dict[str, _Session] = {}
        self._youtube_factory = youtube_factory
        self._discord_factory = discord_factory
        self._client_factory = client_factory
        self._browser_factory = browser_factory
        self._tiktok_browser_factory = tiktok_browser_factory

    @staticmethod
    def _validate_policy(value: object) -> tuple[tuple[str, ...], int]:
        if value is None:
            return (), 240
        if not isinstance(value, dict) or set(value) - {"blocked_words", "max_chars"}:
            raise InputError("invalid live message filter options")
        words = value.get("blocked_words", [])
        if not isinstance(words, list) or len(words) > MAX_BLOCKED_WORDS:
            raise InputError("blocked_words must be a short list")
        sanitized = []
        for entry in words:
            if (not isinstance(entry, str) or not 1 <= len(entry.strip()) <= 40
                or any(c in entry for c in "\r\n")):
                raise InputError("invalid blocked word")
            sanitized.append(entry.strip().casefold())
        limit = value.get("max_chars", 240)
        if type(limit) is not int or not 20 <= limit <= MAX_TEXT_CHARS:
            raise InputError("max_chars must be 20..280")
        return tuple(sanitized), limit

    @staticmethod
    def _allowed(message: SourceMessage, session: _Session) -> bool:
        text = message.text
        if not 1 <= len(text) <= session.max_chars:
            return False
        if URL_PATTERN.search(text) or "@everyone" in text.lower() or "@here" in text.lower():
            return False
        if text.startswith(("!", "/")):
            return False
        folded = text.casefold()
        return not any(blocked in folded for blocked in session.block_words)

    def _authorized(self, mode: Any, token: Any, mode_state: ModeState) -> None:
        if mode not in ("live", "youtube_browser", "tiktok_browser", "discord", "discord_client") or not mode_state.is_owner(mode, token):
            raise ModeConflict("source monitor requires the active mode owner token")

    def start(self, data: dict[str, Any], mode_state: ModeState) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise InputError("source request must be an object")
        mode, token = data.get("mode"), data.get("mode_token")
        self._authorized(mode, token, mode_state)
        source_id = data.get("source_id")
        secret = data.get("credential")
        if mode not in ("discord_client", "youtube_browser", "tiktok_browser") and (secret is None or secret == ""):
            variable = ("VOXWEAVE_YOUTUBE_API_KEY" if mode == "live"
                        else "VOXWEAVE_DISCORD_BOT_TOKEN")
            secret = os.environ.get(variable, "")
        blocked, max_chars = self._validate_policy(data.get("filters"))
        if mode == "live":
            adapter = self._youtube_factory(source_id, secret)
        elif mode == "youtube_browser":
            adapter = self._browser_factory(source_id)
        elif mode == "tiktok_browser":
            adapter = self._tiktok_browser_factory(source_id)
        elif mode == "discord":
            adapter = self._discord_factory(source_id, secret)
        else:
            adapter = self._client_factory(source_id, secret)
        session = _Session(
            mode, token, source_id.strip(), adapter, blocked, max_chars,
        )
        if hasattr(adapter, "set_cancel"):
            adapter.set_cancel(session.cancelled)
        with self._lock:
            # Reconnecting one channel never interrupts the other providers.
            self._authorized(mode, token, mode_state)
            self._cancel_unlocked(mode)
            self._sessions[mode] = session
            thread = threading.Thread(
                target=self._run, args=(session, mode_state),
                name="VoxWeaveTTS-"+mode+"-source", daemon=True,
            )
            session.thread = thread
            thread.start()
            return session.public()

    def _cancel_unlocked(self, mode: str | None = None) -> None:
        targets = (list(self._sessions) if mode is None else [mode])
        for target in targets:
            session = self._sessions.pop(target, None)
            if session is None:
                continue
            session.cancelled.set()
            if hasattr(session.adapter, "close"):
                try:
                    session.adapter.close()
                except OSError:
                    pass
            session.pending.clear()

    def stop_mode(self, mode: str) -> None:
        """Revoke only the source belonging to a newly claimed workspace."""
        with self._lock:
            self._cancel_unlocked(mode)

    def stop_all(self) -> None:
        """Called only during server shutdown, not during tab switches."""
        with self._lock:
            self._cancel_unlocked()

    def stop(self, data: dict[str, Any], mode_state: ModeState) -> dict[str, Any]:
        self._authorized(data.get("mode"), data.get("mode_token"), mode_state)
        with self._lock:
            self._cancel_unlocked(data["mode"])
            return {"state": "stopped", "pending": 0}

    def status(self, mode: str) -> dict[str, Any]:
        if mode not in ("live", "youtube_browser", "tiktok_browser", "discord", "discord_client"):
            raise InputError("source mode must be live, youtube_browser, tiktok_browser, discord or discord_client")
        with self._lock:
            s = self._sessions.get(mode)
            if s is None:
                return {"mode": mode, "state": "idle", "pending": 0,
                        "received": 0, "discarded": 0, "duplicates": 0,
                        "temporary_credentials": True}
            return s.public()

    def drain(self, data: dict[str, Any], mode_state: ModeState) -> dict[str, Any]:
        mode, token = data.get("mode"), data.get("mode_token")
        self._authorized(mode, token, mode_state)
        limit = data.get("limit", 10)
        if type(limit) is not int or not 1 <= limit <= 20:
            raise InputError("source message drain limit must be 1..20")
        with self._lock:
            s = self._sessions.get(mode)
            if s is None or s.owner_token != token:
                raise ModeConflict("source monitor is not running in this workspace")
            messages = []
            for _ in range(min(limit, len(s.pending))):
                messages.append(s.pending.popleft().public())
            return {"messages": messages, "status": s.public()}

    def _run(self, session: _Session, mode_state: ModeState) -> None:
        backoff = 5.0
        while not session.cancelled.is_set():
            if not mode_state.is_owner(session.mode, session.owner_token):
                break
            try:
                batch: PollResult = session.adapter.poll()
                with self._lock:
                    if self._sessions.get(session.mode) is not session or session.cancelled.is_set():
                        break
                    if not mode_state.is_owner(session.mode, session.owner_token):
                        break
                    session.polls += 1
                    session.state = ("connecting" if session.mode in ("youtube_browser", "tiktok_browser")
                                     and not getattr(session.adapter, "dom_ready", True)
                                     else "running")
                    session.info = ("Discord Desktop RPC subscribed to selected room"
                                    if session.mode == "discord_client"
                                    else ("Browser DOM connected"
                                          if session.mode in ("youtube_browser", "tiktok_browser")
                                          else ("YouTube streamList connected"
                                                if session.mode == "live" and getattr(session.adapter, "transport", "") == "streamList"
                                                else "official API connected")))
                    if session.mode in ("youtube_browser", "tiktok_browser") and session.state == "connecting":
                        session.info = "Waiting for LIVE chat DOM in browser window"
                    for item in batch.messages:
                        if item.message_id in session.seen:
                            session.duplicates += 1
                            continue
                        if len(session.ids) == MAX_SEEN:
                            session.seen.discard(session.ids.popleft())
                        session.ids.append(item.message_id)
                        session.seen.add(item.message_id)
                        if not self._allowed(item, session):
                            session.discarded += 1
                            continue
                        if len(session.pending) == MAX_PENDING:
                            # Preserve older unread messages. Drop only the
                            # arriving overflow item; never evict pending work.
                            session.discarded += 1
                            continue
                        session.pending.append(item)
                        session.received += 1
                    if not batch.online:
                        session.state = "ended"
                        session.info = "live broadcast ended"
                        session.next_poll_seconds = 0
                        break
                    delay = (min(5, max(0.5, batch.delay_seconds))
                             if session.mode in ("youtube_browser", "tiktok_browser") else
                             (0.0 if session.mode == "live" and
                             getattr(session.adapter, "transport", "") == "streamList"
                             else (min(2, max(.1, batch.delay_seconds))
                                   if session.mode == "discord_client"
                                   else min(3600, max(5, batch.delay_seconds)))))
                    session.next_poll_seconds = delay
                backoff = 5
            except SourceFailure as exc:
                with self._lock:
                    if self._sessions.get(session.mode) is not session or session.cancelled.is_set():
                        break
                    session.state = "error" if exc.fatal else "retrying"
                    # Never expose a raw exception containing API secrets.
                    session.info = str(exc)
                    if exc.fatal:
                        session.next_poll_seconds = 0
                        break
                    delay = max(exc.retry_after, backoff, 5)
                    session.next_poll_seconds = min(3600, delay)
                backoff = min(120, backoff * 2)
            except Exception:
                with self._lock:
                    if self._sessions.get(session.mode) is not session or session.cancelled.is_set():
                        break
                    session.state = "retrying"
                    session.info = "unexpected source error; retry later"
                    session.next_poll_seconds = backoff
                delay = backoff
                backoff = min(120, backoff * 2)
            session.cancelled.wait(delay)
        session.cancelled.set()
        if hasattr(session.adapter, "close"):
            try:
                session.adapter.close()
            except OSError:
                pass
