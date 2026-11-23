"""Windows WASAPI device discovery, PCM16 conversion and playback.

Windows endpoints may accept only their native sample rate (e.g. a USB DAC
at 192000 Hz stereo). The original model WAV is kept unchanged. Selection,
conversion and playback happen only within the machine-owned output worker.
"""
from __future__ import annotations

from array import array
import os
import sys
import threading
import time
from typing import Any

from .live_audio import decode_wav

DEFAULT_AUDIO_SETTINGS = {
    "sample_rate": "auto",  # Use original WAV rate if accepted, else native DAC rate.
    "channels": "auto",     # Prefer source mono, try stereo when endpoint rejects mono.
    "buffer_ms": 50,        # Stream PCM in 50 ms frames.
}
COMMON_RATES = (48000, 44100, 96000, 192000, 24000, 22050, 32000, 16000,
                88200, 176400, 11025, 8000)
BUFFER_CHOICES = (20, 50, 100, 200)
_CACHE_LOCK = threading.Lock()
_CACHE_TIME = 0.0
_CACHE_OUTPUTS: list[dict[str, Any]] | None = None


def validate_audio_settings(settings: Any) -> dict[str, Any]:
    if not isinstance(settings, dict) or set(settings) != set(DEFAULT_AUDIO_SETTINGS):
        raise ValueError("audio settings must contain sample_rate, channels and buffer_ms")
    sample_rate = settings["sample_rate"]
    if sample_rate != "auto" and (
        type(sample_rate) is not int or not 8000 <= sample_rate <= 192000
    ):
        raise ValueError("sample_rate must be auto or 8000..192000 Hz")
    channels = settings["channels"]
    if channels != "auto" and (type(channels) is not int or channels not in (1, 2)):
        raise ValueError("channels must be auto, 1 or 2")
    buffer_ms = settings["buffer_ms"]
    if type(buffer_ms) is not int or buffer_ms not in BUFFER_CHOICES:
        raise ValueError("buffer_ms must be 20, 50, 100 or 200")
    return {"sample_rate": sample_rate, "channels": channels, "buffer_ms": buffer_ms}


def _query_outputs() -> list[dict[str, Any]]:
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
            devices.append({"id": device_id, "label": label, "api": api,
                            "native_rate": round(info["default_samplerate"]),
                            "max_channels": info["max_output_channels"]})
    except (ImportError, OSError, ValueError):
        pass
    return devices


def available_outputs() -> list[dict[str, Any]]:
    global _CACHE_TIME, _CACHE_OUTPUTS
    with _CACHE_LOCK:
        if _CACHE_OUTPUTS is None or time.monotonic() - _CACHE_TIME > 5:
            _CACHE_OUTPUTS = _query_outputs()
            _CACHE_TIME = time.monotonic()
        return [dict(item) for item in _CACHE_OUTPUTS]


def _resample_pcm16(source: bytes, source_rate: int, target_rate: int) -> bytes:
    """Linear interpolation, rate-accurate at both ends; no external dependency.

    TTS models primarily upsample from 16–48 kHz to high-rate DAC devices.
    Process mono before channel duplication to save CPU and memory.
    """
    if source_rate == target_rate:
        return source
    if not (8000 <= source_rate <= 192000 and 8000 <= target_rate <= 192000):
        raise ValueError("unsupported PCM16 rate")
    samples = array("h")
    samples.frombytes(source)
    if sys.byteorder != "little":
        samples.byteswap()
    count = len(samples)
    if not count:
        return b""
    total = max(1, round(count * target_rate / source_rate))
    if total * 2 > 100_000_000:
        raise ValueError("resampled audio would exceed memory limit")
    result = array("h", [0]) * total
    for position in range(total):
        before, fraction = divmod(position * source_rate, target_rate)
        if before >= count - 1:
            result[position] = samples[-1]
        else:
            left, right = samples[before], samples[before + 1]
            result[position] = left + (right - left) * fraction // target_rate
    if sys.byteorder != "little":
        result.byteswap()
    return result.tobytes()


def _stereo_pcm16(mono: bytes) -> bytes:
    values = array("h")
    values.frombytes(mono)
    if sys.byteorder != "little":
        values.byteswap()
    stereo = array("h")
    for sample in values:
        stereo.extend((sample, sample))
    if sys.byteorder != "little":
        stereo.byteswap()
    return stereo.tobytes()


