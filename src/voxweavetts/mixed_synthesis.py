"""Optional language-per-span rendering into ONE WAV and ONE subtitle timeline.

Every chunk uses the registered local voice adapter and its own saved
language-specific speed/seed/DSP settings. The ordinary renderer is reused per
chunk, so source queues, audio controls and trusted model validation remain
consistent. No text is dropped or sent to translation from this module.
"""
from __future__ import annotations

import io
import wave
from typing import Any


def resample_pcm16(pcm: bytes, source_rate: int, output_rate: int) -> bytes:
    if source_rate == output_rate or not pcm:
        return pcm
    try:
        # Windows Portable currently embeds CPython 3.11 (mono PCM16).
        import audioop
        return audioop.ratecv(pcm, 2, 1, source_rate, output_rate, None)[0]
    except ImportError:
        # Python 3.13+ no longer ships audioop, and our CI intentionally
        # tests without optional third-party libraries. Linear PCM16 mono
        # interpolation needs only the Python standard library.
        from array import array
        from sys import byteorder
        if len(pcm) % 2:
            raise ValueError("partial PCM16 sample cannot be resampled")
        samples = array("h")
        samples.frombytes(pcm)
        if byteorder != "little":
            samples.byteswap()
        count = max(1, round(len(samples) * output_rate / source_rate))
        converted = array("h")
        for index in range(count):
            whole, remainder = divmod(index * source_rate, output_rate)
            if whole >= len(samples) - 1:
                value = samples[-1]
            else:
                value = round((samples[whole] * (output_rate - remainder)
                              + samples[whole + 1] * remainder) / output_rate)
            converted.append(max(-32768, min(32767, value)))
        if byteorder != "little":
            converted.byteswap()
        return converted.tobytes()


def render_mixed_language_wav(
    plan: dict[str, Any], *, speed: float, voice_id: str, seed: int,
    engine_id: str, voice_controls: dict[str, Any] | None,
    language_voice_routes: dict[str, dict[str, Any]], engine=None,
) -> tuple[bytes, dict[str, Any]]:
    from . import speech
    from .mixed_language import split_language_spans
    from .language_routes import LANGUAGES
    from .processing import InputError
    from .voice_controls import validate_controls

    speech.validate_speech_request(plan, speed, voice_id, engine_id)
    seed = speech.validate_seed(seed)
    controls = validate_controls(voice_controls)
    if (not isinstance(language_voice_routes, dict)
            or len(language_voice_routes) > len(LANGUAGES)
            or any(lang not in LANGUAGES or not isinstance(route, dict)
                   or not {"engine_id", "voice_id"} <= set(route)
                   for lang, route in language_voice_routes.items())):
        raise InputError("invalid mixed-language model routes")
    default_info = speech.get_engine_info(engine_id)
    if not (default_info.assets_ready and default_info.runtime_ready):
        raise speech.EngineUnavailable("default TTS engine is unavailable")

    # Private instances per request: no model/voice state leaks between jobs.
    engines = {(engine_id, seed): engine} if engine is not None else {}
    groups: list[list[tuple[bytes, int] | int]] = []
    sample_rates = [default_info.sample_rate]
    used: list[dict[str, str]] = []
    count = 0
    for segment in plan["segments"]:
        kind = segment["kind"]
        group: list[tuple[bytes, int] | int] = []
        if kind == "speech":
            for span in split_language_spans(segment["spoken_text"]):
                if not span.text.strip():
                    continue
                count += 1
                if count > 96:
                    raise InputError("too many language switches in one speech job")
                route = language_voice_routes.get(span.language)
                selected_engine = route["engine_id"] if route else engine_id
                selected_voice = route["voice_id"] if route else voice_id
                selected_speed = route.get("speed", speed) if route else speed
                selected_seed = speech.validate_seed(route.get("seed", seed)) if route else seed
                selected_controls = (route.get("voice_controls", controls)
                                     if route else controls)
                info = speech.get_engine_info(selected_engine)
                if not (info.assets_ready and info.runtime_ready):
                    raise speech.EngineUnavailable(
                        "configured language TTS model is not installed or unavailable")
                key = (selected_engine, selected_seed)
                if key not in engines:
                    engines[key] = speech.create_voice_engine(selected_engine, selected_seed)
                chunk_plan = {
                    "source": plan.get("source", "manual"),
                    "spoken_text": span.text, "display_text": "",
                    "segments": [{
                        "kind": "speech", "spoken_text": span.text,
                        "display_text": "", "source_start": 0,
                        "source_end": len(span.text), "silence_ms": 0,
                    }],
                }
                wav, metadata = speech.render_wav(
                    chunk_plan, engine_id=selected_engine, voice_id=selected_voice,
                    speed=selected_speed, seed=selected_seed,
                    voice_controls=selected_controls, engine=engines[key],
                )
                with wave.open(io.BytesIO(wav), "rb") as reader:
                    if reader.getnchannels() != 1 or reader.getsampwidth() != 2:
                        raise speech.SpeechFailure(
                            "language TTS generated unsupported WAV format")
                    rate = reader.getframerate()
                    audio = reader.readframes(reader.getnframes())
                if rate != info.sample_rate or rate != metadata["sample_rate"]:
                    raise speech.SpeechFailure("language TTS WAV sample rate mismatch")
                sample_rates.append(rate)
                group.append((audio, rate))
                voice_spec = {"language": span.language,
                              "engine_id": selected_engine, "voice_id": selected_voice}
                if voice_spec not in used:
                    used.append(voice_spec)
        elif kind == "silence":
            group.append(int(segment["silence_ms"]))
        elif kind != "skip":
            raise speech.SpeechFailure("unknown speech plan segment")
        groups.append(group)

    # Select the highest actual source rate to preserve model fidelity.
    output_rate = max(sample_rates)
    if output_rate < 8_000 or output_rate > 96_000:
        raise speech.SpeechFailure("unsupported mixed-language output rate")
    buffer = io.BytesIO()
    timeline: list[dict[str, Any]] = []
    frames = 0
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(output_rate)
        for segment, group in zip(plan["segments"], groups):
            start = frames
            for part in group:
                if isinstance(part, int):
                    pcm = b"\x00\x00" * round(output_rate * part / 1000)
                else:
                    pcm = resample_pcm16(part[0], part[1], output_rate)
                if len(pcm) % 2:
                    raise speech.SpeechFailure("mixed-language TTS emitted a partial sample")
                frames += len(pcm) // 2
                if frames * 2 > speech.MAX_WAV_BYTES:
                    raise InputError("generated audio exceeds size limit")
                writer.writeframesraw(pcm)
            # Keep original protected display text, skip/silence order, and
            # output one subtitle interval per original plan segment.
            timeline.append({
                "kind": segment["kind"], "display_text": segment["display_text"],
                "source_start": segment["source_start"],
                "source_end": segment["source_end"],
                "start_ms": round(start * 1000 / output_rate),
                "end_ms": round(frames * 1000 / output_rate),
            })
        writer.writeframes(b"")
    if frames == 0:
        raise InputError("no speech or silence to render")
    return buffer.getvalue(), {
        "engine_id": engine_id, "voice_id": voice_id,
        "seed": seed if default_info.capabilities.get("seed_control") else None,
        "voice_controls": controls, "sample_rate": output_rate,
        "duration_ms": round(frames * 1000 / output_rate),
        "segments": timeline, "mixed_language": True, "voices_used": used,
    }
