"""Temporary clean Portable + M2M100 native-v2 model/offline wheels + real translation.

No change to production model paths, runtime, user settings or Windows Python.
The test copies only the staged release tree and extracts audited Release assets
into its own disposable directory. Each test phase is reported separately from
Windows cleanup errors, which can transiently lock large safetensors files.
Run manually from a source checkout with previously built release assets;
this script is NOT included in the distributable Portable ZIP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT/"dist"/"VoxWeaveTTS"
MODEL = ROOT/"dist"/"ModelPackagesV2"/"VoxWeaveTTS-M2M100-418M-v1.0.0-format-v2.vwmodel"
WHEEL = ROOT/"dist"/"ReleaseV2_0101"/"VoxWeaveTTS-m2m100-win_amd64-py311-wheelhouse.zip"
started = time.monotonic()

def log(*args):
    print("M2M_FRESH_PORTABLE",*args,round(time.monotonic()-started,1),flush=True)

def run(app, code, timeout=300):
    env=os.environ.copy()
    env["PATH"]=str(Path(env.get("SystemRoot",r"C:\Windows"))/"System32")
    for key in ("VIRTUAL_ENV","PYTHONHOME","UV_PYTHON"):
        env.pop(key,None)
    env.update({"PYTHONPATH":str(app/"src"),"PYTHONNOUSERSITE":"1",
                "PYTHONIOENCODING":"utf-8","HF_HUB_OFFLINE":"1",
                "TRANSFORMERS_OFFLINE":"1"})
    python=app/"runtime"/"python"/"python.exe"
    reply=subprocess.run([str(python),"-c",code],cwd=app,env=env,
                         text=True,encoding="utf-8",errors="replace",
                         capture_output=True,timeout=timeout)
    log("CHILD_EXIT",reply.returncode,
        "OUT",reply.stdout[-900:].replace("\r",""),
        "ERR",reply.stderr[-900:].replace("\r",""))
    if reply.returncode:
        raise RuntimeError("Clean Portable verification failed")
    return reply.stdout

def cleanup_test_root(folder: Path, *, attempts=30, delay=1.0) -> bool:
    """Remove ONLY our disposable test directory; wait for Windows scanners.

    A completed inference test can pass even if Windows temporarily holds the
    large model weights open. Never delete or alter the original model files.
    """
    workspace = (ROOT/"cache"/"temp").resolve()
    if (folder.parent.resolve()!=workspace
        or not folder.name.startswith("m2m100-fresh-portable-")
        or folder.is_symlink()):
        raise ValueError("refusing cleanup outside controlled test workspace")
    for index in range(attempts):
        try:
            if folder.exists():
                shutil.rmtree(folder)
            return True
        except (PermissionError, OSError) as exc:
            if index == attempts-1:
                log("CLEANUP_BLOCKED_BY_WINDOWS_FILE_LOCK",type(exc).__name__,
                    "disposable_directory",str(folder))
                return False
            time.sleep(delay)
    return False

def main() -> None:
    assert all(p.is_file() for p in (MODEL,WHEEL)), "Build model and wheelhouse first"
    assert (STAGE/"src"/"voxweavetts"/"m2m_smoke.py").is_file(), "Rebuild updated Portable stage"
    assert (STAGE/"runtime"/"tools"/"uv.exe").is_file()
    ( ROOT/"cache"/"temp" ).mkdir(parents=True,exist_ok=True)
    parent=Path(tempfile.mkdtemp(prefix="m2m100-fresh-portable-",
                                dir=ROOT/"cache"/"temp"))
    passed=False
    try:
        app=parent/"VoxWeaveTTS"
        log("COPY_CLEAN_PORTABLE")
        shutil.copytree(STAGE,app)
        log("EXTRACT_VERIFIED_WHEELHOUSE")
        with zipfile.ZipFile(WHEEL) as archive:
            assert archive.testzip() is None
            archive.extractall(app)
        log("INSTALL_NATIVE_V2_MODEL")
        run(app,
            "from voxweavetts.universal_model_packages import install_model_package;"
            "from pathlib import Path;"
            "r=install_model_package(Path("+repr(str(MODEL))+"),root=Path.cwd());"
            "print('NATIVE_V2_M2M_MODEL_INSTALL',r['package_id'],r['format_version']);",
            timeout=180)
        log("INSTALL_OFFLINE_M2M_RUNTIME")
        run(app,
            "from pathlib import Path;"
            "from voxweavetts.verified_runtime_installer import install_verified;"
            "from voxweavetts.runtime_registry import inventory;"
            "p=install_verified('m2m100',root=Path.cwd());"
            "r=next(x for x in inventory(Path.cwd()) if x['id']=='m2m100');"
            "assert r['ready'] and r['health_state']=='ready';"
            "print('OFFLINE_M2M_RUNTIME_INSTALLED',p.relative_to(Path.cwd()));",
            timeout=240)
        log("SMOKE_REAL_TRANSLATION")
        run(app,
            "import json;"
            "from voxweavetts.m2m_smoke import verify;"
            "from pathlib import Path;"
            "r=verify(Path.cwd(),timeout=65);"
            "assert r['success'] and len(r['samples'])==2;"
            "print('FIRST_TRANSLATION_2_LANGUAGES',r['elapsed_seconds'],"
            "[(x['source_language'],x['target_language']) for x in r['samples']]);",
            timeout=180)
        moved=parent/"Relocated-VoxWeaveTTS"
        app.rename(moved)
        log("RELOCATED_FOLDER")
        run(moved,
            "from pathlib import Path;"
            "from voxweavetts.portable_doctor import report;"
            "r=report(Path.cwd());"
            "w=next(x for x in r['runtimes'] if x['id']=='m2m100');"
            "assert w['health_state']=='relocated';"
            "print('M2M_RUNTIME_RELOCATED_DETECTED',w['health_state']);",
            timeout=90)
        log("REBUILD_RELOCATED_RUNTIME_FROM_VERIFIED_WHEELS")
        run(moved,
            "from pathlib import Path;"
            "from voxweavetts.verified_runtime_installer import install_verified;"
            "from voxweavetts.runtime_registry import inventory;"
            "install_verified('m2m100',root=Path.cwd());"
            "r=next(x for x in inventory(Path.cwd()) if x['id']=='m2m100');"
            "assert r['ready'];print('RELOCATED_M2M_RUNTIME_REPAIRED');",
            timeout=240)
        log("SMOKE_TRANSLATION_AFTER_REPAIR")
        run(moved,
            "from pathlib import Path;"
            "from voxweavetts.m2m_smoke import verify;"
            "r=verify(Path.cwd(),timeout=65);"
            "assert r['success'] and len(r['samples'])==2;"
            "print('RELOCATED_REAL_M2M_TRANSLATION_OK',r['elapsed_seconds']);",
            timeout=180)
        passed=True
    finally:
        cleaned=cleanup_test_root(parent)
        if cleaned:
            log("DISPOSABLE_TEST_FOLDER_CLEANED")
        elif passed:
            raise RuntimeError(
                "M2M100 install/translation/relocation passed, but Windows "
                "still holds a disposable test file; cleanup must be retried")
    if passed:
        log("ALL_ISOLATED_M2M_PORTABLE_TESTS_PASSED_AND_CLEANED")


if __name__ == "__main__":
    main()
