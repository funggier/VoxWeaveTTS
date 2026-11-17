"""License screening flags review requirements, never grants use rights."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_wheelhouse_rights.py"
spec = importlib.util.spec_from_file_location("wheel_rights_audit", SCRIPT)
audit_module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(audit_module)


def create_wheel(folder: Path, name: str, version: str, metadata: str) -> None:
    wheel = folder / f"{name}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as out:
        out.writestr(f"{name}-{version}.dist-info/METADATA", metadata)
        out.writestr(f"{name}-{version}.dist-info/WHEEL",
                     "Wheel-Version: 1.0\nTag: py3-none-any\n")
        out.writestr(f"{name}/__init__.py", "testing only")


class RightsScreeningTests(unittest.TestCase):
    def test_missing_license_and_noncommercial_flags(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            create_wheel(folder, "unknown", "1.0",
                         "Metadata-Version: 2.1\nName: unknown\nVersion: 1.0\n")
            create_wheel(folder, "nc_model", "1.0",
                         "Metadata-Version: 2.1\nName: nc-model\n"
                         "Version: 1.0\nLicense-Expression: CC-BY-NC-4.0\n")
            findings = {x["name"]: x for x in audit_module.audit_wheels(folder)}
            self.assertIn("license-not-declared", findings["unknown"]["flags"])
            self.assertIn("noncommercial-review", findings["nc-model"]["flags"])

    def test_primary_copyleft_and_nested_notice_are_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            create_wheel(folder, "gpl", "1.0",
                         "Metadata-Version: 2.1\nName: gpl\nVersion: 1.0\n"
                         "License-Expression: GPL-3.0-or-later\n")
            create_wheel(folder, "bsd_vendor", "1.0",
                         "Metadata-Version: 2.1\nName: bsd-vendor\nVersion: 1.0\n"
                         "License: BSD-3-Clause " + "X"*360 +
                         " Includes GCC GPL exception in bundled libraries.\n")
            findings = {x["name"]: x for x in audit_module.audit_wheels(folder)}
            self.assertIn("copyleft-review", findings["gpl"]["flags"])
            self.assertIn("bundled-third-party-review",
                          findings["bsd-vendor"]["flags"])
            self.assertNotIn("copyleft-review", findings["bsd-vendor"]["flags"])


if __name__ == "__main__":
    unittest.main()
