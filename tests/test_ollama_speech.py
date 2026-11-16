"""Ollama Speech is an opt-in VoiceEngine, not an automatic model download."""
from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from voxweavetts import ollama_speech, speech
from voxweavetts.processing import process_text


def wav_bytes(pcm: bytes = b"\x02\x04"*1200) -> bytes:
    output=io.BytesIO()
    with wave.open(output,"wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24000)
        stream.writeframes(pcm)
    return output.getvalue()


class Reply:
    def __init__(self, body: bytes):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size=None):
        return self.body if size is None else self.body[:size]


class OllamaSpeechScaffoldTests(unittest.TestCase):
    def test_disabled_engine_is_registered_but_unavailable_without_network(self):
        with patch.object(ollama_speech, "CONFIG_FILE", Path("not-existing-ollama-speech.json")):
            with patch.object(ollama_speech, "urlopen") as request:
                info=speech.get_engine_info("ollama-speech")
        self.assertEqual(info.language,"en")
        self.assertFalse(info.assets_ready)
        self.assertFalse(info.runtime_ready)
        self.assertFalse(info.capabilities["speed"])
        self.assertFalse(info.capabilities["voice_cloning"])
        self.assertEqual(info.commercial_status,"review_required")
        request.assert_not_called()

    def test_private_lan_ollama_config_is_opt_in_and_rejects_public_urls(self):
        for base in ("http://127.0.0.1:11434", "http://localhost:11434",
                     "http://192.168.0.2:11434"):
            value=ollama_speech.validate_config({
                "enabled":True, "model":"phonon", "base_url":base,
                "voice":"Zoey","language":"en",
            })
            self.assertTrue(value["enabled"])
            self.assertEqual(value["model"],"phonon")
        for url in ("https://example.com","http://example.com:11434",
                    "http://8.8.8.8:11434","http://localhost:11434/a",
                    "http://username:secret@localhost:11434"):
            with self.subTest(url=url),self.assertRaises(ValueError):
                ollama_speech.validate_config({
                    "enabled":True,"model":"phonon","base_url":url})
        with self.assertRaises(ValueError):
            ollama_speech.validate_config({"enabled":True,"model":""})
        with self.assertRaises(ValueError):
            ollama_speech.validate_config({"enabled":True,"model":"phonon",
                                          "unexpected_key":"x"})

    def test_optional_multilingual_model_requires_explicit_language_metadata(self):
        from voxweavetts.language_routes import voice_languages
        config = ollama_speech.validate_config({
            "enabled": True, "model": "local-speech",
            "language": "multi", "supported_languages": ["en", "th"],
        })
        with patch.object(ollama_speech, "load_config", return_value=config), \
             patch.object(ollama_speech, "probe", return_value=(True, True, ("default",))):
            info = ollama_speech.descriptor()
            self.assertEqual(info.supported_languages, ("en", "th"))
            # Probe can confirm speech support, but does not discover languages.
            from voxweavetts.speech import refresh_engine_registry
            refresh_engine_registry()
            try:
                self.assertEqual(voice_languages("ollama-speech", "default"),
                                 {"en", "th"})
            finally:
                refresh_engine_registry()
        for bad in (["multi"], ["th", "th"], ["xx"], "en"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ollama_speech.validate_config({
                    "language": "multi", "supported_languages": bad,
                })

    def test_config_is_portable_local_and_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path=Path(directory)/"settings.json"
            with patch.object(ollama_speech,"CONFIG_FILE",config_path):
                self.assertFalse(ollama_speech.load_config()["enabled"])
                config_path.write_text(json.dumps({
                    "enabled":True, "model":"phonon", "voice":"Zoey",
                    "language":"en"},ensure_ascii=False),encoding="utf-8")
                self.assertEqual(ollama_speech.load_config()["voice"],"Zoey")
                config_path.write_text('{"enabled":true,"model":"x","extra":1}',
                                       encoding="utf-8")
                self.assertFalse(ollama_speech.load_config()["enabled"])
                with self.assertRaises(ValueError):
                    ollama_speech.load_config(strict=True)

    def test_probe_uses_metadata_only_no_pull_or_generate(self):
        cfg=ollama_speech.validate_config({
            "enabled":True,"model":"phonon:latest","voice":"Zoey"})
        visited=[]
        def respond(req, timeout=None):
            address=req if isinstance(req,str) else req.full_url
            visited.append((address,getattr(req,"data",None)))
            if address.endswith("/api/tags"):
                return Reply(b'{"models":[{"name":"phonon:latest"}]}')
            if address.endswith("/api/show"):
                self.assertEqual(json.loads(req.data)["model"],"phonon:latest")
                return Reply(b'{"capabilities":["speech"],"voices":["Zoey","Easton"]}')
            raise AssertionError("no other network calls should occur")
        with patch.object(ollama_speech,"urlopen",side_effect=respond):
            self.assertEqual(ollama_speech.probe(cfg),(True,True,("Zoey","Easton")))
        self.assertEqual([url.split("/")[-1] for url,_ in visited],["tags","show"])

    def test_full_wav_roundtrip_through_existing_subtitle_renderer(self):
        cfg=ollama_speech.validate_config({
            "enabled":True,"model":"phonon","voice":"Zoey","language":"en"})
        pcm=b"\x04\x02"*1200
        visited=[]
        def respond(req, timeout=None):
            address=req.full_url
            visited.append(address)
            if address.endswith("/api/tags"):
                return Reply(b'{"models":[{"name":"phonon:latest"}]}')
            if address.endswith("/api/show"):
                return Reply(b'{"capabilities":["speech"],"voices":["Zoey"]}')
            if address.endswith("/v1/audio/speech"):
                payload=json.loads(req.data)
                self.assertEqual(payload,{
                    "model":"phonon","voice":"Zoey","input":"Hello!",
                    "response_format":"wav",
                })
                self.assertNotIn("speed",payload)
                self.assertNotIn("instructions",payload)
                return Reply(wav_bytes(pcm))
            raise AssertionError("unexpected network access: "+address)
        with patch.object(ollama_speech,"load_config",return_value=cfg),\
             patch.object(ollama_speech,"urlopen",side_effect=respond):
            audio,meta=speech.render_wav(
                process_text("Hello!"),engine_id="ollama-speech",
                voice_id="Zoey",speed=1.0)
        with wave.open(io.BytesIO(audio),"rb") as result:
            self.assertEqual(result.getframerate(),24000)
            self.assertEqual(result.readframes(1200),pcm)
        self.assertEqual(meta["engine_id"],"ollama-speech")
        self.assertTrue(any(address.endswith("/v1/audio/speech") for address in visited))

    def test_ollama_streaming_wav_header_with_unknown_size_is_readable(self):
        # Ollama emits the RIFF/data header before the stream's frame count
        # is known. Both size fields can legitimately be 0xffffffff.
        pcm=bytes((4,6))*2000
        content=bytearray(wav_bytes(pcm))
        self.assertEqual(content[0:4],b"RIFF")
        self.assertEqual(content[36:40],b"data")
        content[4:8]=bytes((255,))*4
        content[40:44]=bytes((255,))*4
        self.assertEqual(ollama_speech.decode_wav_pcm(bytes(content)),pcm)

    def test_rejects_bad_wav_wrong_format_and_speed(self):
        for payload in (b"not wav",b'{"error":"not supported"}',b"",wav_bytes()[:12]):
            with self.subTest(payload=payload[:12]),self.assertRaises(speech.SpeechFailure):
                ollama_speech.decode_wav_pcm(payload)
        output=io.BytesIO()
        with wave.open(output,"wb") as writer:
            writer.setnchannels(2);writer.setsampwidth(2);writer.setframerate(44100)
            writer.writeframes(b"\0"*600)
        with self.assertRaises(speech.SpeechFailure):
            ollama_speech.decode_wav_pcm(output.getvalue())
        engine=ollama_speech.OllamaSpeechEngine()
        with self.assertRaises(speech.EngineUnavailable),patch.object(
                ollama_speech,"urlopen") as network:
            engine.generate("Hello",1.2)
        network.assert_not_called()

    def test_missing_model_never_generates_or_downloads(self):
        cfg=ollama_speech.validate_config({
            "enabled":True,"model":"phonon","voice":"default"})
        with patch.object(ollama_speech,"load_config",return_value=cfg),\
             patch.object(ollama_speech,"probe",return_value=(False,False,())),\
             patch.object(ollama_speech,"urlopen") as network:
            with self.assertRaises(speech.EngineUnavailable):
                ollama_speech.OllamaSpeechEngine().generate("Hello",1.0)
            network.assert_not_called()


if __name__=="__main__":
    unittest.main()
