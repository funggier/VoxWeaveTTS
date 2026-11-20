"""Universal .vwmodel v4 — self-contained, opt-in executable engine plugins.

A deliberate, one-click trust model: selecting an archive and pressing Install
authorizes its Python worker code. The archive is not intrinsically trusted;
hashes prove integrity against its own manifest, NOT publisher identity.
External workers run out-of-process with the current user's OS permissions.

v4 is the only model-package format accepted by the Core. No v4 adapter, runtime hash or engine ID is built into Core.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import zipfile
from pathlib import Path, PurePosixPath

def core_python(root: Path) -> Path:
    """Locate the embedded Python 3.11 runtime without any legacy v3 module."""
    root = Path(root)
    portable = root / "runtime" / "python" / "python.exe"
    if portable.is_file():
        return portable
    development = root / ".venv" / "Scripts" / "python.exe"
    if development.is_file():
        return development
    raise V4PackageError("portable Python 3.11 runtime is missing")


ROOT = Path(__file__).resolve().parents[2]
FORMAT = "voxweavetts.model-package"
VERSION = 4
PROTOCOL = 1
MAX_MANIFEST = 131_072
MAX_METADATA = 131_072
MAX_FILES = 512
MAX_BYTES = 12_000_000_000
MAX_RATIO = 1500
_LOCK = threading.RLock()
_ID = re.compile(r"[a-z][a-z0-9-]{1,39}\Z")
_VERSION = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
_VOICE = re.compile(r"[a-zA-Z][A-Za-z0-9_-]{0,63}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LANG = re.compile(r"[a-z]{2,3}(?:-[A-Za-z]{2,4})?\Z")
_ALLOWED_SUFFIXES = {".py", ".txt", ".json", ".md", ".bin", ".npy", ".onnx",
                     ".safetensors", ".model", ".fst", ".utf8", ".whl", ".pt",
                     ".pth", ".tflite", ".vocab", ".yaml", ".yml", ".so",
                     ".dll", ".exe", ".pyd", ".dat", ".spm", ".bpe", ".cfg", ".wav"}
_WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)
}


class V4PackageError(ValueError):
    pass


def _path(name: str) -> str:
    if (not isinstance(name, str) or not 1 <= len(name) <= 230
        or name.startswith("/") or "\\" in name or ":" in name):
        raise V4PackageError("invalid package asset path")
    parts = PurePosixPath(name).parts
    if (not 1 <= len(parts) <= 7 or PurePosixPath(name).as_posix() != name
        or any(p in ("", ".", "..") or p.startswith(".") or p.endswith((" ", "."))
               or p.split(".")[0].upper() in _WINDOWS_DEVICES
               or any(ord(c) < 33 or c in '<>"|?*' for c in p)
               for p in parts)):
        raise V4PackageError("unsafe package path")
    # Permit this single upstream GPL source tarball as a legal document.
    # This does not enable other compressed/executable payload extensions.
    source_archive = name == "assets/legal/source/espeak-ng-1.52.0-source.tar.gz"
    if not source_archive and PurePosixPath(name).suffix.lower() not in _ALLOWED_SUFFIXES:
        raise V4PackageError("unsupported package file extension")
    return name


def _sha(path: Path) -> str:
    with path.open("rb") as inp:
        return hashlib.file_digest(inp, "sha256").hexdigest()


def _file_index(files: object) -> dict[str, dict]:
    if not isinstance(files, list) or not 2 <= len(files) <= MAX_FILES:
        raise V4PackageError("invalid file index")
    index: dict[str, dict] = {}
    total = 0
    for row in files:
        if not isinstance(row, dict) or set(row) != {"path", "size", "sha256"}:
            raise V4PackageError("invalid file index entry")
        name = _path(row["path"])
        key = name.casefold()
        if (key in index or key == "manifest.json"
            or type(row["size"]) is not int or not 0 < row["size"] <= MAX_BYTES
            or not isinstance(row["sha256"], str)
            or not _SHA.fullmatch(row["sha256"])):
            raise V4PackageError("duplicate, oversized or unpinned file")
        total += row["size"]
        index[key] = row
    if total > MAX_BYTES:
        raise V4PackageError("package exceeds maximum uncompressed size")
    return index


def validate_manifest(m: object) -> dict:
    if (not isinstance(m, dict) or set(m) != {
        "format", "format_version", "package", "engine", "runtime", "rights", "files"}
        or m["format"] != FORMAT or type(m["format_version"]) is not int
        or m["format_version"] != VERSION):
        raise V4PackageError("expected Universal .vwmodel v4")
    pkg, engine, runtime, rights = m["package"], m["engine"], m["runtime"], m["rights"]
    if (not isinstance(pkg, dict)
        or set(pkg) != {"id", "version", "title", "kind", "languages"}
        or not isinstance(pkg["id"], str) or not _ID.fullmatch(pkg["id"])
        or not isinstance(pkg["version"], str) or not _VERSION.fullmatch(pkg["version"])
        or pkg["kind"] not in ("tts", "translation")
        or not isinstance(pkg["title"], str) or not 1 <= len(pkg["title"]) <= 120
        or not isinstance(pkg["languages"], list) or not 1 <= len(pkg["languages"]) <= 32
        or any(not isinstance(s, str) or not _LANG.fullmatch(s)
               for s in pkg["languages"])
        or len(set(pkg["languages"])) != len(pkg["languages"])):
        raise V4PackageError("invalid v4 package metadata")
    if (not isinstance(engine, dict)
        or engine.get("protocol") != PROTOCOL
        or engine.get("entrypoint") not in ("plugin/worker.py", "plugin/worker.exe")):
        raise V4PackageError("invalid v4 worker protocol / entrypoint")
    if pkg["kind"] == "tts":
        required_tts = {"protocol", "entrypoint", "language", "sample_rate", "voices"}
        if (set(engine) not in (required_tts, required_tts | {"voice_language_map"})
            or not isinstance(engine["language"], str)
            or not (engine["language"] == "multi" or _LANG.fullmatch(engine["language"]))
            or type(engine["sample_rate"]) is not int
            or not 8000 <= engine["sample_rate"] <= 96000
            or not isinstance(engine["voices"], list)
            or not 1 <= len(engine["voices"]) <= 64):
            raise V4PackageError("invalid v4 TTS worker / voices")
        voice_ids = set()
        for voice in engine["voices"]:
            if (not isinstance(voice, dict) or set(voice) != {"id", "label"}
                or not isinstance(voice["id"], str) or not _VOICE.fullmatch(voice["id"])
                or voice["id"] in voice_ids or not isinstance(voice["label"], str)
                or not 1 <= len(voice["label"]) <= 110):
                raise V4PackageError("invalid v4 voice")
            voice_ids.add(voice["id"])
        by_voice = engine.get("voice_language_map", {})
        if (not isinstance(by_voice, dict)
            or not set(by_voice) <= voice_ids
            or any(not isinstance(lang, str) or lang not in pkg["languages"]
                   for lang in by_voice.values())
            or (engine["language"] == "multi" and set(by_voice) != voice_ids)):
            raise V4PackageError("multilingual v4 voices must declare exact language mapping")
    elif (set(engine) != {"protocol", "entrypoint", "operation", "languages"}
          or engine["operation"] != "translate"
          or not isinstance(engine["languages"], list)
          or not 1 <= len(engine["languages"]) <= 64
          or any(not isinstance(lang, str) or not _LANG.fullmatch(lang)
                 for lang in engine["languages"])
          or len(set(engine["languages"])) != len(engine["languages"])):
        raise V4PackageError("invalid v4 translation worker metadata")
    if (not isinstance(rights, dict)
        or not set(rights) in (
            {"spdx", "url", "attribution", "source"},
            {"spdx", "url", "attribution", "source", "review_status"})
        or not isinstance(rights["spdx"], str) or not 1 <= len(rights["spdx"]) <= 80
        or not isinstance(rights["url"], str) or not rights["url"].startswith("https://")
        or len(rights["url"]) > 350
        or not isinstance(rights["attribution"], str)
        or not 1 <= len(rights["attribution"]) <= 1000
        or not isinstance(rights["source"], str)
        or not rights["source"].startswith("https://") or len(rights["source"]) > 350
        or ("review_status" in rights and rights["review_status"] not in
            ("declared", "review_required", "hold"))):
        raise V4PackageError("package must declare its rights and source")
    index = _file_index(m["files"])
    if engine["entrypoint"] not in index:
        raise V4PackageError("v4 requires its selected external worker")
    if (not isinstance(runtime, dict)
        or set(runtime) != {"python", "platform", "wheels"}
        or runtime["python"] not in ("3.11", "native")
        or runtime["platform"] not in ("windows-x64", "any")
        or not isinstance(runtime["wheels"], list)
        or len(runtime["wheels"]) > MAX_FILES):
        raise V4PackageError("unsupported v4 Python offline runtime")
    if ((runtime["python"] == "native") != (engine["entrypoint"] == "plugin/worker.exe")
        or (runtime["python"] == "native" and runtime["wheels"])):
        raise V4PackageError("native exe and Python wheel runtimes cannot be mixed")
    wheel_names = set()
    from packaging.utils import parse_wheel_filename
    from packaging.tags import cpython_tags, compatible_tags
    accepted_tags = set(cpython_tags(python_version=(3, 11), platforms=["win_amd64"]))
    accepted_tags.update(compatible_tags(python_version=(3, 11),
                                         interpreter="cp311", platforms=["win_amd64"]))
    for whl in runtime["wheels"]:
        if not isinstance(whl, str) or not whl.startswith("runtime/wheels/"):
            raise V4PackageError("invalid v4 wheel name")
        _path(whl)
        if not whl.endswith(".whl") or whl.casefold() not in index or whl in wheel_names:
            raise V4PackageError("v4 wheel missing from file index")
        wheel_names.add(whl)
        try:
            _name, _ver, _build, tags = parse_wheel_filename(Path(whl).name)
        except ValueError as exc:
            raise V4PackageError("bad wheel filename") from exc
        if not any(t in accepted_tags for t in tags):
            raise V4PackageError("wheel not compatible with Windows Python 3.11")
    if {r["path"] for r in m["files"] if r["path"].endswith(".whl")} != wheel_names:
        raise V4PackageError("unlisted runtime wheel")
    # Python plugin code is restricted to this namespace; no startup hooks,
    # arbitrary executable commands or install scripts are loaded from the ZIP.
    for row in m["files"]:
        name = row["path"]
        if name.endswith(".py") and not name.startswith("plugin/"):
            raise V4PackageError("plugin Python files must stay inside plugin/")
        if (name.endswith((".dll", ".so", ".pyd"))
            and not (name.startswith("assets/") or name.startswith("plugin/"))):
            raise V4PackageError("native libraries must stay inside assets/ or plugin/")
        if name.endswith(".exe") and name != "plugin/worker.exe":
            raise V4PackageError("only the declared native worker.exe is executable")
        if name.endswith((".pt", ".pth")):
            # These can deserialize arbitrary pickle; the chosen plugin is
            # executable anyway. No first-party trust is conferred.
            pass
    return m


def _check_zip(archive: Path) -> dict:
    if archive.suffix.lower() != ".vwmodel" or not archive.is_file() or archive.is_symlink():
        raise V4PackageError("select a local .vwmodel file")
    try:
        with zipfile.ZipFile(archive) as z:
            entries = z.infolist()
            if (not 3 <= len(entries) <= MAX_FILES + 1
                or entries[0].filename != "manifest.json"
                or entries[0].file_size > MAX_MANIFEST):
                raise V4PackageError("invalid v4 ZIP layout")
            try:
                m = validate_manifest(json.loads(z.read("manifest.json").decode("utf-8")))
            except (ValueError, UnicodeError) as exc:
                raise V4PackageError("bad v4 manifest") from exc
            index = _file_index(m["files"])
            if {x.filename.casefold() for x in entries} != set(index) | {"manifest.json"}:
                raise V4PackageError("manifest and archive contents disagree")
            if len({x.filename.casefold() for x in entries}) != len(entries):
                raise V4PackageError("ZIP has duplicate names")
            for entry in entries:
                if (entry.is_dir() or entry.flag_bits & 1
                    or stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFLNK):
                    raise V4PackageError("ZIP links/directories/encryption forbidden")
                if entry.filename == "manifest.json":
                    continue
                row = index[entry.filename.casefold()]
                if (entry.filename != row["path"] or entry.file_size != row["size"]
                    or not entry.compress_size
                    or entry.file_size > entry.compress_size * MAX_RATIO):
                    raise V4PackageError("unsafe or compressed archive entry")
            return m
    except (zipfile.BadZipFile, OSError) as exc:
        raise V4PackageError("invalid model ZIP") from exc


def inspect_archive(path: Path | str) -> dict:
    return _check_zip(Path(path))


def _base(root: Path, kind: str = "tts") -> Path:
    if kind not in ("tts", "translation"):
        raise V4PackageError("unsupported model kind")
    return Path(root) / "models" / "universal" / "v4" / kind


def _model_dir(root: Path, m: dict) -> Path:
    return _base(root, m["package"]["kind"]) / m["package"]["id"] / m["package"]["version"]


def engine_id(m: dict) -> str:
    return "model-" + m["package"]["id"] + "-" + m["package"]["version"].replace(".", "_")


def backend_id(m: dict) -> str:
    return "v4-" + m["package"]["id"] + "-" + m["package"]["version"].replace(".", "-")


def fingerprint(m: dict) -> str:
    index = _file_index(m["files"])
    digests = [index[w.casefold()]["sha256"] for w in m["runtime"]["wheels"]]
    raw = json.dumps([m["runtime"]["python"], m["runtime"]["platform"], digests],
                     sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def runtime_dir(root: Path, m: dict) -> Path:
    return Path(root) / "runtime" / "environments-v4" / fingerprint(m)[:32]


def _marker(root: Path, m: dict) -> Path:
    return runtime_dir(root, m) / ".voxweave-v4-runtime.json"


def ready(root: Path, m: dict) -> bool:
    if m["runtime"]["python"] == "native":
        return (_model_dir(root, m) / "plugin" / "worker.exe").is_file()
    if m["runtime"]["wheels"] == []:
        try:
            return core_python(root).is_file()
        except OSError:
            return False
    path = runtime_dir(root, m)
    try:
        marker = _marker(root, m)
        if path.is_symlink() or not (path / "site-packages").is_dir() or not marker.is_file():
            return False
        data = json.loads(marker.read_text(encoding="utf-8"))
        return (data == {"format": "voxweavetts.v4-runtime", "fingerprint": fingerprint(m),
                         "wheel_count": len(m["runtime"]["wheels"])})
    except (OSError, ValueError, TypeError):
        return False


def _verify_wheel(file: Path) -> None:
    """Reject ZIP traversal, startup hooks and executable wheel installers."""
    with zipfile.ZipFile(file) as z:
        names = set()
        for entry in z.infolist():
            name = entry.filename
            parts = name.split("/")
            mode = stat.S_IFMT(entry.external_attr >> 16)
            if (not name or name.startswith("/") or "\\" in name or ":" in name
                or any(p in (".", "..") or (not p and not entry.is_dir()) for p in parts)
                or mode not in (0, stat.S_IFREG, stat.S_IFDIR)
                or name.lower().endswith(".pth") or ".data/scripts/" in name.lower()
                or name.casefold() in names):
                raise V4PackageError("unsafe wheel startup hook or path")
            names.add(name.casefold())


def _create_runtime(root: Path, m: dict, stage: Path) -> bool:
    if not m["runtime"]["wheels"] or ready(root, m):
        return False
    target = runtime_dir(root, m)
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    if (target.exists() or target.is_symlink() or parent.is_symlink()
        or not parent.resolve().is_relative_to(Path(root).resolve())):
        raise V4PackageError("v4 runtime destination unavailable")
    from .runtime_tools import find_uv
    uv = find_uv(root)
    if not uv:
        raise V4PackageError("portable offline uv installer is missing")
    py = core_python(root)
    scratch = Path(tempfile.mkdtemp(prefix=".v4-runtime-", dir=parent))
    try:
        site = scratch / "site-packages"
        wheels = stage / "runtime" / "wheels"
        # Local exact wheel paths: --no-deps means no online resolver and no
        # implicit downloads. All dependencies must be shipped in the archive.
        args = [uv, "pip", "install", "--offline", "--no-index", "--no-cache",
                "--only-binary", ":all:", "--no-deps",
                "--python", str(py), "--target", str(site)]
        args.extend(str(wheels / Path(name).name) for name in m["runtime"]["wheels"])
        env = os.environ.copy()
        env.update({"UV_OFFLINE": "1", "PIP_NO_INDEX": "1", "UV_NO_PROGRESS": "1",
                    "PYTHONNOUSERSITE": "1",
                    "UV_CACHE_DIR": str(root / "cache" / "uv-v4")})
        (root / "cache" / "uv-v4").mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            args, cwd=str(root), env=env, capture_output=True, text=True,
            timeout=900, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0 or not site.is_dir():
            raise V4PackageError("offline v4 dependency installation failed: "
                                 + (completed.stderr or completed.stdout)[-450:])
        (scratch / ".voxweave-v4-runtime.json").write_text(json.dumps({
            "format": "voxweavetts.v4-runtime", "fingerprint": fingerprint(m),
            "wheel_count": len(m["runtime"]["wheels"])}) + "\n", encoding="utf-8")
        scratch.rename(target)
        return True
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def _clean_runtime(root: Path, m: dict) -> None:
    if not m["runtime"]["wheels"]:
        return
    target = runtime_dir(root, m)
    if (not target.is_dir() or target.is_symlink()
        or not _marker(root, m).is_file()):
        return
    for other, _ in installed_packages(root):
        if fingerprint(other) == fingerprint(m):
            return
    shutil.rmtree(target)


def install(archive: Path | str, *, root: Path = ROOT) -> dict:
    root = Path(root)
    with _LOCK:
        m = inspect_archive(archive)
        if sys_platform() != m["runtime"]["platform"] and m["runtime"]["platform"] != "any":
            raise V4PackageError("this v4 engine targets another platform")
        target = _model_dir(root, m)
        if (target.exists() or target.is_symlink()
            or target.parent.is_symlink()
            or any(old["package"]["id"] == m["package"]["id"]
                   and old["package"]["version"] == m["package"]["version"]
                   for old, _folder in installed_packages(root))):
            raise V4PackageError("this v4 package is already installed")
        target.parent.mkdir(parents=True, exist_ok=True)
        if (target.parent.is_symlink()
            or not target.parent.resolve().is_relative_to(root.resolve())):
            raise V4PackageError("unsafe v4 destination")
        stage = Path(tempfile.mkdtemp(prefix=".v4-install-", dir=target.parent))
        created_runtime = False
        try:
            with zipfile.ZipFile(archive) as z:
                for row in m["files"]:
                    output = stage.joinpath(*PurePosixPath(row["path"]).parts)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    sha = hashlib.sha256()
                    amount = 0
                    with z.open(row["path"]) as src, output.open("xb") as dst:
                        for block in iter(lambda: src.read(1024 * 1024), b""):
                            amount += len(block)
                            if amount > row["size"]:
                                raise V4PackageError("archive entry exceeds declared size")
                            sha.update(block)
                            dst.write(block)
                    if amount != row["size"] or sha.hexdigest() != row["sha256"]:
                        raise V4PackageError("model asset SHA-256 mismatch")
            for whl in m["runtime"]["wheels"]:
                _verify_wheel(stage.joinpath(*PurePosixPath(whl).parts))
            (stage / "manifest.json").write_text(
                json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            created_runtime = _create_runtime(root, m, stage)
            if m["runtime"]["python"] != "native" and not ready(root, m):
                raise V4PackageError("offline runtime did not become ready")
            for name in m["runtime"]["wheels"]:
                (stage / name).unlink()
            if (stage / "runtime" / "wheels").is_dir():
                (stage / "runtime" / "wheels").rmdir()
                (stage / "runtime").rmdir()
            stage.rename(target)
            return {"format_version": 4, "package_id": m["package"]["id"],
                    "version": m["package"]["version"], "engine_id": engine_id(m),
                    "runtime_status": "ready", "activation_supported": True,
                    "user_trusted_plugin_code": True}
        except BaseException:
            if created_runtime:
                _clean_runtime(root, m)
            raise
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def sys_platform() -> str:
    if os.name == "nt" or platform.system().lower() == "windows":
        return "windows-x64" if platform.machine().lower() in ("amd64", "x86_64") else "windows-arm64"
    return "other"


def _installed(folder: Path) -> dict | None:
    marker = folder / "manifest.json"
    try:
        if (folder.is_symlink() or not marker.is_file() or marker.is_symlink()
            or marker.stat().st_size > MAX_MANIFEST):
            return None
        m = validate_manifest(json.loads(marker.read_text(encoding="utf-8")))
        for row in m["files"]:
            if row["path"].startswith("runtime/wheels/"):
                continue
            path = folder.joinpath(*PurePosixPath(row["path"]).parts)
            if (not path.is_file() or path.is_symlink()
                or not path.resolve().is_relative_to(folder.resolve())
                or path.stat().st_size != row["size"]):
                return None
        # Always validate the worker code and metadata hash before execution.
        # Large weight assets are checked on installation; don't rehash GB every
        # time the user opens an engine dropdown.
        for row in m["files"]:
            if row["path"].endswith(".py") or row["path"].endswith(".json"):
                if _sha(folder / row["path"]) != row["sha256"]:
                    return None
        return m
    except (OSError, ValueError, KeyError, TypeError):
        return None


def installed_packages(root: Path = ROOT) -> list[tuple[dict, Path]]:
    results = []
    for kind in ("tts", "translation"):
        base = _base(root, kind)
        for marker in sorted(base.glob("*/*/manifest.json")):
            folder = marker.parent
            if (marker.is_symlink() or folder.is_symlink() or folder.parent.is_symlink()
                or not folder.resolve().is_relative_to(base.resolve())):
                continue
            m = _installed(folder)
            if m and _model_dir(root, m) == folder:
                results.append((m, folder))
    return results


def for_engine(engine: str, root: Path = ROOT) -> tuple[dict, Path] | None:
    for m, folder in installed_packages(root):
        if engine_id(m) == engine:
            return m, folder
    return None


def for_backend(backend: str, root: Path = ROOT) -> tuple[dict, Path] | None:
    for m, folder in installed_packages(root):
        if backend_id(m) == backend:
            return m, folder
    return None


def remove(package_id: str, version: str, *, root: Path = ROOT) -> bool:
    if (not isinstance(package_id, str) or not _ID.fullmatch(package_id)
        or not isinstance(version, str) or not _VERSION.fullmatch(version)):
        raise V4PackageError("invalid v4 package removal")
    with _LOCK:
        for m, folder in installed_packages(root):
            if m["package"]["id"] != package_id or m["package"]["version"] != version:
                continue
            # No deletion of modified/unmanaged files even after a plugin has
            # been executed: third-party engines may have persisted new data.
            paths = {"manifest.json"} | {r["path"] for r in m["files"]
                                         if not r["path"].startswith("runtime/wheels/")}
            dirs = set()
            for path in paths:
                dirs.update(x.as_posix() for x in PurePosixPath(path).parents
                            if x.as_posix() != ".")
            for item in folder.rglob("*"):
                rel = item.relative_to(folder).as_posix()
                if (item.is_symlink()
                    or not item.resolve().is_relative_to(folder.resolve())
                    or (item.is_file() and rel not in paths)
                    or (item.is_dir() and rel not in dirs)):
                    raise V4PackageError("unmanaged v4 model files; refusing force removal")
            for row in m["files"]:
                if row["path"].startswith("runtime/wheels/"):
                    continue
                if _sha(folder / row["path"]) != row["sha256"]:
                    raise V4PackageError("modified v4 model asset; refusing removal")
            shutil.rmtree(folder)
            _clean_runtime(root, m)
            if not any(folder.parent.iterdir()):
                folder.parent.rmdir()
            return True
    return False


def status(m: dict, folder: Path, *, root: Path = ROOT) -> dict:
    is_ready = ready(root, m)
    nc = "BY-NC" in m["rights"]["spdx"].upper() or "NONCOMMERCIAL" in m["rights"]["spdx"].upper()
    return {"package_id": m["package"]["id"], "version": m["package"]["version"],
            "title": ("[NC / NonCommercial] " if nc else "") + m["package"]["title"],
            "model_kind": m["package"]["kind"], "format_version": 4,
            "engine_adapter": ("external-tts-protocol-1" if m["package"]["kind"] == "tts"
                               else "external-translation-protocol-1"),
            "adapter_trusted": True, "user_trusted_plugin_code": True,
            "runtime_id": backend_id(m), "runtime_fingerprint": fingerprint(m),
            "runtime_source": "offline-bundled-wheels", "runtime_ready": is_ready,
            "runtime_state": "ready" if is_ready else "runtime-not-installed",
            "engine_id": engine_id(m), "voices": m["engine"].get("voices", []),
            "languages": m["package"]["languages"],
            "license": {**m["rights"], "review_status": m["rights"].get("review_status", "declared")},
            "source": {"url": m["rights"]["source"]}, "dependencies": m["runtime"]["wheels"]}


def worker_command(root: Path, m: dict) -> list[str]:
    pair = for_engine(engine_id(m), root)
    if pair is None or not ready(root, m):
        raise V4PackageError("external worker or runtime is not installed")
    _manifest, folder = pair
    # The plugin can only select a known, fixed entrypoint from its own verified
    # directory. Do not accept manifest-provided commands or shell fragments.
    entry = folder / m["engine"]["entrypoint"]
    if _sha(entry) != next(row["sha256"] for row in m["files"]
                           if row["path"] == m["engine"]["entrypoint"]):
        raise V4PackageError("external worker executable code changed")
    if m["runtime"]["python"] == "native":
        return [str(entry), "--model-dir", str(folder)]
    python = core_python(root)
    site = runtime_dir(root, m) / "site-packages"
    script = (
        "import runpy,sys; "
        "sys.path[:0]=[sys.argv[1],sys.argv[2],sys.argv[3]]; "
        "sys.argv=[sys.argv[4],'--model-dir',sys.argv[5]]; "
        "runpy.run_path(sys.argv[0],run_name='__main__')"
    )
    return [str(python), "-S", "-u", "-c", script,
            str(site), str(folder / "plugin"), str(folder),
            str(entry), str(folder)]
