"""Low-latency PCM broadcast for remote live audio listeners.

No file queue is transferred to listeners. Each subscriber receives only fresh
100 ms PCM16 frames from the current output, with bounded buffers and no replay.
"""
from __future__ import annotations
import array
import sys
from collections import deque
import base64
import json
import threading
import time
import wave
from io import BytesIO
from typing import Any

FRAME_MS = 100
MAX_LISTENERS = 12


def decode_wav(wav_data: bytes) -> tuple[int, int, bytes]:
    with wave.open(BytesIO(wav_data), "rb") as source:
        rate = source.getframerate()
        channels = source.getnchannels()
        bits = source.getsampwidth()
        if (not 8000 <= rate <= 96000 or channels not in (1, 2)
                or bits != 2 or source.getcomptype() != "NONE"):
            raise ValueError("live output requires PCM16 mono/stereo WAV")
        payload = source.readframes(source.getnframes())
    if channels == 2:
        stereo = array.array("h")
        stereo.frombytes(payload)
        if sys.byteorder != "little":
            stereo.byteswap()
        mono = array.array("h", (
            (int(stereo[i]) + int(stereo[i+1])) // 2
            for i in range(0, len(stereo), 2)
        ))
        if sys.byteorder != "little":
            mono.byteswap()
        payload = mono.tobytes()
    return rate, 1, payload


class LiveAudioHub:
    def __init__(self):
        self._lock = threading.RLock()
        self._listeners: set["LiveListener"] = set()
        self._revision = 0

    def subscribe(self) -> "LiveListener":
        with self._lock:
            if len(self._listeners) >= MAX_LISTENERS:
                raise ValueError("too many live audio listeners")
            listener = LiveListener(self)
            self._listeners.add(listener)
            return listener

    def unsubscribe(self, listener: "LiveListener") -> None:
        with self._lock:
            self._listeners.discard(listener)
            listener.close()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._listeners)

    def publish(self, event: str, data: dict[str, Any]) -> None:
        packet = {"event": event, **data}
        with self._lock:
            self._revision += 1
            packet["revision"] = self._revision
            for listener in self._listeners:
                listener.feed(packet)

    def broadcast(self, wav_data: bytes, stop: threading.Event,
                  progress: Any) -> bool:
        rate, _, pcm = decode_wav(wav_data)
        bytes_per_frame = 2
        chunk_size = max(2, rate * FRAME_MS // 1000 * bytes_per_frame)
        actual_duration_ms = int(len(pcm) / (rate * bytes_per_frame) * 1000)
        started = time.monotonic()
        self.publish("begin", {"sample_rate": rate})
        for position in range(0, len(pcm), chunk_size):
            if stop.is_set():
                self.publish("stop", {})
                return False
            # Keep producer close to wall clock even with no connected viewers.
            expected = (position / (rate * bytes_per_frame))
            delay = started + expected - time.monotonic()
            if delay > 0 and stop.wait(delay):
                self.publish("stop", {})
                return False
            chunk = pcm[position:position+chunk_size]
            self.publish("pcm", {
                "sample_rate": rate,
                "data": base64.b64encode(chunk).decode("ascii"),
            })
            progress(min(actual_duration_ms, int((position + len(chunk)) / (rate * bytes_per_frame) * 1000)))
        remaining = started + len(pcm) / (rate * bytes_per_frame) - time.monotonic()
        if remaining > 0 and stop.wait(remaining):
            self.publish("stop", {})
            return False
        self.publish("end", {})
        return True


class LiveListener:
    def __init__(self, parent: LiveAudioHub):
        self.parent = parent
        self._cv = threading.Condition()
        self._buffer: deque[dict[str, Any]] = deque(maxlen=8)
        self._closed = False

    def feed(self, packet: dict[str, Any]) -> None:
        with self._cv:
            if self._closed:
                return
            # Slow/mobile clients skip stale PCM instead of delayed playback.
            if len(self._buffer) == self._buffer.maxlen:
                self._buffer.clear()
                self._buffer.append({"event": "reset"})
            self._buffer.append(packet)
            self._cv.notify()

    def take(self, timeout: float = 3.0) -> dict[str, Any] | None:
        with self._cv:
            if not self._buffer and not self._closed:
                self._cv.wait(timeout)
            return self._buffer.popleft() if self._buffer else None

    def close(self) -> None:
        with self._cv:
            self._closed = True
            self._cv.notify_all()
