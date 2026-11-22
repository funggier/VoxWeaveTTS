"""Resolve the Portable listener settings and authorize HTTP clients."""
from __future__ import annotations

import base64
import hmac
import ipaddress
import json
import os
from dataclasses import dataclass, field
import re
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
NETWORK_FILE = Path(__file__).resolve().parents[2] / "data" / "network.json"
NETWORK_USERNAME = "voxweave"


@dataclass(frozen=True)
class NetworkSettings:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    access_code: str = field(default="", repr=False)
    username: str = NETWORK_USERNAME

    def __post_init__(self) -> None:
        if not isinstance(self.host, str):
            raise ValueError("IP must be an IPv4 address")
        try:
            address = ipaddress.IPv4Address(self.host)
        except ValueError:
            raise ValueError("IP must be an IPv4 address, such as 127.0.0.1") from None
        if address.packed[0] >= 224:
            raise ValueError("IP must be a local interface address or 0.0.0.0")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port must be 1..65535")
        if not isinstance(self.access_code, str) or (
            (self.access_code or not address.is_loopback)
            and not re.fullmatch(r"[!-~]{4,128}", self.access_code)
        ):
            raise ValueError("network access requires a code of 4..128 printable ASCII characters")

        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,31}", self.username):
            raise ValueError("username must be 1..32 letters, digits, underscore, dot or dash")


def load_network_settings(
    host: str | None = None, port: int | None = None, *, path: Path | None = None
) -> NetworkSettings:
    try:
        with (path if path is not None else NETWORK_FILE).open(encoding="utf-8-sig") as source:
            settings = json.load(source)
    except FileNotFoundError:
        settings = {}
    except (OSError, ValueError):
        raise ValueError("could not read data/network.json") from None
    if not isinstance(settings, dict):
        raise ValueError("data/network.json must be an object")
    return NetworkSettings(
        host if host is not None else settings.get("host", DEFAULT_HOST),
        port if port is not None else settings.get("port", DEFAULT_PORT),
        os.environ.get("VOXWEAVETTS_NETWORK_PASSWORD", settings.get("access_code", "")),
        os.environ.get("VOXWEAVETTS_NETWORK_USERNAME", settings.get("username", NETWORK_USERNAME)),
    )


class NetworkAccess:
    """Use the actual connection address and a per-installation access code."""

    def __init__(self, settings: NetworkSettings):
        credentials = f"{settings.username}:{settings.access_code}".encode("ascii")
        self._authorization = b"Basic " + base64.b64encode(credentials)

    @staticmethod
    def is_owner(peer: str, local_ip: str) -> bool:
        return ipaddress.IPv4Address(peer).is_loopback or peer == local_ip

    @staticmethod
    def valid_host(host: str, local_ip: str, port: int) -> bool:
        allowed = {f"{local_ip}:{port}"}
        if ipaddress.IPv4Address(local_ip).is_loopback:
            allowed.add(f"localhost:{port}")
        if port == 80:
            allowed.update(authority.rsplit(":", 1)[0] for authority in tuple(allowed))
        return host in allowed

    def authorized(self, header: str) -> bool:
        return hmac.compare_digest(header.encode("latin-1"), self._authorization)
