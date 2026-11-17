"""Publisher trust, signed execution approval, revocation and IPC SDK."""
from __future__ import annotations

import base64
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts.engine_provider_catalog import (
    ProviderApprovalError, all_providers, approve_provider_folder,
)
from voxweavetts.provider_signing import (
    SigningError, approve_signed_provider, fingerprint, revoke_publisher,
    sign_provider, trust_publisher, trusted_publishers,
    verify_signed_provider,
)
from voxweavetts.tts_provider_sdk import (
    ProtocolError, parse_request, serve, SynthesisRequest,
)

ROOT = Path(__file__).resolve().parents[1]


class SignedProviderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / "extensions" / "engine-providers" / "minimal-demo"
        self.folder.parent.mkdir(parents=True)
        shutil.copytree(ROOT / "examples" / "tts-provider-minimal", self.folder)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat,
        )
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw)
        self.fp = fingerprint(self.public)

    def trust(self):
        trust_publisher(root=self.root, publisher_id="example-publisher",
                        public_key=self.public, expected_fingerprint=self.fp,
                        confirm_trust=True)

    def signed(self):
        self.trust()
        sign_provider(folder=self.folder, publisher_id="example-publisher",
                      private_key=self.private)

    def test_trust_and_execution_approval_are_separate(self):
        with self.assertRaisesRegex(SigningError, "explicit"):
            trust_publisher(root=self.root, publisher_id="example-publisher",
                            public_key=self.public, expected_fingerprint=self.fp)
        with self.assertRaisesRegex(SigningError, "fingerprint"):
            trust_publisher(root=self.root, publisher_id="example-publisher",
                            public_key=self.public, expected_fingerprint="a"*64,
                            confirm_trust=True)
        self.signed()
        verified = verify_signed_provider(folder=self.folder, root=self.root)
        self.assertEqual(verified["key_fingerprint"], self.fp)
        self.assertNotIn("minimal-demo", all_providers(self.root))
        with self.assertRaisesRegex(SigningError, "separate approval"):
            approve_signed_provider(folder=self.folder, root=self.root)
        with self.assertRaisesRegex(ProviderApprovalError, "signed provider"):
            approve_provider_folder(self.folder, root=self.root, trust_code=True)
        state = approve_signed_provider(folder=self.folder, root=self.root,
                                        confirm_executable_code=True)
        self.assertEqual(state["format"], "voxweavetts.approved-provider-v2")
        self.assertIn("minimal-demo", all_providers(self.root))
        self.assertIn("minimal-demo", all_providers(self.root))

    def test_revoke_key_disables_and_does_not_delete_approval(self):
        self.signed()
        approve_signed_provider(folder=self.folder, root=self.root,
                                confirm_executable_code=True)
        self.assertIn("minimal-demo", all_providers(self.root))
        with self.assertRaisesRegex(SigningError, "confirmation"):
            revoke_publisher(root=self.root, publisher_id="example-publisher")
        self.assertTrue(revoke_publisher(
            root=self.root, publisher_id="example-publisher", confirm_revoke=True))
        self.assertNotIn("minimal-demo", all_providers(self.root))
        self.assertTrue((self.folder / "approved.json").is_file())

    def test_any_signed_code_change_disables_provider(self):
        self.signed()
        approve_signed_provider(folder=self.folder, root=self.root,
                                confirm_executable_code=True)
        with (self.folder / "worker.py").open("a") as file:
            file.write("\n# executable modification\n")
        self.assertNotIn("minimal-demo", all_providers(self.root))
        with self.assertRaisesRegex(SigningError, "differs"):
            verify_signed_provider(folder=self.folder, root=self.root)

    def test_signature_substitution_or_key_swap_is_rejected(self):
        self.signed()
        signature = self.folder / "provider-signature.json"
        raw = json.loads(signature.read_text())
        raw["signature_base64"] = base64.b64encode(b"0" * 64).decode()
        signature.write_text(json.dumps(raw))
        with self.assertRaisesRegex(SigningError, "signature"):
            verify_signed_provider(folder=self.folder, root=self.root)

    def test_replacing_detached_signature_disables_prior_approval(self):
        self.signed()
        approve_signed_provider(folder=self.folder, root=self.root,
                                confirm_executable_code=True)
        signature = self.folder / "provider-signature.json"
        raw = json.loads(signature.read_text())
        signature.write_text(json.dumps(raw, separators=(",", ":")))
        self.assertNotIn("minimal-demo", all_providers(self.root))

    def test_manual_legacy_approvals_still_work_without_signature(self):
        self.assertNotIn("minimal-demo", all_providers(self.root))
        approve_provider_folder(self.folder, root=self.root, trust_code=True)
        self.assertIn("minimal-demo", all_providers(self.root))
        # An injected signature file cannot silently fall back to legacy trust.
        (self.folder / "provider-signature.json").write_text("{}")
        self.assertNotIn("minimal-demo", all_providers(self.root))

    def test_missing_cryptography_fails_closed(self):
        self.signed()
        approve_signed_provider(folder=self.folder, root=self.root,
                                confirm_executable_code=True)
        with patch("voxweavetts.provider_signing._cryptography",
                   side_effect=SigningError("unavailable")):
            self.assertNotIn("minimal-demo", all_providers(self.root))

    def test_duplicate_or_changed_trust_requires_revoke(self):
        self.trust()
        self.assertEqual(trusted_publishers(self.root)["example-publisher"]["fingerprint"],
                         self.fp)
        with self.assertRaisesRegex(SigningError, "already trusted"):
            self.trust()


