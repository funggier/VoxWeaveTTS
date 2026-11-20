"""Offline upstream-source provenance tests; no invented Vachana code license."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_v4_vachanatts_pypi_provenance as auditor


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def example(root: Path, *, modify_source: bool = False) -> tuple:
    source = io.BytesIO()
    with tarfile.open(fileobj=source, mode="w:gz") as tar:
        originals = {"vachanatts/file%d.py" % i: ("script%d" % i).encode()
                     for i in range(16)}
        for name, body in originals.items():
            path = "vachanatts-0.0.7/" + name
            item = tarfile.TarInfo(path)
            src = body + (b"changed" if modify_source and name.endswith("1.py")
                          else b"")
            item.size = len(src)
            tar.addfile(item, io.BytesIO(src))
        meta = b"Metadata-Version: 2.4\nName: vachanatts\nVersion: 0.0.7\n"
        item = tarfile.TarInfo("vachanatts-0.0.7/PKG-INFO")
        item.size = len(meta)
        tar.addfile(item, io.BytesIO(meta))
    wheel_file = io.BytesIO()
    with zipfile.ZipFile(wheel_file, mode="w") as wheel:
        for name, body in originals.items():
            wheel.writestr(name, body)
        for i in range(9):
            original_body = originals[f"vachanatts/file{i}.py"]
            wheel.writestr(
                f"vachanatts1/file{i}.py",
                original_body + (b"different" if i < 3 else b""),
            )
        wheel.writestr("vachanatts-0.0.7.dist-info/METADATA",
                       "Metadata-Version: 2.4\nName: vachanatts\nVersion: 0.0.7\n")
    wheel_data = wheel_file.getvalue()
    name = "runtime/wheels/vachanatts-0.0.7-py3-none-any.whl"
    target = root / "VoxWeaveTTS-vachana-thai-four-voices-1.0-LEGAL-QA-format-v4.vwmodel"
    with zipfile.ZipFile(target, "w") as outer:
        outer.writestr("manifest.json", json.dumps({
            "package": {"id": "vachana-thai-four-voices"},
            "runtime": {"wheels": [name]},
            "rights": {"spdx": "MIT"},
            "files": [{"path": name, "sha256": sha(wheel_data),
                       "size": len(wheel_data)}],
        }))
        outer.writestr(name, wheel_data)
    sdist = root / "vachanatts-0.0.7.tar.gz"
    sdist.write_bytes(source.getvalue())
    return target, sdist, sha(wheel_data), sha(source.getvalue())


class VachanaOriginalCodeAuditTests(unittest.TestCase):
    def test_matching_sdist_does_not_clear_unlicensed_extra_namespace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package, source, wheel_sha, source_sha = example(root)
            with patch.object(auditor, "ORIGINAL_WHEEL_SHA", wheel_sha), \
                 patch.object(auditor, "ORIGINAL_SOURCE_SHA", source_sha):
                result = auditor.assess(package, source)
            self.assertEqual(result["source_files_matched"], 16)
            self.assertEqual(result["secondary_namespace_file_count"], 9)
            self.assertEqual(result["secondary_namespace_different_from_primary_count"], 3)
            self.assertEqual(result["model_weight_license_unmodified"], "MIT")
            self.assertTrue(result["code_license_not_verified"])
            self.assertFalse(result["public_release_authorized"])

    def test_source_mismatch_rejected_even_if_source_archive_hash_is_pinned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package, source, wheel_sha, source_sha = example(
                root, modify_source=True)
            with patch.object(auditor, "ORIGINAL_WHEEL_SHA", wheel_sha), \
                 patch.object(auditor, "ORIGINAL_SOURCE_SHA", source_sha):
                with self.assertRaisesRegex(ValueError, "sdist file differs"):
                    auditor.assess(package, source)

    def test_wrong_upstream_sha_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package, source, wheel_sha, source_sha = example(root)
            with patch.object(auditor, "ORIGINAL_WHEEL_SHA", wheel_sha):
                with self.assertRaisesRegex(ValueError, "source tarball SHA"):
                    auditor.assess(package, source)


if __name__ == "__main__":
    unittest.main()
