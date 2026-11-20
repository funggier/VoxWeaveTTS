"""Self-contained Model Worker protocol v1 for v4 .vwmodel packages.

The package ships this implementation and its pinned dependencies. No imports
from VoxWeaveTTS Core. Each backend config resides in plugin/adapter.json,
so Core only needs to know the stable JSONL protocol, not specific model APIs.

This plugin is an example of writing v4 adapters, not an assertion of rights
to redistribute any model checkpoints or third-party runtime wheels.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import redirect_stdout
import json
import math
import os
import sys
from pathlib import Path

PROTOCOL = 1
MAX_REQUEST = 20_000
MAX_TEXT = 5_000
MAX_PCM = 32_000_000
SUPER_LANGS = {
    "ar", "bg", "hr", "cs", "da", "nl", "en", "et", "fi", "fr", "de",
    "el", "hi", "hu", "id", "it", "ja", "ko", "lv", "lt", "pl", "pt",
    "ro", "ru", "sk", "sl", "es", "sv", "tr", "uk", "vi",
}
KOKORO_LANGS = {
    "a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi",
    "i": "it", "j": "ja", "p": "pt-br",
}


def pcm16(values):
    import numpy as np
    arr = np.asarray(values, dtype=np.float32)
    if arr.ndim != 1 or not arr.size or not np.isfinite(arr).all():
        raise ValueError("invalid model audio")
    return (np.clip(arr, -1, 1) * 32767).astype("<i2").tobytes()


class ModelWorker:
    def __init__(self, root: Path):
        self.root = root
        descriptor = json.loads((root / "plugin" / "adapter.json").read_text("utf-8"))
        if not isinstance(descriptor, dict) or set(descriptor) != {"backend", "voices", "sample_rate"}:
            raise ValueError("invalid worker adapter config")
        self.backend = descriptor["backend"]
        self.voices = set(descriptor["voices"])
        self.rate = descriptor["sample_rate"]
        self.assets = root / "assets"
        self.native = None
        self.selected = None
        self.japanese = None

    def synthesize(self, text: str, voice: str, speed: float, seed: int) -> bytes:
        if voice not in self.voices or not 0.1 <= speed <= 5 or not 0 <= seed <= 2147483647:
            raise ValueError("invalid TTS controls")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise ValueError("invalid speech input")
        match self.backend:
            case "makham-paradee-onnx-v1":
                from pythaitts.pretrained.makham.paradee_tts import MakHamTTSParadee
                if self.native is None:
                    self.native = MakHamTTSParadee(
                        model_path=self.assets / "paradee_thai_int8.onnx",
                        config_path=self.assets / "config.json", intra_op_threads=4, speed=1.0)
                self.native.speed = speed
                return pcm16(self.native.generate(text))
            case "fastthaig2p-kokoro-v1":
                import onnxruntime as ort
                from pythaitts.pretrained.fastthaig2p.tts import TTS
                if self.native is None or self.selected != seed:
                    ort.set_seed(seed)
                    self.native = TTS(
                        model_path=self.assets / "kokoro_thai.onnx",
                        voicepack_path=self.assets / ("voices/" + voice + ".npy"),
                        config_path=self.assets / "config.json",
                        device="cpu", intra_op_threads=4, speed=1.0)
                    self.selected = seed
                self.native.speed = speed
                return pcm16(self.native.generate(text))
            case "vachana-onnx-v1":
                from vachanatts.voice import Voice
                from vachanatts.config import SpeechConfig
                if self.native is None or self.selected != voice:
                    self.native = Voice.load(
                        model_path=self.assets / "voices" / (voice + ".onnx"),
                        config_path=self.assets / "speaker_config.json", use_cuda=False)
                    if int(self.native.config.sample_rate) != self.rate:
                        raise ValueError("voice sample rate mismatch")
                    self.selected = voice
                config = SpeechConfig(length_scale=1.0 / speed,
                                      noise_scale=0.667, noise_w_scale=0.8)
                result = b"".join(chunk.audio_int16_bytes
                                  for chunk in self.native.synthesize(text, config))
                if not result:
                    raise ValueError("empty Vachana audio")
                return result
            case "kokoro-onnx-v1":
                from kokoro_onnx import Kokoro
                if self.native is None:
                    self.native = Kokoro(
                        str(self.assets / "kokoro-v1.0.int8.onnx"),
                        str(self.assets / "voices-v1.0.bin"))
                lang = KOKORO_LANGS.get(voice[0])
                if not lang:
                    raise ValueError("unsupported Kokoro language")
                if voice[0] == "j":
                    # misaki 0.9+ may install an empty full-unidic wrapper.
                    # Prefer the actual local UniDic Lite dictionary, offline.
                    try:
                        import unidic
                        import unidic_lite
                        if (not (Path(unidic.DICDIR) / "mecabrc").is_file()
                                and (Path(unidic_lite.DICDIR) / "mecabrc").is_file()):
                            unidic.DICDIR = unidic_lite.DICDIR
                    except ImportError:
                        pass
                    if self.japanese is None:
                        from misaki import ja
                        self.japanese = ja.JAG2P()
                    phonemes, _ = self.japanese(text)
                    audio, rate = self.native.create(
                        phonemes, voice=voice, speed=speed, lang="ja", is_phonemes=True)
                else:
                    audio, rate = self.native.create(
                        text, voice=voice, speed=speed, lang=lang)
                if rate != self.rate:
                    raise ValueError("Kokoro sample rate mismatch")
                return pcm16(audio)
            case "sherpa-melo-zh-v1" | "sherpa-supertonic-v1":
                import sherpa_onnx as sherpa
                if self.native is None:
                    if self.backend == "sherpa-melo-zh-v1":
                        model = sherpa.OfflineTtsModelConfig(
                            vits=sherpa.OfflineTtsVitsModelConfig(
                                model=str(self.assets / "model.onnx"),
                                lexicon=str(self.assets / "lexicon.txt"),
                                tokens=str(self.assets / "tokens.txt")),
                            num_threads=2, provider="cpu")
                    else:
                        model = sherpa.OfflineTtsModelConfig(
                            supertonic=sherpa.OfflineTtsSupertonicModelConfig(
                                duration_predictor=str(self.assets / "duration_predictor.int8.onnx"),
                                text_encoder=str(self.assets / "text_encoder.int8.onnx"),
                                vector_estimator=str(self.assets / "vector_estimator.int8.onnx"),
                                vocoder=str(self.assets / "vocoder.int8.onnx"),
                                tts_json=str(self.assets / "tts.json"),
                                unicode_indexer=str(self.assets / "unicode_indexer.bin"),
                                voice_style=str(self.assets / "voice.bin")),
                            num_threads=2, provider="cpu")
                    config = sherpa.OfflineTtsConfig(model=model)
                    if not config.validate():
                        raise ValueError("invalid sherpa model configuration")
                    self.native = sherpa.OfflineTts(config)
                if self.backend == "sherpa-melo-zh-v1":
                    audio = self.native.generate(text, 0, speed)
                else:
                    lang, _, sid = voice.partition("_s")
                    if lang not in SUPER_LANGS or sid not in ("0", "1"):
                        raise ValueError("invalid Supertonic voice")
                    config = sherpa.GenerationConfig()
                    config.sid = int(sid)
                    config.speed = speed
                    config.num_steps = 4
                    config.extra = {"lang": lang}
                    audio = self.native.generate(text, config)
                if audio.sample_rate != self.rate:
                    raise ValueError("sherpa sample rate mismatch")
                return pcm16(audio.samples)
            case "wayu-nc-v1":
                os.environ.setdefault("OMP_NUM_THREADS", "2")
                os.environ.setdefault("MKL_NUM_THREADS", "2")
                import torch
                torch.set_num_threads(2)
                try:
                    torch.set_num_interop_threads(1)
                except RuntimeError:
                    pass
                from wayu_tts import ThaiTTS
                import numpy as np
                if self.native is None:
                    self.native = ThaiTTS.from_pretrained(self.assets, device="cpu")
                    if self.native.sample_rate != self.rate:
                        raise ValueError("Wayu sample rate mismatch")
                audio = self.native(text, voice=voice, speed=speed, seed=seed)
                return pcm16(np.asarray(audio, dtype=np.float32))
            case _:
                raise ValueError("this v4 plugin does not implement the declared model")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    arguments = parser.parse_args()
    root = Path(arguments.model_dir)
    worker = ModelWorker(root)
    for line in sys.stdin:
        request_id = None
        try:
            if len(line) > MAX_REQUEST or not line.endswith("\n"):
                raise ValueError("oversized JSONL request")
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("invalid request")
            request_id = item.get("request_id")
            if (item.get("version") != PROTOCOL or item.get("method") != "synthesize"
                or type(request_id) is not int or request_id < 1):
                raise ValueError("invalid TTS worker protocol")
            text = item["text"]
            voice = item["voice_id"]
            if not isinstance(voice, str) or voice not in worker.voices:
                raise ValueError("unknown voice ID")
            # Third-party ML progress must never pollute the JSONL stdout.
            with redirect_stdout(sys.stderr):
                audio = worker.synthesize(text, voice, float(item["speed"]), int(item["seed"]))
            if not audio or len(audio) > MAX_PCM or len(audio) % 2:
                raise ValueError("invalid PCM16 output")
            response = {
                "version": PROTOCOL, "request_id": request_id, "ok": True,
                "sample_rate": worker.rate, "pcm16_b64": base64.b64encode(audio).decode("ascii")}
        except (Exception, MemoryError) as exc:
            detail = str(exc).lower()
            exhausted = isinstance(exc, MemoryError) or "out of memory" in detail or "1455" in detail
            print("v4 engine worker:", type(exc).__name__, file=sys.stderr)
            response = {"version": PROTOCOL, "request_id": request_id,
                        "ok": False,
                        "error": "resource_exhausted" if exhausted else "synthesis_failure"}
        sys.stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
