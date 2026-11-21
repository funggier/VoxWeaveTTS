"""User-initiated Windows Save As dialog for browser-compatible source exports.

Called only by a host-only, same-origin, explicit-intent HTTP endpoint.
Never choose a file path automatically, log credentials, or expose saved paths.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

MAX_PROFILE_EXPORT_BYTES = 16_384
_SAVE_DIALOG_LOCK = threading.Lock()
_NO_CREDENTIAL_MODES = frozenset(("tiktok", "youtube_browser", "tiktok_browser"))
_ALLOWED_MODES = _NO_CREDENTIAL_MODES | {"live", "discord", "discord_client"}
_COMMON_FIELDS = frozenset((
    "format", "version", "mode", "source_id", "filters", "auto_read",
    "read_history_limit",
))
_OPTIONAL_FIELDS = frozenset((
    "read_sender_name", "random_queue_enabled", "random_queue_threshold", "random_queue_keep",
))


class SaveDialogUnavailable(Exception):
    """Native Save As UI could not be opened on the local host."""


class SaveDialogBusy(Exception):
    """Another user-initiated Save As dialog is already active."""


def validate_export_payload(data: Any) -> tuple[str, str]:
    """Return a bounded UTF-8 payload and safe file name; never echo secrets."""
    if not isinstance(data, dict) or set(data) != {"filename", "profile"}:
        raise ValueError("invalid export request")
    profile = data["profile"]
    filename = data["filename"]
    if not isinstance(profile, dict):
        raise ValueError("invalid profile")
    mode = profile.get("mode")
    if (not isinstance(mode, str) or mode not in _ALLOWED_MODES
        or profile.get("format") != "voxweavetts.source-settings"
        or type(profile.get("version")) is not int or profile["version"] != 1):
        raise ValueError("unsupported settings profile")
    credentials = (
        ("client_id", "client_secret", "redirect_uri") if mode == "discord_client"
        else () if mode in _NO_CREDENTIAL_MODES else ("credential",)
    )
    required = _COMMON_FIELDS | set(credentials)
    fields = set(profile)
    if not required <= fields <= required | _OPTIONAL_FIELDS:
        raise ValueError("invalid settings fields")
    for key in ("read_sender_name", "random_queue_enabled"):
        if key in profile and type(profile[key]) is not bool:
            raise ValueError("invalid settings flags")
    threshold = profile.get("random_queue_threshold", 20)
    keep = profile.get("random_queue_keep", 5)
    if type(threshold) is not int or type(keep) is not int or not 1 <= keep < threshold <= 100_000:
        raise ValueError("invalid random queue settings")
    if not isinstance(profile.get("source_id"), str) or not isinstance(profile.get("auto_read"), bool):
        raise ValueError("invalid settings fields")
    if not isinstance(profile.get("filters"), dict):
        raise ValueError("invalid settings filters")
    if not isinstance(filename, str) or not re.fullmatch(
        rf"VoxWeaveTTS-{mode}-[A-Za-z0-9_-]{{1,48}}[.]json", filename
    ):
        raise ValueError("invalid suggested filename")
    if not all(isinstance(profile[key], str) for key in credentials):
        raise ValueError("invalid credentials")
    payload = json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
    if len(payload.encode("utf-8")) > MAX_PROFILE_EXPORT_BYTES:
        raise ValueError("settings file is too large")
    return payload, filename


def _native_file_picker(filename: str) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
    except Exception as exc:
        # Tk initialization can fail on a headless or non-interactive host.
        raise SaveDialogUnavailable("native Save As dialog unavailable") from exc

    try:
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        selected = filedialog.asksaveasfilename(
            parent=root, title="VoxWeaveTTS — Save Settings",
            initialfile=filename, defaultextension=".json",
            filetypes=[("JSON settings", "*.json")],
            confirmoverwrite=True,
        )
        return selected or None
    except (OSError, RuntimeError, tk.TclError) as exc:
        raise SaveDialogUnavailable("native Save As dialog unavailable") from exc
    finally:
        try:
            root.destroy()
        except (OSError, RuntimeError, tk.TclError):
            pass


def save_source_profile_dialog(
    request: dict[str, Any], *, choose_path: Callable[[str], str | None] | None = None,
) -> bool:
    """Display a dialog, save only after user selection. False means cancelled."""
    payload, filename = validate_export_payload(request)
    if not _SAVE_DIALOG_LOCK.acquire(blocking=False):
        raise SaveDialogBusy("save dialog busy")
    try:
        selected = (choose_path or _native_file_picker)(filename)
        if not selected:
            return False
        target = Path(selected)
        if target.suffix.lower() != ".json":
            raise ValueError("selected settings file must end with .json")
        # Atomic replacement in the user's chosen folder. Never emit the
        # full path or any credential to the HTTP response or application logs.
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=target.parent,
                prefix=".voxweave-profile-", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return True
    finally:
        _SAVE_DIALOG_LOCK.release()
