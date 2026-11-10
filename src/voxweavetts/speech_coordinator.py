"""Engine-neutral speech preparation queue, private jobs and versioned events.

The coordinator consumes an already-filtered speech plan and a renderer
callable. It has NO dependency on any specific model, voice package or ML
framework. 'ready' means audio was synthesized, NOT played. Playback-clock
events belong to a future dedicated player.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import time
from typing import Any, Callable
from uuid import uuid4

from .processing import InputError
from .manual_alignment import validate_manual_cues
from .audio_alignment import AudioAlignmentProvider, PCMActivityProvider, BASIS as ACTIVITY_BASIS

EVENT_SCHEMA_VERSION = 1
MAX_JOBS = 12
MAX_AUDIO_BYTES = 16_000_000
MAX_TOTAL_AUDIO_BYTES = 64_000_000
JOB_TTL_SECONDS = 900
_TERMINAL = frozenset({"ready", "failed", "cancelled"})


class QueueFull(Exception):
    """Bounded coordinator cannot accept another job."""


class JobMissing(Exception):
    """The job ID is unknown or expired."""


class AlignmentConflict(Exception):
    """A different editor has updated this job's manual timecodes."""


class JobNotReady(Exception):
    """Job audio has not reached the ready state."""


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class _Job:
    id: str
    source: str
    source_message_id: str | None
    display_text: str
    engine_id: str
    voice_id: str
    plan: dict[str, Any] | None
    render_args: dict[str, Any]
    state: str = "queued"
    created_at: str = field(default_factory=_now_utc)
    created_mono: float = field(default_factory=time.monotonic)
    updated_at: str = field(default_factory=_now_utc)
    event_seq: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    audio: bytes | None = None
    timeline: dict[str, Any] | None = None
    alignment_revision: int = 0
    error: str | None = None

    def snapshot(self) -> dict[str, Any]:
        # No raw original text, spoken replacement, pronunciation rules or
        # unfiltered audio input is exported to status/event clients.
        data: dict[str, Any] = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "speech_id": self.id,
            "state": self.state,
            "source": self.source,
            "display_text": self.display_text,
            "engine_id": self.engine_id,
            "voice_id": self.voice_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_sequence": self.event_seq,
            "audio_ready": self.state == "ready",
        }
        if self.state == "ready" and self.timeline:
            data["audio"] = self.timeline
            data["alignment_revision"] = self.alignment_revision
        if self.error is not None:
            data["error"] = self.error
        return data


