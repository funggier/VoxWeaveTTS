"""Published model pack inventory is source-pinned and carries legal notices."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class ModelPackCatalogTests(unittest.TestCase):
    def test_catalog_contains_two_distributable_optional_packs(self):
        catalog=json.loads((ROOT/"model-packs"/"catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"],1)
        self.assertEqual(catalog["release_tag"],"modelpacks-v0.4.2")
        self.assertEqual({p["package_id"] for p in catalog["packages"]},{
            "vachana-thai-four-voices","fastthaig2p-thai-som",
        })
        for pack in catalog["packages"]:
            with self.subTest(package=pack["package_id"]):
                self.assertTrue(pack["download_url"].startswith(
                    "https://github.com/funggier/VoxWeaveTTS/releases/download/"
                    "modelpacks-v0.4.2/"))
                self.assertTrue(pack["download_url"].endswith(pack["file"]))
                self.assertTrue(pack["file"].endswith(".vwmodel"))
                self.assertGreater(pack["size_bytes"],1_000_000)
                self.assertRegex(pack["sha256"],r"^[a-f0-9]{64}$")
                self.assertEqual(pack["review_status"],"review_required")
                self.assertIn(pack["upstream_declared_license"],("MIT","Apache-2.0"))
                self.assertTrue(pack["upstream_source"].startswith("https://"))
                self.assertTrue(pack["conditions"])
                self.assertGreaterEqual(len(pack["embedded_notices"]),2)
                for name in pack["embedded_notices"]:
                    self.assertTrue(name.startswith("legal/"))
                    target=ROOT/"model-packs"/(
                        "vachana" if pack["package_id"].startswith("vachana")
                        else "fastthaig2p")/(
                        {"license.txt":"LICENSE.txt",
                         "notice.txt":"NOTICE.txt",
                         "attribution.md":"ATTRIBUTION.md"}[Path(name).name])
                    self.assertTrue(target.is_file(),target)
                for sha in pack["upstream_asset_sha256"].values():
                    self.assertRegex(sha,r"^[0-9a-f]{64}$")
        fast=next(p for p in catalog["packages"]
                  if p["package_id"]=="fastthaig2p-thai-som")
        self.assertIn("CC-BY-4.0",fast["training_license"])
        self.assertIn("legal/notice.txt",fast["embedded_notices"])


if __name__=="__main__":
    unittest.main()
