"""Archive Hugging Face tokenizers 0.22.2 Apache LICENSE from exact PyPI sdist."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = (ROOT / "cache" / "v4-rights-evidence" / "runtime-sources" /
       "tokenizers-0.22.2")
PROJECT = "tokenizers"
VERSION = "0.22.2"
FILE_IN_SOURCE = "tokenizers-0.22.2/tokenizers/LICENSE"


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def fetch(url: str, maximum: int) -> bytes:
    with urlopen(Request(url, headers={
        "User-Agent": "VoxWeaveTTS-v4-license-archive",
    }), timeout=30) as reply:
        result = reply.read(maximum + 1)
    if not result or len(result) > maximum:
        raise ValueError("invalid upstream archive response")
    return result


def collect(out_dir: Path = OUT) -> dict:
    pypi_url = "https://pypi.org/pypi/tokenizers/0.22.2/json"
    published = json.loads(fetch(pypi_url, 2_000_000))
    source = next(d for d in published["urls"] if d["packagetype"] == "sdist")
    original = fetch(source["url"], 2_000_000)
    if sha(original) != source["digests"]["sha256"]:
        raise ValueError("PyPI source SHA-256 mismatch")
    with tarfile.open(fileobj=io.BytesIO(original), mode="r:gz") as archive:
        license_text = archive.extractfile(FILE_IN_SOURCE).read()
    if not license_text.lstrip().startswith(b"Apache License"):
        raise ValueError("source does not contain expected Apache 2.0 license")
    out_dir.mkdir(parents=True, exist_ok=True)
    destination = out_dir / "LICENSE.txt"
    if destination.exists() and destination.read_bytes() != license_text:
        raise ValueError("upstream source license changed")
    destination.write_bytes(license_text)
    report = {
        "schema": "voxweavetts.v4-tokenizers-original-license",
        "version": 1,
        "package_version": VERSION,
        "license": "Apache-2.0",
        "original_source_url": source["url"],
        "original_source_sha256": sha(original),
        "original_license_member": FILE_IN_SOURCE,
        "license_sha256": sha(license_text),
        "license_bytes": len(license_text),
        "original_license_copy": destination.relative_to(ROOT).as_posix(),
        "public_release_authorized": False,
    }
    (out_dir / "INDEX.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    result = collect()
    print(json.dumps(result, indent=2))