class ProviderSDKTests(unittest.TestCase):
    REQUEST = {"version": 1, "request_id": 4, "method": "synthesize",
               "text": "สวัสดีครับ", "voice_id": "demo", "speed": 1.1, "seed": 4}

    def test_request_contract_bounds_and_untrusted_directives(self):
        rid, request = parse_request(self.REQUEST, voices=frozenset({"demo"}),
                                     engines=frozenset({"demo-v1"}))
        self.assertEqual(rid, 4)
        self.assertEqual(request.text, "สวัสดีครับ")
        for changes in ({"method": "run"}, {"command": "rm -rf"},
                        {"text": "A" * 5001}, {"seed": True},
                        {"speed": float("inf")}, {"voice_id": "unknown"},
                        {"engine_id": "arbitrary"}, {"request_id": -1}):
            with self.subTest(changes=changes), self.assertRaises(ProtocolError):
                parse_request({**self.REQUEST, **changes},
                              voices=frozenset({"demo"}),
                              engines=frozenset({"demo-v1"}))

    def test_success_failure_and_resource_errors_are_bounded_and_redacted(self):
        records = [
            self.REQUEST,
            {**self.REQUEST, "request_id": 5, "text": "secret request"},
            {**self.REQUEST, "request_id": 6, "text": "OOM"},
            {**self.REQUEST, "request_id": 7, "text": "bad", "voice_id": "wrong"},
        ]

        def synthesize(request):
            if request.text == "secret request":
                raise RuntimeError("local private file path leak")
            if request.text == "OOM":
                raise MemoryError()
            return b"\x00\x01" * 5

        source = io.BytesIO(b"".join(
            json.dumps(x, ensure_ascii=False).encode() + b"\n" for x in records))
        output = io.BytesIO()
        serve(synthesize, sample_rate=24000, voice_ids=["demo"],
              input_stream=source, output_stream=output)
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([r["ok"] for r in replies], [True, False, False, False])
        self.assertEqual(replies[0]["pcm16_b64"], base64.b64encode(b"\x00\x01" * 5).decode())
        self.assertEqual(replies[2]["error"], "resource_exhausted")
        self.assertNotIn("private", output.getvalue().decode())
        self.assertNotIn("secret", output.getvalue().decode())

    def test_oversized_line_is_never_executed(self):
        called = []
        source = io.BytesIO(b"z" * (64 * 1024 + 2) + b"\n")
        output = io.BytesIO()
        serve(lambda request: called.append(request) or b"\x00\x00",
              sample_rate=24000, voice_ids=("demo",),
              input_stream=source, output_stream=output)
        self.assertEqual(called, [])
        self.assertFalse(json.loads(output.getvalue())["ok"])


if __name__ == "__main__":
    unittest.main()
