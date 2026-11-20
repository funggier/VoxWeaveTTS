"""Create a private v4 demo with a NEW dependency wheel not known to Core.

The fixture uses a local, original Python library v4fixture. A real plugin can
replace both this library and worker with a TTS runtime/model, without an app
update. No internet access. Output remains under cache/, not GitHub Releases.
"""
from __future__ import annotations

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
sys.path.insert(0, str(ROOT / "scripts"))
QA = ROOT / "cache" / "temp" / "v4-wheel-qa"
ARCHIVE = ROOT / "cache" / "v4-qa-candidates" / "demo-wheel-plugin-format-v4.vwmodel"
WHEEL = "v4fixture-1.0.0-py3-none-any.whl"
RECORD = "v4fixture-1.0.0.dist-info/RECORD"


def make_wheel(target: Path) -> None:
    files = {
        "v4fixture/__init__.py": (
            '"""Private original QA library."""\n'
            'def tone_seed(text):\n    return sum(ord(ch) for ch in text)\n'
        ).encode(),
        "v4fixture-1.0.0.dist-info/METADATA": (
            "Metadata-Version: 2.1\nName: v4fixture\nVersion: 1.0.0\n"
            "Summary: Original local-only v4 package QA fixture\n"
        ).encode(),
        "v4fixture-1.0.0.dist-info/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: VoxWeaveTTS-v4-QA\n"
            "Root-Is-Purelib: true\nTag: py3-none-any\n"
        ).encode(),
    }
    record = io.StringIO()
    out = csv.writer(record, lineterminator="\n")
    for name, raw in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
        out.writerow([name, "sha256=" + digest, str(len(raw))])
    out.writerow([RECORD, "", ""])
    files[RECORD] = record.getvalue().encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zip_out:
        for name, raw in files.items():
            zip_out.writestr(name, raw)


def main() -> None:
    if QA.exists() or ARCHIVE.exists():
        raise ValueError("QA fixture already built; never overwrite it")
    (QA / "plugin").mkdir(parents=True)
    (QA / "runtime" / "wheels").mkdir(parents=True)
    (QA / "assets").mkdir()
    make_wheel(QA / "runtime" / "wheels" / WHEEL)
    # The new plugin imports the package from the *isolated* v4 site-packages.
    worker = (ROOT / "examples/v4-demo-tone/plugin/worker.py").read_text(encoding="utf-8")
    worker = worker.replace("import base64\n", "import base64\nfrom v4fixture import tone_seed\n")
    worker = worker.replace("sum(map(ord, text))", "tone_seed(text)")
    (QA / "plugin" / "worker.py").write_text(worker, encoding="utf-8")
    (QA / "assets" / "readme.txt").write_text("Private v4 offline Wheel smoke test, not a speech engine.\n")
    spec = json.loads((ROOT / "examples/v4-demo-tone/spec.json").read_text(encoding="utf-8"))
    spec["package"]["id"] = "demo-wheel-plugin"
    spec["package"]["title"] = "Demo custom dependency wheel (not speech)"
    spec["runtime"]["wheels"] = ["runtime/wheels/" + WHEEL]
    spec_file = ROOT / "cache" / "temp" / "v4-wheel-spec.json"
    spec_file.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    from build_vwmodel_v4 import build
    output = build(QA, spec_file, ARCHIVE)
    print("V4_NEW_WHEEL_ARCHIVE",output,output.stat().st_size,flush=True)


if __name__ == "__main__":
    main()
