"""M2M100 uses structured application metadata, never JSON text as model input."""
from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from voxweavetts.ai_processing import DEFAULTS, process_ai, validate_settings
from voxweavetts.m2m_pipeline import (
    MAX_SEGMENT_CHARS, ambiguous_han_source, infer_source_language,
    plan_translation, split_preserving_text, translate_structured,
)


def settings(**extra):
    return validate_settings({
        **DEFAULTS, "enabled": True, "engine": "m2m100", "operation": "translate",
        "auto_detect": False, "translation_mode": "whole_message",
        "source_language": "en", "target_language": "th",
        **extra,
    })


class M2MStructuredTranslationTests(unittest.TestCase):
    def test_segment_planning_exact_roundtrip_for_multilingual_punctuation(self):
        inputs = [
            "Hello?  This is a second sentence.\nAnother!",
            "こんにちは、世界。" * 70,
            ("First long passage with punctuation! " * 40).rstrip(),
            "สวัสดีครับ " * 100,
            "x" * 1000,
            "Hello\n\nWorld",
        ]
        for example in inputs:
            with self.subTest(example=example[:20]):
                segments = split_preserving_text(example)
                self.assertEqual("".join(segments), example)
                self.assertTrue(all(0 < len(x) <= MAX_SEGMENT_CHARS for x in segments))
                self.assertLessEqual(len(segments), 48)
        with self.assertRaisesRegex(ValueError,"too many"):
            split_preserving_text("X"*500, limit=32, max_segments=4)

    def test_explicit_language_source_override_and_no_json_in_model_call(self):
        messages=[]
        input_text="Hello there!   How are you?"
        def translate(text, config, context):
            messages.append((text, config["source_language"], config["target_language"],
                             context))
            return "สวัสดีค่ะ?" if "Hello" in text else "คุณเป็นอย่างไร?"
        output=translate_structured(input_text, settings(), translate, [])
        self.assertEqual(output, "สวัสดีค่ะ?")
        self.assertTrue(messages)
        self.assertEqual(messages[0][0], input_text)
        self.assertEqual(messages[0][1:3], ("en","th"))
        self.assertNotIn('"text"', messages[0][0])
        self.assertEqual(messages[0][3], [])

    def test_long_message_splits_into_bounded_requests_and_preserves_spacing(self):
        source=("Cats are sleeping in the morning.  "*16).rstrip()
        received=[]
        def translate(chunk, cfg, _context):
            received.append(chunk)
            return "แมวกำลังนอน" + ("." if chunk.endswith(".") else "")
        result=process_ai(source,settings(),model_call=translate)
        self.assertEqual(result["status"],"processed")
        self.assertGreater(len(received),2)
        self.assertTrue(all(len(s)<=MAX_SEGMENT_CHARS for s in received))
        self.assertNotIn('{"text"', " ".join(received))
        self.assertTrue(result["text"].count("แมว")>=2)

    def test_script_detection_is_conservative_for_han_and_latin(self):
        self.assertEqual(infer_source_language("こんにちは東京"),"ja")
        self.assertEqual(infer_source_language("안녕하세요"),"ko")
        self.assertEqual(infer_source_language("สวัสดี"),"th")
        self.assertEqual(infer_source_language("नमस्ते"),"hi")
        self.assertEqual(infer_source_language("Привет"),"ru")
        self.assertEqual(infer_source_language("Hello!"),"en")
        self.assertTrue(ambiguous_han_source("東京"))
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            infer_source_language("東京")
        self.assertEqual(plan_translation("東京","ja","th").source_language,"ja")
        # Explicit selection is authoritative even if script resembles Chinese.
        self.assertEqual(plan_translation("東京","zh","th").source_language,"zh")

    def test_han_only_auto_never_tries_incorrect_language_or_silent_skip(self):
        calls=[]
        for target in ("zh","ja","th"):
            with self.subTest(target=target):
                result=process_ai("東京", settings(
                    source_language="auto",target_language=target,
                    auto_detect=True),model_call=lambda *args:calls.append(args) or "x")
                self.assertEqual(result["status"],"fallback")
                self.assertEqual(result["text"],"東京")
                self.assertIn("ambiguous",result["warning"])
        self.assertEqual(calls, [])

    def test_explicit_language_lets_han_only_translate(self):
        requests=[]
        result=process_ai("東京",settings(source_language="ja", target_language="th",
                                          auto_detect=True),
                           model_call=lambda text,params,context:requests.append(
                               (text,params["source_language"])) or "โตเกียว")
        self.assertEqual(result["status"],"processed")
        self.assertEqual(requests,[("東京","ja")])
        self.assertEqual(result["text"],"โตเกียว")

    def test_wrong_script_fallback_and_bypass_setting(self):
        source="What is your name?"
        for bypass in (False,True):
            result=process_ai(source, settings(
                translation_bypass_validation=bypass,
                fallback="filtered"),
                model_call=lambda *_:"আপনার নাম কী?")
            with self.subTest(bypass=bypass):
                if bypass:
                    self.assertEqual(result["status"],"processed")
                    self.assertEqual(result["text"],"আপনার নাম কী?")
                else:
                    self.assertEqual(result["status"],"fallback")
                    self.assertEqual(result["text"],source)
                    self.assertIn("target language script",result["warning"])
        result=process_ai(source, settings(fallback="skip"),
                          model_call=lambda *_:"Japanese Chinese Japanese Chinese")
        self.assertEqual(result["status"],"skipped_on_error")
        self.assertEqual(result["text"],"")

    def test_same_source_target_does_not_invoke_model(self):
        calls=[]
        result=process_ai("สวัสดี",settings(source_language="th",target_language="th",
                              auto_detect=False),model_call=lambda *args:calls.append(args))
        self.assertEqual(result["text"],"สวัสดี")
        self.assertEqual(calls,[])

    def test_real_adapter_refuses_tokenizer_truncation_and_forces_target_id(self):
        from voxweavetts.ai_engine_registry import M2M100Adapter
        class FakeTokenizer:
            def __init__(self, length):
                self.length=length
                self.src_lang=None
                self.truncation=None
            def __call__(self, text, **kwargs):
                self.truncation=kwargs.get("truncation")
                return {"input_ids":SimpleNamespace(shape=(1,self.length))}
            def get_lang_id(self, language):
                self.language=language
                return 42
            def batch_decode(self, tokens, **kwargs):
                return ["คุณชื่ออะไร?"]
        class FakeModel:
            def __init__(self):
                self.options=None
            def generate(self, **kwargs):
                self.options=kwargs
                return [[123]]
        with (patch("voxweavetts.ai_engine_registry.m2m_info",
                    return_value=SimpleNamespace(
                        assets_ready=True,runtime_ready=True)),
              patch("voxweavetts.universal_model_packages.native_translation_packages",
                    return_value=[({"package_id":"v2-native-test","version":"1.0.0"},
                                   Path("unused-model-folder"))]),
              # The actual Portable runtime routes to an isolated worker if
              # optional Torch/Transformers imports are absent. This test
              # deliberately exercises the trusted inline adapter using a
              # mocked tokenizer/model rather than the worker lifecycle.
              patch("voxweavetts.ai_engine_registry.find_spec",
                    return_value=SimpleNamespace()),
              patch("voxweavetts.ai_engine_registry._loaded_m2m") as load):
            for length in (512,513):
                with self.subTest(tokens=length):
                    tok=FakeTokenizer(length)
                    model=FakeModel()
                    load.return_value=(tok,model)
                    if length>512:
                        with self.assertRaisesRegex(ValueError, "512 source tokens"):
                            M2M100Adapter().process("What is your name?",settings(),[],inline_worker=True)
                        self.assertIsNone(model.options)
                    else:
                        output=M2M100Adapter().process("What is your name?",settings(),[],inline_worker=True)
                        self.assertEqual(output,"คุณชื่ออะไร?")
                        self.assertEqual(model.options["forced_bos_token_id"],42)
                        self.assertEqual(tok.language,"th")
                    self.assertEqual(tok.truncation,False)
                    self.assertEqual(tok.src_lang,"en")

    def test_unsupported_context_only_data_is_not_sent_to_m2m(self):
        calls=[]
        text="Tell me a secret"
        result=process_ai(text,settings(),model_call=lambda body,cfg,context:
                          calls.append((body,context)) or "กรุณาบอกความลับ")
        self.assertEqual(result["status"],"processed")
        self.assertEqual(calls,[(text,[])])


if __name__=="__main__":
    unittest.main()
