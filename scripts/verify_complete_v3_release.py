"""Release gate: require every legacy voice option as a complete v3 offline model.

This intentionally fails for the incomplete v0.11.0 inventory. Missing models
or runtime redistribution HOLDS must not be silently omitted when a release is
advertised as having a complete model catalog. The audit is read-only.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from voxweavetts.universal_model_packages import inspect_archive
from voxweavetts.provider_rights import review

EXPECTED = {
    "makham-paradee": ("tts", "makham-paradee-onnx-v1", "pythaitts"),
    "fastthaig2p-thai-som": ("tts", "fastthaig2p-kokoro-v1", "pythaitts"),
    "vachana-thai-four-voices": ("tts", "vachana-onnx-v1", "vachana"),
    "kokoro-multilingual-int8": ("tts", "kokoro-onnx-v1", "kokoro"),
    "wayu-paxa-edge-nc": ("tts", "wayu-nc-v1", "wayu-nc"),
    "melo-chinese-onnx": ("tts", "sherpa-melo-zh-v1", "sherpa"),
    "supertonic3-multilingual-int8": ("tts", "sherpa-supertonic-v1", "sherpa"),
    "m2m100-418m": ("translation", "m2m100-transformers-v1", "m2m100"),
}


def inspect_release(directory: Path, repo: Path = ROOT) -> dict:
    installed: dict[str, dict] = {}
    issues: list[str] = []
    for archive in sorted(Path(directory).glob("*.vwmodel")):
        try:
            manifest = inspect_archive(archive)
            name = manifest["package"]["id"]
            if name not in EXPECTED:
                issues.append("unknown v3 package: " + name)
                continue
            if name in installed:
                issues.append("duplicate v3 package identity: " + name)
                continue
            kind, adapter, runtime = EXPECTED[name]
            if (manifest["package"]["kind"] != kind
                or manifest["adapter"]["id"] != adapter
                or manifest["runtime"]["id"] != runtime):
                issues.append("unexpected v3 adapter/runtime: " + name)
                continue
            installed[name] = manifest
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            issues.append("invalid package " + archive.name + ": " + type(exc).__name__)
    missing = sorted(set(EXPECTED) - set(installed))
    for name in missing:
        issues.append("missing complete offline v3 package: " + name)
    # A model archive's own rights metadata cannot self-authorize publication
    # of executable wheels. Only app-owned trusted wheel locks and the
    # developer's explicitly reviewed redistribution gate can permit it.
    for name, manifest in installed.items():
        provider = EXPECTED[name][2]
        if manifest["runtime"]["source"] == "bundled-wheels":
            trusted = repo / "scripts" / "wheelhouse-locks" / (provider + ".json")
            if not trusted.is_file():
                issues.append("missing app-owned approved wheel lock: " + provider)
            state = review(provider)
            if state["offline_wheelhouse_release_allowed"] is False:
                issues.append("unresolved dependency rights HOLD: " + provider)
        elif manifest["runtime"]["source"] != "core-bundled":
            issues.append("non-offline v3 runtime: " + name)
    # Additional audit: even if a candidate is accidentally copied into the
    # release staging folder, it must not pass by its self-declared hash.
    return {
        "format": "voxweavetts.complete-v3-release-audit",
        "complete": not issues,
        "expected_model_count": len(EXPECTED),
        "found_model_count": len(installed),
        "missing": missing,
        "issues": issues,
    }


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--packages", type=Path, default=ROOT / "dist" / "ModelPackagesV3")
    cli.add_argument("--json", action="store_true")
    args = cli.parse_args()
    report = inspect_release(args.packages)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("COMPLETE_V3_RELEASE", "PASS" if report["complete"] else "BLOCKED")
        for item in report["issues"]:
            print("BLOCKER", item)
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
