"""Tests for exact native component and upstream-notice provenance QA."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import archive_v4_sherpa_native_notices as subject


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fixture(folder: Path, package_id: str, *, dll: bytes = b"same-dll",
            second_dll: bytes | None = None) -> None:
    wheel = io.BytesIO()
    with zipfile.ZipFile(wheel, "w") as w:
        w.writestr("sherpa_onnx/lib/onnxruntime.dll", dll)
        w.writestr("sherpa_onnx_core-2.0.1.data/data/Scripts/onnxruntime.dll",
                   second_dll if second_dll is not None else dll)
    wheel_path = "runtime/wheels/sherpa_onnx_core-2.0.1-py3-none-win_amd64.whl"
    content = wheel.getvalue()
    archive = folder / (
        f"VoxWeaveTTS-{package_id}-1.0.0-LEGAL-QA-format-v4.vwmodel"
    )
    manifest = {
        "runtime": {"wheels": [wheel_path]},
        "files": [{"path": wheel_path, "sha256": sha(content), "size": len(content)}],
    }
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr(wheel_path, content)


class FakeResponse:
    def __init__(self, data: bytes):
        self.content = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, max_bytes: int):
        return self.content[:max_bytes]


class SherpaNativeNoticesTests(unittest.TestCase):
    def test_records_same_dll_without_guessing_public_redistribution_rights(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            for model in subject.MODELS:
                fixture(root, model)
            details = subject.observe_bundled_dlls(root)
            self.assertEqual(set(details), set(subject.MODELS))
            self.assertEqual(len({x["dll_sha256"] for x in details.values()}), 1)
            documents = {
                "LICENSE": b"MIT License\nCopyright Microsoft\n",
                "ThirdPartyNotices.txt":
                    b"THIRD PARTY SOFTWARE NOTICES AND INFORMATION\nOriginal\n",
            }
            with patch.object(subject, "urlopen", side_effect=lambda request, **kw:
                              FakeResponse(documents[request.full_url.rsplit("/", 1)[-1]])), \
                 patch.object(subject, "ROOT", root):
                report = subject.collect(root, root / "saved-notices")
            self.assertFalse(report["public_release_authorized"])
            self.assertFalse(report["upstream_documents"]["LICENSE"][
                "source_ref_is_verified_commit"])
            self.assertEqual(report["model_packages"][subject.MODELS[0]][
                "dll_sha256"], sha(b"same-dll"))
            self.assertEqual((root / "saved-notices" / "ThirdPartyNotices.txt").read_bytes(),
                             documents["ThirdPartyNotices.txt"])

    def test_duplicated_sherpa_onnx_runtime_must_match_exactly(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            fixture(root, subject.MODELS[0], second_dll=b"changed")
            fixture(root, subject.MODELS[1])
            with self.assertRaisesRegex(ValueError, "differing ONNX DLL"):
                subject.observe_bundled_dlls(root)

    def test_two_model_packages_must_share_same_native_dll(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            fixture(root, subject.MODELS[0], dll=b"v1")
            fixture(root, subject.MODELS[1], dll=b"v2")
            with self.assertRaisesRegex(ValueError, "same ONNX DLL"):
                subject.observe_bundled_dlls(root)


if __name__ == "__main__":
    unittest.main()
