"""Copy unmodified upstream licenses for binary Wheels lacking embedded text.

A source (GitHub) tag/branch is resolved to a pinned 40-char commit first;
copies and SHA-256 provenance stay in the local, ignored rights-evidence area.
This only gathers legal evidence; it does not assert redistribution clearance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import requests

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"cache"/"v4-rights-evidence"/"runtime-sources"

SOURCES=[
    ("flatbuffers","google/flatbuffers","v25.12.19","LICENSE"),
    ("sentencepiece","google/sentencepiece","v0.2.1","LICENSE"),
    # ONNXRuntime source endpoint is currently unavailable to this validator;
    # do not synthesize or substitute a different license document.
]


def get_json(url: str) -> dict:
    result=requests.get(url,timeout=14)
    result.raise_for_status()
    return result.json()


def copy() -> dict:
    out={}
    for name,repo,ref,source_file in SOURCES:
        ref_data=get_json(f"https://api.github.com/repos/{repo}/git/ref/"
                          +("heads/" if ref in ("main", "master") else "tags/")+ref)
        obj=ref_data["object"]
        if obj["type"]=="tag":
            obj=get_json(f"https://api.github.com/repos/{repo}/git/tags/{obj['sha']}")["object"]
        if obj["type"]!="commit" or len(obj["sha"])!=40:
            raise ValueError("expected pinned GitHub commit: "+repo)
        revision=obj["sha"]
        url=f"https://raw.githubusercontent.com/{repo}/{revision}/{source_file}"
        response=requests.get(url,timeout=15)
        response.raise_for_status()
        data=response.content
        if len(data)>300_000 or b"\0" in data:
            raise ValueError("non-text upstream legal document")
        item=DEST/name
        item.mkdir(parents=True,exist_ok=True)
        path=item/(source_file+".txt")
        if path.exists() and path.read_bytes()!=data:
            raise ValueError("original license text changed unexpectedly: "+repo)
        path.write_bytes(data)
        digest=hashlib.sha256(data).hexdigest()
        out[name]={"repository":repo,"revision":revision,"tag_or_ref":ref,
                   "url":url,"sha256":digest,"bytes":len(data),
                   "local_copy":path.relative_to(ROOT).as_posix(),
                   "scope":"upstream source for a runtime dependency; does not relicense the wheel"}
        print("VERIFIED_UPSTREAM_RUNTIME_LICENSE",name,revision[:12],digest[:12],flush=True)
    (DEST/"INDEX.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    return out


if __name__=="__main__":
    copy()
