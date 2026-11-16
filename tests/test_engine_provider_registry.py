"""New model-provider lifecycle: isolated environments, trust and old-model migration."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from voxweavetts import speech
from voxweavetts.engine_provider_catalog import (
    PROVIDERS, ProviderApprovalError, all_providers,
    approve_provider_folder, provider_for_adapter, provider_for_engine,
)
from voxweavetts.engine_provider_installer import InstallError, install, ready
from voxweavetts.engine_worker_gateway import gateway
from voxweavetts.engine_worker_proxy import ProviderVoiceEngine

ROOT = Path(__file__).resolve().parents[1]


class EngineProviderTests(unittest.TestCase):
    def test_every_legacy_family_has_a_separate_installer_recipe(self):
        expected = {
            "fastthaig2p-kokoro-v1": "pythaitts",
            "vachana-onnx-v1": "vachana",
            "kokoro-onnx-v1": "kokoro",
            "sherpa-supertonic-v1": "sherpa",
            "sherpa-melo-zh-v1": "sherpa",
        }
        for adapter, profile_id in expected.items():
            with self.subTest(adapter=adapter):
                profile = provider_for_adapter(adapter)
                self.assertEqual(profile.id, profile_id)
                self.assertTrue(profile.requirements_path().is_file())
                self.assertEqual(profile.python_path().parent.parent.name, profile_id)
        self.assertEqual(provider_for_engine("fastthaig2p-cpu").id, "pythaitts")
        self.assertEqual(provider_for_engine("makham-paradee-cpu").id, "pythaitts")
        self.assertEqual(provider_for_engine("vachana-cpu").id, "vachana")
        self.assertEqual(provider_for_engine("personal-nc-wayu-paxa-edge-cpu").id, "wayu-nc")

    def test_new_provider_code_requires_explicit_trust_and_hash_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "extensions" / "engine-providers" / "minimal-demo"
            folder.parent.mkdir(parents=True)
            shutil.copytree(ROOT / "examples" / "tts-provider-minimal", folder)
            self.assertNotIn("minimal-demo", all_providers(root))
            with self.assertRaises(ProviderApprovalError):
                approve_provider_folder(folder, root=root)
            approved = approve_provider_folder(folder, root=root, trust_code=True)
            self.assertEqual(approved.driver, "external")
            self.assertIn("minimal-demo", all_providers(root))
            self.assertEqual(
                provider_for_engine("minimal-demo-v1", root=root).id, "minimal-demo")
            # Revoking or changing approved executable content automatically
            # disables the provider until deliberately reviewed again.
            with (folder / "worker.py").open("a", encoding="utf-8") as stream:
                stream.write("\n# modified after approval\n")
            self.assertNotIn("minimal-demo", all_providers(root))

    def test_external_provider_can_declare_shared_bilingual_voices(self):
        from voxweavetts.engine_contract import EngineRegistry
        from voxweavetts.language_routes import voice_languages
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "extensions" / "engine-providers" / "minimal-demo"
            folder.parent.mkdir(parents=True)
            shutil.copytree(ROOT / "examples" / "tts-provider-minimal", folder)
            manifest = json.loads((folder / "provider.json").read_text(encoding="utf-8"))
            manifest["language"] = "th"
            manifest["supported_languages"] = ["th", "en"]
            (folder / "provider.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            provider = approve_provider_folder(folder, root=root, trust_code=True)
            registry = EngineRegistry()
            with patch("voxweavetts.engine_provider_catalog.all_providers",
                       return_value={"minimal-demo": provider}):
                speech._register_external_providers(registry)
            info = registry.get("minimal-demo-v1")
            self.assertEqual(info.supported_languages, ("th", "en"))
            self.assertEqual(info.as_dict()["supported_languages"], ["th", "en"])
            with patch.object(speech, "_REGISTRY", registry):
                self.assertEqual(voice_languages("minimal-demo-v1", "demo"),
                                 {"th", "en"})

    def test_external_provider_can_declare_per_voice_language_map(self):
        from voxweavetts.engine_contract import EngineRegistry
        from voxweavetts.language_routes import voice_languages
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "extensions" / "engine-providers" / "minimal-demo"
            folder.parent.mkdir(parents=True)
            shutil.copytree(ROOT / "examples" / "tts-provider-minimal", folder)
            manifest = json.loads((folder / "provider.json").read_text(encoding="utf-8"))
            manifest["language"] = "multi"
            manifest["voice_language_map"] = {"demo": "en"}
            (folder / "provider.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            provider = approve_provider_folder(folder, root=root, trust_code=True)
            registry = EngineRegistry()
            with patch("voxweavetts.engine_provider_catalog.all_providers",
                       return_value={"minimal-demo": provider}):
                speech._register_external_providers(registry)
            with patch.object(speech, "_REGISTRY", registry):
                self.assertEqual(voice_languages("minimal-demo-v1", "demo"), {"en"})

    def test_external_language_declarations_are_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "extensions" / "engine-providers" / "minimal-demo"
            folder.parent.mkdir(parents=True)
            shutil.copytree(ROOT / "examples" / "tts-provider-minimal", folder)
            original = json.loads((folder / "provider.json").read_text(encoding="utf-8"))
            cases = [
                {"supported_languages": ["en", "en"]},
                {"supported_languages": ["de"]},
                {"supported_languages": ["not-a-code"]},
                {"supported_languages": ["en"], "voice_language_map": {"demo": "en"}},
                {"voice_language_map": {"other": "en"}},
            ]
            for changed in cases:
                with self.subTest(changed=changed):
                    manifest = {**original, **changed}
                    (folder / "provider.json").write_text(
                        json.dumps(manifest), encoding="utf-8")
                    with self.assertRaises(ProviderApprovalError):
                        approve_provider_folder(folder, root=root, trust_code=True)

    def test_installer_rejects_non_catalog_model_dependency_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(InstallError):
                install("../malicious", root=Path(temp))
            self.assertFalse(ready(PROVIDERS["pythaitts"], root=Path(temp)))

    def test_existing_ids_route_through_gateway_proxy_without_renaming(self):
        from voxweavetts.engine_provider_catalog import PROVIDERS
        for engine_id, provider_id in (
            ("fastthaig2p-cpu", "pythaitts"),
            ("makham-paradee-cpu", "pythaitts"),
            ("vachana-cpu", "vachana"),
        ):
            with self.subTest(engine=engine_id):
                with patch("voxweavetts.engine_worker_gateway.EngineWorkerGateway.available",
                           return_value=True):
                    engine = speech.create_voice_engine(engine_id, 100)
                    self.assertIsInstance(engine, ProviderVoiceEngine)
                    self.assertEqual(engine.id, engine_id)
                    self.assertEqual(engine.sample_rate, PROVIDERS[provider_id].sample_rate)

    def test_native_fallback_when_isolated_runtime_not_installed(self):
        with patch("voxweavetts.engine_worker_gateway.EngineWorkerGateway.available",
                   return_value=False):
            engine = speech.create_voice_engine("makham-paradee-cpu", 100)
            self.assertEqual(type(engine).__name__, "MakHamParadeeEngine")

    def test_external_provider_cannot_claim_builtin_engine_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "extensions" / "engine-providers" / "minimal-demo"
            folder.parent.mkdir(parents=True)
            shutil.copytree(ROOT / "examples" / "tts-provider-minimal", folder)
            manifest = json.loads((folder / "provider.json").read_text(encoding="utf-8"))
            manifest["engine_id"] = "fastthaig2p-cpu"
            (folder / "provider.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ProviderApprovalError):
                approve_provider_folder(folder, root=root, trust_code=True)


if __name__ == "__main__":
    unittest.main()
