"""Pinned, data-only, offline wheels for app-approved worker runtimes.

The trusted lock lives in scripts/wheelhouse-locks (shipped with the app).
The large wheel files live separately in runtime/wheelhouse/<runtime-id>/.
Untrusted .vwmodel archives, web requests and external providers cannot supply
wheel locks, executable paths, requirements or pip flags.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from email.parser import BytesParser
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
FORMAT = "voxweavetts.trusted-wheel-lock"
VERSION = 1
PYTHON_ABI = "3.11"
MAX_LOCK_BYTES = 1 << 20
MAX_WHEELS = 512
MAX_WHEEL_BYTES = 4 * 1024**3
MAX_TOTAL_BYTES = 12 * 1024**3
MAX_ZIP_MEMBERS = 200_000
MAX_METADATA_BYTES = 1024 * 1024
_ID = re.compile(r"[a-z][a-z0-9-]{1,39}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_DISTRIBUTION = re.compile(r"[A-Za-z0-9_]+\Z")
_VERSION = re.compile(r"[A-Za-z0-9_.!+]+\Z")
_WHEEL_TAG = re.compile(r"[A-Za-z0-9_.]+\Z")
_PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[A-Za-z0-9_.,-]+\])?==([A-Za-z0-9_.!+]+)\Z")


class WheelhouseError(ValueError):
    pass


def _platform() -> str:
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in ("amd64", "x86_64"):
        return "win_amd64"
    if sys.platform == "win32" and machine in ("arm64", "aarch64"):
        return "win_arm64"
    if sys.platform == "darwin":
        return "macos_" + machine
    return "linux_" + machine


def _safe_id(runtime_id: str) -> str:
    if not isinstance(runtime_id, str) or not _ID.fullmatch(runtime_id):
        raise WheelhouseError("invalid runtime identity")
    # Whitelist the trusted first-party providers. External provider wheel
    # signing/approval belongs to Phase D, not this fixed first-party lock.
    from .engine_provider_catalog import PROVIDERS
    if runtime_id != "m2m100" and runtime_id not in PROVIDERS:
        raise WheelhouseError("unapproved runtime identity")
    return runtime_id


def _recipe(root: Path, runtime_id: str) -> Path:
    from .engine_provider_catalog import PROVIDERS
    from .m2m_runtime import REQUIREMENTS
    path = (Path(root) / REQUIREMENTS if runtime_id == "m2m100"
            else PROVIDERS[runtime_id].requirements_path(root))
    if (not path.is_file() or path.is_symlink() or path.stat().st_size > 32768
        or not path.resolve().is_relative_to(Path(root).resolve())):
        raise WheelhouseError("trusted dependency recipe missing or redirected")
    return path


def _pins(recipe: Path) -> dict[str, str]:
    """Allow only literal exact pins, not index URLs/VCS/editables/options."""
    pins: dict[str, str] = {}
    for line in recipe.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = _PIN.fullmatch(line)
        if not match:
            raise WheelhouseError("runtime recipe has non-pinned or remote dependencies")
        name = _normalize(match.group(1))
        if name in pins and pins[name] != match.group(2):
            raise WheelhouseError("contradictory trusted dependency pins")
        pins[name] = match.group(2)
    if not pins:
        raise WheelhouseError("empty trusted runtime recipe")
    return pins


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _split_wheel(name: str) -> tuple[str, str]:
    if (not isinstance(name, str) or len(name) > 230 or not name.endswith(".whl")
        or "/" in name or "\\" in name or name.startswith(".")):
        raise WheelhouseError("unsafe wheel filename")
    parts = name[:-4].split("-")
    if len(parts) not in (5, 6):
        raise WheelhouseError("wheel filename must follow PEP 427")
    dist, version = parts[:2]
    if not _DISTRIBUTION.fullmatch(dist) or not _VERSION.fullmatch(version):
        raise WheelhouseError("invalid wheel distribution/version")
    if len(parts) == 6 and not re.fullmatch(r"[0-9][A-Za-z0-9_]*", parts[2]):
        raise WheelhouseError("invalid wheel build tag")
    if any(not _WHEEL_TAG.fullmatch(x) for x in parts[-3:]):
        raise WheelhouseError("invalid wheel compatibility tags")
    return _normalize(dist), version


def _lock_path(root: Path, runtime_id: str) -> Path:
    return Path(root) / "scripts" / "wheelhouse-locks" / (runtime_id + ".json")


def _wheel_dir(root: Path, runtime_id: str) -> Path:
    return Path(root) / "runtime" / "wheelhouse" / runtime_id


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def validate_lock(raw: object, *, root: Path, runtime_id: str) -> dict:
    runtime_id = _safe_id(runtime_id)
    if (not isinstance(raw, dict)
        or set(raw) != {"format", "version", "runtime_id", "python_abi",
                        "platform", "recipe_sha256", "wheels"}
        or raw["format"] != FORMAT or type(raw["version"]) is not int
        or raw["version"] != VERSION or raw["runtime_id"] != runtime_id
        or raw["python_abi"] != PYTHON_ABI or raw["platform"] != _platform()
        or not isinstance(raw["recipe_sha256"], str)
        or not _SHA.fullmatch(raw["recipe_sha256"])):
        raise WheelhouseError("invalid or incompatible trusted wheel lock")
    if raw["recipe_sha256"] != _digest(_recipe(Path(root), runtime_id)):
        raise WheelhouseError("trusted runtime dependency recipe changed")
    pins = _pins(_recipe(Path(root), runtime_id))
    rows = raw["wheels"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_WHEELS:
        raise WheelhouseError("invalid wheel inventory")
    seen_names: set[str] = set()
    seen_files: set[str] = set()
    selected: dict[str, str] = {}
    total = 0
    for row in rows:
        if (not isinstance(row, dict)
            or set(row) != {"filename", "name", "version", "size", "sha256"}
            or not isinstance(row["sha256"], str)
            or not _SHA.fullmatch(row["sha256"])
            or type(row["size"]) is not int
            or not 100 <= row["size"] <= MAX_WHEEL_BYTES):
            raise WheelhouseError("invalid trusted wheel entry")
        normalized, version = _split_wheel(row["filename"])
        if (not isinstance(row["name"], str) or row["name"] != normalized
            or not isinstance(row["version"], str) or row["version"] != version
            or normalized in seen_names
            or row["filename"].casefold() in seen_files):
            raise WheelhouseError("duplicate/inconsistent wheel entries")
        seen_names.add(normalized)
        seen_files.add(row["filename"].casefold())
        selected[normalized] = version
        total += row["size"]
    if total > MAX_TOTAL_BYTES or any(selected.get(name) != version
                                      for name, version in pins.items()):
        raise WheelhouseError("trusted wheel lock missing pinned top-level dependencies")
    return raw


def trusted_lock(root: Path, runtime_id: str) -> dict:
    root = Path(root)
    runtime_id = _safe_id(runtime_id)
    path = _lock_path(root, runtime_id)
    if (not path.is_file() or path.is_symlink()
        or path.stat().st_size > MAX_LOCK_BYTES
        or not path.resolve().is_relative_to(root.resolve())):
        raise WheelhouseError("trusted wheel lock has not been published")
    try:
        return validate_lock(json.loads(path.read_text(encoding="utf-8")),
                             root=root, runtime_id=runtime_id)
    except (OSError, TypeError, ValueError, UnicodeError) as exc:
        raise WheelhouseError("invalid trusted wheel lock") from exc


def _check_directory(root: Path, runtime_id: str) -> Path:
    directory = _wheel_dir(root, runtime_id)
    if (not directory.is_dir() or directory.is_symlink()
        or directory.parent.is_symlink()
        or directory.resolve().parent != directory.parent.resolve()
        or not directory.resolve().is_relative_to(root.resolve())):
        raise WheelhouseError("wheelhouse directory missing or redirected")
    return directory


def _present(lock: dict, directory: Path) -> None:
    expected = {row["filename"].casefold() for row in lock["wheels"]}
    found = set()
    for path in directory.iterdir():
        if (not path.is_file() or path.is_symlink()
            or path.resolve().parent != directory.resolve()
            or path.name.casefold() not in expected
            or path.name.casefold() in found):
            raise WheelhouseError("wheelhouse has unexpected or redirected files")
        found.add(path.name.casefold())
    if found != expected:
        raise WheelhouseError("wheelhouse files are missing")
    for row in lock["wheels"]:
        path = directory / row["filename"]
        if not path.is_file() or path.is_symlink() or path.stat().st_size != row["size"]:
            raise WheelhouseError("wheelhouse size mismatch or unsafe wheel")


def status(root: Path, runtime_id: str) -> dict:
    """Cheap read-only UI diagnostic; never labels unchecked bytes verified."""
    try:
        runtime_id = _safe_id(runtime_id)
        if runtime_id == "wayu-nc":
            _pins(_recipe(root, runtime_id))  # A VCS requirement cannot be audited offline.
        lock = trusted_lock(root, runtime_id)
        _present(lock, _check_directory(root, runtime_id))
        return {"state": "present-unverified", "ready_to_verify": True,
                "wheels": len(lock["wheels"]),
                "total_bytes": sum(r["size"] for r in lock["wheels"])}
    except (WheelhouseError, OSError, UnicodeError) as exc:
        state = ("not-published" if "not been published" in str(exc)
                 else "recipe-unsupported" if "remote dependencies" in str(exc)
                 else "not-ready")
        return {"state": state, "ready_to_verify": False, "wheels": 0,
                "total_bytes": 0}


def _inspect_wheel(path: Path, row: dict) -> None:
    """Check ZIP structure and wheel identity before allowing uv to import it."""
    try:
        with zipfile.ZipFile(path) as archive:
            files = archive.infolist()
            if len(files) > MAX_ZIP_MEMBERS:
                raise WheelhouseError("wheel archive has too many members")
            if sum(x.file_size for x in files) > min(8 * 1024**3,
                                                    max(path.stat().st_size * 256, 10 * 1024**2)):
                raise WheelhouseError("wheel archive decompression size exceeds limit")
            metadata = []
            wheel_file = []
            for member in files:
                name = member.filename
                if (name.startswith("/") or "\\" in name
                    or any(piece in (".", "..") for piece in name.split("/"))
                    or (member.external_attr >> 16) & 0o170000 == 0o120000):
                    raise WheelhouseError("unsafe path or symlink within wheel")
                if name.endswith(".dist-info/METADATA"):
                    metadata.append(member)
                if name.endswith(".dist-info/WHEEL"):
                    wheel_file.append(member)
            if len(metadata) != 1 or len(wheel_file) != 1:
                raise WheelhouseError("missing wheel metadata")
            if (metadata[0].file_size > MAX_METADATA_BYTES
                or wheel_file[0].file_size > MAX_METADATA_BYTES):
                raise WheelhouseError("oversized wheel metadata")
            msg = BytesParser().parsebytes(archive.read(metadata[0]))
            if (_normalize(str(msg.get("Name", ""))) != row["name"]
                or str(msg.get("Version", "")) != row["version"]):
                raise WheelhouseError("wheel metadata disagrees with trusted lock")
    except (OSError, zipfile.BadZipFile, RuntimeError, UnicodeError) as exc:
        raise WheelhouseError("wheel archive is invalid") from exc


def lock_text(lock: dict) -> str:
    """One exact version and SHA for every wheel; no user-supplied pip options."""
    return "".join(
        f'{row["name"]}=={row["version"]} --hash=sha256:{row["sha256"]}\n'
        for row in sorted(lock["wheels"], key=lambda x: x["name"]))


@contextmanager
def verified_wheels(root: Path, runtime_id: str) -> Iterator[tuple[Path, Path]]:
    """Snapshot and hash every wheel before installing; no cache/index fallback."""
    root = Path(root)
    lock = trusted_lock(root, runtime_id)
    directory = _check_directory(root, runtime_id)
    _present(lock, directory)
    staging_parent = root / "cache" / "temp"
    staging_parent.mkdir(parents=True, exist_ok=True)
    if (staging_parent.is_symlink() or staging_parent.parent.is_symlink()
        or not staging_parent.resolve().is_relative_to(root.resolve())):
        raise WheelhouseError("temporary wheel staging location is redirected")
    required = sum(row["size"] for row in lock["wheels"])
    if shutil.disk_usage(staging_parent).free < required + 128 * 1024**2:
        raise WheelhouseError("not enough free disk space for verified wheel snapshot")
    with tempfile.TemporaryDirectory(prefix="verified-wheels-", dir=staging_parent) as td:
        stage = Path(td)
        wheel_stage = stage / "wheels"
        wheel_stage.mkdir()
        for row in lock["wheels"]:
            source = directory / row["filename"]
            _inspect_wheel(source, row)
            copied = wheel_stage / row["filename"]
            digest = hashlib.sha256()
            size = 0
            with source.open("rb") as inp, copied.open("xb") as out:
                for block in iter(lambda: inp.read(1 << 20), b""):
                    size += len(block)
                    if size > row["size"]:
                        raise WheelhouseError("wheel changed during verification")
                    digest.update(block)
                    out.write(block)
            if size != row["size"] or digest.hexdigest() != row["sha256"]:
                raise WheelhouseError("wheel SHA-256 mismatch")
        requirements = stage / "requirements.lock"
        requirements.write_text(lock_text(lock), encoding="utf-8")
        yield wheel_stage, requirements


def _verify_dependency_closure(root: Path, runtime_id: str,
                               directory: Path, rows: list[dict]) -> None:
    """Curation-only: every dependency, extra and version must be represented.

    uv independently resolves and checks the hash-pinned dependencies at
    installation time. This check prevents curating an accidentally incomplete
    wheel set in the first place. The application runtime has no packaging
    import dependency; only the maintainer's curation script uses it.
    """
    try:
        from packaging.requirements import Requirement
        from packaging.markers import default_environment
        from packaging.utils import parse_wheel_filename
        from packaging.tags import sys_tags
    except ImportError as exc:
        raise WheelhouseError("maintainer needs packaging to audit wheel dependencies") from exc
    supported = set(sys_tags())
    for row in rows:
        _dist, _version, _build, tags = parse_wheel_filename(row["filename"])
        if not supported.intersection(tags):
            raise WheelhouseError("wheel has incompatible Python/OS/ABI tags")
    recipes = _recipe(root, runtime_id)
    selected = {row["name"]: row for row in rows}
    requirements = {}
    for line in recipes.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            req = Requirement(line)
            requirements.setdefault(_normalize(req.name), set()).update(req.extras)
    seen = set()
    todo = list(requirements.items())
    for name in requirements:
        todo.append((name, set()))
    while todo:
        name, extras = todo.pop()
        identifier = (name, tuple(sorted(extras)))
        if identifier in seen:
            continue
        seen.add(identifier)
        row = selected.get(name)
        if row is None:
            raise WheelhouseError("wheelhouse missing required dependency " + name)
        path = directory / row["filename"]
        with zipfile.ZipFile(path) as archive:
            metadata = next(m for m in archive.namelist() if m.endswith(".dist-info/METADATA"))
            parsed = BytesParser().parsebytes(archive.read(metadata))
        for value in parsed.get_all("Requires-Dist", []):
            dep = Requirement(value)
            conditions = {""} | set(extras)
            if dep.marker and not any(
                dep.marker.evaluate({**default_environment(), "extra": extra})
                for extra in conditions):
                continue
            normalized = _normalize(dep.name)
            pinned = selected.get(normalized)
            if pinned is None:
                raise WheelhouseError("wheelhouse missing transitive dependency " + normalized)
            if dep.specifier and not dep.specifier.contains(pinned["version"],
                                                            prereleases=True):
                raise WheelhouseError("incompatible dependency " + normalized)
            todo.append((normalized, set(dep.extras)))
    referenced = {name for name, _ in seen}
    if set(selected) != referenced:
        raise WheelhouseError("wheelhouse has unrelated executable wheels")


def draft_lock(root: Path, runtime_id: str, wheel_dir: Path) -> dict:
    """Maintainer-only offline draft; never publish or approve the bytes here."""
    root = Path(root)
    runtime_id = _safe_id(runtime_id)
    recipe = _recipe(root, runtime_id)
    pins = _pins(recipe)
    wheel_dir = Path(wheel_dir)
    if not wheel_dir.is_dir():
        raise WheelhouseError("select a local directory containing wheel archives")
    files = sorted(wheel_dir.iterdir(), key=lambda p: p.name)
    if not files or len(files) > MAX_WHEELS:
        raise WheelhouseError("empty or oversized candidate wheel directory")
    rows = []
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise WheelhouseError("non-wheel file in candidate folder")
        name, version = _split_wheel(path.name)
        size = path.stat().st_size
        if not 100 <= size <= MAX_WHEEL_BYTES:
            raise WheelhouseError("invalid wheel size")
        row = {"filename": path.name, "name": name, "version": version,
               "size": size, "sha256": _digest(path)}
        _inspect_wheel(path, row)
        rows.append(row)
    _verify_dependency_closure(root, runtime_id, wheel_dir, rows)
    draft = {"format": FORMAT, "version": VERSION, "runtime_id": runtime_id,
             "python_abi": PYTHON_ABI, "platform": _platform(),
             "recipe_sha256": _digest(recipe), "wheels": rows}
    return validate_lock(draft, root=root, runtime_id=runtime_id)
