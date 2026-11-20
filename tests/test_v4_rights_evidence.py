"""Rights evidence remains verifiable offline without copying vendor text to Git."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_v4_rights_evidence import verify, bundle


def fixture(root: Path) -> Path:
    folder = root / "cache" / "v4-rights-evidence"
    doc = folder / "upstream" / "hf-model" / "sample" / ("a" * 40) / "LICENSE"
    doc.parent.mkdir(parents=True)
    doc.write_bytes(b"Original test license text from a test fixture\n")
    doc_hash = hashlib.sha256(doc.read_bytes()).hexdigest()
    wheel = folder / "wheel-docs" / "abcde" / "example-1.0.dist-info" / "METADATA"
    wheel.parent.mkdir(parents=True)
    wheel.write_bytes(b"Metadata-Version: 2.4\nLicense-Expression: MIT\n")
    wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    index = {
        "schema": "voxweavetts.v4-upstream-rights-evidence",
        "source_errors": [],
        "source_repositories": [{"repo": "sample", "kind": "hf-model",
                                 "revision": "a" * 40}],
        "upstream_documents": [{
            "source_kind": "hf-model", "repository": "sample",
            "revision": "a" * 40, "source_path": "LICENSE",
            "local_copy": doc.relative_to(root).as_posix(),
            "sha256": doc_hash, "size_bytes": doc.stat().st_size,
        }],
        "all_models_public_redistribution_cleared": False,
    }
    index_file = root / "docs" / "v4_upstream_evidence_index.json"
    index_file.parent.mkdir(parents=True)
    index_file.write_text(json.dumps(index))
    (folder / "INDEX.json").write_text(json.dumps(index))
    wheel_index = {
        "unique_wheel_evidence": {
            "f" * 64: {
                "wheel_sha256": "f" * 64,
                "files": [{
                    "local_copy": wheel.relative_to(root).as_posix(),
                    "sha256": wheel_hash, "size_bytes": wheel.stat().st_size,
                }],
            }
        }
    }
    (folder / "wheel-index.json").write_text(json.dumps(wheel_index))
    return index_file


class V4RightsEvidenceTests(unittest.TestCase):
    def test_verifies_original_documents_and_wheel_license_copies_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            result = verify(index, root)
            self.assertEqual(result["publisher_documents_verified"], 1)
            self.assertEqual(result["wheel_documents_verified"], 1)
            self.assertFalse(result["public_release_authorized"])

    def test_original_document_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            license_file = next((root / "cache" / "v4-rights-evidence"
                                 / "upstream").rglob("LICENSE"))
            license_file.write_bytes(b"license text silently changed")
            with self.assertRaisesRegex(ValueError, "changed or is missing"):
                verify(index, root)

    def test_wheel_license_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            metadata = next((root / "cache/v4-rights-evidence/wheel-docs").rglob("METADATA"))
            metadata.write_bytes(b"invalid metadata")
            with self.assertRaisesRegex(ValueError, "changed or missing"):
                verify(index, root)

    def test_zip_contains_only_verified_evidence_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            result = bundle(verify(index, root), root=root)
            self.assertFalse(result["public_release_authorized"])
            import zipfile
            with zipfile.ZipFile(result["archive"]) as z:
                self.assertIsNone(z.testzip())
                self.assertTrue(any(x.endswith("/LICENSE") for x in z.namelist()))
            with self.assertRaisesRegex(ValueError, "already exists"):
                bundle(verify(index, root), root=root)

    def test_traversal_and_attempt_to_claim_redistribution_clearance_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            data = json.loads(index.read_text())
            data["upstream_documents"][0]["local_copy"] = "../secrets.txt"
            index.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "invalid original-document path"):
                verify(index, root)
            data["upstream_documents"][0]["local_copy"] = (
                "cache/v4-rights-evidence/upstream/hf-model/sample/" + "a" * 40
                + "/LICENSE")
            data["all_models_public_redistribution_cleared"] = True
            index.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "unsafe rights-evidence index"):
                verify(index, root)

    def test_git_index_has_fixed_origins_not_an_install_allowlist(self):
        index = json.loads((ROOT / "docs/v4_upstream_evidence_index.json").read_text("utf-8"))
        self.assertFalse(index["all_models_public_redistribution_cleared"])
        self.assertFalse(index["raw_documents_repository_tracked"])
        self.assertGreaterEqual(len(index["source_repositories"]), 15)
        for source in index["source_repositories"]:
            self.assertEqual(len(source["revision"]), 40)
        for document in index["upstream_documents"]:
            self.assertIn("sha256", document)
            self.assertEqual(len(document["sha256"]), 64)
            self.assertTrue(document["local_copy"].startswith(
                "cache/v4-rights-evidence/upstream/"))


if __name__ == "__main__":
    unittest.main()
