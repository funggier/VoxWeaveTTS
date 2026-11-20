"""Offline tests of ONNX Runtime 1.31.1 evidence for the V4 model packs."""
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
import archive_v4_onnxruntime_131_notices as subject


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture(folder: Path, model: str, *, dll: bytes = b"ort-native") -> None:
    wheel = io.BytesIO()
    with zipfile.ZipFile(wheel, "w") as inner:
        inner.writestr("onnxruntime/capi/onnxruntime.dll", dll)
        inner.writestr("onnxruntime/capi/onnxruntime_providers_shared.dll",
                       b"provider-library")
        inner.writestr("onnxruntime/capi/onnxruntime_pybind11_state.pyd",
                       b"python-bindings")
    content = wheel.getvalue()
    member = "runtime/wheels/onnxruntime-1.31.1-cp311-cp311-win_amd64.whl"
    target = folder / f"VoxWeaveTTS-{model}-1-LEGAL-QA-format-v4.vwmodel"
    with zipfile.ZipFile(target, "w") as outer:
        outer.writestr("manifest.json", json.dumps({
            "runtime": {"wheels": [member]},
            "files": [{"path": member, "sha256": sha(content), "size": len(content)}],
        }))
        outer.writestr(member, content)


class Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class ORT131NoticesTests(unittest.TestCase):
    def test_archives_exact_notice_documents_without_approving_redistribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for model in subject.MODELS:
                fixture(folder, model)
            originals = {
                "LICENSE": b"MIT License\nCopyright Microsoft",
                "ThirdPartyNotices.txt": (
                    b"THIRD PARTY SOFTWARE NOTICES AND INFORMATION\n"
                ),
                "VERSION_NUMBER": b"1.31.1\n",
            }
            with patch.object(
                subject, "urlopen",
                side_effect=lambda request, **kwargs: Response(
                    originals[request.full_url.rsplit("/", 1)[-1]]
                )
            ), patch.object(subject, "ROOT", folder):
                result = subject.collect(folder, folder / "record")
            self.assertFalse(result["public_release_authorized"])
            self.assertEqual(len(result["bundled_packages"]), 4)
            self.assertEqual(result["bundled_packages"][
                subject.MODELS[0]]["dll_sha256"], sha(b"ort-native"))
            self.assertEqual(result["upstream_documents"]["LICENSE"]["sha256"],
                             sha(originals["LICENSE"]))
            self.assertFalse(result["upstream_documents"]["LICENSE"][
                "source_tag_resolved_to_immutable_commit"])
            self.assertEqual((folder / "record" / "VERSION_NUMBER").read_bytes(),
                             originals["VERSION_NUMBER"])

    def test_rejects_different_onnx_runtime_wheel_across_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for model in subject.MODELS:
                fixture(folder, model, dll=b"dll-one")
            fixture(folder, subject.MODELS[-1], dll=b"dll-two")
            with self.assertRaisesRegex(ValueError, "wheel differs"):
                subject.inventory(folder)

    def test_rejects_unmatched_upstream_version_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for model in subject.MODELS:
                fixture(folder, model)
            contents = {
                "LICENSE": b"MIT License\noriginal",
                "ThirdPartyNotices.txt": b"THIRD PARTY SOFTWARE NOTICES\n",
                "VERSION_NUMBER": b"another-version\n",
            }
            with patch.object(subject, "urlopen", side_effect=lambda request, **kw:
                              Response(contents[request.full_url.rsplit("/", 1)[-1]])), \
                 patch.object(subject, "ROOT", folder):
                with self.assertRaisesRegex(ValueError, "source tag version"):
                    subject.collect(folder, folder / "notices")


if __name__ == "__main__":
    unittest.main()
