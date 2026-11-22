"""Minimal token-gated LAN listening gateway.

The main VoxWeaveTTS control API stays loopback-only. The optional LAN
gateway exposes only a live PCM stream, an aggregate status and stop/replay
commands, never WAV downloads, secret settings or raw chat text.
"""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import socket
import threading
from typing import Any
from urllib.parse import urlsplit
from pathlib import Path

MAX_LISTENER_PORT = 65535
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def local_ip() -> str:
    """Best-effort LAN address; no packet is transmitted by UDP connect."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 9))
        address = sock.getsockname()[0]
        return address if address and not address.startswith("127.") else "127.0.0.1"
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


class ListeningGateway:
    def __init__(self, runtime: Any, port: int = 8766, host: str = "0.0.0.0"):
        if not 1 <= port <= MAX_LISTENER_PORT:
            raise ValueError("invalid listener port")
        self.runtime = runtime
        self.port = port
        self.host = host
        self.token = secrets.token_urlsafe(32)
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.error: str | None = None

    @property
    def url(self) -> str:
        # Fragment prevents credentials being sent in HTTP GET or access logs.
        return f"http://{local_ip() if self.host == '0.0.0.0' else self.host}:{self.port}/listen#token={self.token}"

    def start(self) -> None:
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _authorized(self) -> bool:
                authorization = self.headers.get("Authorization", "")
                expected = "Bearer " + gateway.token
                return hmac.compare_digest(authorization, expected)

            def _respond(self, status: int, mime: str, body: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Access-Control-Allow-Origin", "null")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, status: int, data: dict[str, Any]) -> None:
                self._respond(status, "application/json; charset=utf-8",
                              json.dumps(data).encode("utf-8"))

            def do_GET(self) -> None:
                route = urlsplit(self.path).path
                if route in {"/listen", "/listen.html"}:
                    document = (PROJECT_ROOT / "web" / "listen.html").read_bytes()
                    self._respond(200, "text/html; charset=utf-8", document)
                elif route == "/v1/live/status":
                    if not self._authorized():
                        self._json(401, {"error": "listener authorization required"})
                    else:
                        data = gateway.runtime.snapshot()
                        self._json(200, {
                            "mode": data["mode"], "output": data["output"],
                            "audio_state": data["audio_state"],
                            "active_workspace": data["active_workspace"],
                            "listener_count": data["listeners"],
                            "completed": data["completed"], "failed": data["failed"],
                        })
                elif route == "/v1/live/stream":
                    if not self._authorized():
                        self._json(401, {"error": "listener authorization required"})
                        return
                    try:
                        listener = gateway.runtime.audio_hub.subscribe()
                    except ValueError:
                        self._json(429, {"error": "too many listeners"})
                        return
                    try:
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                        self.send_header("Cache-Control", "no-store, no-transform")
                        self.send_header("Connection", "close")
                        self.send_header("X-Accel-Buffering", "no")
                        self.end_headers()
                        self.wfile.write(b"event: connected\\ndata: {}\\n\\n".replace(b"\\n", b"\n"))
                        self.wfile.flush()
                        while not gateway.runtime._shutdown.is_set():
                            packet = listener.take(2.0)
                            if packet is None:
                                self.wfile.write(b": heartbeat\n\n")
                            else:
                                payload = json.dumps(packet, separators=(",", ":"))
                                self.wfile.write(
                                    ("data: " + payload + "\n\n").encode("ascii")
                                )
                            self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                        pass
                    finally:
                        gateway.runtime.audio_hub.unsubscribe(listener)
                else:
                    self._json(404, {"error": "unknown listening endpoint"})

            def do_POST(self) -> None:
                route = urlsplit(self.path).path
                size = self.headers.get("Content-Length", "")
                if size.isdecimal() and int(size) <= 256:
                    self.rfile.read(int(size))
                else:
                    self._json(400, {"error": "invalid request"})
                    self.close_connection = True
                    return
                if not self._authorized():
                    self._json(401, {"error": "listener authorization required"})
                    return
                origin = self.headers.get("Origin")
                host = self.headers.get("Host")
                if origin and origin != "http://" + host:
                    self._json(403, {"error": "same-origin listening control required"})
                    return
                if route == "/v1/live/replay":
                    try:
                        self._json(202, gateway.runtime.replay_latest())
                    except ValueError:
                        self._json(409, {"error": "no speech available for replay"})
                elif route == "/v1/live/stop":
                    self._json(200, gateway.runtime.stop_audio())
                else:
                    self._json(404, {"error": "unknown listening endpoint"})

            def log_message(self, fmt: str, *args: Any) -> None:
                # Never log bearer tokens, messages, audio or listener URLs.
                pass

        try:
            self.server = ThreadingHTTPServer((self.host, self.port), Handler)
            self.server.daemon_threads = True
            self.thread = threading.Thread(
                target=self.server.serve_forever,
                name="voxweavetts-listener-gateway", daemon=True
            )
            self.thread.start()
        except OSError as exc:
            self.error = type(exc).__name__
            self.server = None

    def close(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=3)
