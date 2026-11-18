"""Opt-in, offline M2M100 real-inference verification for an extracted Portable.

Loads only the installed first-party native-v2 model using its isolated worker.
Uses two fixed non-sensitive short examples, never changes user settings or
downloads data. This is NOT a semantic accuracy or commercial-rights audit.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from .m2m_runtime import M2MRuntimeError, TranslationWorkerSession, ready
from .translation_protocol import TranslationContractError, validate_translation
from .universal_model_packages import native_translation_packages

ROOT = Path(__file__).resolve().parents[2]
MODEL_ID = "m2m100-418m@1.0.0"
SAMPLES = (("en", "th", "Good morning."), ("th", "en", "ขอบคุณครับ"))


def verify(root: Path = ROOT, *, timeout: float = 120.0) -> dict[str, Any]:
    """Run two small translations in one isolated session (no network)."""
    root = Path(root)
    if not 15 <= timeout <= 180:
        raise ValueError("translation verification timeout must be 15-180 seconds")
    if not ready(root):
        raise M2MRuntimeError(
            "M2M100 isolated runtime is not ready; install the verified wheelhouse "
            "or repair the runtime in Settings")
    candidates = native_translation_packages(root)
    if not any(
        m["package_id"] == "m2m100-418m" and m["version"] == "1.0.0"
        for m, _ in candidates
    ):
        raise M2MRuntimeError(
            "M2M100 native-v2 model package is not installed or failed verification")
    session = TranslationWorkerSession(root=root, timeout=timeout)
    outputs = []
    started = time.monotonic()
    try:
        for source, target, phrase in SAMPLES:
            started_call = time.monotonic()
            result = session.translate(phrase, {
                "model": MODEL_ID,
                "source_language": source,
                "target_language": target,
            })
            if not isinstance(result, str) or not result.strip():
                raise M2MRuntimeError("M2M100 worker returned empty translation")
            if result.strip().casefold() == phrase.strip().casefold():
                raise M2MRuntimeError(
                    "M2M100 returned unchanged source instead of translation")
            try:
                # The smoke test must detect a wrong-script output even if the
                # worker responded 'ok'. This is a structural/script check,
                # not proof of linguistic accuracy or commercial rights.
                validate_translation(phrase, result, target)
            except TranslationContractError as exc:
                raise M2MRuntimeError(
                    "M2M100 output does not satisfy target-language checks") from exc
            outputs.append({
                "source_language": source,
                "target_language": target,
                "source_text": phrase,
                "translation": result,
                "elapsed_seconds": round(time.monotonic() - started_call, 3),
            })
    finally:
        session.close()
    return {
        "format": "voxweavetts.m2m100-inference-check-v1",
        "model": MODEL_ID,
        "runtime": "isolated-cpu-worker",
        "offline": True,
        "success": True,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "samples": outputs,
        "limitations": (
            "Semantic accuracy and language fluency require human review; "
            "M2M100 is experimental for live chat."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable result")
    parser.add_argument("--timeout", type=float, default=120.0,
                        help="maximum seconds per translation, 15-180")
    args = parser.parse_args(argv)
    try:
        result = verify(timeout=args.timeout)
    except (ValueError, OSError, M2MRuntimeError) as exc:
        print("M2M100 verification failed: " + str(exc), file=sys.stderr)
        return 2
    if args.json:
        # ASCII-only by default, even when a Windows console uses cp1252.
        print(json.dumps(result, indent=2))
    else:
        print("M2M100 real isolated-worker translation: passed")
        for row in result["samples"]:
            print(
                f"  {row['source_language']}->{row['target_language']}: "
                f"{row['source_text']} -> {row['translation']} "
                f"({row['elapsed_seconds']} seconds)")
        print(result["limitations"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
