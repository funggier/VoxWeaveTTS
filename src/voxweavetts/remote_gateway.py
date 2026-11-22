"""Restricted LAN API gateway for standalone Desktop clients.

Never expose the unrestricted localhost API over the network. HTTPS is not
provided by the built-in LAN gateway; use a trusted LAN/VPN, not Internet.
"""
from __future__ import annotations
import base64
from collections import deque
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .network_config import check_password, validate_host

GET_ROUTES = frozenset({"/v1/runtime/state", "/v1/jobs"})
POST_ROUTES = {
    "/v1/runtime/mode": "set-runtime-mode",
    "/v1/runtime/output": "set-runtime-output",
    "/v1/runtime/replay": "replay-computer-audio",
    "/v1/runtime/playback": "control-computer-playback",
    "/v1/jobs": "queue-speech",
}
STATE_KEYS = frozenset({
    "mode", "output", "available_outputs", "audio_state", "active_speech_id",
    "active_workspace", "pending_source_messages", "last_completed_speech_id",
    "completed", "failed", "last_error", "worker_running", "revision",
    "listeners", "sources",
})
JOB_KEYS = frozenset({"speech_id", "state", "source", "created_at", "audio"})
MAX_BODY = 10000


class RemoteControlGateway:
    def __init__(self, bind_host: str, bind_port: int, local_port: int,
                 username: str, password_hash: str, local_host: str = "127.0.0.1"):
        self.host = validate_host(bind_host)
        if not 0 <= bind_port <= 65535 or not 1 <= local_port <= 65535:
            raise ValueError("invalid port")
        if not password_hash:
            raise ValueError("remote control requires a configured password")
        self.port = bind_port
        self.local_port = local_port
        self.local_host = validate_host(local_host)
        self.username = username
        self.password_hash = password_hash
        self.server = None
        self.thread = None
        self.error = None
        self._fail_lock = threading.Lock()
        self._failed: dict[str, deque[float]] = {}

    def _allowed_attempt(self, addr: str) -> bool:
        now = time.monotonic()
        with self._fail_lock:
            attempts = self._failed.setdefault(addr, deque())
            while attempts and attempts[0] < now - 60:
                attempts.popleft()
            return len(attempts) < 8

    def _record_failure(self, addr: str) -> None:
        with self._fail_lock:
            self._failed.setdefault(addr, deque()).append(time.monotonic())

    def start(self):
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def respond(self, status: int, data: dict):
                raw=json.dumps(data,ensure_ascii=False,separators=(",",":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length",str(len(raw)))
                self.send_header("Cache-Control","no-store")
                self.send_header("X-Content-Type-Options","nosniff")
                self.send_header("Connection","close")
                self.end_headers()
                self.wfile.write(raw)

            def authenticate(self) -> bool:
                addr = self.client_address[0]
                if not gateway._allowed_attempt(addr):
                    self.respond(429, {"error":"too many login attempts"})
                    return False
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("Basic "):
                    gateway._record_failure(addr)
                    self.respond(401, {"error":"username/password required"})
                    return False
                try:
                    decoded=base64.b64decode(auth[6:],validate=True).decode("utf-8")
                    user, password=decoded.split(":",1)
                except (ValueError,UnicodeDecodeError):
                    gateway._record_failure(addr)
                    self.respond(401, {"error":"invalid login"})
                    return False
                if not (hmac.compare_digest(user,gateway.username) and
                        check_password(password,gateway.password_hash)):
                    gateway._record_failure(addr)
                    self.respond(401, {"error":"invalid login"})
                    return False
                return True

            def proxy(self, method, route, data=None, intent=""):
                headers={"Accept":"application/json"}
                body=None
                if data is not None:
                    headers.update({
                        "Content-Type":"application/json",
                        "X-VoxWeaveTTS-Intent":intent,
                    })
                    body=json.dumps(data,ensure_ascii=False).encode("utf-8")
                request=Request(
                    f"http://{gateway.local_host}:{gateway.local_port}{route}",
                    data=body,method=method,headers=headers)
                try:
                    with urlopen(request,timeout=15) as response:
                        value=json.load(response)
                        code=response.status
                except HTTPError as error:
                    code=error.code
                    try:value=json.load(error)
                    except ValueError:value={"error":"local API rejected request"}
                except (URLError,OSError,TimeoutError):
                    self.respond(502,{"error":"local server unavailable"})
                    return
                if not isinstance(value,dict):
                    self.respond(502,{"error":"invalid local API response"})
                    return
                if method=="GET" and route=="/v1/runtime/state":
                    value={k:v for k,v in value.items() if k in STATE_KEYS}
                    # Only aggregate source status, no secrets or raw messages.
                    if isinstance(value.get("sources"),dict):
                        value["sources"]={
                            key:{"state":item.get("state","idle"),
                                 "pending":item.get("pending",0)}
                            for key,item in value["sources"].items()
                            if isinstance(item,dict)
                        }
                elif method=="GET" and route=="/v1/jobs":
                    value={"jobs":[{k:v for k,v in job.items() if k in JOB_KEYS}
                                   for job in value.get("jobs",[]) if isinstance(job,dict)][-30:]}
                self.respond(code,value)

            def do_GET(self):
                if self.path not in GET_ROUTES:
                    self.respond(404,{"error":"unknown remote endpoint"});return
                if not self.authenticate():return
                self.proxy("GET",self.path)

            def do_POST(self):
                if self.path not in POST_ROUTES:
                    self.respond(404,{"error":"unknown remote endpoint"});return
                if not self.authenticate():return
                if self.headers.get("Origin"):
                    self.respond(403,{"error":"remote gateway does not accept browser-origin calls"});return
                if self.headers.get("Content-Type","").split(";")[0].lower()!="application/json":
                    self.respond(415,{"error":"JSON required"});return
                if self.headers.get("X-VoxWeaveTTS-Intent")!=POST_ROUTES[self.path]:
                    self.respond(403,{"error":"explicit command intent required"});return
                length=self.headers.get("Content-Length","")
                if not length.isdecimal() or not 0<int(length)<=MAX_BODY:
                    self.respond(413,{"error":"invalid request size"});return
                try:
                    data=json.loads(self.rfile.read(int(length)))
                    if not isinstance(data,dict):
                        raise ValueError("invalid body")
                except (ValueError,UnicodeDecodeError):
                    self.respond(400,{"error":"invalid JSON"});return
                if self.path=="/v1/jobs":
                    if set(data)!={"text","source","mode"} or data["source"]!="manual" or data["mode"]!="studio" or not isinstance(data["text"],str) or not 1<=len(data["text"])<=8000:
                        self.respond(400,{"error":"invalid remote speech job"});return
                self.proxy("POST",self.path,data,POST_ROUTES[self.path])

            def log_message(self,*args):
                # Do not leak credentials, content, or token-bearing URLs to log.
                pass

        try:
            self.server=ThreadingHTTPServer((self.host,self.port),Handler)
            self.server.daemon_threads=True
            self.thread=threading.Thread(target=self.server.serve_forever,
                                         name="voxweavetts-remote-api",daemon=True)
            self.thread.start()
        except OSError as err:
            self.error=type(err).__name__
            self.server=None

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=3)
