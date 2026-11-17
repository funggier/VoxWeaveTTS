#!/usr/bin/env python3
"""Offline first-party CLI for explicit Ed25519 TTS publisher trust.

Private keys are never generated, stored or exported by VoxWeaveTTS. Signers
manage keys separately, outside the application's portable folders.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voxweavetts.provider_signing import (
    SigningError, approve_signed_provider, fingerprint, revoke_publisher,
    sign_provider, trust_publisher, trusted_publishers,
    verify_signed_provider,
)


def _public(path: Path) -> bytes:
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    key = load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise SigningError("public key must use Ed25519")
    return key.public_bytes(Encoding.Raw, PublicFormat.Raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    trust = commands.add_parser("trust", help="pin independently verified Ed25519 key")
    trust.add_argument("--publisher-id", required=True)
    trust.add_argument("--public-key", required=True, type=Path)
    trust.add_argument("--expected-sha256", required=True)
    trust.add_argument("--confirm-trust", action="store_true")
    revoke = commands.add_parser("revoke", help="revoke publisher trust immediately")
    revoke.add_argument("--publisher-id", required=True)
    revoke.add_argument("--confirm-revoke", action="store_true")
    commands.add_parser("list", help="list trusted publisher IDs and public fingerprints")
    sign = commands.add_parser("sign", help="sign provider code with external key")
    sign.add_argument("--publisher-id", required=True)
    sign.add_argument("--private-key", required=True, type=Path)
    sign.add_argument("--folder", required=True, type=Path)
    verify = commands.add_parser("verify", help="verify signed provider and pinned key")
    verify.add_argument("--folder", required=True, type=Path)
    approve = commands.add_parser("approve", help="allow execution of verified signed provider")
    approve.add_argument("--folder", required=True, type=Path)
    approve.add_argument("--confirm-executable-code", action="store_true")
    args = parser.parse_args()
    if args.command == "trust":
        print("Pinned publisher fingerprint:", trust_publisher(
            root=ROOT, publisher_id=args.publisher_id, public_key=_public(args.public_key),
            expected_fingerprint=args.expected_sha256, confirm_trust=args.confirm_trust,
        ))
    elif args.command == "revoke":
        print("Publisher trust revoked:", revoke_publisher(
            root=ROOT, publisher_id=args.publisher_id,
            confirm_revoke=args.confirm_revoke))
    elif args.command == "list":
        for publisher, info in sorted(trusted_publishers(ROOT).items()):
            print(publisher, info["fingerprint"])
    elif args.command == "sign":
        from cryptography.hazmat.primitives.serialization import (
            load_pem_private_key,
        )
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        if args.private_key.resolve().is_relative_to(ROOT.resolve()):
            raise SigningError("private signing keys must be outside application folder")
        key = load_pem_private_key(args.private_key.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise SigningError("private signing key must be Ed25519")
        print("Detached signature:", sign_provider(
            folder=args.folder, publisher_id=args.publisher_id, private_key=key))
    elif args.command == "verify":
        result = verify_signed_provider(folder=args.folder, root=ROOT)
        print("Signature verified:", result["publisher_id"],
              result["key_fingerprint"])
        print("Code still requires separate explicit execution approval")
    else:
        result = approve_signed_provider(
            folder=args.folder, root=ROOT,
            confirm_executable_code=args.confirm_executable_code)
        print("Approved exact code and signing key:", result["publisher_id"])


if __name__ == "__main__":
    try:
        main()
    except (SigningError, OSError, ValueError, ImportError) as exc:
        print("Provider trust error:", exc, file=sys.stderr)
        raise SystemExit(1)
