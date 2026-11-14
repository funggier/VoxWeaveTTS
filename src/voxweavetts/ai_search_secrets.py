"""Local API key storage for opt-in search providers.

On Windows, keys are encrypted with user-scoped DPAPI and stored in Portable
data/settings/ (not in AI settings JSON or exportable profiles). A copied
encrypted file is not portable to another Windows account. On other OSes, the
operator must use environment variables; plaintext persistence is refused.
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
import tempfile
import threading
from pathlib import Path
from ctypes import wintypes

ROOT = Path(__file__).resolve().parents[2]
SECRET_FILE = ROOT / "data" / "settings" / "ai-search-secrets.json"
_ENV = {"ollama": "OLLAMA_API_KEY", "tavily": "TAVILY_API_KEY"}
_LOCK = threading.RLock()


class SecretUnavailable(RuntimeError):
    pass


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data: bytes, *, decrypt: bool) -> bytes:
    if os.name != "nt":
        raise SecretUnavailable("persisting API keys requires Windows DPAPI")
    from ctypes import windll
    crypt32, kernel32 = windll.crypt32, windll.kernel32
    src = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    input_blob = _Blob(len(data), ctypes.cast(src, ctypes.POINTER(ctypes.c_ubyte)))
    out = _Blob()
    description = ctypes.c_wchar_p("VoxWeaveTTS search provider API key")
    if decrypt:
        fn = crypt32.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(_Blob), ctypes.POINTER(ctypes.c_wchar_p),
                       ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                       wintypes.DWORD, ctypes.POINTER(_Blob)]
        fn.restype = wintypes.BOOL
        ok = fn(ctypes.byref(input_blob), None, None, None, None,
                0x1, ctypes.byref(out))  # CRYPTPROTECT_UI_FORBIDDEN
    else:
        fn = crypt32.CryptProtectData
        fn.argtypes = [ctypes.POINTER(_Blob), ctypes.c_wchar_p, ctypes.POINTER(_Blob),
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                       ctypes.POINTER(_Blob)]
        fn.restype = wintypes.BOOL
        ok = fn(ctypes.byref(input_blob), description, None, None, None,
                0x1, ctypes.byref(out))
    if not ok:
        raise SecretUnavailable("Windows DPAPI could not protect the API key")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def _read() -> dict[str, str]:
    if not SECRET_FILE.is_file():
        return {}
    if SECRET_FILE.stat().st_size > 8192 or SECRET_FILE.is_symlink():
        raise SecretUnavailable("API key store is invalid")
    try:
        record = json.loads(SECRET_FILE.read_text(encoding="utf-8"))
        if (not isinstance(record, dict) or set(record) - set(_ENV)
                or any(not isinstance(v, str) or len(v) > 2048 for v in record.values())):
            raise ValueError("key store schema")
    except (OSError, ValueError, UnicodeError) as exc:
        raise SecretUnavailable("API key store cannot be read") from exc
    return record


def get_key(provider: str) -> str:
    if not isinstance(provider, str) or provider not in _ENV:
        raise ValueError("API key not supported for provider")
    with _LOCK:
        record = _read()
        if provider in record:
            try:
                value = _dpapi(base64.b64decode(record[provider], validate=True),
                               decrypt=True).decode("utf-8")
                return value
            except (ValueError, UnicodeError, SecretUnavailable) as exc:
                raise SecretUnavailable("saved API key cannot be decrypted by this account") from exc
        return os.environ.get(_ENV[provider], "")


def key_status() -> dict[str, bool]:
    with _LOCK:
        record = _read()
        return {name: bool(record.get(name) or os.environ.get(env))
                for name, env in _ENV.items()}


def update_key(provider: str, action: str, value: str = "") -> dict[str, bool]:
    if (not isinstance(provider, str) or provider not in _ENV or
            not isinstance(action, str) or action not in {"save", "clear"}):
        raise ValueError("unsupported search key operation")
    if (action == "save" and (not isinstance(value, str) or
            not 8 <= len(value) <= 512 or not value.isascii() or
            any(ord(ch) < 33 for ch in value))):
        raise ValueError("invalid API key")
    if action == "clear" and value:
        raise ValueError("clear may not include an API key")
    with _LOCK:
        record = _read()
        if action == "save":
            record[provider] = base64.b64encode(
                _dpapi(value.encode("utf-8"), decrypt=False)
            ).decode("ascii")
        else:
            record.pop(provider, None)
        SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(
                    dir=SECRET_FILE.parent, prefix=".search-credential-",
                    suffix=".tmp", mode="wb", delete=False) as stream:
                temp = Path(stream.name)
                stream.write(json.dumps(record).encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, SECRET_FILE)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
    return key_status()
