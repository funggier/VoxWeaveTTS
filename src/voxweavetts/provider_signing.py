"""Offline Ed25519 publisher identity and explicit signed-provider approval.

No remote key lookup, TOFU, public certificate authority, or executable
provider import. The local user must pin each publisher key fingerprint and
separately approve each exact signed code bundle for execution.

Verification requires the audited 'cryptography' library. Without it, signed
providers fail closed; legacy manually reviewed v1 approvals remain separate.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from typing import Any

PUBLISHER_FORMAT = "voxweavetts.publisher-trust-v1"
SIGNATURE_FORMAT = "voxweavetts.provider-signature-v1"
APPROVAL_FORMAT = "voxweavetts.approved-provider-v2"
SIGNED_DOMAIN = b"VoxWeaveTTS\x00external-engine-provider\x00ed25519-v1\x00"
PINNED_FILES = ("provider.json", "worker.py", "requirements.txt")
ID = re.compile(r"[a-z][a-z0-9-]{2,63}\Z")
HEX_SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_TRUST_BYTES = 32768
MAX_SIGNATURE_BYTES = 3072
MAX_PROVIDER_FILE_BYTES = {
    "provider.json": 12_000,
    "worker.py": 4 * 1024 * 1024,
    "requirements.txt": 32768,
}


class SigningError(ValueError):
    """A publisher or provider signature cannot be trusted."""


def _cryptography():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey, Ed25519PrivateKey,
        )
        from cryptography.exceptions import InvalidSignature
    except ImportError as exc:
        raise SigningError(
            "Ed25519 verification unavailable: cryptography must be installed "
            "in the application Core runtime") from exc
    return Ed25519PublicKey, Ed25519PrivateKey, InvalidSignature


def fingerprint(public_key: bytes) -> str:
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        raise SigningError("Ed25519 public key must be exactly 32 bytes")
    return hashlib.sha256(public_key).hexdigest()


def _canonical(message: dict) -> bytes:
    return SIGNED_DOMAIN + json.dumps(
        message, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _read_json(path: Path, limit: int) -> Any:
    if (not path.is_file() or path.is_symlink() or path.stat().st_size > limit):
        raise SigningError("missing/unsafe/oversized signature or trust record")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SigningError("invalid trust/signature JSON") from exc


def _trust_path(root: Path) -> Path:
    return Path(root) / "settings" / "trusted-provider-publishers.json"


def _validate_trust(raw: Any) -> dict[str, dict[str, str]]:
    if (not isinstance(raw, dict) or set(raw) != {"format", "publishers"}
        or raw["format"] != PUBLISHER_FORMAT
        or not isinstance(raw["publishers"], dict)
        or len(raw["publishers"]) > 128):
        raise SigningError("invalid publisher trust store")
    for publisher, key in raw["publishers"].items():
        if (not isinstance(publisher, str) or not ID.fullmatch(publisher)
            or not isinstance(key, dict)
            or set(key) != {"public_key_base64", "fingerprint"}
            or not isinstance(key["fingerprint"], str)
            or not HEX_SHA.fullmatch(key["fingerprint"])):
            raise SigningError("invalid trusted publisher record")
        public_key = _decode_b64(key["public_key_base64"], 32)
        if fingerprint(public_key) != key["fingerprint"]:
            raise SigningError("trusted publisher fingerprint mismatch")
    return raw["publishers"]


def _decode_b64(value: Any, expected_bytes: int) -> bytes:
    if not isinstance(value, str) or len(value) > 128 or not value.isascii():
        raise SigningError("invalid key or signature encoding")
    try:
        result = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SigningError("invalid base64 key or signature") from exc
    if len(result) != expected_bytes:
        raise SigningError("invalid Ed25519 key or signature length")
    return result


def trusted_publishers(root: Path) -> dict[str, dict[str, str]]:
    """Read-only; no trust defaults, implicit key pins or remote requests."""
    path = _trust_path(root)
    if not path.exists() and not path.is_symlink():
        return {}
    if path.parent.is_symlink():
        raise SigningError("publisher trust directory is redirected")
    return _validate_trust(_read_json(path, MAX_TRUST_BYTES))


def _write_trust(root: Path, publishers: dict[str, dict[str, str]]) -> None:
    root = Path(root)
    file = _trust_path(root)
    file.parent.mkdir(parents=True, exist_ok=True)
    if (file.is_symlink() or file.parent.is_symlink()
        or not file.parent.resolve().is_relative_to(root.resolve())):
        raise SigningError("unsafe publisher trust store")
    record = {"format": PUBLISHER_FORMAT, "publishers": publishers}
    _validate_trust(record)
    payload = json.dumps(record, sort_keys=True, indent=2) + "\n"
    if len(payload.encode("utf-8")) > MAX_TRUST_BYTES:
        raise SigningError("publisher trust store is too large")
    # Never overwrite an existing trust file through a symlink or non-atomic
    # stream. No private signing keys are persisted in application settings.
    tmp = file.with_name("." + file.name + "." + secrets.token_hex(6))
    try:
        with tmp.open("x", encoding="utf-8") as output:
            output.write(payload)
        os.replace(tmp, file)
    finally:
        tmp.unlink(missing_ok=True)


def trust_publisher(*, root: Path, publisher_id: str, public_key: bytes,
                    expected_fingerprint: str, confirm_trust: bool = False) -> str:
    """Requires user authorization and an independently checked key fingerprint."""
    if not confirm_trust:
        raise SigningError("publisher trust requires explicit user confirmation")
    if not isinstance(publisher_id, str) or not ID.fullmatch(publisher_id):
        raise SigningError("invalid publisher id")
    computed = fingerprint(public_key)
    if (not isinstance(expected_fingerprint, str)
        or not HEX_SHA.fullmatch(expected_fingerprint)
        or expected_fingerprint != computed):
        raise SigningError("public key does not match expected fingerprint")
    publishers = trusted_publishers(root)
    if publisher_id in publishers:
        raise SigningError("publisher already trusted; revoke before key rotation")
    publishers[publisher_id] = {
        "public_key_base64": base64.b64encode(public_key).decode("ascii"),
        "fingerprint": computed,
    }
    _write_trust(root, publishers)
    return computed


def revoke_publisher(*, root: Path, publisher_id: str,
                     confirm_revoke: bool = False) -> bool:
    if not confirm_revoke:
        raise SigningError("publisher revocation requires explicit confirmation")
    if not isinstance(publisher_id, str) or not ID.fullmatch(publisher_id):
        raise SigningError("invalid publisher id")
    publishers = trusted_publishers(root)
    if publisher_id not in publishers:
        return False
    publishers.pop(publisher_id)
    _write_trust(root, publishers)
    return True


def _sha256_file(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _provider_files(folder: Path, root: Path | None = None) -> dict[str, str]:
    """Strictly resolve a provider's three execution-relevant files, as data."""
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise SigningError("external provider directory is redirected")
    if root is not None:
        base = Path(root) / "extensions" / "engine-providers"
        if (base.is_symlink() or base.parent.is_symlink()
            or folder.parent.resolve() != base.resolve()
            or folder.resolve().parent != base.resolve()):
            raise SigningError("provider outside approved extension directory")
    hashes = {}
    for name in PINNED_FILES:
        path = folder / name
        if (not path.is_file() or path.is_symlink()
            or path.stat().st_size > MAX_PROVIDER_FILE_BYTES[name]
            or path.resolve().parent != folder.resolve()):
            raise SigningError("missing, redirected or oversized provider file")
        hashes[name] = _sha256_file(path)
    return hashes


