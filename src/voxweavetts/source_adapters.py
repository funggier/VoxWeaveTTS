"""Opt-in, local-only read-only live message sources (stdlib HTTP).

No social API credentials in URLs except YouTube's official API-key query.
URLs are constructed against fixed official hosts, never from chat content.
Do not log raw requests, URLs, bot tokens or responses.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .processing import InputError

MAX_API_RESPONSE = 512_000
YT_CHAT = re.compile(r"[A-Za-z0-9_-]{5,160}\Z")
YT_VIDEO = re.compile(r"[A-Za-z0-9_-]{11}\Z")
DISCORD_CHANNEL = re.compile(r"[0-9]{16,22}\Z")
YT_HOST = "www.googleapis.com"
DISCORD_HOST = "discord.com"


class SourceFailure(Exception):
    def __init__(self, message: str, *, fatal: bool = False,
                 retry_after: float = 0):
        super().__init__(message)
        self.fatal = fatal
        self.retry_after = retry_after


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _fetch_json(url: str, headers: dict[str, str],
                timeout: float = 7) -> tuple[object, dict[str, str]]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in (YT_HOST, DISCORD_HOST):
        raise InputError("unsupported official source endpoint")
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "VoxWeaveTTS/0.3 live-readonly",
        **headers,
    })
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(MAX_API_RESPONSE + 1)
            if len(body) > MAX_API_RESPONSE:
                raise SourceFailure("source response exceeded size limit")
            response_headers = {k.lower(): v for k, v in response.headers.items()}
            return json.loads(body.decode("utf-8")), response_headers
    except HTTPError as exc:
        status = exc.code
        retry = 0.0
        if status == 429:
            try:
                raw = exc.read(2048)
                obj = json.loads(raw)
                retry = float(obj.get("retry_after", 0))
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
            try:
                retry = max(retry, float(exc.headers.get("Retry-After", 0)))
            except (TypeError, ValueError):
                pass
            retry = min(3600, max(5, retry))
            raise SourceFailure("source rate limit; retry later",
                                retry_after=retry) from None
        # Report only the HTTP category, never Google's error body: it can
        # contain sensitive API key or user/channel details.
        service = "YouTube" if parsed.hostname == YT_HOST else "Discord"
        explanation = {
            400: "invalid request, channel ID or live chat ID",
            401: "credentials missing, invalid or expired",
            403: "access denied; check API enablement, key restrictions, quota and permissions",
            404: "video/live chat/channel not found or not accessible",
        }[status] if status in (400, 401, 403, 404) else None
        if explanation:
            raise SourceFailure(
                f"{service} API HTTP {status}: {explanation}",
                fatal=True,
            ) from None
        if 300 <= status < 400:
            raise SourceFailure("source redirect denied", fatal=True) from None
        raise SourceFailure("source temporarily unavailable", retry_after=10) from None
    except (TimeoutError, URLError, OSError):
        # Never echo exception strings: YouTube errors may contain an API key URL.
        raise SourceFailure("source connection failed; retry later",
                            retry_after=10) from None
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise SourceFailure("invalid official source JSON", retry_after=10) from None


@dataclass(frozen=True)
class SourceMessage:
    message_id: str
    author: str
    text: str

    def public(self) -> dict[str, str]:
        return {"message_id": self.message_id,
                "author": self.author, "text": self.text}


@dataclass(frozen=True)
class PollResult:
    messages: tuple[SourceMessage, ...]
    delay_seconds: float
    online: bool = True


def _normal_text(value: object, max_chars: int = 350) -> str:
    if not isinstance(value, str):
        return ""
    # Retain Thai diacritics/emoji. Remove ASCII control bytes, not graphemes.
    text = "".join(" " if ord(c) < 32 or ord(c) == 127 else c for c in value)
    text = " ".join(text.split())
    return text if 1 <= len(text) <= max_chars else ""


class YouTubeLiveAdapter:
    """Public liveChatMessages.list; first page is used as history baseline."""

    def __init__(self, source_id: str, api_key: str,
                 fetcher=_fetch_json) -> None:
        if not isinstance(source_id, str):
            raise InputError("liveChat ID or YouTube video ID required")
        source_id = source_id.strip()
        if not YT_CHAT.fullmatch(source_id):
            raise InputError("invalid YouTube live chat/video ID")
        if not isinstance(api_key, str) or not 10 <= len(api_key) <= 250:
            raise InputError("YouTube Data API key required")
        if any(c.isspace() for c in api_key):
            raise InputError("invalid YouTube API key")
        self.chat_id = source_id
        self.api_key = api_key
        self._fetcher = fetcher
        self.page_token: str | None = None
        self.started = False
        self.resolved = False

    def _resolve_video(self) -> None:
        if not YT_VIDEO.fullmatch(self.chat_id):
            self.resolved = True
            return
        url = "https://www.googleapis.com/youtube/v3/videos?" + urlencode({
            "part": "liveStreamingDetails", "id": self.chat_id,
            "key": self.api_key,
        })
        result, _ = self._fetcher(url, {})
        details = result.get("items", []) if isinstance(result, dict) else []
        first = details[0] if isinstance(details, list) and details else {}
        streaming = first.get("liveStreamingDetails") if isinstance(first, dict) else None
        chat_id = streaming.get("activeLiveChatId") if isinstance(streaming, dict) else None
        if not isinstance(chat_id, str) or not YT_CHAT.fullmatch(chat_id):
            raise SourceFailure("video has no active live chat", fatal=True)
        self.chat_id = chat_id
        self.resolved = True

    def poll(self) -> PollResult:
        if not self.resolved:
            self._resolve_video()
        params = {
            "part": "snippet,authorDetails",
            "liveChatId": self.chat_id,
            "key": self.api_key,
            "maxResults": "200",
        }
        if self.page_token:
            params["pageToken"] = self.page_token
        url = "https://www.googleapis.com/youtube/v3/liveChat/messages?" + urlencode(params)
        result, _ = self._fetcher(url, {})
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            raise SourceFailure("unexpected YouTube live chat response", retry_after=10)
        page = result.get("nextPageToken")
        if not isinstance(page, str) or not page:
            raise SourceFailure("YouTube continuation token missing", retry_after=10)
        self.page_token = page
        interval = result.get("pollingIntervalMillis", 6000)
        try:
            delay = min(180, max(5, float(interval) / 1000))
        except (ValueError, TypeError):
            delay = 6.0
        baseline = not self.started
        self.started = True
        if baseline:
            return PollResult((), delay)
        parsed: list[SourceMessage] = []
        for item in result["items"]:
            if not isinstance(item, dict):
                continue
            snippet = item.get("snippet", {})
            if not isinstance(snippet, dict) or snippet.get("type") != "textMessageEvent":
                continue
            details = snippet.get("textMessageDetails")
            text = _normal_text(details.get("messageText")) if isinstance(details, dict) else ""
            ident = item.get("id")
            author = item.get("authorDetails")
            if text and isinstance(ident, str) and ident:
                parsed.append(SourceMessage(
                    ident, _normal_text(author.get("displayName", ""), 80)
                    if isinstance(author, dict) else "", text))
        return PollResult(tuple(parsed), delay, online=not bool(result.get("offlineAt")))


class DiscordChannelAdapter:
    """Read-only REST channel history polling, no user tokens/self-bots."""

    def __init__(self, channel_id: str, bot_token: str,
                 fetcher=_fetch_json) -> None:
        if not isinstance(channel_id, str) or not DISCORD_CHANNEL.fullmatch(channel_id.strip()):
            raise InputError("invalid Discord channel ID")
        if not isinstance(bot_token, str) or not 20 <= len(bot_token) <= 250:
            raise InputError("Discord BOT token required")
        if any(c.isspace() for c in bot_token):
            raise InputError("invalid Discord BOT token")
        self.channel_id = channel_id.strip()
        self._token = bot_token
        self._fetcher = fetcher
        self.after_id: str | None = None
        self.started = False

    def poll(self) -> PollResult:
        params = {"limit": "100"}
        if self.after_id:
            params["after"] = self.after_id
        url = ("https://discord.com/api/v10/channels/" + self.channel_id
               + "/messages?" + urlencode(params))
        result, headers = self._fetcher(url, {
            "Authorization": "Bot " + self._token,
        })
        if not isinstance(result, list):
            raise SourceFailure("unexpected Discord channel response", retry_after=10)
        messages = sorted((item for item in result
                           if isinstance(item, dict) and
                           isinstance(item.get("id"), str) and
                           item["id"].isdigit()), key=lambda item: int(item["id"]))
        if messages:
            newest = messages[-1]["id"]
            if self.after_id is None or int(newest) > int(self.after_id):
                self.after_id = newest
        baseline = not self.started
        self.started = True
        delay = 5.0
        # Discord says to heed route-specific response headers, not fixed quotas.
        try:
            if headers.get("x-ratelimit-remaining") == "0":
                delay = max(delay, float(headers.get("x-ratelimit-reset-after", "0")) + .5)
        except (TypeError, ValueError):
            pass
        if baseline:
            return PollResult((), min(3600, delay))
        parsed = []
        for item in messages:
            author = item.get("author")
            if not isinstance(author, dict) or author.get("bot") or item.get("webhook_id"):
                continue
            if item.get("type", 0) not in (0, 19):
                continue
            text = _normal_text(item.get("content"))
            if text:
                parsed.append(SourceMessage(
                    item["id"],
                    _normal_text(author.get("global_name") or author.get("username") or "", 80),
                    text))
        return PollResult(tuple(parsed), min(3600, delay))