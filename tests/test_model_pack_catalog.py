"""Published model pack inventory is source-pinned and carries legal notices."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class ModelPackCatalogTests(unittest.TestCase):
    def test_catalog_contains_seven_distributable_tts_packs_including_makham_and_nc(self):
        catalog=json.loads((ROOT/"model-packs"/"catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"],1)
        self.assertEqual(catalog["release_tag"],"v0.9.5")
        self.assertEqual({p["package_id"] for p in catalog["packages"]},{
            "vachana-thai-four-voices","fastthaig2p-thai-som",
            "kokoro-multilingual-int8",
            "melo-chinese-onnx", "supertonic3-multilingual-int8",
            "wayu-paxa-edge-nc", "makham-paradee",
        })
        for pack in catalog["packages"]:
            with self.subTest(package=pack["package_id"]):
                self.assertTrue(pack["download_url"].startswith(
                    "https://github.com/funggier/VoxWeaveTTS/releases/download/"
                    "v0.9.5/"))
                self.assertTrue(pack["download_url"].endswith(pack["file"]))
                self.assertTrue(pack["file"].endswith(".vwmodel"))
                self.assertGreater(pack["size_bytes"],1_000_000)
                self.assertRegex(pack["sha256"],r"^[a-f0-9]{64}$")
                if pack["package_id"] == "makham-paradee":
                    self.assertEqual(pack["engine_adapter"],"makham-paradee-onnx-v1")
                    self.assertEqual(pack["voices"],["paradee_thai"])
                    self.assertEqual(pack["upstream_declared_license"],"Apache-2.0")
                    self.assertEqual(pack["upstream_asset_sha256"]["paradee_thai_int8.onnx"],
                                     "ad179a2c11b54b1185e84d9c0b759a57058588405620f12163084aaad250813d")
                if pack["package_id"] == "wayu-paxa-edge-nc":
                    self.assertEqual(pack["review_status"], "hold")
                    self.assertEqual(pack["upstream_declared_license"], "CC-BY-NC-4.0")
                    self.assertIn("legal/acceptable-use.txt", pack["embedded_notices"])
                    self.assertIn("README.md", pack["embedded_notices"])
                    self.assertEqual(len(pack["voices"]), 12)
                    self.assertEqual(pack["engine_adapter"], "wayu-nc-v1")
                    self.assertIn("model.pth", pack["upstream_asset_sha256"])
                else:
                    self.assertEqual(pack["review_status"],"review_required")
                    self.assertIn(pack["upstream_declared_license"],
                                  ("MIT","Apache-2.0","OpenRAIL-M"))
                self.assertTrue(pack["upstream_source"].startswith("https://"))
                self.assertTrue(pack["conditions"])
                self.assertGreaterEqual(len(pack["embedded_notices"]),2)
                for name in pack["embedded_notices"]:
                    self.assertTrue(name.startswith("legal/") or (pack["package_id"]=="wayu-paxa-edge-nc" and name=="README.md"))
                    # Kokoro embeds upstream legal files in the downloadable
                    # .vwmodel; unlike the two Thai builders it has no copied
                    # source tree under model-packs/ in a fresh checkout.
                    if pack["package_id"] in ("kokoro-multilingual-int8",
                                              "melo-chinese-onnx",
                                              "supertonic3-multilingual-int8",
                                              "wayu-paxa-edge-nc",
                                              "makham-paradee"):
                        continue
                    target=ROOT/"model-packs"/(
                        "vachana" if pack["package_id"].startswith("vachana")
                        else "fastthaig2p")/(
                        {"license.txt":"LICENSE.txt",
                         "notice.txt":"NOTICE.txt",
                         "attribution.md":"ATTRIBUTION.md"}[Path(name).name])
                    self.assertTrue(target.is_file(),target)
                for sha in pack["upstream_asset_sha256"].values():
                    self.assertRegex(sha,r"^[0-9a-f]{64}$")
        kokoro=next(p for p in catalog["packages"]
                    if p["package_id"]=="kokoro-multilingual-int8")
        self.assertEqual(len(kokoro["voices"]),18)
        self.assertEqual(kokoro["engine_adapter"],"kokoro-onnx-v1")
        chinese=next(p for p in catalog["packages"]
                     if p["package_id"]=="melo-chinese-onnx")
        self.assertEqual(chinese["voices"], ["zh_melo"])
        self.assertEqual(chinese["engine_adapter"], "sherpa-melo-zh-v1")
        multilingual=next(p for p in catalog["packages"]
                          if p["package_id"]=="supertonic3-multilingual-int8")
        self.assertEqual(len(multilingual["voices"]),62)
        self.assertEqual(multilingual["upstream_declared_license"],"OpenRAIL-M")
        self.assertEqual(multilingual["engine_adapter"],"sherpa-supertonic-v1")
        fast=next(p for p in catalog["packages"]
                  if p["package_id"]=="fastthaig2p-thai-som")
        self.assertIn("CC-BY-4.0",fast["training_license"])
        self.assertIn("legal/notice.txt",fast["embedded_notices"])


if __name__=="__main__":
    unittest.main()
