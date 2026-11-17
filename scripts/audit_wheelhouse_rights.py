#!/usr/bin/env python3
"""Read-only per-wheel license/provenance screening for release preparation.

This is a *review queue*, not legal clearance or a commercial-use grant.
No code is executed from candidate wheels.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from voxweavetts.offline_wheelhouse import WheelhouseError, draft_lock


def audit_wheels(directory: Path) -> list[dict]:
    found = []
    for wheel in sorted(directory.glob("*.whl")):
        with zipfile.ZipFile(wheel) as bundle:
            members = [x for x in bundle.infolist()
                       if x.filename.endswith(".dist-info/METADATA")]
            if len(members) != 1 or members[0].file_size > 1024 * 1024:
                raise WheelhouseError("wheel has invalid metadata")
            meta = BytesParser().parsebytes(bundle.read(members[0]))
            raw = str(meta.get("License-Expression") or meta.get("License") or "")
            classifiers = [value for value in meta.get_all("Classifier", [])
                           if value.startswith("License ::")]
            license_files = [x.filename for x in bundle.infolist()
                             if re.search(r"(?:^|/)(?:LICENSE|COPYING|NOTICE)", x.filename,
                                          flags=re.IGNORECASE)]
            short = raw.strip().replace("\r", " ").replace("\n", " ")[:160]
            if len(raw) > 160:
                short += "…"
            # Long notices can include separately licensed vendored libraries;
            # distinguish those from the distribution's primary license.
            claims = " ".join([raw[:320]] + classifiers).upper()
            all_claims = " ".join([raw] + classifiers).upper()
            flags = []
            if not raw.strip() and not classifiers and not license_files:
                flags.append("license-not-declared")
            if re.search(r"(?:NON.COMMERCIAL|CC[- ]BY[- ]NC|\bNC\b)", claims):
                flags.append("noncommercial-review")
            if re.search(r"\b(?:A?GPL|LGPL)[ -]?(?:V?\d|LICENSE)", claims):
                flags.append("copyleft-review")
            elif "GPL" in all_claims and len(raw) > 320:
                flags.append("bundled-third-party-review")
            if not license_files:
                flags.append("license-text-not-in-wheel")
            found.append({
                "name": str(meta.get("Name") or ""), "version": str(meta.get("Version") or ""),
                "filename": wheel.name, "license_claim": short,
                "license_classifiers": classifiers,
                "license_files": license_files[:20],
                "flags": flags,
            })
    return found


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime-id", required=True)
    p.add_argument("--source", type=Path, required=True)
    args = p.parse_args()
    draft = draft_lock(ROOT, args.runtime_id, args.source)
    audit = audit_wheels(args.source)
    if len(audit) != len(draft["wheels"]):
        raise WheelhouseError("incomplete wheel inventory")
    warnings = [{"name": x["name"], "flags": x["flags"]}
                for x in audit if x["flags"]]
    result = {
        "status": "manual-review-required",
        "legal_clearance": False,
        "runtime_id": args.runtime_id,
        "wheels": audit,
        "review_queue": warnings,
        "note": "Do not infer redistribution/commercial rights from hashes or package classifiers.",
    }
    out = ROOT / "cache" / "wheelhouse-rights" / (args.runtime_id + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print("Read-only rights review:", out)
    print("Wheels:", len(audit), "flagged for manual review:",
          len(warnings), "legal clearance: NOT GRANTED")
    for row in warnings:
        print(" -", row["name"], ": ", ", ".join(row["flags"]))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print("Wheelhouse audit failed:", exc, file=sys.stderr)
        raise SystemExit(1)
