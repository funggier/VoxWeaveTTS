"""Engine-neutral audio activity analysis, using Python's standard library only.

This is NOT forced alignment: PCM energy can locate audible activity/gaps,
but cannot determine which Thai word or syllable is being spoken. A future
commercially cleared aligner can implement AudioAlignmentProvider separately.
No waveform, original text, or words are persisted by this module.
"""
from __future__ import annotations

from array import array
import io
import math
import sys
import wave
from typing import Any, Protocol

FRAME_MS = 20
MIN_VOICE_MS = 60
MERGE_GAP_MS = 100
PADDING_MS = 20
MAX_INTERVALS_PER_SEGMENT = 32
BASIS = "pcm16_mono_rms_energy_20ms_heuristic"


class AudioAlignmentProvider(Protocol):
    """Bounded optional post-render provider; neither TTS nor HTTP contract."""

    id: str

    def analyze(
        self, wav: bytes, segments: list[dict[str, Any]],
    ) -> list[list[dict[str, int]]] | None:
        """Return per-segment activity intervals, or None if unsupported."""


class PCMActivityProvider:
    """Detect speech-like energy islands inside generated speech segments.

    Thresholds are relative to each segment, so the result is a signal
    heuristic (it cannot distinguish other sounds/music from speech).
    """
    id = "builtin-pcm16-energy-v1"

    def analyze(
        self, wav: bytes, segments: list[dict[str, Any]],
    ) -> list[list[dict[str, int]]] | None:
        if not isinstance(wav, bytes) or len(wav) < 44:
            return None
        try:
            with wave.open(io.BytesIO(wav), "rb") as reader:
                if (reader.getnchannels() != 1 or reader.getsampwidth() != 2
                        or reader.getcomptype() != "NONE"):
                    return None
                sample_rate = reader.getframerate()
                if not 8000 <= sample_rate <= 96000:
                    return None
                total_frames = reader.getnframes()
                if total_frames <= 0 or total_frames > 16_000_000:
                    return None
                frames_per_bin = max(1, round(sample_rate * FRAME_MS / 1000))
                result: list[list[dict[str, int]]] = []
                for segment in segments:
                    kind=segment.get("kind")
                    start_ms=segment.get("start_ms")
                    end_ms=segment.get("end_ms")
                    if (type(start_ms) is not int or type(end_ms) is not int
                            or not 0 <= start_ms <= end_ms
                            or end_ms > math.ceil(total_frames * 1000 / sample_rate) + 1):
                        return None
                    if kind != "speech":
                        result.append([])
                        continue
                    begin_frame = min(total_frames, round(start_ms * sample_rate / 1000))
                    end_frame = min(total_frames, round(end_ms * sample_rate / 1000))
                    if end_frame <= begin_frame:
                        result.append([])
                        continue
                    reader.setpos(begin_frame)
                    samples = array("h")
                    samples.frombytes(reader.readframes(end_frame-begin_frame))
                    if sys.byteorder != "little":
                        samples.byteswap()
                    bins: list[float] = []
                    for pos in range(0, len(samples), frames_per_bin):
                        # Stride sampling reduces cost; RMS in 16-bit PCM units.
                        piece = samples[pos:pos+frames_per_bin:4]
                        rms = math.sqrt(sum(int(n)*int(n) for n in piece) / len(piece))
                        bins.append(rms)
                    if not bins:
                        result.append([])
                        continue
                    # Relative to real peak plus a conservative absolute
                    # floor: low-level noise alone does not count as speech.
                    threshold = max(300.0, max(bins) * 0.18)
                    active = [x >= threshold for x in bins]
                    runs: list[tuple[int, int]] = []
                    start: int | None = None
                    for index, present in enumerate(active + [False]):
                        if present and start is None:
                            start = index
                        elif not present and start is not None:
                            if (index-start)*FRAME_MS >= MIN_VOICE_MS:
                                runs.append((start, index))
                            start = None
                    # Join gaps shorter than 100ms; then pad by 20ms.
                    merged: list[tuple[int, int]] = []
                    for a, b in runs:
                        if merged and (a-merged[-1][1])*FRAME_MS < MERGE_GAP_MS:
                            merged[-1] = (merged[-1][0], b)
                        else:
                            merged.append((a, b))
                    if len(merged) > MAX_INTERVALS_PER_SEGMENT:
                        # Pathological rapidly alternating energy: use a
                        # single broad activity window rather than huge JSON.
                        merged=[(merged[0][0], merged[-1][1])]
                    intervals: list[dict[str, int]] = []
                    for a, b in merged:
                        left = max(start_ms, start_ms + a*FRAME_MS - PADDING_MS)
                        right = min(end_ms, start_ms + b*FRAME_MS + PADDING_MS)
                        if intervals and left <= intervals[-1]["end_ms"]:
                            intervals[-1]["end_ms"] = max(right, intervals[-1]["end_ms"])
                        elif right > left:
                            intervals.append({"start_ms":left,"end_ms":right})
                    result.append(intervals)
                return result
        except (OSError, EOFError, ValueError, wave.Error, OverflowError):
            return None