class SpeechCoordinator:
    """Sequential, bounded, in-memory queue for model-neutral audio rendering."""

    def __init__(
        self,
        renderer: Callable[..., tuple[bytes, dict[str, Any]]],
        *,
        max_jobs: int = MAX_JOBS,
        max_total_audio_bytes: int = MAX_TOTAL_AUDIO_BYTES,
        ttl_seconds: float = JOB_TTL_SECONDS,
        alignment_provider: AudioAlignmentProvider | None = None,
    ) -> None:
        if not callable(renderer):
            raise TypeError("renderer must be callable")
        if not 1 <= max_jobs <= 100 or max_total_audio_bytes < 1024 or ttl_seconds <= 0:
            raise ValueError("invalid coordinator limits")
        self._renderer = renderer
        self._alignment_provider = alignment_provider if alignment_provider is not None else PCMActivityProvider()
        self._max_jobs = max_jobs
        self._max_total_audio_bytes = max_total_audio_bytes
        self._ttl_seconds = ttl_seconds
        self._jobs: dict[str, _Job] = {}
        self._queue: deque[str] = deque()
        self._dedupe: dict[tuple[str, str], str] = {}
        self._audio_bytes = 0
        self._cv = threading.Condition(threading.RLock())
        self._closed = False
        self._thread = threading.Thread(
            target=self._work, name="voxweavetts-speech-queue", daemon=True
        )
        self._thread.start()

    @staticmethod
    def _public_timeline(
        info: dict[str, Any],
        activity_intervals: list[list[dict[str, int]]] | None = None,
    ) -> dict[str, Any]:
        # Allowlist public display metadata. Never expose original/spoken text.
        segments = []
        for index, segment in enumerate(info.get("segments", [])):
            clean = {
                "kind": segment["kind"],
                "display_text": segment["display_text"],
                "start_ms": segment["start_ms"],
                "end_ms": segment["end_ms"],
            }
            if activity_intervals is not None:
                clean["activity_intervals"] = activity_intervals[index]
            segments.append(clean)
        return {
            "duration_ms": info["duration_ms"],
            "sample_rate": info["sample_rate"],
            "segments": segments,
            "timing_basis": "generated_audio_samples_not_playback",
            "activity_basis": ACTIVITY_BASIS if activity_intervals is not None else "unavailable",
            "word_alignment": False,
        }

    def _transition(self, job: _Job, state: str, *, error: str | None = None) -> None:
        job.state = state
        job.updated_at = _now_utc()
        job.error = error
        job.event_seq += 1
        job.events.append({
            "schema_version": EVENT_SCHEMA_VERSION,
            "sequence": job.event_seq,
            "type": f"speech.{state}",
            "speech_id": job.id,
            "state": state,
            "timestamp": job.updated_at,
        })
        self._cv.notify_all()

    def _drop(self, job: _Job) -> None:
        self._jobs.pop(job.id, None)
        if job.source_message_id:
            self._dedupe.pop((job.source, job.source_message_id), None)
        if job.audio is not None:
            self._audio_bytes -= len(job.audio)
        job.audio = None
        job.plan = None

    def _prune(self) -> None:
        now = time.monotonic()
        for job in list(self._jobs.values()):
            if (job.state in _TERMINAL
                and now - job.created_mono > self._ttl_seconds):
                self._drop(job)
    def _make_room(self) -> None:
        # Evict completed jobs only when a NEW submission needs space, never
        # while clients are polling a just-finished job or downloading audio.
        if len(self._jobs) >= self._max_jobs:
            for job in list(self._jobs.values()):
                if job.state in _TERMINAL:
                    self._drop(job)
                    if len(self._jobs) < self._max_jobs:
                        break

    def submit(
        self, plan: dict[str, Any], *, engine_id: str, voice_id: str,
        render_args: dict[str, Any], source_message_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(plan, dict) or not isinstance(plan.get("segments"), list):
            raise InputError("invalid speech plan")
        if not isinstance(engine_id, str) or not isinstance(voice_id, str):
            raise InputError("engine_id and voice_id must be strings")
        if source_message_id is not None and (
            not isinstance(source_message_id, str)
            or not 1 <= len(source_message_id) <= 128
        ):
            raise InputError("source_message_id must be 1–128 characters")
        source = plan["source"]
        with self._cv:
            if self._closed:
                raise QueueFull("coordinator stopped")
            self._prune()
            key = (source, source_message_id) if source_message_id else None
            if key is not None and key in self._dedupe:
                existing = self._jobs.get(self._dedupe[key])
                if existing:
                    return existing.snapshot()
            self._make_room()
            if len(self._jobs) >= self._max_jobs:
                raise QueueFull("speech queue is full; try again later")
            job = _Job(
                id=uuid4().hex, source=source, source_message_id=source_message_id,
                display_text=plan["display_text"], engine_id=engine_id,
                voice_id=voice_id, plan=plan, render_args=dict(render_args),
            )
            self._jobs[job.id] = job
            if key is not None:
                self._dedupe[key] = job.id
            self._transition(job, "queued")
            self._queue.append(job.id)
            self._cv.notify_all()
            return job.snapshot()

    def _work(self) -> None:
        while True:
            with self._cv:
                while not self._queue and not self._closed:
                    self._cv.wait()
                if self._closed:
                    return
                job = self._jobs.get(self._queue.popleft())
                if job is None or job.state != "queued":
                    continue
                self._transition(job, "rendering")
                plan = job.plan
                arguments = dict(job.render_args)
            try:
                if plan is None:
                    raise ValueError("missing plan")
                wav, metadata = self._renderer(plan, **arguments)
                if (not isinstance(wav, bytes) or len(wav) < 44
                    or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE"
                    or len(wav) > MAX_AUDIO_BYTES):
                    raise ValueError("invalid or excessive rendered WAV")
                try:
                    activity = self._alignment_provider.analyze(
                        wav, metadata["segments"])
                    if activity is not None:
                        if (not isinstance(activity, list)
                            or len(activity) != len(metadata["segments"])):
                            raise ValueError("invalid activity provider length")
                        # Explicit public allowlist; untrusted future providers
                        # cannot expose text or arbitrary metadata through API.
                        safe_activity = []
                        for part, intervals in zip(metadata["segments"], activity):
                            if (not isinstance(intervals, list)
                                or len(intervals) > 32):
                                raise ValueError("invalid activity intervals")
                            start, end = part["start_ms"], part["end_ms"]
                            prior = start
                            safe = []
                            for item in intervals:
                                left, right = item.get("start_ms"), item.get("end_ms")
                                if (type(left) is not int or type(right) is not int
                                    or not start <= prior <= left < right <= end
                                    or part["kind"] != "speech"):
                                    raise ValueError("invalid activity time bounds")
                                safe.append({"start_ms":left,"end_ms":right})
                                prior = right
                            safe_activity.append(safe)
                        activity = safe_activity
                except Exception:
                    # Optional analysis must never prevent successful WAV output.
                    activity = None
                timeline = self._public_timeline(metadata, activity)
                with self._cv:
                    if job.state == "cancelled":
                        continue
                    if self._audio_bytes + len(wav) > self._max_total_audio_bytes:
                        job.plan = None
                        self._transition(job, "failed", error="audio queue memory limit reached")
                        continue
                    job.audio = wav
                    job.timeline = timeline
                    job.plan = None
                    self._audio_bytes += len(wav)
                    self._transition(job, "ready")
            except Exception:
                # Never leak model exceptions or user input into public events.
                with self._cv:
                    if job.state != "cancelled":
                        job.plan = None
                        self._transition(job, "failed", error="speech rendering failed")

    def get(self, job_id: str) -> dict[str, Any]:
        with self._cv:
            self._prune()
            job = self._jobs.get(job_id)
            if job is None:
                raise JobMissing("unknown speech_id")
            return job.snapshot()

    def set_manual_alignment(
        self, job_id: str, cues: Any, expected_revision: Any,
    ) -> dict[str, Any]:
        """Install user-marked text/audio ranges for a ready WAV, in memory.

        No new audio synthesis or disk write is performed; client must
        explicitly export the cues if long-term retention is needed.
        """
        with self._cv:
            self._prune()
            job = self._jobs.get(job_id)
            if job is None:
                raise JobMissing("unknown speech_id")
            if job.state != "ready" or job.timeline is None:
                raise JobNotReady("manual alignment requires generated audio")
            if type(expected_revision) is not int or expected_revision < 0:
                raise InputError("expected_revision must be a nonnegative integer")
            if job.alignment_revision != expected_revision:
                raise AlignmentConflict("manual cues were updated by another editor")
            cleaned = validate_manual_cues(job.timeline["segments"], cues)
            # Keep only segment-sliced display text and bounded integer offsets.
            job.timeline["manual_cues"] = cleaned
            job.timeline["manual_alignment_basis"] = "user_marked_browser_wav_timecodes"
            job.alignment_revision += 1
            job.updated_at = _now_utc()
            return job.snapshot()

    def list(self) -> list[dict[str, Any]]:
        with self._cv:
            self._prune()
            return [job.snapshot() for job in self._jobs.values()]

    def events(self, job_id: str) -> list[dict[str, Any]]:
        with self._cv:
            self._prune()
            job = self._jobs.get(job_id)
            if job is None:
                raise JobMissing("unknown speech_id")
            return [dict(event) for event in job.events]

    def audio(self, job_id: str) -> bytes:
        with self._cv:
            self._prune()
            job = self._jobs.get(job_id)
            if job is None:
                raise JobMissing("unknown speech_id")
            if job.state != "ready" or job.audio is None:
                raise JobNotReady("speech audio is not ready")
            return job.audio

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._cv:
            self._prune()
            job = self._jobs.get(job_id)
            if job is None:
                raise JobMissing("unknown speech_id")
            if job.state not in {"cancelled", "failed"}:
                if job.audio is not None:
                    self._audio_bytes -= len(job.audio)
                    job.audio = None
                job.plan = None
                job.timeline = None
                self._transition(job, "cancelled")
            return job.snapshot()

    def wait(self, job_id: str, timeout: float = 10.0) -> dict[str, Any]:
        """Test/UI helper, not used by the HTTP request handler."""
        deadline = time.monotonic() + timeout
        with self._cv:
            while True:
                job = self._jobs.get(job_id)
                if job is None:
                    raise JobMissing("unknown speech_id")
                if job.state in _TERMINAL:
                    return job.snapshot()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return job.snapshot()
                self._cv.wait(timeout=remaining)

    def close(self) -> None:
        with self._cv:
            self._closed = True
            for job in self._jobs.values():
                if job.state not in _TERMINAL:
                    job.plan = None
                    self._transition(job, "cancelled")
            self._cv.notify_all()
        self._thread.join(timeout=1.0)