def _signature_message(publisher_id: str, hashes: dict[str, str]) -> dict:
    if (not isinstance(publisher_id, str) or not ID.fullmatch(publisher_id)
        or not isinstance(hashes, dict) or set(hashes) != set(PINNED_FILES)
        or any(not isinstance(x, str) or not HEX_SHA.fullmatch(x)
               for x in hashes.values())):
        raise SigningError("invalid signed provider payload")
    return {"format": SIGNATURE_FORMAT,
            "publisher_id": publisher_id, "files": hashes}


def sign_provider(*, folder: Path, publisher_id: str,
                  private_key: Any) -> Path:
    """Developer-only: creates detached signature; private key never saved."""
    _, PrivateKey, _ = _cryptography()
    if not isinstance(private_key, PrivateKey):
        raise SigningError("Ed25519 private key object required")
    hashes = _provider_files(folder)
    message = _signature_message(publisher_id, hashes)
    signature = private_key.sign(_canonical(message))
    path = Path(folder) / "provider-signature.json"
    if path.exists() or path.is_symlink():
        raise SigningError("refusing to replace existing signature")
    record = {**message,
              "signature_base64": base64.b64encode(signature).decode("ascii")}
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")
    return path


def verify_signed_provider(*, folder: Path, root: Path) -> dict:
    """Verify Ed25519 signature against a pre-trusted publisher fingerprint."""
    PublicKey, _, InvalidSignature = _cryptography()
    folder = Path(folder)
    hashes = _provider_files(folder, root)
    signature_path = folder / "provider-signature.json"
    record = _read_json(signature_path, MAX_SIGNATURE_BYTES)
    if (not isinstance(record, dict)
        or set(record) != {"format", "publisher_id", "files", "signature_base64"}):
        raise SigningError("invalid signed provider envelope")
    signed_message = _signature_message(record["publisher_id"], record["files"])
    if record["format"] != SIGNATURE_FORMAT or record["files"] != hashes:
        raise SigningError("signed provider differs from application files")
    trusted = trusted_publishers(root).get(record["publisher_id"])
    if trusted is None:
        raise SigningError("publisher key has not been explicitly trusted")
    key = _decode_b64(trusted["public_key_base64"], 32)
    signature = _decode_b64(record["signature_base64"], 64)
    try:
        PublicKey.from_public_bytes(key).verify(signature, _canonical(signed_message))
    except (InvalidSignature, ValueError) as exc:
        raise SigningError("invalid publisher signature") from exc
    return {"publisher_id": record["publisher_id"],
            "key_fingerprint": trusted["fingerprint"],
            "files": hashes,
            "signature_sha256": _sha256_file(signature_path)}


