"""Engine-neutral speech preparation queue, private jobs and versioned events.

The coordinator consumes an already-filtered speech plan or an optional
asynchronous AI preparation callback, then a renderer callable. AI preparation
and TTS rendering use separate workers with one bounded job registry. Live
translation can run concurrently while the client retains playback order. It has
NO dependency on any specific model, voice package or ML framework. 'ready'
means audio was synthesized, NOT played.
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
MAX_JOBS = 768  # six Live modes: up to 100 prepared + 20 WAV jobs each, plus active/other jobs
MAX_AUDIO_BYTES = 16_000_000
MAX_TOTAL_AUDIO_BYTES = 512_000_000  # bounded global WAV cache, not per source
JOB_TTL_SECONDS = 900
TRANSLATION_GATHER_SECONDS = 0.15
_TERMINAL = frozenset({"ready", "failed", "cancelled", "skipped"})


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
    prepare: Callable[[], tuple[dict[str, Any], dict[str, Any]]] | None = None
    hold_for_render: bool = False
    state: str = "queued"
    created_at: str = field(default_factory=_now_utc)
    created_mono: float = field(default_factory=time.monotonic)
    updated_mono: float = field(default_factory=time.monotonic)
    updated_at: str = field(default_factory=_now_utc)
    event_seq: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    audio: bytes | None = None
    timeline: dict[str, Any] | None = None
    alignment_revision: int = 0
    error: str | None = None
    # Model-bound text is private and never copied into snapshot()/events().
    model_inputs: list[dict[str, Any]] | None = None
    successful_chunks: int = 0
    failed_chunks: int = 0
    chunk_outcomes_available: bool = False

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
        if self.chunk_outcomes_available:
            data["successful_chunks"] = self.successful_chunks
            data["failed_chunks"] = self.failed_chunks
            data["partial_failure"] = self.successful_chunks > 0 and self.failed_chunks > 0
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
        if not 1 <= max_jobs <= 1024 or max_total_audio_bytes < 1024 or ttl_seconds <= 0:
            raise ValueError("invalid coordinator limits")
        self._renderer = renderer
        self._alignment_provider = alignment_provider if alignment_provider is not None else PCMActivityProvider()
        self._max_jobs = max_jobs
        self._max_total_audio_bytes = max_total_audio_bytes
        self._ttl_seconds = ttl_seconds
        self._jobs: dict[str, _Job] = {}
        self._queue: deque[str] = deque()
        self._prepare_queue: deque[str] = deque()
        self._translation_queue: deque[str] = deque()
        self._translation_workers: set[threading.Thread] = set()
        self._translation_limit = 1
        self._translation_minimum = 1
        self._translation_timer: threading.Timer | None = None
        self._dedupe: dict[tuple[str, str], str] = {}
        self._audio_bytes = 0
        self._cv = threading.Condition(threading.RLock())
        self._closed = False
        self._thread = threading.Thread(
            target=self._work, name="voxweavetts-speech-queue", daemon=True
        )
        self._thread.start()
        self._prepare_thread = threading.Thread(
            target=self._work_prepare, name="voxweavetts-ai-preparation", daemon=True
        )
        self._prepare_thread.start()

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
        job.updated_mono = time.monotonic()
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
        job.prepare = None
        job.model_inputs = None
        # Drop queued IDs as well as metadata, otherwise repeated cancellation
        # under load may accumulate unbounded stale references.
        for pending in (self._prepare_queue, self._translation_queue, self._queue):
            try:
                pending.remove(job.id)
            except ValueError:
                pass

    def _prune(self) -> None:
        now = time.monotonic()
        for job in list(self._jobs.values()):
            # A generated staged WAV must not expire based on when the
            # earlier translation started. It gets its own TTL after ready.
            since = (job.updated_mono if job.state == "ready" and
                     job.hold_for_render else job.created_mono)
            if (job.state in _TERMINAL
                and now - since > self._ttl_seconds):
                self._drop(job)
    def _make_room(self) -> None:
        # Evict completed jobs only when a NEW submission needs space, never
        # while clients are polling a just-finished job or downloading audio.
        if len(self._jobs) >= self._max_jobs:
            for job in list(self._jobs.values()):
                # Until the browser has actually fetched a staged WAV, it
                # must not be evicted by an unrelated mode that submits work.
                if job.state in _TERMINAL and not (
                    job.state == "ready" and job.hold_for_render
                ):
                    self._drop(job)
                    if len(self._jobs) < self._max_jobs:
                        break

    def submit(
        self, plan: dict[str, Any], *, engine_id: str, voice_id: str,
        render_args: dict[str, Any], source_message_id: str | None = None,
        hold_for_render: bool = False,
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
                hold_for_render=hold_for_render,
            )
            self._jobs[job.id] = job
            if key is not None:
                self._dedupe[key] = job.id
            if not plan.get("spoken_text", "").strip() and not any(
                    x.get("kind") == "silence" for x in plan["segments"]):
                job.plan = None
                self._transition(job, "skipped")
            else:
                self._transition(job, "prepared" if hold_for_render else "queued")
                if not hold_for_render:
                    self._queue.append(job.id)
            self._cv.notify_all()
            return job.snapshot()

    def submit_deferred(
        self, prepare: Callable[[], tuple[dict[str, Any], dict[str, Any]]], *,
        source: str, engine_id: str = "pending", voice_id: str = "pending",
        source_message_id: str | None = None, hold_for_render: bool = False,
        live_translation: bool = False,
    ) -> dict[str, Any]:
        """Reserve stable speech ID; prepare on a separate worker.

        The prepare callable returns (processed speech plan, validated TTS args).
        It must not expose raw chat through public job metadata.
        """
        if not callable(prepare):
            raise InputError("prepare must be callable")
        if not isinstance(source, str) or not 1 <= len(source) <= 80:
            raise InputError("invalid deferred speech source")
        if not isinstance(engine_id, str) or not isinstance(voice_id, str):
            raise InputError("invalid engine or voice")
        if source_message_id is not None and (
            not isinstance(source_message_id, str)
            or not 1 <= len(source_message_id) <= 128
        ):
            raise InputError("source_message_id must be 1–128 characters")
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
                display_text="", engine_id=engine_id, voice_id=voice_id,
                plan=None, render_args={}, prepare=prepare,
                hold_for_render=hold_for_render,
            )
            self._jobs[job.id] = job
            if key is not None:
                self._dedupe[key] = job.id
            self._transition(job, "preparing")
            if live_translation:
                self._translation_queue.append(job.id)
                self._start_translations()
            else:
                self._prepare_queue.append(job.id)
            self._cv.notify_all()
            return job.snapshot()

    def set_translation_limits(self, limit: int, minimum: int) -> None:
        if type(limit) is not int or type(minimum) is not int or not 1 <= minimum <= limit:
            raise ValueError("invalid live translation limits")
        with self._cv:
            self._translation_limit = limit
            self._translation_minimum = minimum
            self._start_translations()

    def _cancel_translation_timer(self) -> None:
        if self._translation_timer is not None:
            self._translation_timer.cancel()
            self._translation_timer = None

    def _wake_translations(self) -> None:
        with self._cv:
            if self._translation_timer is threading.current_thread():
                self._translation_timer = None
                self._start_translations()

    def _start_translations(self) -> None:
        # Called with the coordinator lock held. Count an in-flight call
        # until it actually returns, even if the browser has cancelled it.
        if (self._closed or not self._translation_queue
                or len(self._translation_workers) >= self._translation_limit):
            self._cancel_translation_timer()
            return
        if self._translation_workers and len(self._translation_queue) < self._translation_minimum:
            oldest = self._jobs[self._translation_queue[0]]
            remaining = TRANSLATION_GATHER_SECONDS - (time.monotonic() - oldest.created_mono)
            if remaining > 0:
                if self._translation_timer is None:
                    timer = threading.Timer(remaining, self._wake_translations)
                    timer.daemon = True
                    self._translation_timer = timer
                    timer.start()
                return
        # Flush an idle lane or a tail that has reached its deadline.
        self._cancel_translation_timer()
        while self._translation_queue and len(self._translation_workers) < self._translation_limit:
            job = self._jobs.get(self._translation_queue.popleft())
            if job is None or job.state != "preparing" or job.prepare is None:
                continue
            worker = threading.Thread(
                target=self._work_translate, args=(job, job.prepare),
                name="voxweavetts-live-translation", daemon=True,
            )
            self._translation_workers.add(worker)
            try:
                worker.start()
            except RuntimeError:
                self._translation_workers.remove(worker)
                job.prepare = None
                self._transition(job, "failed", error="AI speech preparation failed")

    def _work_translate(self, job: _Job, callback: Callable) -> None:
        try:
            self._prepare_job(job, callback)
        finally:
            with self._cv:
                self._translation_workers.remove(threading.current_thread())
                self._start_translations()

    def _work_prepare(self) -> None:
        while True:
            with self._cv:
                while not self._prepare_queue and not self._closed:
                    self._cv.wait()
                if self._closed:
                    return
                job = self._jobs.get(self._prepare_queue.popleft())
                if job is None or job.state != "preparing" or job.prepare is None:
                    continue
                callback = job.prepare
            self._prepare_job(job, callback)

    def _prepare_job(self, job: _Job, callback: Callable) -> None:
        with self._cv:
            if self._closed or job.state != "preparing":
                return
        try:
            plan, arguments = callback()
            if (not isinstance(plan, dict) or not isinstance(plan.get("segments"), list)
                    or not isinstance(arguments, dict)
                    or not isinstance(arguments.get("engine_id"), str)
                    or not isinstance(arguments.get("voice_id"), str)):
                raise ValueError("invalid prepared speech data")
            with self._cv:
                if job.state != "preparing" or self._closed:
                    return
                job.plan = plan
                job.render_args = dict(arguments)
                job.prepare = None
                job.engine_id = arguments["engine_id"]
                job.voice_id = arguments["voice_id"]
                job.display_text = plan["display_text"]
                if not plan.get("spoken_text", "").strip() and not any(
                        x.get("kind") == "silence" for x in plan["segments"]):
                    job.plan = None
                    self._transition(job, "skipped")
                else:
                    self._transition(job, "prepared" if job.hold_for_render else "queued")
                    if not job.hold_for_render:
                        self._queue.append(job.id)
                self._cv.notify_all()
        except Exception:
            # Never expose AI errors or unfiltered text from tools, models,
            # reference files, or the original message through job events.
            with self._cv:
                if job.state == "preparing":
                    job.prepare = None
                    self._transition(job, "failed", error="AI speech preparation failed")

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
                # Resolve exactly the TTS language spans and chunks after AI,
                # replacement and pronunciation processing. Keep them private
                # even after the mutable speech plan is released.
                from .tts_model_inputs import collect_model_inputs
                model_inputs = collect_model_inputs(
                    plan, {"engine_id": job.engine_id,
                           "voice_id": job.voice_id, **arguments}
                )
                with self._cv:
                    if job.state == "cancelled" or self._closed:
                        continue
                    job.model_inputs = model_inputs
                wav, metadata = self._renderer(plan, **arguments)
                outcomes = metadata.get("chunk_success")
                if (isinstance(outcomes, list)
                    and len(outcomes) == len(model_inputs)
                    and all(type(outcome) is bool for outcome in outcomes)):
                    with self._cv:
                        job.model_inputs = [
                            {**item, "success": passed}
                            for item, passed in zip(model_inputs, outcomes)
                        ]
                        job.successful_chunks = sum(outcomes)
                        job.failed_chunks = len(outcomes) - job.successful_chunks
                        job.chunk_outcomes_available = True
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
            except Exception as exc:
                # Never leak model exceptions or user input into public events.
                from .speech import AllChunksFailed
                all_failed = isinstance(exc, AllChunksFailed)
                with self._cv:
                    if job.state != "cancelled":
                        job.plan = None
                        if all_failed:
                            job.successful_chunks = 0
                            job.failed_chunks = len(job.model_inputs or [])
                            job.chunk_outcomes_available = True
                            job.model_inputs = [
                                {**item, "success": False}
                                for item in (job.model_inputs or [])
                            ]
                        self._transition(
                            job, "failed",
                            error=("all_tts_chunks_failed" if all_failed
                                   else "speech rendering failed")
                        )

    def acknowledge_staged_audio(self, job_id: str) -> dict[str, Any]:
        """Browser copied the WAV bytes; it is safe for global job eviction."""
        with self._cv:
            self._prune()
            job = self._jobs.get(job_id)
            if job is None:
                raise JobMissing("unknown speech_id")
            if job.state != "ready":
                raise JobNotReady("staged WAV is not available")
            job.hold_for_render = False
            return job.snapshot()

    def start_render(self, job_id: str) -> dict[str, Any]:
        """Release a prepared speech plan to the single TTS worker.

        Only the explicit browser admission makes a staged job render.
        Idempotent for already rendering/ready; cancelled work stays cancelled.
        """
        with self._cv:
            self._prune()
            job = self._jobs.get(job_id)
            if job is None:
                raise JobMissing("unknown speech_id")
            if job.state == "prepared":
                if job.plan is None:
                    raise JobNotReady("prepared speech plan missing")
                self._transition(job, "queued")
                self._queue.append(job.id)
                self._cv.notify_all()
            elif job.state not in ("queued", "rendering", "ready"):
                raise JobNotReady("job cannot start rendering")
            return job.snapshot()

    def get_prepared_model_inputs(self, job_id: str) -> dict[str, Any]:
        """Explicit PRIVATE inspection after AI + post-rules, before TTS.

        Queued, rendering and ready stages qualify. Unlike snapshot/events,
        this returns the actual speech model-bound text only through the
        same-origin intent-gated HTTP endpoint. Never return source text
        when AI preparation is still running or a job has been skipped.
        """
        with self._cv:
            self._prune()
            job = self._jobs.get(job_id)
            if job is None:
                raise JobMissing("unknown speech_id")
            if job.state not in ("prepared", "queued", "rendering", "ready"):
                raise JobNotReady("speech preparation has not completed")
            if job.model_inputs is None and job.plan is not None:
                from .tts_model_inputs import collect_model_inputs
                job.model_inputs = collect_model_inputs(
                    job.plan,
                    {"engine_id": job.engine_id, "voice_id": job.voice_id,
                     **job.render_args},
                )
            return {
                "speech_id": job.id,
                "state": job.state,
                "available": job.model_inputs is not None,
                "inputs": [dict(item) for item in (job.model_inputs or [])],
            }

    def get_model_inputs(self, job_id: str) -> dict[str, Any]:
        """Private local diagnostic; never part of ordinary speech status."""
        with self._cv:
            self._prune()
            job = self._jobs.get(job_id)
            if job is None:
                raise JobMissing("unknown speech_id")
            if job.state not in ("ready", "failed", "skipped"):
                raise JobNotReady("speech has not finished generating")
            return {
                "speech_id": job.id,
                "state": job.state,
                "available": job.model_inputs is not None,
                "inputs": [dict(row) for row in (job.model_inputs or [])],
                "successful_chunks": job.successful_chunks,
                "failed_chunks": job.failed_chunks,
                "partial_failure": job.successful_chunks > 0 and job.failed_chunks > 0,
            }

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
            # Ready audio remains cancellable to preserve existing UI stop.
            if job.state not in {"cancelled", "failed", "skipped"}:
                if job.audio is not None:
                    self._audio_bytes -= len(job.audio)
                    job.audio = None
                job.plan = None
                job.prepare = None
                job.timeline = None
                job.model_inputs = None
                for pending in (self._prepare_queue, self._translation_queue, self._queue):
                    try:
                        pending.remove(job.id)
                    except ValueError:
                        pass
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
            translation_workers = tuple(self._translation_workers)
            self._translation_queue.clear()
            self._cancel_translation_timer()
            for job in self._jobs.values():
                if job.state not in _TERMINAL:
                    job.plan = None
                    job.prepare = None
                    job.model_inputs = None
                    self._transition(job, "cancelled")
            self._cv.notify_all()
        self._thread.join(timeout=1.0)
        self._prepare_thread.join(timeout=1.0)
        deadline = time.monotonic() + 1.0
        for worker in translation_workers:
            worker.join(timeout=max(0.0, deadline - time.monotonic()))