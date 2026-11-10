"""Future custom TTS engines can be installed without changing core modules."""
import io
import struct
import unittest
import wave
from unittest.mock import patch

from voxweavetts.engine_contract import (
    ADAPTER_API_VERSION, EngineInfo, EngineRegistry,
)
from voxweavetts.processing import InputError, process_text
from voxweavetts import speech


class OwnEngine:
    id = "my-thai-engine"
    sample_rate = 24000

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def generate(self, text: str, speed: float) -> bytes:
        return struct.pack("<h", self.seed % 4000 + 1200) * 1200


def describe_own_engine():
    return EngineInfo(
        id="my-thai-engine", label="My trained Thai model",
        language="th", voice_id="my_voice", sample_rate=24000,
        assets_ready=True, runtime_ready=True,
        capabilities={"speech": True, "speed": True, "voice_cloning": False},
    )


class RegistryContractTests(unittest.TestCase):
    def test_register_custom_engine_without_model_dependency(self):
        registry = EngineRegistry()
        registry.register(
            "my-thai-engine",
            describe=describe_own_engine,
            create=lambda seed: OwnEngine(seed),
        )
        self.assertEqual(registry.list()[0].as_dict()["adapter_api_version"], 1)
        self.assertEqual(registry.get("my-thai-engine").commercial_status, "review_required")
        self.assertEqual(registry.create("my-thai-engine", 27).seed, 27)
        with self.assertRaises(ValueError):
            registry.register("my-thai-engine", describe=describe_own_engine,
                              create=lambda seed: OwnEngine(seed))
        with self.assertRaises(InputError):
            registry.get("not-found")

    def test_own_engine_uses_existing_processor_and_renderer(self):
        registry = EngineRegistry()
        registry.register("my-thai-engine", describe=describe_own_engine,
                          create=lambda seed: OwnEngine(seed))
        plan = process_text(
            "อมตะ คำลับ",
            rules=[{"match": "คำลับ", "mode": "silence", "silence_ms": 400}],
            pronunciations={"อมตะ": "อะ มะ ตะ"},
        )
        with patch.object(speech, "_REGISTRY", registry):
            wav, meta = speech.render_wav(
                plan, engine_id="my-thai-engine", voice_id="my_voice", seed=88
            )
        with wave.open(io.BytesIO(wav)) as f:
            self.assertEqual(f.getframerate(), 24000)
            self.assertEqual(f.getnframes(), 1200 + 9600)
        self.assertEqual(meta["engine_id"], "my-thai-engine")
        self.assertEqual(meta["segments"][1]["display_text"], "***")
        self.assertNotIn("คำลับ", str(meta))
        self.assertEqual(plan["display_text"], "อมตะ ***")
        self.assertIn("อะ มะ ตะ", plan["spoken_text"])

    def test_reject_invalid_descriptors_and_wrong_pcm_contract(self):
        for engine_id in ("", "Invalid_CAP", "strange/../", "foo space"):
            with self.assertRaises(ValueError):
                EngineRegistry().register(
                    engine_id, describe=describe_own_engine,
                    create=lambda seed: OwnEngine(seed),
                )
        registry = EngineRegistry()
        registry.register(
            "my-thai-engine",
            describe=describe_own_engine,
            create=lambda seed: OwnEngine(seed),
        )
        with self.assertRaises(ValueError):
            registry.register(
                "my-thai-engine",
                describe=describe_own_engine,
                create=lambda seed: OwnEngine(seed),
            )
        bad_version = EngineRegistry()
        bad_version.register(
            "my-thai-engine",
            describe=lambda: EngineInfo(
                id="my-thai-engine", label="test", language="th", voice_id="v",
                sample_rate=24000, assets_ready=True, runtime_ready=True,
                capabilities={}, adapter_api_version=ADAPTER_API_VERSION + 1,
            ),
            create=lambda seed: OwnEngine(seed),
        )
        with self.assertRaises(ValueError):
            bad_version.list()
        wrong_id = EngineRegistry()
        wrong_id.register(
            "my-thai-engine", describe=describe_own_engine,
            create=lambda seed: type(
                "Wrong", (), {"id": "wrong", "sample_rate": 24000,
                              "generate": lambda self,t,s: b"\x00\x00"}
            )(),
        )
        with self.assertRaises(ValueError):
            wrong_id.create("my-thai-engine", 1)


if __name__ == "__main__":
    unittest.main()
