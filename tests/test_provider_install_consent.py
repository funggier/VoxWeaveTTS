"""Provider-specific installation consent is NOT a redistribution license grant."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts.engine_provider_installer import (
    InstallError, install, install_async,
)
from voxweavetts.provider_rights import (
    INSTALL_TERMS_VERSION, require_local_install_consent, review,
)


class ConsentPolicyTests(unittest.TestCase):
    def test_vachana_and_kokoro_accept_one_explicit_current_version(self):
        for provider in ("vachana", "kokoro"):
            with self.subTest(provider=provider):
                meta = review(provider)
                self.assertTrue(meta["local_install"]["consent_required"])
                self.assertTrue(meta["local_install"]["allowed_with_explicit_consent"])
                self.assertFalse(meta["legal_clearance"])
                self.assertFalse(meta["offline_wheelhouse_release_allowed"])
                for version in (None, 0, True, False, "1", -1, 999):
                    with self.subTest(version=version), self.assertRaisesRegex(
                        ValueError, "acknowledgement"
                    ):
                        require_local_install_consent(
                            provider, terms_version=version,
                        )
                require_local_install_consent(
                    provider, terms_version=INSTALL_TERMS_VERSION
                )
                # Consent never mutates the first-party publication HOLD.
                self.assertEqual(review(provider)["publication_state"], "hold")

    def test_wayu_nc_must_acknowledge_noncommercial_separately(self):
        policy = review("wayu-nc")
        self.assertEqual(policy["model_license"], "CC-BY-NC-4.0")
        self.assertTrue(
            policy["local_install"]["noncommercial_acknowledgment_required"]
        )
        with self.assertRaisesRegex(ValueError, "noncommercial-only"):
            require_local_install_consent(
                "wayu-nc", terms_version=INSTALL_TERMS_VERSION,
            )
        require_local_install_consent(
            "wayu-nc", terms_version=INSTALL_TERMS_VERSION,
            acknowledge_noncommercial=True,
        )
        self.assertEqual(review("wayu-nc")["commercial_status"], "noncommercial-only")
        self.assertFalse(review("wayu-nc")["legal_clearance"])

    def test_nonheld_builtin_installs_need_no_extra_consent(self):
        for provider in ("sherpa", "pythaitts"):
            with self.subTest(provider=provider):
                self.assertFalse(review(provider)["local_install"]["consent_required"])
                require_local_install_consent(provider)
        with self.assertRaisesRegex(ValueError, "unknown"):
            require_local_install_consent("../../untrusted", terms_version=1)


class InstallBeforeMutationTests(unittest.TestCase):
    def test_synchronous_install_checks_consent_before_any_filesystem_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for provider in ("wayu-nc", "vachana", "kokoro"):
                with self.subTest(provider=provider):
                    with self.assertRaisesRegex(InstallError, "acknowledgement"):
                        install(provider, root=root)
                    self.assertFalse((root / "runtime").exists())
                    self.assertFalse((root / "logs").exists())
                    self.assertFalse((root / "cache").exists())

    def test_opted_in_installs_reach_normal_installer_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # No system/network action: bundled uv lookup is stubbed as missing.
            with patch("voxweavetts.runtime_tools.find_uv", return_value=None):
                with self.assertRaisesRegex(InstallError, "uv is not installed"):
                    install("kokoro", root=root, terms_version=INSTALL_TERMS_VERSION)
                with self.assertRaisesRegex(InstallError, "uv is not installed"):
                    install("wayu-nc", root=root,
                            terms_version=INSTALL_TERMS_VERSION,
                            acknowledge_noncommercial=True)
            self.assertFalse((root / "runtime").exists())

    def test_async_installer_denies_unconsented_jobs_before_creating_threads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("voxweavetts.engine_provider_installer.threading.Thread") as thread:
                for provider in ("vachana", "kokoro", "wayu-nc"):
                    with self.subTest(provider=provider):
                        with self.assertRaisesRegex(InstallError, "acknowledgement"):
                            install_async(provider, root=root)
                thread.assert_not_called()
                self.assertFalse((root / "runtime").exists())


if __name__ == "__main__":
    unittest.main()
