"""Loopback-only JSON + WAV API for the VoxWeaveTTS M1 prototype."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import __version__
from .processing import InputError, process_text
from .speech import (
    ENGINE_ID,
    EngineUnavailable,
    SpeechFailure,
    engine_info,
    DEFAULT_SEED,
    render_wav,
    validate_seed,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_REQUEST_BYTES = 65_536
SYNTHESIS_SETTINGS = PROJECT_ROOT / "data" / "settings" / "synthesis.json"
_SETTINGS_LOCK = threading.RLock()


def _load_json(relative: str, default: Any) -> Any:
    path = PROJECT_ROOT / relative
    if not path.exists():
        return default
    if path.stat().st_size > MAX_REQUEST_BYTES:
        raise InputError(f"local {relative} file is too large")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"invalid local {relative} JSON: {exc}") from exc


def _read_seed() -> int:
    with _SETTINGS_LOCK:
        path = SYNTHESIS_SETTINGS
        if not path.exists():
            return DEFAULT_SEED
        if path.stat().st_size > 4096:
            raise InputError("synthesis settings file is too large")
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InputError("invalid synthesis settings file") from exc
        if not isinstance(document, dict):
            raise InputError("synthesis settings must be an object")
        return validate_seed(document.get("seed", DEFAULT_SEED))


def _save_seed(seed: int) -> None:
    """Keep seed preferences with the portable project, not browser storage."""
    seed = validate_seed(seed)
    with _SETTINGS_LOCK:
        path = SYNTHESIS_SETTINGS
        path.parent.mkdir(exist_ok=True, parents=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, prefix=".synthesis-",
                suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump({"seed": seed}, stream)
                stream.write("\n")
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "VoxWeaveTTS/0.1"

    def _headers(self, status: int, content_type: str, length: int,
                 extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def send_json(self, status: int, body: Any) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(payload))
        self.wfile.write(payload)

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        try:
            if route in {"/", "/index.html"}:
                payload = (PROJECT_ROOT / "web" / "index.html").read_bytes()
                self._headers(200, "text/html; charset=utf-8", len(payload))
                self.wfile.write(payload)
            elif route == "/v1/status":
                info = engine_info()
                self.send_json(200, {
                    "app": "VoxWeaveTTS",
                    "version": __version__,
                    "foundation": False,
                    "capabilities": {
                        "text_filter": True,
                        "pronunciation_hints": True,
                        "tts_audio": info.assets_ready and info.runtime_ready,
                        "reproducible_seed": info.assets_ready and info.runtime_ready,
                        "voice_cloning": False,
                        "websocket_streaming": False,
                        "live_connectors": False,
                        "subtitle_overlay": False,
                        "portable_executable": False,
                    },
                })
            elif route == "/v1/settings/synthesis":
                self.send_json(200, {"seed": _read_seed()})
            elif route == "/v1/engines":
                self.send_json(200, {"engines": [engine_info().as_dict()]})
            elif route == "/v1/voices":
                self.send_json(200, {
                    "voices": [{
                        "id": "thai_som",
                        "engine_id": ENGINE_ID,
                        "language": "th",
                        "voice_cloning": False,
                    }]
                })
            elif route == "/v1/rules":
                data = _load_json("data/filters/rules.json", [])
                self.send_json(
                    200, data.get("rules", []) if isinstance(data, dict) else data
                )
            elif route == "/v1/pronunciations":
                self.send_json(
                    200, _load_json("data/dictionaries/pronunciations.json", {})
                )
            else:
                self.send_json(404, {"error": "not found"})
        except (OSError, InputError) as exc:
            self.send_json(400, {"error": str(exc)})

    def _read_json(self) -> dict[str, Any]:
        length_text = self.headers.get("Content-Length", "")
        if not length_text.isdecimal() or int(length_text) > MAX_REQUEST_BYTES:
            raise InputError("invalid or excessive Content-Length (max 65536)")
        data = json.loads(self.rfile.read(int(length_text)).decode("utf-8"))
        if not isinstance(data, dict):
            raise InputError("request must be a JSON object")
        return data

    def _text_plan(self, data: dict[str, Any]) -> dict[str, Any]:
        rules = data.get("rules")
        if rules is None:
            rules = _load_json("data/filters/rules.json", [])
            if isinstance(rules, dict):
                rules = rules.get("rules", [])
        dictionary = data.get("pronunciations")
        if dictionary is None:
            dictionary = _load_json("data/dictionaries/pronunciations.json", {})
        return process_text(
            text=data.get("text"),
            rules=rules,
            pronunciations=dictionary,
            source=data.get("source", "manual"),
        )

    def do_POST(self) -> None:
        route = urlsplit(self.path).path
        if route == "/v1/settings/synthesis":
            if self.headers.get("X-VoxWeaveTTS-Intent") != "save-synthesis-settings":
                self.send_json(403, {"error": "missing settings update intent"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.send_json(415, {"error": "settings must be application/json"})
                return
            try:
                data = self._read_json()
                seed = validate_seed(data.get("seed"))
                _save_seed(seed)
                self.send_json(200, {"seed": seed})
            except (InputError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if route not in {"/v1/text/process", "/v1/speech"}:
            self.send_json(404, {"error": "not found"})
            return
        try:
            data = self._read_json()
            plan = self._text_plan(data)
            if route == "/v1/text/process":
                self.send_json(200, plan)
                return
            if data.get("engine_id", ENGINE_ID) != ENGINE_ID:
                raise InputError(f"unknown engine_id; available: {ENGINE_ID}")
            wav, info = render_wav(
                plan,
                speed=data.get("speed", 1.0),
                voice_id=data.get("voice_id", "thai_som"),
                seed=validate_seed(data.get("seed", _read_seed())),
            )
            self._headers(
                200, "audio/wav", len(wav),
                {
                    "X-VoxWeaveTTS-Engine": info["engine_id"],
                    "X-VoxWeaveTTS-Duration-Ms": str(info["duration_ms"]),
                    "X-VoxWeaveTTS-Seed": str(info["seed"]),
                },
            )
            self.wfile.write(wav)
        except (InputError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except EngineUnavailable as exc:
            self.send_json(503, {"error": str(exc)})
        except (SpeechFailure, OSError):
            self.send_json(502, {"error": "speech engine failed; check local diagnostics"})
        except Exception:
            # Third-party models may embed the original text in errors.
            # Never return a raw traceback or echo filtered text to an API client.
            self.send_json(502, {"error": "speech engine encountered an unexpected error"})

    def log_message(self, format: str, *args: Any) -> None:
        if os.environ.get("VOXWEAVETTS_HTTP_LOG") == "1":
            super().log_message(format, *args)


def serve(port: int = 8765) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("port must be 1..65535")
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"VoxWeaveTTS v{__version__} at http://127.0.0.1:{port}/",
              flush=True)
        info = engine_info()
        print(
            "Thai CPU speech available:"
            f" {info.assets_ready and info.runtime_ready}"
            " (voice clone and live connectors not implemented)",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping VoxWeaveTTS.")