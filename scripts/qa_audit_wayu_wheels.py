"""Read-only QA audit of candidate Wayu wheel bytes (no installation/execution).

Outputs a private report under cache/v3-unreleased-candidates. A clean ZIP
structure does NOT certify legal permission to distribute dependencies.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path
from packaging.utils import parse_wheel_filename

ROOT=Path(__file__).resolve().parents[1]
WHEELS=ROOT/"cache"/"temp"/"qa-wayu-wheels"
REPORT=ROOT/"cache"/"v3-unreleased-candidates"/"wayu-wheel-audit.json"

def audit(root: Path=WHEELS)->dict:
    report=[]
    for file in sorted(Path(root).glob("*.whl")):
        name,version,build,tags=parse_wheel_filename(file.name)
        if not any(str(tag).endswith(("-win_amd64","-any")) for tag in tags):
            raise ValueError("unexpected wheel platform: "+file.name)
        with file.open("rb") as stream:
            digest=hashlib.file_digest(stream,"sha256").hexdigest()
        with zipfile.ZipFile(file) as archive:
            scripts=[]
            licenses=[]
            for item in archive.infolist():
                if item.filename.lower().endswith(".pth") or ".data/scripts/" in item.filename.lower():
                    scripts.append(item.filename)
                if ("license" in item.filename.lower()
                    and (".dist-info/" in item.filename or ".dist-info/licenses/" in item.filename)):
                    licenses.append(item.filename)
        report.append({
            "filename":file.name, "name":str(name), "version":str(version),
            "bytes":file.stat().st_size, "sha256":digest,
            "v3_rejected_members":scripts[:30],
            "license_file_present":bool(licenses),
        })
    duplicates={}
    for row in report:
        duplicates.setdefault(row["name"].casefold(),[]).append(row["version"])
    duplicate_names={k:v for k,v in duplicates.items() if len(v)>1}
    return {
        "format":"voxweavetts.wayu-v3-offline-qa-audit",
        "qa_only":True,"cleared_for_publication":False,
        "wheel_count":len(report),
        "size_mib":round(sum(r["bytes"] for r in report)/1048576,2),
        "rejected_wheels":[{"name":r["name"],"members":r["v3_rejected_members"]}
                           for r in report if r["v3_rejected_members"]],
        "missing_license_file_in_wheel":[r["name"] for r in report
                                          if not r["license_file_present"]],
        "duplicate_names":duplicate_names,
        "wheels":report,
    }

def main()->None:
    data=audit()
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    brief={k:v for k,v in data.items() if k!="wheels"}
    print(json.dumps(brief,ensure_ascii=False,indent=2),flush=True)
    print("READ_ONLY_QA_AUDIT_WRITTEN",REPORT,flush=True)

if __name__=="__main__":
    main()
