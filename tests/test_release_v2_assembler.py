"""Release ZIP curation: source/docs/extension archives never include user data."""
from __future__ import annotations
import importlib.util
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_script():
    path = ROOT / "scripts" / "prepare_release_assets_v2.py"
    spec = importlib.util.spec_from_file_location("test_release_v2_script", path)
    assert spec is not None and spec.loader is not None
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class ReleaseAssemblerTests(unittest.TestCase):
    def test_version_and_only_previously_locked_wheelhouse_families(self):
        script = load_script()
        from voxweavetts import __version__
        self.assertEqual(script.VERSION, __version__)
        self.assertEqual(set(script.RUNTIMES), {"sherpa", "pythaitts", "m2m100"})
        self.assertNotIn("vachana", script.RUNTIMES)
        self.assertNotIn("kokoro", script.RUNTIMES)
        self.assertNotIn("wayu-nc", script.RUNTIMES)

    def test_archive_filters_tracked_content_and_requires_clean_checkout(self):
        script = load_script()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            samples = {
                ".gitignore": "cache/\ndist/\n",
                "LICENSE": "public license\n",
                "README.md": "public readme\n",
                "README_TH.md": "public readme thai\n",
                "docs/release.md": "public release notes\n",
                "extensions/tiktok-live-connector/manifest.json": '{"name":"demo"}',
                "src/voxweavetts/__init__.py":
                    f'__version__ = "{script.VERSION}"\n',
            }
            for name, value in samples.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(value, encoding="utf-8")
            (root / "cache").mkdir()
            (root / "cache" / "secret.txt").write_text("PRIVATE-DATA")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Release Fixture",
                 "-c", "user.email=fixture@example.invalid",
                 "commit", "-m", "fixture", "-q"], cwd=root, check=True
            )
            output = root / "dist" / "assets"
            output.mkdir(parents=True)
            with patch.object(script, "ROOT", root), patch.object(script, "OUTPUT", output):
                script.stage_supplemental_archives()
                source = output / f"VoxWeaveTTS-v{script.VERSION}-source.zip"
                docs = output / f"VoxWeaveTTS-v{script.VERSION}-docs.zip"
                ext = output / f"VoxWeaveTTS-TikTok-Extension-v{script.VERSION}.zip"
                self.assertTrue(all(x.exists() for x in (source, docs, ext)))
                with zipfile.ZipFile(source) as z:
                    self.assertIn("src/voxweavetts/__init__.py", z.namelist())
                    self.assertNotIn("cache/secret.txt", z.namelist())
                with zipfile.ZipFile(docs) as z:
                    self.assertIn("docs/release.md", z.namelist())
                    self.assertIn("LICENSE", z.namelist())
                    self.assertNotIn("cache/secret.txt", z.namelist())
                with zipfile.ZipFile(ext) as z:
                    self.assertEqual(
                        z.namelist(), ["tiktok-live-connector/manifest.json"])
                (root / "README.md").write_text("modified without commit")
                with self.assertRaisesRegex(RuntimeError, "commit all"):
                    script.stage_supplemental_archives()


if __name__ == "__main__":
    unittest.main()
