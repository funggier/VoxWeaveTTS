"""Regression coverage for Windows PCM16 WASAPI output negotiation.

A Realtek USB DAC can accept 192 kHz stereo but reject 24 kHz mono; model
WAV content must be resampled/remixed without changing the original WAV.
"""
from __future__ import annotations

from io import BytesIO
import math
import sys
import types
import wave

import pytest

import voxweavetts.audio_devices as audio_devices


def _make_wav(sample_rate=24000, channels=1, seconds=0.1):
    from array import array
    size = int(sample_rate * seconds)
    samples = array("h")
    for i in range(size):
        value = round(12000 * math.sin(i * 2 * math.pi * 480 / sample_rate))
        samples.extend([value] * channels)
    if sys.byteorder != "little":
        samples.byteswap()
    handle = BytesIO()
    with wave.open(handle, "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(samples.tobytes())
    return handle.getvalue()


class FakeSoundDevice:
    def __init__(self):
        self.opened = []
        self.written = bytearray()
        self.device = [{"name": "DAC", "max_output_channels": 2,
                        "hostapi": 0, "default_samplerate": 192000.0}]

    def query_devices(self, device=None, kind=None):
        if device is None and kind is None:
            return self.device
        return self.device[0]

    def query_hostapis(self):
        return [{"name": "Windows WASAPI"}]

    def RawOutputStream(self, *, samplerate, channels, dtype, device, **kwargs):
        if (samplerate, channels, device) != (192000, 2, 0):
            raise RuntimeError("Invalid sample rate")
        self.opened.append((samplerate, channels, device, kwargs))
        outer = self

        class OutputStream:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def write(self, data):
                outer.written.extend(data)

        return OutputStream()


def test_auto_resamples_24000_mono_to_192000_stereo(monkeypatch):
    fake = FakeSoundDevice()
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    monkeypatch.setattr(audio_devices, "os", types.SimpleNamespace(name="nt"))
    original = _make_wav()
    import threading
    done = []
    output = audio_devices.WindowsDeviceOutput()
    assert output.play(original, 100, threading.Event(), done.append,
                       "wasapi:DAC", settings={"sample_rate": "auto",
                                              "channels": "auto", "buffer_ms": 50})
    assert fake.opened[0][0:3] == (192000, 2, 0)
    assert 2 * 2 * 19200 - 12 <= len(fake.written) <= 2 * 2 * 19200 + 12
    assert done and done[-1] == 100
    assert output.last_format["sample_rate"] == 192000
    assert output.last_format["channels"] == 2


def test_manual_bad_rate_reports_diagnostic(monkeypatch):
    fake = FakeSoundDevice()
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    monkeypatch.setattr(audio_devices, "os", types.SimpleNamespace(name="nt"))
    import threading
    with pytest.raises(OSError, match="24000 Hz"):
        audio_devices.WindowsDeviceOutput().play(
            _make_wav(), 100, threading.Event(), lambda _: None, "wasapi:DAC",
            settings={"sample_rate": 24000, "channels": 2, "buffer_ms": 50},
        )


@pytest.mark.parametrize("settings", [
    {"sample_rate": 500, "channels": "auto", "buffer_ms": 50},
    {"sample_rate": "192000", "channels": "auto", "buffer_ms": 50},
    {"sample_rate": "auto", "channels": 3, "buffer_ms": 50},
    {"sample_rate": "auto", "channels": "auto", "buffer_ms": 7},
    {"sample_rate": "auto", "channels": "auto", "buffer_ms": True},
])
def test_audio_settings_validate_rejects_invalid_values(settings):
    with pytest.raises(ValueError):
        audio_devices.validate_audio_settings(settings)
