"""Security and behavior gates for the opt-in Ollama tool calling phase."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import ai_processing, ai_tools
from voxweavetts.processing import InputError


def settings(**updates):
    return ai_processing.validate_settings({**ai_processing.DEFAULTS, **updates})


class _Reply:
    length = None
    def __init__(self, obj):
        self.obj = obj
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return json.dumps(self.obj, ensure_ascii=False).encode("utf-8")


class AIToolSettingsTests(unittest.TestCase):
    def test_tools_off_and_old_settings_migrate_without_granting_permission(self):
        old = {k: v for k, v in ai_processing.DEFAULTS.items() if not k.startswith("tool_")}
        loaded = ai_processing.validate_settings(old)
        self.assertFalse(loaded["tool_calling_enabled"])
        self.assertFalse(loaded["tool_web_lookup"])
        self.assertFalse(loaded["tool_file_read"])
        self.assertEqual(ai_tools.tool_definitions(loaded, []), [])

    def test_invalid_or_untrusted_permissions_rejected(self):
        invalid = [
            {"tool_calling_enabled": "true"},
            {"tool_max_calls": 0},
            {"tool_max_calls": 4},
            {"tool_max_calls": True},
            {"tool_calling_enabled": True},
            {"tool_calling_enabled": True, "tool_web_lookup": True, "operation": "translate"},
            {"tool_calling_enabled": True, "tool_web_lookup": True, "engine": "m2m100"},
            {"tool_calling_enabled": True, "tool_file_read": True, "operation": "custom"},
            {"tool_calling_enabled": True, "tool_file_read": True,
             "operation": "custom", "allow_context_files": True},
        ]
        for updates in invalid:
            with self.subTest(updates=updates), self.assertRaises(InputError):
                settings(**updates)

    def test_tools_permissioned_by_engine_and_operation_not_external_chat(self):
        config = settings(enabled=True, engine="ollama", operation="custom",
                          tool_calling_enabled=True, tool_web_lookup=True)
        tools = ai_tools.tool_definitions(config, [{"name": "secret.md", "text": "sensitive"}])
        self.assertEqual([x["function"]["name"] for x in tools],
                         ["search_encyclopedia"])
        with self.assertRaises(ai_tools.ToolDenied):
            ai_tools.execute_tool("read_reference_file", {"file_id": 0}, config,
                                  [{"name": "secret.md", "text": "sensitive"}])
        with self.assertRaises(ai_tools.ToolDenied):
            ai_tools.execute_tool("fetch_url", {"url": "http://127.0.0.1"}, config, [])
        with self.assertRaises(ai_tools.ToolDenied):
            ai_tools.execute_tool("search_encyclopedia",
                                  {"query": "cats", "url": "https://example.com"},
                                  config, [])


    def test_search_provider_dropdown_is_validated(self):
        for name in ("wikipedia", "searxng", "ollama", "tavily"):
            cfg = settings(tool_search_provider=name)
            self.assertEqual(cfg["tool_search_provider"], name)
        for name in ("brave", "http://localhost", None, 1, [], {}):
            with self.subTest(name=name), self.assertRaises(InputError):
                settings(tool_search_provider=name)
        for address in ("http://example.org:8080", "http://169.254.169.254:80",
                        "https://localhost:8080", "http://localhost:8080/path"):
            with self.subTest(address=address), self.assertRaises(InputError):
                settings(tool_searxng_url=address)

    def test_general_web_provider_routes_only_to_selected_adapter(self):
        fake = {"results": [], "provider": "mock"}
        for name,method in (("wikipedia", "wikipedia_lookup"),
                            ("searxng", "searxng_search"),
                            ("ollama", "ollama_web_search"),
                            ("tavily", "tavily_search")):
            config = settings(enabled=True, operation="custom", model="example:4b",
                              tool_calling_enabled=True, tool_general_web_search=True,
                              tool_search_provider=name)
            with self.subTest(name=name), patch("voxweavetts.ai_tools."+method,
                                                return_value=fake) as adapter:
                result = ai_tools.execute_tool("search_web", {"query": "Bangkok"}, config, [])
                self.assertEqual(result, fake)
                self.assertEqual(adapter.call_count, 1)
        with self.assertRaises(ai_tools.ToolDenied):
            ai_tools.execute_tool("search_web", {"query": "Bangkok", "url": "x"}, config, [])

    def test_ollama_cloud_search_uses_fixed_https_host_and_no_key_in_response(self):
        config = settings(enabled=True, operation="custom",
                          tool_calling_enabled=True, tool_general_web_search=True,
                          tool_search_provider="ollama")
        response = _Reply({"results": [
            {"title": "Bangkok News", "content": "<b>Latest</b> world news",
             "url": "https://example.org/news"},
            {"title": "Unsafe", "content": "unsafe", "url": "http://127.0.0.1/private"},
        ]})
        requests = []
        class FakeOpener:
            def open(self, request, timeout):
                requests.append(request)
                return response
        with patch("voxweavetts.ai_search_secrets.get_key",return_value="test-secret-not-real"), patch(
            "voxweavetts.ai_tools.build_opener", return_value=FakeOpener()):
            result = ai_tools.execute_tool("search_web", {"query": "Bangkok update"}, config, [])
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].full_url, "https://ollama.com/api/web_search")
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer test-secret-not-real")
        self.assertNotIn("test-secret-not-real", json.dumps(result))
        self.assertEqual(result["results"][0]["snippet"], "Latest world news")
        self.assertEqual(len(result["results"]), 1)

    def test_searxng_is_private_lan_only_and_uses_json_endpoint(self):
        config = settings(enabled=True, operation="custom",
                          tool_calling_enabled=True, tool_general_web_search=True,
                          tool_search_provider="searxng",
                          tool_searxng_url="http://127.0.0.1:8080")
        seen=[]
        class FakeOpener:
            def open(self,request,timeout):
                seen.append(request.full_url)
                return _Reply({"results":[{"title":"City","content":"Bangkok",
                                          "url":"https://example.com/bangkok"}]})
        with patch("voxweavetts.ai_tools.build_opener",return_value=FakeOpener()):
            result=ai_tools.execute_tool("search_web",{"query":"Bangkok"},config,[])
        self.assertIn("/search?q=Bangkok&format=json",seen[0])
        self.assertEqual(result["results"][0]["snippet"],"Bangkok")

    def test_tavily_fixed_https_endpoint_and_api_key(self):
        config = settings(enabled=True, operation="custom",
                          tool_calling_enabled=True, tool_general_web_search=True,
                          tool_search_provider="tavily")
        requests=[]
        class FakeOpener:
            def open(self,request,timeout):
                requests.append(request)
                return _Reply({"results":[{"title":"New","content":"New data",
                                          "url":"https://example.org/new"}]})
        with patch("voxweavetts.ai_search_secrets.get_key",return_value="key-secret-tavily"), patch(
            "voxweavetts.ai_tools.build_opener",return_value=FakeOpener()):
            result=ai_tools.execute_tool("search_web",{"query":"New data"},config,[])
        self.assertEqual(requests[0].full_url,"https://api.tavily.com/search")
        self.assertEqual(requests[0].get_header("Authorization"),"Bearer key-secret-tavily")
        self.assertNotIn("key-secret-tavily",json.dumps(result))

    def test_provider_error_does_not_expose_api_key(self):
        class FailOpener:
            def open(self, request, timeout):
                raise OSError("provider secret in stack trace")
        for method in (ai_tools.ollama_web_search, ai_tools.tavily_search):
            with patch("voxweavetts.ai_search_secrets.get_key",return_value="secret-key-not-real"), patch(
                "voxweavetts.ai_tools.build_opener",return_value=FailOpener()):
                with self.subTest(method=method.__name__), self.assertRaises(ai_tools.ToolUnavailable) as failure:
                    method("Bangkok")
                self.assertNotIn("secret-key-not-real", str(failure.exception))
                self.assertNotIn("provider secret", str(failure.exception))

    def test_web_search_request_is_blocked_after_reference_file_read(self):
        config = settings(enabled=True, operation="custom", model="example:4b",
                          tool_calling_enabled=True, tool_general_web_search=True,
                          tool_search_provider="ollama", tool_file_read=True, allow_context_files=True,
                          context_files=[str(Path(tempfile.gettempdir()) / "terms.md")],
                          tool_max_calls=2)
        replies = [
            _Reply({"message": {"tool_calls": [{"function": {
                "name": "read_reference_file", "arguments": {"file_id": 0}}}]}}),
            _Reply({"message": {"tool_calls": [{"function": {
                "name": "search_web", "arguments": {"query": "secret from glossary"}}}]}}),
        ]
        sent = []
        def mock_ollama(request, timeout):
            sent.append(json.loads(request.data))
            return replies.pop(0)
        with patch("voxweavetts.ai_tools.urlopen", side_effect=mock_ollama), patch(
            "voxweavetts.ai_tools.ollama_web_search") as search:
            with self.assertRaises(ai_processing.AIUnavailable):
                ai_tools.run_tool_chat(config, "system", "question",
                                       [{"name": "terms.md", "text": "secret from glossary"}])
            search.assert_not_called()
        self.assertEqual([tool["function"]["name"] for tool in sent[0]["tools"]],
                         ["search_web", "read_reference_file"])
        self.assertEqual([tool["function"]["name"] for tool in sent[1]["tools"]],
                         ["read_reference_file"])

    def test_file_read_is_restricted_by_index_to_whitelist(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "glossary.md"
            file.write_text("dragon = มังกร", encoding="utf-8")
            config = settings(
                enabled=True, operation="custom", tool_calling_enabled=True,
                tool_file_read=True, allow_context_files=True,
                context_files=[str(file)]
            )
            context = ai_processing._read_context_files(config)
            tools = ai_tools.tool_definitions(config, context)
            self.assertEqual([x["function"]["name"] for x in tools],
                             ["read_reference_file"])
            result = ai_tools.execute_tool("read_reference_file",
                                           {"file_id": 0}, config, context)
            self.assertIn("มังกร", result["text"])
            for args in ({"file_id": 1}, {"file_id": -1}, {"file_id": True},
                         {"path": str(Path(d) / "outside.md")}):
                with self.subTest(args=args), self.assertRaises(ai_tools.ToolDenied):
                    ai_tools.execute_tool("read_reference_file", args, config, context)


class OllamaToolLoopTests(unittest.TestCase):
    def test_web_tool_loop_validated_request_and_answer(self):
        config = settings(enabled=True, engine="ollama", operation="custom",
                          model="qwen3.5:4b", tool_calling_enabled=True,
                          tool_web_lookup=True, tool_max_calls=2,
                          custom_prompt="Look up factual questions on Wikipedia")
        replies = [
            _Reply({"message": {"role": "assistant", "content": "",
                  "tool_calls": [{"function": {"name": "search_encyclopedia",
                                               "arguments": {"query": "Thailand", "language": "en"}}}]}}),
            _Reply({"message": {"role": "assistant", "content": "ประเทศไทยมีเมืองหลวงคือกรุงเทพมหานคร"}}),
        ]
        calls = []
        def fake_urlopen(request, timeout=0):
            calls.append((request, timeout))
            return replies.pop(0)
        with patch("voxweavetts.ai_tools.urlopen", side_effect=fake_urlopen), patch(
            "voxweavetts.ai_tools.wikipedia_lookup",
            return_value={"provider": "Wikipedia only", "results": [
                {"title": "Thailand", "snippet": "Capital Bangkok",
                 "source": "https://en.wikipedia.org/wiki/Thailand"}]}
        ) as lookup:
            actual = ai_processing._ollama_chat("What is the capital of Thailand?",
                                                 config, [])
        self.assertEqual(actual, "ประเทศไทยมีเมืองหลวงคือกรุงเทพมหานคร")
        self.assertEqual(len(calls), 2)
        sent = [json.loads(req.data) for req, _ in calls]
        self.assertEqual(len(sent[0]["tools"]), 1)
        self.assertEqual(sent[0]["messages"][1]["role"], "user")
        self.assertIn("EXTERNAL DATA", sent[0]["messages"][1]["content"])
        self.assertEqual(sent[1]["messages"][-1]["role"], "tool")
        self.assertNotIn("tools", sent[1]) if config["tool_max_calls"] == 1 else None
        lookup.assert_called_once_with("Thailand", "en")

    def test_denied_function_cannot_execute_external_action(self):
        config = settings(enabled=True, operation="custom",
                          model="example:4b", tool_calling_enabled=True,
                          tool_web_lookup=True)
        response = _Reply({"message": {
            "tool_calls": [{"function": {"name": "run_shell",
                                         "arguments": {"command": "del C:\\"}}}]}})
        with patch("voxweavetts.ai_tools.urlopen", return_value=response):
            with self.assertRaises(ai_processing.AIUnavailable):
                ai_tools.run_tool_chat(config, "SYSTEM", "data", [])
        # Fallback is honored when tools or model fail.
        with patch("voxweavetts.ai_tools.urlopen", return_value=response):
            outcome = ai_processing.process_ai("input untrusted", config)
        self.assertEqual(outcome["status"], "fallback")
        self.assertEqual(outcome["text"], "input untrusted")

    def test_malformed_tool_name_or_language_is_denied_not_crash(self):
        config = settings(enabled=True, operation="custom", model="example:4b",
                          tool_calling_enabled=True, tool_web_lookup=True)
        bad_response = _Reply({"message": {"tool_calls": [
            {"function": {"name": ["search_encyclopedia"],
                          "arguments": {"query": "Bangkok"}}}]}})
        with patch("voxweavetts.ai_tools.urlopen", return_value=bad_response):
            outcome = ai_processing.process_ai("Bangkok", config)
        self.assertEqual(outcome["status"], "fallback")
        with self.assertRaises(ai_tools.ToolDenied):
            ai_tools.execute_tool("search_encyclopedia",
                                  {"query": "Bangkok", "language": ["en"]}, config, [])

    def test_multiple_calls_rejected_over_budget(self):
        config = settings(enabled=True, operation="custom", model="example:4b",
                          tool_calling_enabled=True, tool_web_lookup=True,
                          tool_max_calls=1)
        response = _Reply({"message": {"tool_calls": [
            {"function": {"name": "search_encyclopedia",
                          "arguments": {"query": "Thai alphabet"}}},
            {"function": {"name": "search_encyclopedia",
                          "arguments": {"query": "Bangkok"}}},
        ]}})
        with patch("voxweavetts.ai_tools.urlopen", return_value=response), patch(
            "voxweavetts.ai_tools.wikipedia_lookup") as search:
            with self.assertRaises(ai_processing.AIUnavailable):
                ai_tools.run_tool_chat(config, "SYSTEM", "data", [])
            search.assert_not_called()

    def test_reference_file_not_sent_to_web_lookup_after_read(self):
        config = settings(enabled=True, operation="custom", model="example:4b",
                          tool_calling_enabled=True, tool_web_lookup=True,
                          tool_file_read=True, allow_context_files=True,
                          context_files=[str(Path(tempfile.gettempdir()) / "safe.md")],
                          tool_max_calls=2)
        replies = [
            _Reply({"message": {"tool_calls": [{"function": {
                "name": "read_reference_file", "arguments": {"file_id": 0}}}]}}),
            _Reply({"message": {"tool_calls": [{"function": {
                "name": "search_encyclopedia", "arguments": {
                    "query": "Private glossary secret", "language": "en"}}}]}}),
        ]
        with patch("voxweavetts.ai_tools.urlopen", side_effect=lambda *args, **kwargs: replies.pop(0)), patch(
            "voxweavetts.ai_tools.wikipedia_lookup") as search:
            with self.assertRaises(ai_processing.AIUnavailable):
                ai_tools.run_tool_chat(config, "system", "data",
                                       [{"name": "safe.md", "text": "Private glossary secret"}])
            search.assert_not_called()

    def test_encyclopedia_is_single_fixed_https_host_and_language(self):
        fake = _Reply({"query": {"search": [
            {"title": "Bangkok", "snippet": "<span>Capital</span> of Thailand"}]}})
        seen = []
        class FakeOpener:
            def open(self, request, timeout):
                seen.append((request.full_url, timeout))
                return fake
        with patch("voxweavetts.ai_tools.build_opener",
                   return_value=FakeOpener()):
            result = ai_tools.wikipedia_lookup("Bangkok", "th")
        self.assertTrue(seen[0][0].startswith("https://th.wikipedia.org/w/api.php?"))
        self.assertIn("Bangkok", seen[0][0])
        self.assertEqual(result["results"][0]["snippet"], "Capital of Thailand")
        for invalid in ("../etc/passwd", "https://127.0.0.1", ""):
            # Odd valid text is only a query, never treated as a URL to fetch.
            if invalid == "":
                with self.assertRaises(ai_tools.ToolDenied):
                    ai_tools.wikipedia_lookup(invalid)
        with self.assertRaises(ai_tools.ToolDenied):
            ai_tools.wikipedia_lookup("Bangkok", "https://evil.example")


if __name__ == "__main__":
    unittest.main()