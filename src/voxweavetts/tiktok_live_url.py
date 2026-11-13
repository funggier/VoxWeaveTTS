"""Strict public TikTok LIVE URL and username validation for user-chosen tabs."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from .processing import InputError

USERNAME = re.compile(r"^[A-Za-z0-9_.]{2,24}$")


def username_from_input(source: object) -> str:
    """Accept a username or a canonical HTTPS TikTok LIVE tab URL only."""
    if not isinstance(source, str) or len(source) > 240:
        raise InputError("TikTok LIVE username or URL required")
    value = source.strip()
    if value.startswith("@"):
        value = value[1:]
    if USERNAME.fullmatch(value) and not value.startswith(".") and not value.endswith("."):
        return value
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise InputError("invalid TikTok LIVE URL") from None
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise InputError("use a TikTok https LIVE URL")
    try:
        host, port = parsed.hostname, parsed.port
    except ValueError:
        raise InputError("invalid TikTok LIVE URL") from None
    if host not in ("www.tiktok.com", "tiktok.com") or port is not None:
        raise InputError("only canonical tiktok.com LIVE URLs are supported")
    parts = parsed.path.split("/")
    if len(parts) != 3 or not parts[1].startswith("@") or parts[2] != "live":
        raise InputError("use a TikTok LIVE URL like https://www.tiktok.com/@user/live")
    name = parts[1][1:]
    if not USERNAME.fullmatch(name) or name.startswith(".") or name.endswith("."):
        raise InputError("invalid TikTok username")
    return name
