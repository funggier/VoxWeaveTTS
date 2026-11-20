"""Archive ORIGINAL upstream license documents for v4 redistribution evidence.

Run from the local repository using its Python environment. Source documents
remain verbatim bytes, NOT edited or replaced with generated license claims.
All network retrievals use immutable source revisions (HF SHA / Git commit).
The archive lives in ignored cache/v4-rights-evidence/, not GitHub Releases.

Usage:
  .venv\Scripts\python.exe scripts/archive_v4_upstream_rights.py
  .venv\Scripts\python.exe scripts/archive_v4_upstream_rights.py --wheels

The committed JSON evidence index stores URLs and SHA-256 only; full third-party
Model Cards and license documents remain local to avoid republication.
This does not authorize any model/package redistribution.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import io
import json
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "v4-rights-evidence"
PUBLIC_INDEX = ROOT / "docs" / "v4_upstream_evidence_index.json"
PACKAGE_PATH = ROOT / "dist" / "ModelPackagesV4-QA"
HEADERS = {"User-Agent": "VoxWeaveTTS-RightsEvidence/1.0 (+local audit)",
           "Accept": "application/json"}
MAX_DOCUMENT = 1_250_000

# Identified first-party sources. Some models use multiple upstream projects.
SOURCES = [
    ("hf-model", "pythainlp/MakHamTTS", ["makham-paradee", "fastthaig2p-thai-som"]),
    ("hf-dataset", "pythainlp/MakHamTTS-dataset", ["makham-paradee"]),
    ("hf-dataset", "pythainlp/som_tts_dataset", ["fastthaig2p-thai-som"]),
    ("hf-model", "myshell-ai/MeloTTS-Chinese", ["melo-chinese-onnx"]),
    ("hf-model", "Supertone/supertonic-3", ["supertonic3-multilingual-int8"]),
    ("hf-model", "hexgrad/Kokoro-82M", ["kokoro-multilingual-int8"]),
    ("hf-model", "VIZINTZOR/VachanaTTS", ["vachana-thai-four-voices"]),
    ("hf-model", "wayu-ai/wayu-paxa-tts-edge", ["wayu-paxa-edge-nc"]),
    ("hf-model", "facebook/m2m100_418M", ["m2m100-418m"]),
    ("github", "PyThaiNLP/PyThaiTTS", ["makham-paradee", "fastthaig2p-thai-som", "vachana-thai-four-voices"]),
    ("github", "awslabs/FastThaiG2P", ["fastthaig2p-thai-som", "makham-paradee"]),
    ("github", "sahilmahendrakar/paradee", ["makham-paradee"]),
    ("github", "k2-fsa/sherpa-onnx", ["melo-chinese-onnx", "supertonic3-multilingual-int8"]),
    ("github", "wayu-research/wayu-tts-inference", ["wayu-paxa-edge-nc"]),
    ("github", "VYNCX/VachanaTTS", ["vachana-thai-four-voices"]),
]


# Extra legally material documents NOT hosted at a versioned Git revision.
# These are dated HTML snapshots with exact SHA, not immutable Git sources.
WEB_SOURCES = [
    ("wayu-research", "terms.html", "https://www.wayuresearch.org/terms",
     ["wayu-paxa-edge-nc"]),
    ("creativecommons", "cc-by-nc-4.0-legalcode.html",
     "https://creativecommons.org/licenses/by-nc/4.0/legalcode.en",
     ["wayu-paxa-edge-nc"]),
]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def request(url: str, *, json_response: bool = True) -> bytes:
    last = None
    for attempt in range(3):
        try:
            with requests.get(url, timeout=(8, 23), headers=HEADERS,
                              stream=True, allow_redirects=True) as result:
                result.raise_for_status()
                if result.url.split("/")[2] not in {
                    "huggingface.co", "cdn-lfs.hf.co", "cas-bridge.xethub.hf.co",
                    "raw.githubusercontent.com", "api.github.com",
                    "www.wayuresearch.org", "wayuresearch.org",
                    "creativecommons.org", "www.creativecommons.org",
                }:
                    raise ValueError("unexpected document source domain: " + result.url[:180])
                data = bytearray()
                for part in result.iter_content(chunk_size=65536):
                    data.extend(part)
                    if len(data) > MAX_DOCUMENT:
                        raise ValueError("source document exceeds size limit")
                return bytes(data)
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt != 2 and isinstance(exc, requests.RequestException):
                time.sleep(attempt + 1)
            else:
                break
    raise RuntimeError(f"could not fetch official source document: {url} ({last})")


def get_json(url: str) -> dict:
    item = json.loads(request(url).decode("utf-8"))
    if not isinstance(item, dict):
        raise ValueError("source metadata is not an object")
    return item


def fetch_document(spec: dict, item: str) -> dict:
    kind, repo, revision = spec["kind"], spec["repo"], spec["revision"]
    if kind.startswith("hf-"):
        prefix = ("datasets/" if kind == "hf-dataset" else "")
        url = ("https://huggingface.co/" + prefix + repo + "/resolve/"
               + revision + "/" + quote(item, safe="/"))
        view = ("https://huggingface.co/" + prefix + repo + "/blob/"
                + revision + "/" + quote(item, safe="/"))
    else:
        url = ("https://raw.githubusercontent.com/" + repo + "/"
               + revision + "/" + quote(item, safe="/"))
        view = ("https://github.com/" + repo + "/blob/"
                + revision + "/" + quote(item, safe="/"))
    raw = request(url, json_response=False)
    # Source README/LICENSE is a text document; no LFS models, binaries, or pointers.
    if b"\0" in raw or raw.startswith(b"version https://git-lfs.github.com/spec"):
        raise ValueError("unexpected binary/LFS object while archiving documents")
    target = CACHE / "upstream" / kind / repo / revision / item
    if not target.resolve().is_relative_to(CACHE.resolve()):
        raise ValueError("unsafe source path")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha(target.read_bytes()) != sha(raw):
            raise ValueError("pinned upstream document content changed")
    else:
        target.write_bytes(raw)
    return {
        "source_kind": kind, "repository": repo,
        "revision": revision, "source_path": item,
        "url": url, "view_url": view,
        "sha256": sha(raw), "size_bytes": len(raw),
        "local_copy": target.relative_to(ROOT).as_posix(),
        "related_v4_models": spec["models"],
        "source_type": "publisher-document",
        "redistribution_clearance": False,
    }


def documents_for_hf(meta: dict) -> list[str]:
    names = [v.get("rfilename", "") for v in meta.get("siblings", [])]
    documents = []
    for name in names:
        low = name.lower()
        base = low.rsplit("/", 1)[-1]
        if (not name or ".." in Path(name).parts or name.startswith("/")
            or len(name) > 200):
            continue
        if (base in {"readme.md", "license", "license.md", "license.txt",
                     "notice", "notice.md", "notice.txt", "copying",
                     "acceptable_use_policy.md", "usage_policy.md",
                     "model_card.md", "citation.cff"}
            or base.startswith(("license-", "notice-", "license_"))):
            documents.append(name)
    return sorted(set(documents), key=lambda name: (name.count("/"), name.lower()))[:32]


def documents_for_github(repo: str, revision: str) -> list[str]:
    tree_url = "https://api.github.com/repos/" + repo + "/git/trees/" + revision
    metadata = get_json(tree_url)
    names = []
    for row in metadata.get("tree", []):
        name = row.get("path", "")
        if row.get("type") != "blob" or "/" in name:
            continue
        lower = name.lower()
        if (lower in {"readme.md", "license", "license.md", "license.txt",
                      "notice", "notice.md", "notice.txt", "copying",
                      "citation.cff", "pyproject.toml", "setup.py",
                      "model_license.md", "acceptable_use_policy.md",
                      "usage_policy.md"}
            or lower.startswith(("license-", "notice-"))):
            names.append(name)
    return sorted(set(names))[:18]


def collect_source(spec_row: tuple) -> tuple[dict, list[dict]]:
    kind, repo, models = spec_row
    if kind.startswith("hf-"):
        endpoint = ("https://huggingface.co/api/"
                    + ("datasets/" if kind == "hf-dataset" else "models/") + repo)
        meta = get_json(endpoint)
        revision = meta.get("sha")
        card = meta.get("cardData") or {}
        declared = card.get("license") if isinstance(card, dict) else None
        names = documents_for_hf(meta)
    else:
        endpoint = "https://api.github.com/repos/" + repo
        meta = get_json(endpoint)
        branch = meta.get("default_branch", "main")
        commit = get_json(endpoint + "/commits/" + quote(branch, safe=""))
        revision = commit.get("sha")
        license_data = meta.get("license") or {}
        declared = license_data.get("spdx_id") if isinstance(license_data, dict) else None
        names = documents_for_github(repo, revision)
    if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("upstream immutable revision unavailable: " + repo)
    item = {
        "kind": kind, "repo": repo, "revision": revision, "models": models,
        "publisher_declared_license": declared,
        "publisher_metadata_endpoint": endpoint,
        "metadata_sha256": sha(json.dumps(meta, sort_keys=True,
                                         ensure_ascii=False).encode("utf-8")),
        "requested_document_paths": names,
    }
    evidences = []
    for name in names:
        try:
            evidences.append(fetch_document(item, name))
        except Exception as exc:
            evidences.append({
                "source_kind": kind, "repository": repo,
                "revision": revision, "source_path": name,
                "fetch_error": type(exc).__name__ + ": " + str(exc)[:200],
                "redistribution_clearance": False,
            })
    item["downloaded_document_count"] = sum("sha256" in doc for doc in evidences)
    item["failed_document_count"] = len(evidences) - item["downloaded_document_count"]
    item["note"] = ("Publisher license claim is evidence only; not a cleared "
                    "license for each model weight and bundled dependency.")
    print("UPSTREAM_EVIDENCE", repo, "pinned", revision[:12],
          "docs", item["downloaded_document_count"], "failed",
          item["failed_document_count"], flush=True)
    return item, evidences


def collect_webpage(source: tuple[str, str, str, list[str]], timestamp: str) -> dict:
    publisher, name, url, models = source
    raw = request(url, json_response=False)
    if b"\\0" in raw:
        raise ValueError("unexpected binary publisher legal page")
    target = CACHE / "upstream" / "publisher-webpages" / publisher / name
    if not target.resolve().is_relative_to(CACHE.resolve()):
        raise ValueError("unsafe publisher web page path")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Terms websites are mutable; preserve the exact first retrieved snapshot
    # and fail if a subsequent fetch silently tries to replace it.
    if target.exists() and sha(target.read_bytes()) != sha(raw):
        raise ValueError("publisher terms page changed; preserve original snapshot")
    target.write_bytes(raw)
    result = {
        "source_kind": "publisher-legal-webpage",
        "repository": publisher,
        "revision": None,
        "source_path": name,
        "url": url,
        "view_url": url,
        "sha256": sha(raw),
        "size_bytes": len(raw),
        "local_copy": target.relative_to(ROOT).as_posix(),
        "related_v4_models": models,
        "source_type": "official-publisher-terms-snapshot",
        "captured_at_utc": timestamp,
        "immutable_revision": False,
        "redistribution_clearance": False,
    }
    print("PUBLISHER_TERMS_SNAPSHOT", publisher, name, len(raw), flush=True)
    return result


def archives_copy_wheel_docs() -> dict:
    # Imported only if user requests --wheels. Records exact documentation
    # distributed INSIDE the archived vendor wheel, with wheel SHA pins.
    packages: list[dict] = []
    unique: dict[str, dict] = {}
    for package in sorted(PACKAGE_PATH.glob("*UNRELEASED-QA-format-v4.vwmodel")):
        with zipfile.ZipFile(package) as archive:
            m = json.loads(archive.read("manifest.json"))
            pins = {row["path"]: row for row in m["files"]}
            records = []
            for wheel in m["runtime"]["wheels"]:
                pin = pins[wheel]
                digest = pin["sha256"]
                if digest not in unique:
                    raw = archive.read(wheel)
                    if sha(raw) != digest or len(raw) != pin["size"]:
                        raise ValueError("third-party wheel hash verification failed")
                    with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
                        names = zipped.namelist()
                        selected = [
                            name for name in names
                            if ((name.endswith(".dist-info/METADATA") and len(name.split("/")) == 2)
                                or (any(term in name.rsplit("/", 1)[-1].lower()
                                        for term in ("license", "licence", "copying", "notice"))
                                    and not name.lower().endswith((".py", ".pyc"))))
                        ]
                        saved = []
                        for name in selected:
                            info = zipped.getinfo(name)
                            if info.file_size > 500_000:
                                continue
                            data = zipped.read(name)
                            if b"\0" in data:
                                continue
                            target = (CACHE / "wheel-docs" / digest[:16] / name)
                            if not target.resolve().is_relative_to(CACHE.resolve()):
                                raise ValueError("wheel document attempted path traversal")
                            target.parent.mkdir(parents=True, exist_ok=True)
                            if target.exists() and sha(target.read_bytes()) != sha(data):
                                raise ValueError("wheel document changed")
                            target.write_bytes(data)
                            saved.append({
                                "member_path": name, "local_copy": target.relative_to(ROOT).as_posix(),
                                "sha256": sha(data), "size_bytes": len(data),
                            })
                    unique[digest] = {
                        "wheel": Path(wheel).name, "wheel_sha256": digest,
                        "files": saved,
                    }
                records.append(digest)
            packages.append({
                "package_id": m["package"]["id"], "package_archive": package.name,
                "wheel_sha256": records, "public_release_authorized": False,
            })
        print("BUNDLED_WHEEL_DOCS", m["package"]["id"], len(records),flush=True)
    return {"packages": packages, "unique_wheel_evidence": unique}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheels", action="store_true", help="also archive wheel METADATA/LICENSE")
    parser.add_argument("--no-network", action="store_true",
                        help="only archive embedded wheel docs")
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sources: list[dict] = []
    documents: list[dict] = []
    issues: list[str] = []
    if not args.no_network:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {pool.submit(collect_source, row): row for row in SOURCES}
            for future in concurrent.futures.as_completed(jobs):
                row = jobs[future]
                try:
                    item, files = future.result()
                    sources.append(item)
                    documents.extend(files)
                except Exception as exc:
                    issues.append(str(row[0]) + "/" + row[1] + " -> "
                                  + type(exc).__name__ + ": " + str(exc)[:200])
                    print("UPSTREAM_SOURCE_ERROR", issues[-1], flush=True)
    if not args.no_network:
        for webpage in WEB_SOURCES:
            try:
                documents.append(collect_webpage(webpage, timestamp))
            except Exception as exc:
                issues.append("publisher legal terms " + webpage[2] + " -> "
                              + type(exc).__name__ + ": " + str(exc)[:200])
                print("TERMS_FETCH_ERROR", issues[-1], flush=True)
    wheel_result = archives_copy_wheel_docs() if args.wheels else None
    sources.sort(key=lambda r: (r["kind"], r["repo"]))
    documents.sort(key=lambda r: (r["repository"], r["source_path"]))
    public = {
        "schema": "voxweavetts.v4-upstream-rights-evidence",
        "version": 1,
        "retrieved_at_utc": timestamp,
        "source_repositories": sources,
        "upstream_documents": documents,
        "source_errors": issues,
        "all_models_public_redistribution_cleared": False,
        "model_rights_and_runtime_rights_separate": True,
        "raw_documents_local_only": True,
        "raw_documents_repository_tracked": False,
        "local_evidence_root": "cache/v4-rights-evidence",
        "notes": [
            "Copies are publisher-authored bytes from exact Git/HF revisions.",
            "Original copyright and license notices are not modified.",
            "User installing v4 is not a grant to publicly redistribute model binaries.",
            "No package was installed, published or executed during evidence gathering.",
        ],
    }
    if wheel_result:
        public["wheel_documents_copied"] = sum(
            len(w["files"]) for w in wheel_result["unique_wheel_evidence"].values()
        )
        public["unique_wheels_with_local_evidence"] = len(
            wheel_result["unique_wheel_evidence"]
        )
        (CACHE / "wheel-index.json").write_text(
            json.dumps(wheel_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (CACHE / "INDEX.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    PUBLIC_INDEX.parent.mkdir(parents=True,exist_ok=True)
    PUBLIC_INDEX.write_text(
        json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    good = sum("sha256" in row for row in documents)
    print("EVIDENCE_COMPLETE",json.dumps({
        "upstream_sources": len(sources),
        "upstream_documents_copied": good,
        "upstream_documents_failed": len(documents) - good,
        "source_errors": issues, "raw_copy_root": str(CACHE),
        "public_release_allowed": False
    },ensure_ascii=False),flush=True)
    return 0 if not issues and good else 2


if __name__ == "__main__":
    raise SystemExit(main())
