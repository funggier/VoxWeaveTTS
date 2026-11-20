"""Offline QA for original eSpeak NG source and native binary evidence."""
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
import archive_v4_espeak_source as target


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def make_fixture(root: Path, package_id: str, dll: bytes) -> None:
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as wheel:
        wheel.writestr("espeakng_loader/espeak-ng.dll", dll)
    content = inner.getvalue()
    wheel_path = "runtime/wheels/espeakng_loader-0.2.4-py3-none-win_amd64.whl"
    outer_path = root / f"VoxWeaveTTS-{package_id}-1-LEGAL-QA-format-v4.vwmodel"
    with zipfile.ZipFile(outer_path, "w") as outer:
        outer.writestr("manifest.json", json.dumps({
            "runtime": {"wheels": [wheel_path]},
            "files": [{"path": wheel_path, "sha256": sha(content), "size": len(content)}],
        }))
        outer.writestr(wheel_path, content)


class Response:
    def __init__(self, content: bytes):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, chunk_size: int):
        for index in range(0, len(self.content), chunk_size):
            yield self.content[index:index + chunk_size]

    def raise_for_status(self):
        return None


def tiny_source() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as f:
        payload = b"GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n"
        member = tarfile.TarInfo("espeak-ng-1.52.0/COPYING")
        member.size = len(payload)
        f.addfile(member, io.BytesIO(payload))
    return buf.getvalue()


class EspeakNativeSourceTests(unittest.TestCase):
    def test_source_and_upstream_build_provenance_is_sha_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for model in target.MODELS:
                make_fixture(root, model, b"test-dll")
            docs = {
                "LICENSE": b"MIT License\nCopyright original loader",
                "build.sh": b"#!/bin/bash\ncd espeak-ng\n",
                ".github/workflows/build.yml": (
                    b"git clone --single-branch --depth 1 -b 1.52.0 "
                    b"https://github.com/espeak-ng/espeak-ng\n"
                ),
            }
            source_tar = tiny_source()

            def fake_get(url, **kwargs):
                if url == target.SOURCE_URL:
                    return Response(source_tar)
                return Response(docs[url.removeprefix(target.LOADER_BASE)])

            with patch.object(target.requests, "get", side_effect=fake_get), \
                 patch.object(target, "ROOT", root):
                audit = target.collect(root, root / "source-data")

            self.assertFalse(audit["public_release_authorized"])
            self.assertEqual(audit["espeak_ng_upstream_source_tarball"]["sha256"],
                             sha(source_tar))
            self.assertEqual(audit["native_binaries"][target.MODELS[0]]["dll_sha256"],
                             sha(b"test-dll"))
            self.assertEqual((root / "source-data" / "espeak-ng-1.52.0-source.tar.gz").read_bytes(),
                             source_tar)

    def test_different_model_dlls_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_fixture(root, target.MODELS[0], b"dll-a")
            make_fixture(root, target.MODELS[1], b"dll-b")
            with self.assertRaisesRegex(ValueError, "differ"):
                target.bundled_binary_index(root)

    def test_source_tar_must_contain_gpl_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("invalid.tar.gz").write_bytes(b"not a tar file")
            with patch.object(target, "ROOT", root):
                with self.assertRaises((tarfile.TarError, EOFError, OSError)):
                    target.get_tarball("https://example.invalid/source",
                                       root / "invalid.tar.gz")


if __name__ == "__main__":
    unittest.main()
