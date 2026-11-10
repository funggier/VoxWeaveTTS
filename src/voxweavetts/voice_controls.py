"""Voice Studio control schema and real audio postprocessing.

The TTS engine owns speech speed. This module only applies independent DSP
after synthesis. FFmpeg/rubberband is optional and never bundled by this source
repository; future portable distributions must audit and bundle legal binaries.
"""
from __future__ import annotations

import array
import math
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

from .processing import InputError

ROOT = Path(__file__).resolve().parents[2]
CONTROL_FIELDS = {
    "gain_db": {"label": "ความดัง", "min": -18.0, "max": 12.0, "step": 0.5, "default": 0.0, "unit": "dB", "kind": "post_dsp"},
    "pitch_semitones": {"label": "ระดับเสียงสูงต่ำ", "min": -4.0, "max": 4.0, "step": 0.25, "default": 0.0, "unit": "semitones", "kind": "post_dsp"},
    "bass_db": {"label": "เสียงทุ้ม", "min": -12.0, "max": 12.0, "step": 0.5, "default": 0.0, "unit": "dB", "kind": "post_dsp"},
    "treble_db": {"label": "เสียงแหลม", "min": -12.0, "max": 12.0, "step": 0.5, "default": 0.0, "unit": "dB", "kind": "post_dsp"},
}
MAX_OUTPUT_PCM_BYTES = 32_000_000


def ffmpeg_path() -> str | None:
    """Search bundled portable runtime first, then a developer system binary."""
    bundled = ROOT / "runtime" / "ffmpeg" / "bin" / "ffmpeg.exe"
    if bundled.is_file():
        return str(bundled)
    return shutil.which("ffmpeg")


def control_schema() -> dict[str, Any]:
    return {
        "speed": {"label": "ความเร็วการพูด", "min": 0.6, "max": 1.5,
                  "step": 0.05, "default": 1.0, "unit": "x", "kind": "engine_native"},
        "post": CONTROL_FIELDS,
        "formant_preserve": {"label": "รักษาเนื้อเสียงเมื่อปรับ Pitch",
                             "kind": "post_dsp", "default": True},
        "ffmpeg_ready": bool(ffmpeg_path()),
        "independent_formant_shift_supported": False,
    }


def validate_controls(value: Any) -> dict[str, float | bool]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise InputError("voice_controls must be an object")
    extras = set(value) - set(CONTROL_FIELDS) - {"formant_preserve"}
    if extras:
        raise InputError("unsupported voice_controls: " + ", ".join(sorted(extras)))
    result: dict[str, float | bool] = {}
    for name, spec in CONTROL_FIELDS.items():
        raw = value.get(name, spec["default"])
        if type(raw) not in (int, float) or not math.isfinite(raw):
            raise InputError(f"{name} must be a finite number")
        value_num = float(raw)
        if not spec["min"] <= value_num <= spec["max"]:
            raise InputError(f"{name} must be between {spec['min']} and {spec['max']}")
        result[name] = value_num
    preserve = value.get("formant_preserve", True)
    if type(preserve) is not bool:
        raise InputError("formant_preserve must be true or false")
    result["formant_preserve"] = preserve
    return result


def _apply_gain(pcm: bytes, gain_db: float) -> bytes:
    if gain_db == 0.0:
        return pcm
    factor = 10.0 ** (gain_db / 20.0)
    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    for idx, sample in enumerate(samples):
        samples[idx] = max(-32768, min(32767, round(sample * factor)))
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def apply_voice_controls(pcm: bytes, sample_rate: int, controls: dict[str, float | bool]) -> bytes:
    """Apply FFmpeg rubberband pitch/formant-mode + EQ, then independent gain.

    Never constructs a shell command from user text. All floats are validated.
    Default settings leave PCM bit-identical (including explicit silence).
    """
    settings = validate_controls(controls)
    if len(pcm) % 2:
        raise InputError("audio is not PCM16")
    pitch = float(settings["pitch_semitones"])
    bass = float(settings["bass_db"])
    treble = float(settings["treble_db"])
    if any(v != 0 for v in (pitch, bass, treble)):
        ffmpeg = ffmpeg_path()
        if not ffmpeg:
            raise InputError("pitch/bass/treble DSP requires FFmpeg with rubberband support")
        filters: list[str] = []
        if pitch:
            ratio = 2 ** (pitch / 12.0)
            mode = "preserved" if settings["formant_preserve"] else "shifted"
            filters.append(f"rubberband=pitch={ratio:.9f}:formant={mode}")
        if bass:
            filters.append(f"lowshelf=f=180:g={bass:.3f}")
        if treble:
            filters.append(f"highshelf=f=3500:g={treble:.3f}")
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "s16le", "-ar", str(sample_rate), "-ac", "1", "-i", "pipe:0",
            "-af", ",".join(filters), "-f", "s16le", "-acodec", "pcm_s16le",
            "-ar", str(sample_rate), "-ac", "1", "pipe:1",
        ]
        try:
            completed = subprocess.run(command, input=pcm, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InputError("audio DSP unavailable or timed out") from exc
        if completed.returncode or not completed.stdout or len(completed.stdout) % 2:
            raise InputError("audio DSP failed; verify FFmpeg has rubberband support")
        pcm = completed.stdout
    if len(pcm) > MAX_OUTPUT_PCM_BYTES:
        raise InputError("postprocessed audio exceeds size limit")
    return _apply_gain(pcm, float(settings["gain_db"]))
