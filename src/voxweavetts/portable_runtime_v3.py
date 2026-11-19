"""Offline, relocatable runtime pool for Universal .vwmodel v3.

Packages contain wheel bytes and a hash-pinned dependency lock. This module
never downloads, invokes a package-provided installer, executes wheel hooks,
or accepts executable commands from a manifest. Python is the bundled core
interpreter; only the dependency search path is runtime-specific.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import stat
from typing import Any

RUNTIME_FORMAT = "voxweavetts.runtime-v3"
PYTHON_ABI = "3.11"
_LOCK = __import__("threading").RLock()


class OfflineRuntimeError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fingerprint(manifest: dict) -> str:
    """Content identity, independent of model ID and installation root."""
    spec = manifest["runtime"]
    index = {x["path"]: x["sha256"] for x in manifest["files"]}
    identity = {
        "kind": spec["kind"], "python": spec["python"],
        "platform": spec["platform"], "accelerator": spec["accelerator"],
        "source": spec["source"],
        "lock_hash": index.get(spec.get("lockfile"), ""),
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def runtime_folder(root: Path, manifest: dict) -> Path:
    return Path(root) / "runtime" / "environments" / fingerprint(manifest)[:32]


def core_python(root: Path) -> Path:
    root = Path(root)
    path = root / "runtime" / "python" / "python.exe"
    if path.is_file():
        return path
    dev = root / ".venv" / "Scripts" / "python.exe"
    if dev.is_file():
        return dev
    raise OfflineRuntimeError("portable Python 3.11 is missing")


def ready(root: Path, manifest: dict) -> bool:
    spec = manifest["runtime"]
    if spec["source"] == "core-bundled":
        try:
            return core_python(root).is_file()
        except OfflineRuntimeError:
            return False
    if spec["source"] != "bundled-wheels":
        return False
    folder = runtime_folder(root, manifest)
    marker = folder / ".voxweave-runtime-v3.json"
    site = folder / "site-packages"
    try:
        if (not folder.is_dir() or folder.is_symlink()
            or not site.is_dir() or site.is_symlink()
            or not marker.is_file() or marker.is_symlink()
            or marker.stat().st_size > 4096):
            return False
        record = json.loads(marker.read_text(encoding="utf-8"))
        return (record.get("format") == RUNTIME_FORMAT
                and record.get("fingerprint") == fingerprint(manifest)
                and record.get("abi") == PYTHON_ABI
                and record.get("wheel_count") > 0)
    except (OSError, ValueError, TypeError):
        return False


def site_packages(root: Path, manifest: dict) -> Path | None:
    if manifest["runtime"]["source"] == "core-bundled":
        return None
    return runtime_folder(root, manifest) / "site-packages"


def _requirements(lock: dict) -> str:
    """Require an exact SHA-256 for every package; uv resolves only local wheels."""
    from packaging.utils import parse_wheel_filename
    hashes: dict[tuple[str, str], set[str]] = {}
    for wheel in lock["wheels"]:
        name, version, _build, _tags = parse_wheel_filename(Path(wheel["path"]).name)
        key = (str(name).replace("_", "-").lower(), str(version))
        hashes.setdefault(key, set()).add(wheel["sha256"])
    requirements = []
    for item in lock["requirements"]:
        key = (re.sub(r"[-_.]+", "-", item["name"]).lower(), item["version"])
        if key not in hashes:
            raise OfflineRuntimeError("runtime wheel missing for a locked dependency")
        requirements.append(item["name"] + "==" + item["version"] + " " +
                            " ".join("--hash=sha256:" + x for x in sorted(hashes[key])))
    if len(requirements) != len(hashes):
        raise OfflineRuntimeError("runtime contains undeclared wheels")
    return "\n".join(sorted(requirements)) + "\n"


def _approve_bundle(root: Path, manifest: dict, lock: dict) -> None:
    """A model archive cannot choose arbitrary executable Python wheels.

    Only exact wheel hashes previously curated into the application are
    permitted. The entire comparison is local; no network/license server.
    """
    provider = manifest["runtime"]["id"]
    trusted_path = Path(root) / "scripts" / "wheelhouse-locks" / (provider + ".json")
    try:
        if (not trusted_path.is_file() or trusted_path.is_symlink()
            or trusted_path.stat().st_size > 131072):
            raise OfflineRuntimeError("no approved offline wheel bundle for this provider")
        trusted = json.loads(trusted_path.read_text(encoding="utf-8"))
        if (trusted.get("format") != "voxweavetts.trusted-wheel-lock"
            or trusted.get("runtime_id") != provider
            or trusted.get("python_abi") != PYTHON_ABI
            or trusted.get("platform") != "win_amd64"):
            raise OfflineRuntimeError("incompatible trusted runtime lock")
        expected = {entry["filename"]: entry["sha256"]
                    for entry in trusted["wheels"]}
        actual = {Path(entry["path"]).name: entry["sha256"]
                  for entry in lock["wheels"]}
        if actual != expected or len(actual) != len(lock["wheels"]):
            raise OfflineRuntimeError("package wheels do not match locally approved hashes")
        required = {(re.sub(r"[-_.]+", "-", entry["name"]).lower(),
                     entry["version"]) for entry in trusted["wheels"]}
        supplied = {(re.sub(r"[-_.]+", "-", entry["name"]).lower(),
                     entry["version"]) for entry in lock["requirements"]}
        if required != supplied or len(supplied) != len(lock["requirements"]):
            raise OfflineRuntimeError("runtime dependencies differ from approved lock")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, OfflineRuntimeError):
            raise
        raise OfflineRuntimeError("invalid trusted runtime approval") from exc


def _verify_trusted_wheels(root: Path, runtime_id: str,
                           lock: dict, staged_model: Path) -> None:
    """Only first-party, offline-allowlisted wheel bytes are executable.

    A package's own SHA-256 list is integrity, NOT publisher authenticity:
    anyone can create a package with malicious code and matching hashes.
    The trusted wheel lock is shipped with the application, not the archive.
    """
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,39}", runtime_id):
        raise OfflineRuntimeError("unrecognized runtime identity")
    trusted_file = Path(root) / "scripts" / "wheelhouse-locks" / (runtime_id + ".json")
    if (not trusted_file.is_file() or trusted_file.is_symlink()
        or trusted_file.stat().st_size > 65536):
        raise OfflineRuntimeError(
            "offline runtime wheels are not approved for this provider")
    try:
        trusted = json.loads(trusted_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OfflineRuntimeError("invalid application-owned trusted wheel lock") from exc
    if (trusted.get("format") != "voxweavetts.trusted-wheel-lock"
        or trusted.get("runtime_id") != runtime_id
        or trusted.get("python_abi") != PYTHON_ABI
        or trusted.get("platform") not in ("win_amd64", "any")
        or not isinstance(trusted.get("wheels"), list)
        or not trusted["wheels"]):
        raise OfflineRuntimeError("trusted runtime lock does not match platform")
    trusted_rows = {}
    for row in trusted["wheels"]:
        if (not isinstance(row, dict)
            or not isinstance(row.get("filename"), str)
            or not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", row["filename"])
            or not isinstance(row.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise OfflineRuntimeError("invalid trusted wheel descriptor")
        if row["filename"].casefold() in trusted_rows:
            raise OfflineRuntimeError("duplicate wheel in approved runtime")
        trusted_rows[row["filename"].casefold()] = row
    package_rows = {}
    for row in lock["wheels"]:
        filename = Path(row["path"]).name
        approved = trusted_rows.get(filename.casefold())
        if (approved is None or row["sha256"] != approved["sha256"]
            or row["path"] != "runtime/wheels/" + filename):
            raise OfflineRuntimeError("wheel SHA-256 is not trusted by this application")
        if filename.casefold() in package_rows:
            raise OfflineRuntimeError("duplicate bundled wheel")
        package_rows[filename.casefold()] = row
        wheel_path = staged_model / row["path"]
        if (not wheel_path.is_file() or wheel_path.is_symlink()
            or wheel_path.stat().st_size != approved.get("size",
                                                         wheel_path.stat().st_size)):
            raise OfflineRuntimeError("approved wheel size mismatch")
        try:
            with zipfile.ZipFile(wheel_path) as archive:
                for entry in archive.infolist():
                    name = entry.filename
                    parts = name.split("/")
                    mode = stat.S_IFMT(entry.external_attr >> 16)
                    if (not name or name.startswith("/") or "\\" in name
                        or ":" in name or any(x in ("", ".", "..") for x in parts
                                              if x != "" or not entry.is_dir())
                        or (mode not in (0, stat.S_IFREG, stat.S_IFDIR))
                        or name.lower().endswith(".pth")
                        or ".data/scripts/" in name.lower()):
                        raise OfflineRuntimeError("unsafe executable or path inside wheel")
        except (OSError, zipfile.BadZipFile) as exc:
            raise OfflineRuntimeError("invalid wheel archive") from exc
    if set(package_rows) != set(trusted_rows):
        raise OfflineRuntimeError("offline package must embed the full trusted runtime")


def install(root: Path, manifest: dict, staged_model: Path) -> bool:
    """Stage/install a dependency runtime transactionally. Returns True if created."""
    root = Path(root)
    spec = manifest["runtime"]
    if spec["source"] == "core-bundled":
        core_python(root)
        return False
    if spec["source"] != "bundled-wheels":
        raise OfflineRuntimeError("v3 requires a complete offline runtime bundle")
    if ready(root, manifest):
        return False
    target = runtime_folder(root, manifest)
    with _LOCK:
        if target.exists():
            raise OfflineRuntimeError(
                "runtime is incomplete; uninstall its models and reinstall the package")
        runtime_parent = target.parent
        runtime_parent.mkdir(parents=True, exist_ok=True)
        if runtime_parent.is_symlink() or not runtime_parent.resolve().is_relative_to(root.resolve()):
            raise OfflineRuntimeError("unsafe runtime destination")
        from .runtime_tools import find_uv
        uv = find_uv(root)
        if not uv:
            raise OfflineRuntimeError("bundled offline installer uv.exe is missing")
        py = core_python(root)
        try:
            lock_path = staged_model / spec["lockfile"]
            if lock_path.is_symlink() or lock_path.stat().st_size > 65536:
                raise OfflineRuntimeError("untrusted wheel lock")
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            if set(lock) != {"requirements", "wheels"} or not lock["wheels"]:
                raise OfflineRuntimeError("offline wheel lock is incomplete")
            _verify_trusted_wheels(root, spec["id"], lock, staged_model)
            _approve_bundle(root, manifest, lock)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise OfflineRuntimeError("invalid bundled runtime lock") from exc
        stage = Path(tempfile.mkdtemp(prefix=".runtime-v3-", dir=runtime_parent))
        try:
            wheels = stage / "wheels"
            wheels.mkdir()
            for entry in lock["wheels"]:
                source = staged_model / entry["path"]
                if (not source.is_file() or source.is_symlink()
                    or _sha(source) != entry["sha256"]):
                    raise OfflineRuntimeError("bundled wheel integrity check failed")
                shutil.copy2(source, wheels / source.name)
            (stage / "requirements.lock").write_text(_requirements(lock), encoding="utf-8")
            site = stage / "site-packages"
            env = os.environ.copy()
            env.update({
                "UV_OFFLINE": "1", "PIP_NO_INDEX": "1",
                "UV_NO_PROGRESS": "1", "PYTHONNOUSERSITE": "1",
                "UV_CACHE_DIR": str(root / "cache" / "uv-v3"),
                "TEMP": str(root / "cache" / "temp"),
                "TMP": str(root / "cache" / "temp"),
            })
            (root / "cache" / "uv-v3").mkdir(parents=True, exist_ok=True)
            (root / "cache" / "temp").mkdir(parents=True, exist_ok=True)
            command = [
                uv, "pip", "install", "--offline", "--no-index", "--no-cache",
                "--only-binary", ":all:", "--require-hashes",
                "--no-sources",
                "--python", str(py), "--target", str(site),
                "--find-links", str(wheels), "-r", str(stage / "requirements.lock"),
            ]
            result = subprocess.run(
                command, cwd=str(root), env=env,
                capture_output=True, text=True, timeout=900, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode:
                raise OfflineRuntimeError(
                    "offline runtime install failed: " + (result.stderr or result.stdout)[-750:])
            if not site.is_dir():
                raise OfflineRuntimeError("offline runtime did not create site-packages")
            # Absolute paths to the staging location must never be serialized.
            (stage / ".voxweave-runtime-v3.json").write_text(
                json.dumps({"format": RUNTIME_FORMAT,
                            "fingerprint": fingerprint(manifest),
                            "abi": PYTHON_ABI,
                            "wheel_count": len(lock["wheels"])}) + "\n",
                encoding="utf-8",
            )
            shutil.rmtree(wheels)
            (stage / "requirements.lock").unlink()
            stage.rename(target)
            return True
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def uninstall_if_unreferenced(root: Path, manifest: dict) -> None:
    """Only delete an app-owned runtime if no installed model uses it."""
    if manifest["runtime"]["source"] == "core-bundled":
        return
    from .universal_model_packages import installed_packages
    target = runtime_folder(root, manifest)
    with _LOCK:
        if any(fingerprint(other) == fingerprint(manifest)
               for other, _folder in installed_packages(root)):
            return
        if (target.is_dir() and not target.is_symlink()
            and target.parent == Path(root) / "runtime" / "environments"
            and (target / ".voxweave-runtime-v3.json").is_file()):
            shutil.rmtree(target)


def run_command(root: Path, manifest: dict, module: str, args: list[str] | None = None) -> list[str]:
    """Run a trusted app module using bundled Python and isolated v3 libraries."""
    if not ready(root, manifest):
        raise OfflineRuntimeError("offline package runtime is not installed")
    site = site_packages(root, manifest)
    if site is None:
        return [str(core_python(root)), "-u", "-m", module, *(args or [])]
    # -S excludes global/user site-packages; only bundled stdlib, trusted src
    # and this exact verified runtime are available.
    script = ("import runpy,sys; "
              "sys.path[:0]=[sys.argv[1],sys.argv[2]]; "
              "sys.argv=[sys.argv[3]]+sys.argv[4:]; "
              "runpy.run_module(sys.argv[0],run_name='__main__')")
    return [str(core_python(root)), "-S", "-u", "-c", script,
            str(Path(root) / "src"), str(site), module, *(args or [])]
