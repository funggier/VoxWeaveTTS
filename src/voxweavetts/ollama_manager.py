"""Local Ollama model discovery and explicit memory preload.

Never downloads models; requires an exact name already returned by /api/tags.
All requests target the fixed loopback Ollama server, not arbitrary user URLs.
"""
from __future__ import annotations

import json
import re
import threading
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:11434"
MAX_RESPONSE = 128_000
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,99}\Z")
_PRELOAD_LOCK = threading.Lock()


class OllamaUnavailable(RuntimeError):
    pass


def validate_model_name(value: Any) -> str:
    if (not isinstance(value, str) or not _MODEL.fullmatch(value)
            or "://" in value or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise ValueError("invalid Ollama model name")
    return value


def _request(endpoint: str, *, data: dict[str, Any] | None = None,
             timeout: int = 6) -> dict[str, Any]:
    url = BASE + endpoint
    headers = {"Content-Type": "application/json"}
    request = Request(
        url, data=(json.dumps(data).encode("utf-8") if data is not None else None),
        headers=headers, method="POST" if data is not None else "GET"
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.length is not None and response.length > MAX_RESPONSE:
                raise OllamaUnavailable("Ollama response too large")
            payload = response.read(MAX_RESPONSE + 1)
        if len(payload) > MAX_RESPONSE:
            raise OllamaUnavailable("Ollama response too large")
        result = json.loads(payload.decode("utf-8"))
        if not isinstance(result, dict):
            raise OllamaUnavailable("Ollama returned unexpected data")
        return result
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeError) as exc:
        raise OllamaUnavailable("local Ollama service is unavailable or returned an error") from exc


def installed_models() -> dict[str, Any]:
    try:
        rows = _request("/api/tags").get("models", [])
    except OllamaUnavailable:
        return {"running": False, "models": []}
    models: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        raise OllamaUnavailable("invalid Ollama installed-model list")
    for item in rows[:200]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        try:
            validate_model_name(name)
        except ValueError:
            continue
        models.append({
            "name": name,
            "size_bytes": item["size"] if type(item.get("size")) is int else None,
        })
    return {"running": True, "models": models}


def loaded_models() -> dict[str, Any]:
    try:
        rows = _request("/api/ps").get("models", [])
    except OllamaUnavailable:
        return {"running": False, "models": []}
    if not isinstance(rows, list):
        raise OllamaUnavailable("invalid Ollama loaded-model list")
    items = []
    for item in rows[:200]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        try:
            validate_model_name(name)
        except ValueError:
            continue
        items.append({"name": name, "expires_at": str(item.get("expires_at") or "")[:80]})
    return {"running": True, "models": items}


def model_status(model: str = "") -> dict[str, Any]:
    installed = installed_models()
    loaded = loaded_models() if installed["running"] else {"running": False, "models": []}
    names = [item["name"] for item in installed["models"]]
    in_memory = [item["name"] for item in loaded["models"]]
    result = {
        "server_running": installed["running"],
        "loaded_status_available": loaded["running"],
        "installed_models": installed["models"],
        "loaded_models": loaded["models"],
    }
    if model:
        validate_model_name(model)
        result["selected"] = {
            "name": model,
            "installed": model in names,
            "in_memory": model in in_memory,
        }
    return result


def preload(model: str, keep_alive_minutes: int = 360) -> dict[str, Any]:
    """Explicitly warm a preinstalled model into RAM/VRAM; never pull."""
    validate_model_name(model)
    if type(keep_alive_minutes) is not int or not 1 <= keep_alive_minutes <= 360:
        raise ValueError("keep_alive_minutes must be 1..360")
    if not _PRELOAD_LOCK.acquire(blocking=False):
        raise OllamaUnavailable("another Ollama model preload is in progress")
    try:
        installed = installed_models()
        if not installed["running"]:
            raise OllamaUnavailable("start Ollama on this computer first")
        if model not in {m["name"] for m in installed["models"]}:
            raise OllamaUnavailable("model not installed; install it separately in Ollama")
        # Empty prompt: instruct Ollama to load/keep model in memory, not to
        # translate, chat, execute a tool or download a model.
        reply = _request("/api/generate", data={
            "model": model,
            "prompt": "",
            "stream": False,
            "keep_alive": f"{keep_alive_minutes}m",
        }, timeout=180)
        if reply.get("error"):
            raise OllamaUnavailable("Ollama could not preload the selected model")
        current = loaded_models()
        ready = model in {m["name"] for m in current["models"]}
        return {
            "model": model,
            "preload_requested": True,
            "in_memory": ready,
            "keep_alive_minutes": keep_alive_minutes,
            "loaded_status_available": current["running"],
        }
    finally:
        _PRELOAD_LOCK.release()