def approve_signed_provider(*, folder: Path, root: Path,
                            confirm_executable_code: bool = False) -> dict:
    """Separately approve the exact signed worker/recipe after verifying key."""
    if not confirm_executable_code:
        raise SigningError("executing signed provider requires separate approval")
    from .engine_provider_catalog import _validate_external_manifest
    folder = Path(folder)
    report = verify_signed_provider(folder=folder, root=root)
    manifest = _read_json(folder / "provider.json", MAX_PROVIDER_FILE_BYTES["provider.json"])
    _validate_external_manifest(manifest, folder)
    approval = {
        "format": APPROVAL_FORMAT,
        "publisher_id": report["publisher_id"],
        "key_fingerprint": report["key_fingerprint"],
        "signature_sha256": report["signature_sha256"],
        "files": report["files"],
    }
    destination = folder / "approved.json"
    if destination.is_symlink():
        raise SigningError("approved provider marker is redirected")
    tmp = destination.with_name("." + destination.name + "." + secrets.token_hex(6))
    try:
        tmp.write_text(json.dumps(approval, sort_keys=True, indent=2) + "\n",
                       encoding="utf-8")
        os.replace(tmp, destination)
    finally:
        tmp.unlink(missing_ok=True)
    return approval


def signed_approval_valid(*, folder: Path, root: Path, state: Any) -> bool:
    """Fail closed on changed code, revoked key or changed signed envelope."""
    if (not isinstance(state, dict)
        or set(state) != {"format", "publisher_id", "key_fingerprint",
                           "signature_sha256", "files"}
        or state["format"] != APPROVAL_FORMAT):
        return False
    try:
        report = verify_signed_provider(folder=folder, root=root)
        return all(state[key] == report[key] for key in
                   ("publisher_id", "key_fingerprint", "signature_sha256", "files"))
    except (SigningError, OSError, TypeError, UnicodeError, AttributeError):
        return False
