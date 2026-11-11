"""Private local Save As endpoint and native file-writer regression tests."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voxweavetts.profile_export import (
    SaveDialogBusy, SaveDialogUnavailable,
    save_source_profile_dialog, validate_export_payload,
)
from voxweavetts.server import Handler


def profile_for(mode: str) -> dict:
    result = {
        "format": "voxweavetts.source-settings", "version": 1,
        "mode": mode, "source_id": "",
        "filters": {"blocked_words": "ทดสอบ", "max_chars": ""},
        "auto_read": True, "read_history_limit": 20,
    }
    if mode == "discord_client":
        result.update({
            "client_id": "", "client_secret": "TEST_PRIVATE_SECRET_NOT_FOR_REAL_USE",
            "redirect_uri": "http://127.0.0.1:8765",
        })
    else:
        result["credential"] = "TEST_PRIVATE_CREDENTIAL_NOT_FOR_REAL_USE"
    return result


def request_for(mode: str) -> dict:
    return {"filename": f"VoxWeaveTTS-{mode}-settings.json",
            "profile": profile_for(mode)}


class SaveDialogFilesTests(unittest.TestCase):
    def test_save_to_user_selected_folder_and_roundtrip_secrets(self):
        for mode in ("live", "discord", "discord_client"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / "sub folder" / "settings.json"
                target.parent.mkdir()
                original = request_for(mode)
                dialog_calls = []
                def choose(suggested):
                    dialog_calls.append(suggested)
                    return str(target)
                self.assertTrue(save_source_profile_dialog(original, choose_path=choose))
                self.assertEqual(dialog_calls, [original["filename"]])
                restored = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(restored, original["profile"])
                self.assertEqual(len(list(target.parent.glob(".voxweave-profile-*.tmp"))), 0)

    def test_cancel_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(save_source_profile_dialog(
                request_for("live"), choose_path=lambda _: None))
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_bad_requests_are_rejected_without_echoing_secrets(self):
        valid = request_for("discord_client")
        for bad in (
            {**valid, "filename": "../../secret.json"},
            {**valid, "filename": "VoxWeaveTTS-live-settings.json"},
            {**valid, "profile": {**valid["profile"], "mode": "other"}},
            {**valid, "profile": {**valid["profile"], "extra": "PRIVATE"}},
            {**valid, "profile": {**valid["profile"], "client_secret": "x" * 20_000}},
        ):
            with self.subTest(filename=bad["filename"]):
                with self.assertRaises(ValueError):
                    validate_export_payload(bad)

    def test_refuse_non_json_selected_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "secrets.txt"
            with self.assertRaises(ValueError):
                save_source_profile_dialog(
                    request_for("discord_client"), choose_path=lambda _: str(target))
            self.assertFalse(target.exists())


class SaveDialogHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)

    def send(self, data=None, *, origin=None, intent="choose-source-profile-file",
             content_type="application/json", fetch_site="same-origin"):
        headers = {"Content-Type": content_type}
        if origin is not False:
            headers["Origin"] = origin or self.base
        if intent is not None:
            headers["X-VoxWeaveTTS-Intent"] = intent
        if fetch_site:
            headers["Sec-Fetch-Site"] = fetch_site
        payload = json.dumps(data if data is not None else request_for("discord_client"),
                             ensure_ascii=False).encode("utf-8")
        req = Request(self.base + "/v1/sources/save-profile",
                      data=payload, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            try:
                return exc.code, json.load(exc)
            finally:
                exc.close()

    def test_real_save_selected_path_without_exposing_secrets_in_response(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "my saved settings.json"
            def choose_profile(request):
                return save_source_profile_dialog(
                    request, choose_path=lambda _: str(target))
            with patch("voxweavetts.server.save_source_profile_dialog",
                       side_effect=choose_profile) as saved:
                status, result = self.send()
            self.assertEqual(status, 200)
            self.assertEqual(result, {"saved": True, "cancelled": False})
            self.assertEqual(saved.call_count, 1)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")),
                             profile_for("discord_client"))
            self.assertNotIn("PRIVATE", json.dumps(result))
            self.assertNotIn(str(target), json.dumps(result))

    def test_cancel_never_creates_file(self):
        with patch("voxweavetts.server.save_source_profile_dialog", return_value=False):
            status, result = self.send()
        self.assertEqual(status, 200)
        self.assertEqual(result, {"saved": False, "cancelled": True})

    def test_wrong_origin_intent_or_site_is_rejected_before_dialog(self):
        with patch("voxweavetts.server.save_source_profile_dialog") as dialog:
            cases = [
                {"origin": "http://evil.example"},
                {"origin": False},
                {"intent": None},
                {"intent": "save-something-else"},
                {"fetch_site": "cross-site"},
                {"content_type": "text/plain"},
            ]
            for case in cases:
                with self.subTest(case=case):
                    status, result = self.send(**case)
                    self.assertIn(status, (403, 415))
                    self.assertNotIn("PRIVATE", json.dumps(result))
            dialog.assert_not_called()

    def test_invalid_payload_and_unavailable_dialog_dont_reflect_secrets(self):
        with patch("voxweavetts.server.save_source_profile_dialog",
                   side_effect=ValueError("PRIVATE_SECRET_IN_EXCEPTION")):
            status, result = self.send()
        self.assertEqual(status, 400)
        self.assertNotIn("PRIVATE", json.dumps(result))
        for error, expected in ((SaveDialogBusy(), 409),
                                (SaveDialogUnavailable(), 503),
                                (OSError("PRIVATE_FILE_PATH"), 500)):
            with self.subTest(error=type(error).__name__), patch(
                "voxweavetts.server.save_source_profile_dialog", side_effect=error
            ):
                status, result = self.send()
                self.assertEqual(status, expected)
                self.assertNotIn("PRIVATE", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
