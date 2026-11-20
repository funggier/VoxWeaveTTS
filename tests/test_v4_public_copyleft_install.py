"""Regression: released Kokoro and Wayu must install their GPL source files.

v0.12.1 rejected each legal .tar.gz path as a bad V4 manifest before
runtime setup. This fixture deliberately carries both sets of exact paths
and proves installation, discovery and removal instead of only _path().
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_vwmodel_v4 import build
from test_v4_plugin_packages import fixture
from voxweavetts import universal_model_v4 as v4

_SOURCE_ARCHIVES = (
    "espeak-ng-1.52.0",
    "phonemizer-3.6.0",
    "phonemizer-fork-3.3.2",
    "gensim-4.4.0",
    "num2words-0.5.6",
)


def original_tar() -> bytes:
    """Minimal valid gzip tar; no extracted or executed source on install."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        source = b"Copyright original authors; original license preserved."
        member = tarfile.TarInfo("LICENSE")
        member.size = len(source)
        archive.addfile(member, io.BytesIO(source))
    return buffer.getvalue()


class CopyleftSourceInstallTests(unittest.TestCase):
    def test_offline_model_install_preserves_exact_original_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fixture(base / "origin")
            source = base / "origin" / "source"
            legal = source / "assets" / "legal" / "source"
            legal.mkdir(parents=True)
            payload = original_tar()
            for version in _SOURCE_ARCHIVES:
                (legal / f"{version}-source.tar.gz").write_bytes(payload)
            archive = base / "with-copyleft-licenses.vwmodel"
            build(source, base / "origin" / "spec.json", archive)
            manifest = v4.inspect_archive(archive)
            self.assertEqual(manifest["package"]["id"], "demo-future-engine")
            expected_paths = {
                f"assets/legal/source/{version}-source.tar.gz"
                for version in _SOURCE_ARCHIVES
            }
            self.assertTrue(expected_paths.issubset(
                {x["path"] for x in manifest["files"]}
            ))
            root = base / "portable"
            with patch.object(
                v4, "core_python", return_value=Path(sys.executable)
            ), patch.object(v4, "sys_platform", return_value="windows-x64"):
                installed = v4.install(archive, root=root)
                self.assertEqual(installed["runtime_status"], "ready")
                found = v4.installed_packages(root)
                self.assertEqual(len(found), 1)
                _, location = found[0]
                for name in expected_paths:
                    self.assertEqual(
                        (location / name).read_bytes(), payload, name
                    )
                    row = next(x for x in manifest["files"]
                               if x["path"] == name)
                    self.assertEqual(row["sha256"],
                                     hashlib.sha256(payload).hexdigest())
                self.assertTrue(v4.remove(
                    "demo-future-engine", "1.0.0", root=root
                ))
                self.assertFalse(v4.installed_packages(root))

    def test_untrusted_executable_archive_is_still_rejected(self):
        for candidate in (
            "runtime/wheels/injected.tar.gz",
            "plugin/worker-source.tar.gz",
            "assets/legal/source/../../../injected-source.tar.gz",
            "assets/legal/source/arbitrary-source.tar.gz",
        ):
            with self.subTest(path=candidate):
                with self.assertRaises(v4.V4PackageError):
                    v4._path(candidate)


if __name__ == "__main__":
    unittest.main()
