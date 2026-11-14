"""Windows user-scoped API key storage and secret-free settings contracts."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import ai_search_secrets as secrets
from voxweavetts import ai_processing


class CredentialsTests(unittest.TestCase):
    def test_old_ai_settings_migrate_with_no_search_permission(self):
        old={key:value for key,value in ai_processing.DEFAULTS.items()
             if key not in ("tool_search_provider","tool_searxng_url")}
        current=ai_processing.validate_settings(old)
        self.assertEqual(current["tool_search_provider"],"wikipedia")
        self.assertEqual(current["tool_searxng_url"],"http://127.0.0.1:8080")
        self.assertFalse(current["tool_general_web_search"])
        self.assertNotIn("api_key",current)

    def test_reject_malformed_secrets(self):
        for provider in ("wikipedia","searxng","other",None,[],{}):
            with self.subTest(provider=provider),self.assertRaises(ValueError):
                secrets.get_key(provider)
        for value in ("short", "with spaces", "token\nother", "", None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                secrets.update_key("ollama","save",value)

    @unittest.skipUnless(os.name=="nt","DPAPI persistent encryption requires Windows")
    def test_saved_api_key_is_encrypted_and_not_returned(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(
            secrets,"SECRET_FILE",Path(directory)/"ai-search-secrets.json"),patch.dict(
            os.environ,{"OLLAMA_API_KEY":"","TAVILY_API_KEY":""}):
            plaintext="mock-credential-only-never-send"
            status=secrets.update_key("ollama","save",plaintext)
            self.assertEqual(status,{"ollama":True,"tavily":False})
            raw=secrets.SECRET_FILE.read_text("utf-8")
            self.assertNotIn(plaintext,raw)
            self.assertNotIn("mock-credential-only",raw)
            self.assertEqual(secrets.get_key("ollama"),plaintext)
            self.assertNotIn(plaintext,json.dumps(secrets.key_status()))
            cleared=secrets.update_key("ollama","clear")
            self.assertFalse(cleared["ollama"])
            self.assertEqual(secrets.get_key("ollama"),"")

    def test_environment_credentials_not_written_to_disk(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(
            secrets,"SECRET_FILE",Path(directory)/"secrets.json"),patch.dict(
            os.environ,{"OLLAMA_API_KEY":"provided-by-environment","TAVILY_API_KEY":""}):
            self.assertEqual(secrets.get_key("ollama"),"provided-by-environment")
            self.assertTrue(secrets.key_status()["ollama"])
            self.assertFalse(secrets.SECRET_FILE.exists())


if __name__=="__main__":
    unittest.main()
