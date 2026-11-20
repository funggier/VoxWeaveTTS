"""Archive original PyPI source tarballs for GPL/LGPL Wheels bundled by V4.

Each source distribution is downloaded directly from the package's versioned
PyPI JSON API and SHA-256-checked against the repository's published digest.
Source archives and license metadata are retained *unchanged* and associated
with the exact Wheel from the local immutable QA manifest, not with a guessed
newer release. Original licenses, source-build obligations and redistribution
conditions remain applicable; this program provides audit evidence, not a
legal clearance assertion.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "dist" / "ModelPackagesV4-QA"
OUT = ROOT / "cache" / "v4-rights-evidence" / "runtime-sources" / "copyleft-wheel-sdists"
COPYLEFT_PACKAGES = {
    "phonemizer": ("3.6.0", "GPL-3.0-or-later"),
    "phonemizer-fork": ("3.3.2", "GPL-3.0-or-later"),
    "gensim": ("4.4.0", "LGPL-2.1-only"),
    "num2words": ("0.5.6", "LGPL (upstream declaration)"),
}
DISTRO_NAME = {
    "phonemizer": "phonemizer",
    "phonemizer-fork": "phonemizer_fork",
    "gensim": "gensim",
    "num2words": "num2words",
}
MAX_TARBALL = 50_000_000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get(url: str, max_bytes: int) -> bytes:
    request = Request(url, headers={
        "User-Agent": "VoxWeaveTTS-v4-upstream-source-audit",
    })
    with urlopen(request, timeout=55) as resp:
        content = resp.read(max_bytes + 1)
    if not content or len(content) > max_bytes:
        raise ValueError("untrusted source download exceeded size bound")
    return content


def included_wheels(archive_dir: Path = QA) -> dict:
    found = {name: {} for name in COPYLEFT_PACKAGES}
    for package in archive_dir.glob("*-UNRELEASED-QA-format-v4.vwmodel"):
        with zipfile.ZipFile(package) as outer:
            manifest = json.loads(outer.read("manifest.json"))
            model = manifest["package"]["id"]
            for wheel_name in manifest["runtime"]["wheels"]:
                basename = Path(wheel_name).name.lower()
                for project, (version, license_id) in COPYLEFT_PACKAGES.items():
                    if not basename.startswith(
                        DISTRO_NAME[project].lower() + "-" + version + "-"
                    ):
                        continue
                    wheel_row = next(
                        f for f in manifest["files"] if f["path"] == wheel_name
                    )
                    # Hash without materializing the multi-hundred-MB archive.
                    with outer.open(wheel_name) as stream:
                        hasher = hashlib.sha256()
                        size = 0
                        while block := stream.read(1024 * 1024):
                            hasher.update(block)
                            size += len(block)
                    if (size != wheel_row["size"]
                        or hasher.hexdigest() != wheel_row["sha256"]):
                        raise ValueError("source audit Wheel SHA mismatch")
                    found[project][model] = {
                        "wheel_filename": basename,
                        "wheel_sha256": wheel_row["sha256"],
                    }
    if not all(found.values()):
        raise ValueError("one or more expected copyleft Wheels not found")
    return found


def collect(archive_dir: Path = QA, out_dir: Path = OUT) -> dict:
    wheels = included_wheels(archive_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    for project, (version, expected_license) in COPYLEFT_PACKAGES.items():
        url = f"https://pypi.org/pypi/{project}/{version}/json"
        info = json.loads(get(url, 2_000_000))
        if (info["info"]["version"] != version
            or info["info"]["name"].lower().replace("_", "-") != project):
            raise ValueError("PyPI metadata source does not match target release")
        sources = [p for p in info["urls"] if p["packagetype"] == "sdist"
                   and p["filename"].endswith(".tar.gz")]
        if len(sources) != 1:
            raise ValueError("expected exactly one source tarball")
        src = sources[0]
        target = out_dir / (DISTRO_NAME[project] + "-" + version + ".tar.gz")
        if target.is_file():
            data = target.read_bytes()
        else:
            data = get(src["url"], MAX_TARBALL)
        if sha(data) != src["digests"]["sha256"] or len(data) != src["size"]:
            raise ValueError("PyPI published source SHA/size mismatch")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            members = tf.getmembers()
            if (not members or any(
                m.name.startswith("/") or ".." in Path(m.name).parts
                for m in members
            )):
                raise ValueError("source tarball contains invalid member paths")
            notices = sorted(
                m.name for m in members if m.isfile() and (
                    Path(m.name).name.lower() in (
                        "license", "license.txt", "license.md",
                        "copying", "copying.txt", "notice", "notice.txt"
                    ) or Path(m.name).name.lower().startswith("license.")
                )
            )
        target.write_bytes(data)
        result[project] = {
            "version": version,
            "primary_license": expected_license,
            "pypi_license_description": info["info"].get("license") or "",
            "pypi_info_url": url,
            "source_url": src["url"],
            "source_filename": src["filename"],
            "source_sha256": sha(data),
            "source_bytes": len(data),
            "local_copy": target.relative_to(ROOT).as_posix(),
            "source_member_count": len(members),
            "source_license_files": notices,
            "original_wheels": wheels[project],
            "reproducible_build_verified": False,
            "public_release_authorized": False,
        }
    index = {
        "schema": "voxweavetts.v4-copyleft-wheel-source-qa",
        "version": 1,
        "packages": result,
        "note": "Each original GPL/LGPL Wheel's pinned source distribution "
                "is archived for recipient access; use remains subject to "
                "upstream licenses and any combined-work requirements.",
        "public_release_authorized": False,
    }
    (out_dir / "INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return index


if __name__ == "__main__":
    idx = collect()
    print(json.dumps({
        name: {
            "source_bytes": item["source_bytes"],
            "source_sha256": item["source_sha256"],
            "used_in_models": list(item["original_wheels"]),
            "source_license_files_count": len(item["source_license_files"]),
        } for name, item in idx["packages"].items()
    }, indent=2))
