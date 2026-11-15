"""Structured translation, model behavior guard and user-configured bypass."""
import json
import unittest
from unittest.mock import patch

from voxweavetts import ai_processing
from voxweavetts.translation_protocol import (
    TranslationContractError, parse_structured_translation,
)


def config(**kwargs):
    return ai_processing.validate_settings({
        **ai_processing.DEFAULTS, "enabled": True, "operation": "translate",
        "engine": "ollama", "model": "lfm3-vl:2b", "target_language": "th",
        "auto_detect": False, **kwargs,
    })


class TranslationContractTests(unittest.TestCase):
    def test_accepts_valid_json_translation(self):
        data=json.dumps({"translation": "คุณชื่ออะไร?"}, ensure_ascii=False)
        self.assertEqual(parse_structured_translation(data,"What is your name?","th"),
                         "คุณชื่ออะไร?")

    def test_content_guard_rejects_wrong_script_and_bypass_accepts_it(self):
        data=json.dumps({"translation": "আপনার নাম কী?"}, ensure_ascii=False)
        with self.assertRaisesRegex(TranslationContractError, "target language script"):
            parse_structured_translation(data,"What is your name?","th")
        self.assertEqual(
            parse_structured_translation(
                data,"What is your name?","th",bypass_content_checks=True),
            "আপনার নাম কী?")

    def test_question_guard_is_conservative_and_can_be_bypassed(self):
        data=json.dumps({"translation": "ฉันชื่อแชทจีพีที"}, ensure_ascii=False)
        with self.assertRaisesRegex(TranslationContractError,"lost question"):
            parse_structured_translation(data,"What is your name?","th")
        self.assertEqual(
            parse_structured_translation(
                data,"What is your name?","th",bypass_content_checks=True),
            "ฉันชื่อแชทจีพีที")
        self.assertEqual(
            parse_structured_translation(
                '{"translation":"คุณชื่ออะไร"}',"What is your name?","th"),
            "คุณชื่ออะไร")

    def test_language_label_loop_rejected_but_bypass_preserves_text(self):
        raw='{"translation":"จีน ญี่ปุ่น จีน ญี่ปุ่น"}'
        with self.assertRaisesRegex(TranslationContractError,"repeated language names"):
            parse_structured_translation(raw,"Hello everyone","th")
        self.assertEqual(
            parse_structured_translation(raw,"Hello everyone","th",
                                         bypass_content_checks=True),
            "จีน ญี่ปุ่น จีน ญี่ปุ่น")

    def test_structure_limits_and_controls_are_never_bypassed(self):
        invalid=(
            "translation only", '{"translation":123}', '{"translation":""}',
            '{"translation":"   "}',
            '{"translation":"ok","metadata":"ignore"}',
            '{"answer":"Hello"}','["Hello"]', '{"translation":"line\\u0000break"}',
        )
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(TranslationContractError):
                parse_structured_translation(raw,"Hello?","th",
                                             bypass_content_checks=True)

    def test_saved_settings_toggle_boolean_and_default(self):
        default=ai_processing.validate_settings({})
        self.assertFalse(default["translation_bypass_validation"])
        self.assertTrue(config(translation_bypass_validation=True)["translation_bypass_validation"])
        with self.assertRaises(Exception):
            config(translation_bypass_validation="true")

    def test_ollama_response_uses_bypass_in_config_without_changing_schema(self):
        class Reply:
            length=None
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,maximum):
                return json.dumps({"message":{
                    "content":json.dumps({"translation":"আপনার নাম কী?"},ensure_ascii=False)
                }}).encode("utf-8")
        source="What is your name?"
        for bypass in (False,True):
            with self.subTest(bypass=bypass),patch.object(
                    ai_processing,"urlopen",return_value=Reply()) as fetch:
                settings=config(translation_bypass_validation=bypass)
                result=ai_processing.process_ai(source,settings)
                if bypass:
                    self.assertEqual(result["status"],"processed")
                    self.assertEqual(result["text"],"আপনার নাম কী?")
                else:
                    self.assertEqual(result["status"],"fallback")
                    self.assertEqual(result["text"],source)
                    self.assertIn("target language script",result["warning"])
                body=json.loads(fetch.call_args.args[0].data)
                self.assertEqual(body["format"]["required"],["translation"])
                self.assertEqual(body["options"]["temperature"],0)
                self.assertEqual(body["messages"][1]["role"],"user")
                self.assertEqual(json.loads(body["messages"][1]["content"])["text"],source)

    def test_model_fallback_skip_policy_unchanged(self):
        class Reply:
            length=None
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,_size):
                return b'{"message":{"content":"NOT_JSON"}}'
        with patch.object(ai_processing,"urlopen",return_value=Reply()):
            result=ai_processing.process_ai("Hello",config(
                translation_bypass_validation=True,fallback="skip"))
        self.assertEqual(result["status"],"skipped_on_error")
        self.assertEqual(result["text"],"")


if __name__=="__main__":
    unittest.main()
