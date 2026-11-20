"""Produce a private QA copy of Vachana's wheel set without the unused ssg-cli.

The original third-party wheel remains byte-for-byte unchanged. Output is
stored under cache/ and MUST NOT be used in a public .vwmodel release: this
does not resolve vachanatts wheel licensing or third-party redistribution.
No wheel code is imported or executed.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cache" / "temp" / "phasec-vachana-candidate"
OUTPUT = ROOT / "cache" / "temp" / "qa-vachana-scriptless"
SSG_WHEEL = "ssg-0.0.8-py3-none-any.whl"
SSG_SHA256 = "15bc2a4307d1d37a5a77385f8b26178fcaada6c7bf2bf40511d1330f55d395c0"
SCRIPT = "ssg-0.0.8.data/scripts/ssg-cli"
RECORD = "ssg-0.0.8.dist-info/RECORD"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def strip_script(original: Path, output: Path, *,
                 expected_wheel: str = SSG_WHEEL, forbidden_script: str = SCRIPT,
                 record_path: str = RECORD,
                 expected_source_sha256: str = SSG_SHA256) -> dict:
    if original.name != expected_wheel:
        raise ValueError("not an approved ssg source wheel")
    if sha256(original) != expected_source_sha256:
        raise ValueError("source wheel differs from explicitly reviewed SHA-256 pin")
    output.parent.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[zipfile.ZipInfo, bytes]] = []
    with zipfile.ZipFile(original, "r") as wheel:
        contents = set(wheel.namelist())
        if forbidden_script not in contents or record_path not in contents:
            raise ValueError("source ssg wheel differs from the reviewed layout")
        for entry in wheel.infolist():
            if entry.filename in (forbidden_script, record_path):
                continue
            if entry.is_dir() or not entry.filename or entry.filename.startswith("/"):
                raise ValueError("unexpected wheel ZIP member")
            data = wheel.read(entry)
            entries.append((entry, data))
    # A wheel's RECORD must describe the new installed payload exactly.
    out_record = io.StringIO(newline="")
    writer = csv.writer(out_record, lineterminator="\n")
    for entry, data in entries:
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii").rstrip("=")
        writer.writerow([entry.filename, "sha256=" + digest, str(len(data))])
    writer.writerow([record_path, "", ""])
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as dest:
        for entry, data in entries:
            dest.writestr(entry, data)
        dest.writestr(record_path, out_record.getvalue().encode("utf-8"))
    with zipfile.ZipFile(output) as dest:
        if forbidden_script in dest.namelist() or record_path not in dest.namelist():
            raise ValueError("script removal verification failed")
        for row in csv.reader(io.StringIO(dest.read(record_path).decode("utf-8"))):
            if len(row) != 3:
                raise ValueError("malformed new wheel RECORD")
            if row[0] == record_path:
                if row[1:] != ["", ""]:
                    raise ValueError("RECORD must have blank self-digest")
                continue
            data = dest.read(row[0])
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii").rstrip("=")
            if row[1] != "sha256=" + digest or row[2] != str(len(data)):
                raise ValueError("new wheel RECORD hash/size mismatch")
    return {
        "source": str(original), "original_sha256": sha256(original),
        "qa_copy": str(output), "qa_sha256": sha256(output),
        "removed": [forbidden_script], "for_publication": False,
    }


def prepare(source: Path = SOURCE, target: Path = OUTPUT) -> dict:
    if target.exists() or target.is_symlink():
        raise ValueError("private QA output already exists: " + str(target))
    if not source.is_dir() or target.resolve().is_relative_to(source.resolve()):
        raise ValueError("invalid QA wheel source/target")
    originals = sorted(source.glob("*.whl"))
    if SSG_WHEEL not in {x.name for x in originals} or len(originals) < 10:
        raise ValueError("not a complete Vachana source wheel set")
    target.mkdir(parents=True)
    for wheel in originals:
        if wheel.name == SSG_WHEEL:
            result = strip_script(wheel, target / wheel.name)
        else:
            shutil.copyfile(wheel, target / wheel.name)
            if sha256(wheel) != sha256(target / wheel.name):
                raise ValueError("source wheel changed during private QA copy")
    (target / "QA-ONLY.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source", type=Path, default=SOURCE)
    cli.add_argument("--target", type=Path, default=OUTPUT)
    args = cli.parse_args()
    report = prepare(args.source, args.target)
    print("PRIVATE_QA_SCRIPTLESS_WHEEL", json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
