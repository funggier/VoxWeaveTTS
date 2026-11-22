"""Enumerate and play PCM on a named Windows output endpoint.

PortAudio via the optional sounddevice package is used only for computer
output. Resolve the *name*, not a transient numeric device index, each time.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

from .live_audio import decode_wav


def available_outputs() -> list[dict[str, Any]]:
    devices = [{"id": "default", "label": "Windows default output", "api": "system"}]
    if os.name != "nt":
        return devices
    try:
        import sounddevice as sd
        apis = sd.query_hostapis()
        seen = set()
        for info in sd.query_devices():
            api = apis[info["hostapi"]]["name"]
            if api != "Windows WASAPI" or info["max_output_channels"] < 1:
                continue
            label = info["name"]
            device_id = "wasapi:" + label
            if device_id in seen:
                continue
            seen.add(device_id)
            devices.append({"id": device_id, "label": label, "api": api})
    except (ImportError, OSError, ValueError):
        pass
    return devices


class WindowsDeviceOutput:
    def play(self, wav: bytes, duration_ms: int, stop: threading.Event,
             progress: Any, device_id: str = "default") -> bool:
        if os.name != "nt":
            raise OSError("Windows sound output unavailable")
        try:
            import sounddevice as sd
        except ImportError:
            if device_id != "default":
                raise OSError("sounddevice is required for named output devices")
            from .computer_runtime import WindowsWaveOutput
            return WindowsWaveOutput().play(wav, duration_ms, stop, progress)

        rate, channels, pcm = decode_wav(wav)
        index: int | None = None
        if device_id != "default":
            if not device_id.startswith("wasapi:"):
                raise ValueError("invalid output device")
            wanted = device_id[len("wasapi:"):]
            apis = sd.query_hostapis()
            for idx, info in enumerate(sd.query_devices()):
                if (info["name"] == wanted and info["max_output_channels"] >= channels
                    and apis[info["hostapi"]]["name"] == "Windows WASAPI"):
                    index = idx
                    break
            if index is None:
                raise OSError("selected audio device is no longer connected")
        sample_bytes = channels * 2
        frame_count = len(pcm) // sample_bytes
        block_frames = max(1, rate // 20)
        with sd.RawOutputStream(samplerate=rate, channels=channels,
                                dtype="int16", device=index) as stream:
            for frame in range(0, frame_count, block_frames):
                if stop.is_set():
                    return False
                end = min(frame + block_frames, frame_count)
                stream.write(pcm[frame * sample_bytes:end * sample_bytes])
                progress(min(duration_ms, round(end * 1000 / rate)))
        return not stop.is_set()