def _stream_candidates(rate: int, source_channels: int, audio: dict[str, Any],
                       native_rate: int, max_channels: int):
    requested_rate = audio["sample_rate"]
    rates = [requested_rate] if requested_rate != "auto" else [
        rate, native_rate, *COMMON_RATES
    ]
    chosen_channels = audio["channels"]
    channels = [chosen_channels] if chosen_channels != "auto" else [
        source_channels, 2 if source_channels == 1 else 1
    ]
    seen = set()
    for rate_option in rates:
        if not isinstance(rate_option, int) or not 8000 <= rate_option <= 192000:
            continue
        for channel_option in channels:
            if channel_option > max_channels or (rate_option, channel_option) in seen:
                continue
            seen.add((rate_option, channel_option))
            yield rate_option, channel_option


class WindowsDeviceOutput:
    def __init__(self):
        self.last_format: dict[str, Any] | None = None

    def play(self, wav: bytes, duration_ms: int, stop: threading.Event,
             progress: Any, device_id: str = "default",
             *, settings: dict[str, Any] | None = None) -> bool:
        if os.name != "nt":
            raise OSError("Windows sound output unavailable")
        audio = validate_audio_settings(
            DEFAULT_AUDIO_SETTINGS if settings is None else settings
        )
        try:
            import sounddevice as sd
        except ImportError:
            if device_id != "default":
                raise OSError("sounddevice is required for named output devices")
            # WinMM owns its stream format. It cannot promise the explicitly
            # selected rate/channels, so never ignore a manual request.
            if audio["sample_rate"] != "auto" or audio["channels"] != "auto":
                raise OSError("manual Sample Rate/channels require sounddevice; "
                              "the WinMM fallback cannot force the selected format")
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
                if (info["name"] == wanted and info["max_output_channels"] >= 1
                        and apis[info["hostapi"]]["name"] == "Windows WASAPI"):
                    index = idx
                    break
            if index is None:
                raise OSError("Selected audio device is no longer connected")
        info = sd.query_devices(index, "output") if index is not None else sd.query_devices(kind="output")
        native = round(info["default_samplerate"])
        max_channels = int(info["max_output_channels"])
        attempted: list[str] = []
        stream = None
        output_rate = 0
        output_channels = 0
        for candidate_rate, candidate_channels in _stream_candidates(
                rate, channels, audio, native, max_channels):
            if stop.is_set():
                return False
            try:
                stream = sd.RawOutputStream(
                    samplerate=candidate_rate, channels=candidate_channels,
                    dtype="int16", device=index,
                )
                output_rate, output_channels = candidate_rate, candidate_channels
                break
            except Exception as exc:
                attempted.append(f"{candidate_rate}Hz/{candidate_channels}ch:{type(exc).__name__}")
                if audio["sample_rate"] != "auto" and audio["channels"] != "auto":
                    break
        if stream is None:
            selected_rate = audio["sample_rate"]
            diagnostic = (str(selected_rate) if selected_rate != "auto"
                          else f"source {rate} / native {native}")
            raise OSError(
                f"Audio device rejected {diagnostic} Hz "
                f"(channels={audio['channels']}); "
                "choose Sample Rate: Auto or the device's native rate. "
                f"Formats checked: {', '.join(attempted[:8])}"
            )

        with stream:
            # All model WAVs are downmixed to PCM16 mono by decode_wav().
            pcm = _resample_pcm16(pcm, rate, output_rate)
            if output_channels == 2:
                pcm = _stereo_pcm16(pcm)
            self.last_format = {
                "sample_rate": output_rate,
                "channels": output_channels,
                "source_rate": rate,
                "source_channels": channels,
                "buffer_ms": audio["buffer_ms"],
                "device": device_id,
                "requested_rate": audio["sample_rate"],
                "requested_channels": audio["channels"],
                "resampled": output_rate != rate,
                "channel_converted": output_channels != channels,
            }
            sample_bytes = output_channels * 2
            frame_count = len(pcm) // sample_bytes
            block_frames = max(1, output_rate * audio["buffer_ms"] // 1000)
            for frame in range(0, frame_count, block_frames):
                if stop.is_set():
                    return False
                end = min(frame + block_frames, frame_count)
                stream.write(pcm[frame * sample_bytes:end * sample_bytes])
                progress(min(duration_ms, round(end * 1000 / output_rate)))
        return not stop.is_set()