"""Build a private, NOT-for-publication Wayu Paxa Edge NC v3 QA package.

Combines exact SHA-pinned upstream NC weights with third-party candidate wheels
acquired during build time. The final archive installs with zero network access
only after an ephemeral, QA-only trusted wheel hash lock is configured in a
disposable Portable stage.

This tool DOES NOT audit licenses or authorize redistribution. Never copy its
output into dist/ModelPackagesV3 or a GitHub release.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import sys
from pathlib import Path
from packaging.utils import parse_wheel_filename

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
NAME="wayu-paxa-edge-nc"
CACHE=ROOT/"cache"
QA=CACHE/"v3-unreleased-candidates"
WHEELS=CACHE/"temp"/"qa-wayu-wheels"
STAGE=QA/(NAME+"-qa-source")
ARCHIVE=QA/(NAME+"-UNRELEASED-QA-offline-format-v3.vwmodel")
SETUP_PREFIX="setuptools-"
SETUP_PIN="ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2"
WAYU_SOURCE_WHEEL_PIN="66558a9a7ececc935ee1ef37d75d27fa0692981674d88f08633f989894233389"

def digest(file: Path) -> str:
    with file.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()

def build()->dict:
    if STAGE.exists() or STAGE.is_symlink() or ARCHIVE.exists() or ARCHIVE.is_symlink():
        raise ValueError("QA Wayu stage/archive already exist; never overwrite")
    files=sorted(WHEELS.glob("*.whl"))
    if len(files)<100 or not any(f.name.startswith("wayu_tts-") for f in files):
        raise ValueError("offline Wayu QA wheel closure incomplete")
    if not any(f.name.startswith("en_core_web_sm-") for f in files):
        raise ValueError("spaCy language model missing from offline closure")
    from prepare_missing_v3_candidates import prepared_original
    from qa_rebuild_vachana_wheel import strip_script
    original=prepared_original(NAME,STAGE)
    wheel_dest=STAGE/"runtime"/"wheels"
    wheel_dest.mkdir(parents=True)
    requirements={}
    pins=[]
    scriptless=[]
    for file in files:
        name,version,build_tag,tags=parse_wheel_filename(file.name)
        if not any(str(tag).endswith(("-win_amd64","-any")) for tag in tags):
            raise ValueError("unapproved Windows wheel platform")
        key=str(name).replace("_","-").lower()
        if key in requirements:
            raise ValueError("duplicate wheel package identity: "+key)
        requirements[key]={"name":str(name), "version":str(version)}
        dst=wheel_dest/file.name
        if file.name.startswith("wayu_tts-") and digest(file)!=WAYU_SOURCE_WHEEL_PIN:
            raise ValueError("Wayu inference wheel differs from pinned upstream build")
        if file.name.startswith(SETUP_PREFIX):
            with __import__("zipfile").ZipFile(file) as z:
                records=[x for x in z.namelist() if x.count("/")==1
                         and x.startswith("setuptools-") and x.endswith(".dist-info/RECORD")]
            if len(records)!=1:
                raise ValueError("unexpected setuptools wheel record layout")
            result=strip_script(file,dst,expected_wheel=file.name,
                                forbidden_script="distutils-precedence.pth",
                                record_path=records[0],
                                expected_source_sha256=SETUP_PIN)
            scriptless.append(result)
        else:
            shutil.copyfile(file,dst)
            if digest(file)!=digest(dst):
                raise ValueError("copy failed verification: "+file.name)
        pins.append({"path":"runtime/wheels/"+file.name,"sha256":digest(dst)})
    lock={"requirements":[requirements[k] for k in sorted(requirements)],
          "wheels":pins}
    path=STAGE/"runtime"/"locks"/"approved.lock"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(lock,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    existing=sorted(f.relative_to(STAGE).as_posix() for f in STAGE.rglob("*") if f.is_file())
    excluded={"manifest-assets.json","legal/rights.json","runtime/locks/approved.lock"}
    (STAGE/"manifest-assets.json").write_text(
        json.dumps({"paths":[p for p in existing if p not in excluded]},
                   ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    spec={
        "package":{
            "id":NAME,"version":original["version"],"kind":"tts",
            "title":original["title"],"languages":["th","en"],
        },
        "adapter":{"id":"wayu-nc-v1","api_version":1,"trust":"builtin"},
        "runtime":{
            "id":"wayu-nc","kind":"python-target","python":"3.11",
            "platform":"windows-x64","accelerator":"cpu",
            "source":"bundled-wheels","install_policy":"auto",
            "lockfile":"runtime/locks/approved.lock",
        },
        "capabilities":{
            "language":"th","sample_rate":24000,"voices":original["voices"],
        },
    }
    spec_path=QA/(NAME+"-QA-spec.json")
    spec_path.write_text(json.dumps(spec,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    from build_vwmodel_v3 import build as native_build
    output=native_build(STAGE,spec_path,ARCHIVE)
    return {
        "qa_archive":str(output),"wheels":len(files),
        "source_weights_version":original["version"],
        "license":original["license"]["spdx"],"scriptless_qa":scriptless,
        "for_publication":False,"notices_reviewed":False,
        "sha256":digest(output),
    }

if __name__=="__main__":
    print("WAYU_V3_OFFLINE_QA_BUILD",json.dumps(build(),ensure_ascii=False),flush=True)
