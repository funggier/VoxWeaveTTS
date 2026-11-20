"""One-time v4 QA migration: add explicit language per multilingual voice.

No model weights, runtime wheels or code are changed. The two private
UNRELEASED-QA v4 archives are rewritten with only their manifest's
voice_language_map metadata added. All asset hashes and sizes are checked
against the pre-existing manifest while copying. Never publishes anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"dist/ModelPackagesV4-QA"
_KOKORO={
    "a":"en","b":"en","e":"es","f":"fr",
    "h":"hi","i":"it","j":"ja","p":"pt",
}


def _hash(file: Path) -> str:
    with file.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def _map(model: str, m: dict) -> dict[str,str]:
    voice_ids=[item["id"] for item in m["engine"]["voices"]]
    if model=="supertonic3-multilingual-int8":
        mapping={vid:vid.split("_s",1)[0] for vid in voice_ids}
    elif model=="kokoro-multilingual-int8":
        mapping={vid:_KOKORO[vid[0]] for vid in voice_ids}
    else:
        raise ValueError("not an explicitly reviewed multilingual v4 QA archive")
    if len(mapping)!=len(voice_ids) or not set(mapping.values()) <= set(m["package"]["languages"]):
        raise ValueError("voice-to-language map is incomplete or not declared")
    return mapping


def rewrite(model: str) -> dict:
    archives=list(QA.glob("VoxWeaveTTS-"+model+"-*-UNRELEASED-QA-format-v4.vwmodel"))
    if len(archives)!=1:
        raise ValueError("expected exactly one QA v4 model for "+model)
    original=archives[0]
    with zipfile.ZipFile(original) as z:
        m=json.loads(z.read("manifest.json"))
        if m["format_version"]!=4 or m["package"]["id"]!=model:
            raise ValueError("source is not a verified v4 model")
        if "voice_language_map" in m["engine"]:
            return {"model":model,"already_mapped":True}
    mapping=_map(model,m)
    m["engine"]["voice_language_map"]=mapping
    import sys
    sys.path.insert(0,str(ROOT/"src"))
    from voxweavetts.universal_model_v4 import validate_manifest,inspect_archive
    validate_manifest(m)
    before=_hash(original)
    fd,name=tempfile.mkstemp(prefix=".v4-multilingual-",suffix=".vwmodel",dir=QA)
    os.close(fd)  # Windows cannot rename/delete an open mkstemp descriptor
    temp=Path(name)
    try:
        indexed={r["path"]:r for r in m["files"]}
        with zipfile.ZipFile(original,"r") as z,zipfile.ZipFile(
                temp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=5,
                allowZip64=True) as out:
            out.writestr("manifest.json",json.dumps(m,ensure_ascii=False,
                         separators=(",",":")).encode("utf-8"))
            for entry in z.infolist():
                if entry.filename=="manifest.json":
                    continue
                row=indexed[entry.filename]
                digest=hashlib.sha256()
                amount=0
                with z.open(entry) as src,out.open(entry.filename,"w",force_zip64=True) as dest:
                    for chunk in iter(lambda: src.read(1024*1024),b""):
                        amount+=len(chunk)
                        digest.update(chunk)
                        dest.write(chunk)
                if amount!=row["size"] or digest.hexdigest()!=row["sha256"]:
                    raise ValueError("v4 asset hash drift: "+entry.filename)
        rebuilt=inspect_archive(temp)
        if rebuilt["engine"]["voice_language_map"]!=mapping:
            raise ValueError("v4 language map not preserved")
        after=_hash(temp)
        os.replace(temp,original)
        return {"model":model,"sha256_before":before,"sha256_after":after,
                "voices_mapped":len(mapping),"data_assets_unchanged":True,
                "public_release_authorized":False}
    finally:
        temp.unlink(missing_ok=True)


def main():
    report=[rewrite(name) for name in ("supertonic3-multilingual-int8",
                                      "kokoro-multilingual-int8")]
    folder=ROOT/"cache/v4-qa-candidates"
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/"voice-language-upgrade-report.json"
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                    encoding="utf-8")
    print("V4_VOICE_LANGUAGE_MAP_QA",json.dumps(report,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
