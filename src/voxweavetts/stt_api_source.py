"""Versioned, read-only VoxWeaveSTT transcript connector.

This adapter consumes finalized transcript events from a separate STT process.
It does not import STT internals, start STT sessions, or expose credentials.
Loopback HTTP is allowed only for 127.0.0.1; LAN requires paired HTTPS and a
SHA-256 pinned certificate, using STT's existing remote gateway contract.
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import ipaddress
import json
import re
import ssl
from urllib.parse import urlsplit

from .processing import InputError
from .source_adapters import PollResult, SourceFailure, SourceMessage

MAX_REPLY = 4 * 1024 * 1024
SESSION_ID = re.compile(r"[0-9a-f]{32}\Z")
FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")


class VoxWeaveSTTAdapter:
    """Source adapter: never replay completed transcriptions on initial connect."""

    transport = "stt-final-api"

    def __init__(self, source_id: str, credential: object = None):
        if not isinstance(source_id, str) or len(source_id) > 120:
            raise InputError("invalid VoxWeaveSTT server address")
        parsed = urlsplit(source_id)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
            raise InputError("use an IP address and port for VoxWeaveSTT")
        host = parsed.hostname
        if host == "localhost":
            host = "127.0.0.1"
        try:
            ip = ipaddress.ip_address(host)
            port = parsed.port
        except ValueError as exc:
            raise InputError("VoxWeaveSTT requires a valid IPv4 address and port") from exc
        if ip.version != 4 or port is None or not 1 <= port <= 65535:
            raise InputError("VoxWeaveSTT requires an IPv4 address and port")
        if (ip.is_unspecified or ip.is_link_local or ip.is_multicast or
            ip.is_reserved and not ip.is_loopback):
            raise InputError("VoxWeaveSTT server IP is not allowed")
        if parsed.scheme == "http" and str(ip) != "127.0.0.1":
            raise InputError("remote STT requires paired HTTPS, not plain HTTP")
        if parsed.scheme == "https" and not (ip.is_private or ip.is_loopback):
            raise InputError("STT HTTPS requires a private LAN address")
        self.host, self.port, self.secure = str(ip), port, parsed.scheme == "https"
        self.origin = f"https://{self.host}:{port}"
        self._pin, self._fingerprint = "", ""
        self._cookie = ""
        self._paired = not self.secure
        if self.secure:
            if not isinstance(credential, dict) or set(credential) != {"pin", "fingerprint"}:
                raise InputError("STT LAN requires a pairing PIN and SHA-256 fingerprint")
            pin = credential["pin"]
            fingerprint = credential["fingerprint"]
            if not isinstance(pin, str) or not re.fullmatch(r"[0-9]{8}", pin):
                raise InputError("STT LAN pairing PIN must be 8 digits")
            if not isinstance(fingerprint, str):
                raise InputError("STT LAN certificate fingerprint is required")
            fingerprint = fingerprint.lower().replace(":", "").replace(" ", "")
            if not FINGERPRINT.fullmatch(fingerprint):
                raise InputError("STT LAN SHA-256 fingerprint must have 64 hexadecimal characters")
            self._pin, self._fingerprint = pin, fingerprint
        self._session = None
        self._cursor = 0
        self._initialized = False
        self.phase = "connecting"
        self.info = "Connecting to VoxWeaveSTT"

    def close(self) -> None:
        self._cookie = ""
        self._pin = ""

    def _get(self, route: str) -> dict:
        return self._request("GET", route)

    def _request(self, method: str, route: str, data: dict | None = None) -> dict:
        if not route.startswith(("/api/", "/remote/")) or "\r" in route or "\n" in route:
            raise SourceFailure("invalid STT API path", fatal=True)
        if self.secure:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            conn = http.client.HTTPSConnection(self.host, self.port, context=context, timeout=4)
        else:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=4)
        try:
            if self.secure:
                conn.connect()
                der = conn.sock.getpeercert(binary_form=True)
                actual = hashlib.sha256(der).hexdigest() if der else ""
                if not hmac.compare_digest(actual, self._fingerprint):
                    raise SourceFailure("STT LAN TLS fingerprint mismatch", fatal=True)
            headers = {"Accept": "application/json"}
            if self.secure and self._cookie:
                headers["Cookie"] = f"VWSTT_LAN={self._cookie}"
            if self.secure and method == "POST":
                headers["Origin"] = self.origin
                headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8") if data is not None else None
            conn.request(method, route, body=body, headers=headers)
            response = conn.getresponse()
            if response.length is not None and response.length > MAX_REPLY:
                raise SourceFailure("STT API reply too large", fatal=True)
            raw = response.read(MAX_REPLY + 1)
            if len(raw) > MAX_REPLY:
                raise SourceFailure("STT API reply too large", fatal=True)
            if response.status != 200:
                if response.status in (401, 403):
                    raise SourceFailure("STT API access denied; check pairing and LAN configuration", fatal=True)
                if response.status in (404, 410):
                    raise SourceFailure("STT session is no longer available", retry_after=5)
                if 300 <= response.status < 400:
                    raise SourceFailure("STT API redirect rejected", fatal=True)
                raise SourceFailure(f"STT API HTTP {response.status}", retry_after=5)
            if self.secure and route == "/remote/pair":
                cookie = response.getheader("Set-Cookie", "").split(";", 1)[0]
                if not cookie.startswith("VWSTT_LAN=") or len(cookie) > 200:
                    raise SourceFailure("STT LAN pairing returned no session", fatal=True)
                self._cookie = cookie.split("=", 1)[1]
            try:
                value = json.loads(raw)
            except (ValueError, UnicodeDecodeError) as exc:
                raise SourceFailure("STT API returned invalid JSON", retry_after=5) from exc
            if not isinstance(value, dict):
                raise SourceFailure("STT API returned an invalid object", retry_after=5)
            return value
        except SourceFailure:
            raise
        except (OSError, TimeoutError, ssl.SSLError, http.client.HTTPException):
            raise SourceFailure("VoxWeaveSTT connection unavailable", retry_after=5) from None
        finally:
            conn.close()

    def _ensure_paired(self) -> None:
        if self._paired:
            return
        result = self._request("POST", "/remote/pair", {"code": self._pin})
        if result.get("paired") is not True or not self._cookie:
            raise SourceFailure("STT LAN pairing unsuccessful", fatal=True)
        self._pin = ""
        self._paired = True

    def poll(self) -> PollResult:
        self._ensure_paired()
        status = self._get("/remote/status" if self.secure else "/api/status")
        if status.get("api_version") != 1 and not self.secure:
            raise SourceFailure("unsupported VoxWeaveSTT API version", fatal=True)
        active = status.get("active")
        draining_final = False
        if not isinstance(active, dict) or not isinstance(active.get("id"), str):
            if self._session is None:
                self._initialized = True
                self.phase = "waiting_session"
                self.info = "Connected; waiting for STT transcription"
                return PollResult((), 0.6)
            # STT flushes a final segment on Stop. Drain that finished session
            # before returning to the idle state; it is still in the journal.
            active = {"id": self._session, "status": "stopped"}
            draining_final = True
        session = active["id"]
        if not SESSION_ID.fullmatch(session):
            raise SourceFailure("STT returned invalid session ID", retry_after=5)
        if session != self._session:
            self._session = session
            # Initial connection starts at the current end: no replay of speech
            # spoken before Connect. Subsequent NEW sessions start at zero.
            sequence = active.get("event_sequence", 0)
            self._cursor = max(0, sequence) if not self._initialized and type(sequence) is int else 0
            self._initialized = True
        path = (f"/remote/events?session_id={session}&after={self._cursor}"
                if self.secure else f"/api/sessions/{session}/events?after={self._cursor}")
        result = self._get(path)
        values = result.get("events")
        if not isinstance(values, list) or len(values) > 200:
            raise SourceFailure("STT returned invalid transcript events", retry_after=5)
        messages = []
        expected = self._cursor
        for event in values:
            if not isinstance(event, dict) or event.get("type") != "transcript.final":
                continue
            sequence = event.get("api_sequence")
            text = event.get("text")
            segment = event.get("segment_id")
            revision = event.get("revision", 0)
            # STT /api/sessions/<id>/events uses the transcription job ID,
            # whereas each transcript.final carries its audio capture ID.
            # Validate the capture ID but never require equality with job ID.
            if (not isinstance(event.get("session_id"), str) or not 1 <= len(event["session_id"]) <= 128 or type(sequence) is not int
                or sequence <= expected or not isinstance(text, str)
                or not isinstance(segment, str) or len(segment) > 160
                or type(revision) is not int or revision < 0):
                raise SourceFailure("STT transcript event violates contract", retry_after=5)
            if text.strip() and len(text) <= 8000:
                messages.append(SourceMessage(
                    f"{session}:{segment}:{revision}", "", text.strip(),
                ))
            expected = sequence
        cursor = result.get("last_sequence")
        if type(cursor) is not int or cursor < self._cursor:
            raise SourceFailure("STT cursor moved backwards", retry_after=5)
        self._cursor = cursor
        if draining_final and not result.get("has_more"):
            self._session = None
        self.phase = "waiting_session" if draining_final else "ready"
        self.info = ("Connected; STT session finished" if draining_final
                     else "Receiving finalized STT transcripts")
        return PollResult(tuple(messages), 0.05 if result.get("has_more") else 0.6)
