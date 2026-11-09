"""Loopback-only HTTP preview API for the VoxWeaveTTS text plan."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import __version__
from .processing import InputError, process_text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_REQUEST_BYTES = 65_536


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


class Handler(BaseHTTPRequestHandler):
    server_version = "VoxWeaveTTS/0.1"

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
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
                self.send_json(200, {
                    "app": "VoxWeaveTTS",
                    "version": __version__,
                    "foundation": True,
                    "capabilities": {
                        "text_filter": True,
                        "pronunciation_hints": True,
                        "tts_audio": False,
                        "voice_cloning": False,
                        "websocket_streaming": False,
                        "live_connectors": False,
                        "subtitle_overlay": False,
                        "portable_executable": False,
                    },
                })
            elif route == "/v1/rules":
                data = _load_json("data/filters/rules.json", [])
                self.send_json(200, data.get("rules", []) if isinstance(data, dict) else data)
            elif route == "/v1/pronunciations":
                self.send_json(200, _load_json("data/dictionaries/pronunciations.json", {}))
            else:
                self.send_json(404, {"error": "not found"})
        except (OSError, InputError) as exc:
            self.send_json(400, {"error": str(exc)})

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/v1/text/process":
            self.send_json(404, {"error": "not found"})
            return
        try:
            length_text = self.headers.get("Content-Length", "")
            if not length_text.isdecimal() or int(length_text) > MAX_REQUEST_BYTES:
                self.send_json(413, {"error": "invalid or excessive Content-Length"})
                return
            data = json.loads(self.rfile.read(int(length_text)).decode("utf-8"))
            if not isinstance(data, dict):
                raise InputError("request must be a JSON object")
            raw_rules = data.get("rules")
            if raw_rules is None:
                raw_rules = _load_json("data/filters/rules.json", [])
                if isinstance(raw_rules, dict):
                    raw_rules = raw_rules.get("rules", [])
            raw_dictionary = data.get("pronunciations")
            if raw_dictionary is None:
                raw_dictionary = _load_json(
                    "data/dictionaries/pronunciations.json", {}
                )
            result = process_text(
                text=data.get("text"),
                rules=raw_rules,
                pronunciations=raw_dictionary,
                source=data.get("source", "manual"),
            )
            self.send_json(200, result)
        except (InputError, json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            self.send_json(400, {"error": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        if os.environ.get("VOXWEAVETTS_HTTP_LOG") == "1":
            super().log_message(format, *args)


def serve(port: int = 8765) -> None:
    if not (1 <= port <= 65535):
        raise ValueError("port must be 1..65535")
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"VoxWeaveTTS foundation v{__version__} on http://127.0.0.1:{port}/",
              flush=True)
        print("Text preview only: no speech engine or voice cloning installed.",
              flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping VoxWeaveTTS.")
