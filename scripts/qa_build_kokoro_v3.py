"""Build an isolated private Kokoro v3 QA archive without plac_runner script.

Requires the pinned v3 draft and cached wheels. Kept entirely under cache/;
NOT approved for publication while phonemizer/espeak/JP frontend compliance
remains under review. No network and no execution of upstream wheel code.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache"
QA = CACHE / "v3-unreleased-candidates"
WHEEL_SOURCE = CACHE / "temp" / "phasec-kokoro-candidate"
WHEEL_COPY = CACHE / "temp" / "qa-kokoro-scriptless"
NAME = "kokoro-multilingual-int8"
SOURCE = QA / (NAME + "-source")
STAGE = QA / (NAME + "-qa-scriptless-source")
ARCHIVE = QA / (NAME + "-UNRELEASED-QA-scriptless-format-v3.vwmodel")
PLAC = "plac-1.4.7-py2.py3-none-any.whl"
PLAC_CLI = "plac-1.4.7.data/scripts/plac_runner.py"
PLAC_RECORD = "plac-1.4.7.dist-info/RECORD"
PLAC_SOURCE_SHA256 = "8af4bcd5d52e06c31fab641bffb7040d0eb0e579e2f70a4d2e87af5eed0612ea"


def build() -> dict:
    if not SOURCE.is_dir() or not WHEEL_SOURCE.is_dir():
        raise ValueError("missing private Kokoro native v3 source/compiled wheels")
    if WHEEL_COPY.exists() or STAGE.exists() or ARCHIVE.exists():
        raise ValueError("existing QA output; refusing to modify")
    WHEEL_COPY.mkdir(parents=True)
    sys.path.insert(0, str(ROOT / "scripts"))
    from qa_rebuild_vachana_wheel import strip_script, sha256
    for file in sorted(WHEEL_SOURCE.glob("*.whl")):
        destination = WHEEL_COPY / file.name
        if file.name == PLAC:
            report = strip_script(file, destination, expected_wheel=PLAC,
                                  forbidden_script=PLAC_CLI, record_path=PLAC_RECORD,
                                  expected_source_sha256=PLAC_SOURCE_SHA256)
        else:
            shutil.copyfile(file, destination)
            if sha256(file) != sha256(destination):
                raise ValueError("original Kokoro QA wheel changed")
    (WHEEL_COPY / "QA-ONLY.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    shutil.copytree(SOURCE, STAGE)
    file = STAGE / "runtime" / "wheels" / PLAC
    shutil.copyfile(WHEEL_COPY / PLAC, file)
    with file.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    lock_path = STAGE / "runtime" / "locks" / "approved.lock"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    count = 0
    for row in lock["wheels"]:
        if row["path"] == "runtime/wheels/" + PLAC:
            row["sha256"] = digest
            count += 1
    if count != 1:
        raise ValueError("Kokoro PLAC wheel not indexed exactly once")
    lock_path.write_text(json.dumps(lock, sort_keys=True, indent=2)+"\n", encoding="utf-8")
    from build_vwmodel_v3 import build as build_v3
    result = build_v3(STAGE, QA / (NAME + "-spec.json"), ARCHIVE)
    return {"archive": str(result), "plac_qa_sha256": digest,
            "qa_only": True, "publication_allowed": False}

def main() -> None:
    print("KOKORO_V3_QA_SCRIPTLESS",
          json.dumps(build(), ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
