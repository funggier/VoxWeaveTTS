"""Engine-neutral playback reports and segment subtitle selection.

The Browser HTMLMediaElement owns the actual playback clock. This service
only relays reported currentTime to a read-only local overlay and never equates
generated-WAV ready with playback. Data is ephemeral, not persisted.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import threading
import time
from typing import Any

from .processing import InputError

SESSION_RE = re.compile(r"^[0-9a-f]{32}$")
EVENTS = frozenset({"start", "progress", "paused", "resumed", "seeked", "ended", "stopped"})
STALE_AFTER_SECONDS = 3.0
SCHEMA_VERSION = 1


@dataclass
class _Session:
    session_id: str
    speech_id: str
    engine_id: str
    segments: list[dict[str, Any]]
    duration_ms: int
    sequence: int
    state: str
    position_ms: int
    updated_mono: float


class PlaybackConflict(Exception):
    """Old, expired or superseded browser playback session."""


class PlaybackState:
    """Single locally controlled active playback, with latest-sequence wins."""

    def __init__(self, *, stale_after: float = STALE_AFTER_SECONDS) -> None:
        if not 0.5 <= stale_after <= 60.0:
            raise ValueError("stale_after out of bounds")
        self._stale_after = stale_after
        self._lock = threading.RLock()
        self._active: _Session | None = None

    @staticmethod
    def _validate_event(data: Any) -> tuple[str, str, str, int, int]:
        if not isinstance(data, dict):
            raise InputError("playback event must be an object")
        session_id = data.get("session_id")
        speech_id = data.get("speech_id")
        event = data.get("event")
        sequence = data.get("sequence")
        position = data.get("position_ms")
        if not isinstance(session_id, str) or not SESSION_RE.fullmatch(session_id):
            raise InputError("invalid playback session_id")
        if not isinstance(speech_id, str) or not SESSION_RE.fullmatch(speech_id):
            raise InputError("invalid playback speech_id")
        if not isinstance(event, str) or event not in EVENTS:
            raise InputError("unknown playback event")
        if type(sequence) is not int or not 1 <= sequence <= 2_147_483_647:
            raise InputError("invalid playback sequence")
        if (type(position) not in (int, float)
            or not math.isfinite(position)
            or not 0 <= position <= 3_600_000):
            raise InputError("invalid media currentTime position")
        return session_id, speech_id, event, sequence, round(position)

    @staticmethod
    def _cue(session: _Session) -> str:
        if session.state != "playing":
            return ""
        for cue in session.segments:
            if cue["start_ms"] <= session.position_ms < cue["end_ms"]:
                return cue["display_text"] if cue["kind"] == "speech" else ""
        return ""

    @staticmethod
    def _validated_job(job: Any, speech_id: str) -> tuple[list[dict[str, Any]], int, str]:
        if not isinstance(job, dict) or job.get("speech_id") != speech_id or job.get("state") != "ready":
            raise InputError("playback requires a ready speech job")
        audio = job.get("audio")
        if not isinstance(audio, dict):
            raise InputError("job has no audio timeline")
        duration = audio.get("duration_ms")
        segments = audio.get("segments")
        if (type(duration) is not int or not 1 <= duration <= 3_600_000
            or not isinstance(segments, list) or not 1 <= len(segments) <= 512):
            raise InputError("invalid audio timeline")
        clean = []
        previous = 0
        for segment in segments:
            if not isinstance(segment, dict):
                raise InputError("invalid timeline segment")
            kind, display = segment.get("kind"), segment.get("display_text")
            start, end = segment.get("start_ms"), segment.get("end_ms")
            if (kind not in ("speech", "silence")
                or not isinstance(display, str) or len(display) > 1200
                or type(start) is not int or type(end) is not int
                or not 0 <= previous <= start <= end <= duration):
                raise InputError("invalid audio segment timing")
            clean.append({"kind": kind, "display_text": display if kind == "speech" else "",
                          "start_ms": start, "end_ms": end})
            previous = end
        engine_id = job.get("engine_id")
        if not isinstance(engine_id, str) or not engine_id:
            raise InputError("invalid audio engine")
        return clean, duration, engine_id

    def report(self, data: dict[str, Any], *, ready_job: dict[str, Any] | None = None) -> dict[str, Any]:
        session_id, speech_id, event, sequence, position = self._validate_event(data)
        with self._lock:
            if event == "start":
                if ready_job is None:
                    raise InputError("a ready speech job is required to start playback")
                cues, duration, engine_id = self._validated_job(ready_job, speech_id)
                # A delayed start response must not rewind an active session.
                if self._active and self._active.session_id == session_id:
                    if sequence <= self._active.sequence:
                        return self._snapshot()
                    raise PlaybackConflict("playback session has already started")
                self._active = _Session(
                    session_id=session_id, speech_id=speech_id, engine_id=engine_id,
                    segments=cues, duration_ms=duration, sequence=sequence,
                    state="playing", position_ms=min(position, duration),
                    updated_mono=time.monotonic(),
                )
            else:
                current = self._active
                if (current is None or current.session_id != session_id
                    or current.speech_id != speech_id):
                    raise PlaybackConflict("playback session is no longer active")
                if sequence <= current.sequence:
                    return self._snapshot()
                if current.state in ("ended", "stopped"):
                    raise PlaybackConflict("playback session is terminal")
                current.sequence = sequence
                current.position_ms = min(position, current.duration_ms)
                current.updated_mono = time.monotonic()
                if event in ("resumed", "progress"):
                    if event == "resumed" or current.state == "playing":
                        current.state = "playing"
                elif event == "paused":
                    current.state = "paused"
                elif event == "ended":
                    current.state = "ended"
                elif event == "stopped":
                    current.state = "stopped"
                # seeked leaves playing/paused state unchanged.
            return self._snapshot()

    def _snapshot(self) -> dict[str, Any]:
        session = self._active
        if session is None:
            return {
                "schema_version": SCHEMA_VERSION, "state": "idle",
                "speech_id": None, "session_id": None,
                "position_ms": 0, "duration_ms": 0,
                "sequence": 0, "subtitle": "", "stale": False,
                "clock_basis": "browser_html_media_current_time_reported",
            }
        elapsed = time.monotonic() - session.updated_mono
        stale = session.state == "playing" and elapsed > self._stale_after
        return {
            "schema_version": SCHEMA_VERSION,
            "state": "stale" if stale else session.state,
            "speech_id": session.speech_id,
            "session_id": session.session_id,
            "engine_id": session.engine_id,
            "position_ms": session.position_ms,
            "duration_ms": session.duration_ms,
            "sequence": session.sequence,
            "subtitle": "" if stale else self._cue(session),
            "stale": stale,
            "clock_basis": "browser_html_media_current_time_reported",
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot()