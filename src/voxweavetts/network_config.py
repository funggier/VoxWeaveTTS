"""Portable network settings: simple username/password, separate LAN control endpoint."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "settings" / "network.json"
_LOCK = threading.RLock()
FIELDS = ("username", "remote_enabled", "control_host", "control_port",
          "api_port", "listener_host", "listener_port")
DEFAULTS: dict[str, Any] = {
    "username": "voxweave", "remote_enabled": False,
    "control_host": "0.0.0.0", "control_port": 8776,
    "api_port": 8765, "listener_host": "0.0.0.0",
    "listener_port": 8766, "password_hash": None,
}
_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,31}$")
_ITERATIONS = 240000


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not 4 <= len(password) <= 128:
        raise ValueError("password must contain 4..128 characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in password):
        raise ValueError("password contains a control character")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str | None) -> bool:
    if not isinstance(password, str) or not isinstance(stored, str):
        return False
    try:
        algo, rounds, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256" or int(rounds) != _ITERATIONS:
            return False
        raw_salt, raw_digest = bytes.fromhex(salt), bytes.fromhex(digest)
        if len(raw_salt) != 16 or len(raw_digest) != 32:
            return False
        check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                   raw_salt, _ITERATIONS)
        return hmac.compare_digest(check, raw_digest)
    except (ValueError, OverflowError):
        return False


def validate_host(host: str) -> str:
    try:
        address = ipaddress.IPv4Address(host)
    except (ipaddress.AddressValueError, TypeError):
        raise ValueError("host must be a numeric IPv4 address") from None
    if address.is_multicast or address.is_reserved or str(address) == "255.255.255.255":
        raise ValueError("invalid bind address")
    return str(address)


def _validate(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict) or set(doc) != set(DEFAULTS):
        raise ValueError("invalid network configuration")
    new = dict(doc)
    for field in ("api_port", "control_port", "listener_port"):
        value = new[field]
        if type(value) is not int or not 1 <= value <= 65535:
            raise ValueError(field + " must be 1..65535")
    if len({new["api_port"], new["control_port"], new["listener_port"]}) != 3:
        raise ValueError("API, control and listener ports must be different")
    for field in ("control_host", "listener_host"):
        new[field] = validate_host(new[field])
    if type(new["remote_enabled"]) is not bool:
        raise ValueError("remote_enabled must be boolean")
    if not isinstance(new["username"], str) or not _NAME.fullmatch(new["username"]):
        raise ValueError("username must be 1..32 ASCII letters, digits, _, . or -")
    if new["password_hash"] is not None and (
        not isinstance(new["password_hash"], str) or
        not new["password_hash"].startswith("pbkdf2_sha256$")
    ):
        raise ValueError("invalid stored password")
    if new["remote_enabled"] and not new["password_hash"]:
        raise ValueError("set password before enabling LAN control")
    return new


def public_network(doc: dict[str, Any]) -> dict[str, Any]:
    return {**{k: doc[k] for k in FIELDS},
            "password_configured": bool(doc["password_hash"])}


def load_network(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with _LOCK:
        if not path.is_file():
            return dict(DEFAULTS)
        try:
            if path.stat().st_size > 8192:
                raise ValueError("network settings are too large")
            return _validate(json.loads(path.read_text(encoding="utf-8-sig")))
        except (OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
            raise ValueError("invalid network settings") from exc


def save_network(updates: dict[str, Any], path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not isinstance(updates, dict) or set(updates) - (set(FIELDS) | {"password", "password_configured"}):
        raise ValueError("unknown network setting")
    with _LOCK:
        old = load_network(path)
        new = {**old, **{k: v for k, v in updates.items() if k in FIELDS}}
        password = updates.get("password", "")
        if password:
            new["password_hash"] = hash_password(password)
        elif password is None or password == "":
            pass
        else:
            raise ValueError("invalid password")
        checked = _validate(new)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=".network-", suffix=".tmp", delete=False) as f:
                temp = Path(f.name)
                json.dump(checked, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(temp, path)
        finally:
            if temp:
                temp.unlink(missing_ok=True)
        return checked
