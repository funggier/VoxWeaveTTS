"""Native portable API client for VoxWeaveTTS on Windows.

All commands go over HTTP to the same server used by the web UI. Closing this
window does not stop the server, interrupt the audio or revoke sources.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from .network import load_network_settings
import webbrowser


ROOT = Path(__file__).resolve().parents[2]


def api(port: int, route: str, data: dict[str, Any] | None = None,
        intent: str | None = None) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    method = "GET"
    payload = None
    if data is not None:
        method = "POST"
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers.update({
            "Content-Type": "application/json",
            "X-VoxWeaveTTS-Intent": intent or "",
        })
    request = Request(
        f"http://{(lambda h: '127.0.0.1' if h == '0.0.0.0' else h)(load_network_settings().host)}:{port}{route}", data=payload,
        method=method, headers=headers,
    )
    try:
        with urlopen(request, timeout=5.0) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            detail = json.load(exc).get("error", "request rejected")
        except (ValueError, OSError):
            detail = "request rejected"
        raise RuntimeError(f"API {exc.code}: {detail}") from None


def launch_server(port: int) -> None:
    """Start a detached server if needed. No absolute paths are persisted."""
    try:
        data = api(port, "/v1/status")
        if data.get("app") == "VoxWeaveTTS":
            return
    except (URLError, OSError, ValueError, TimeoutError):
        pass
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HF_HOME": str(ROOT / "cache" / "huggingface"),
        "TORCH_HOME": str(ROOT / "cache" / "torch"),
        "XDG_CACHE_HOME": str(ROOT / "cache"),
        "TEMP": str(ROOT / "cache" / "temp"),
        "TMP": str(ROOT / "cache" / "temp"),
    })
    for name in ("cache/temp", "cache/torch", "cache/huggingface"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    flags = 0
    if os.name == "nt":
        flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                 | getattr(subprocess, "DETACHED_PROCESS", 0))
    subprocess.Popen(
        [sys.executable, "-m", "voxweavetts", "--port", str(port)],
        cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=flags, close_fds=True,
    )


class DesktopClient:
    def __init__(self, port: int):
        self.port = port
        self.root = tk.Tk()
        self.root.title("VoxWeaveTTS — Desktop API Controller")
        self.root.geometry("780x600")
        self.root.minsize(650, 510)
        self.inbox: Queue[tuple[str, Any]] = Queue()
        self.closed = False
        self.fetching = False
        self.mode = tk.StringVar(value="browser")
        self.output = tk.StringVar(value="default")
        self.status = tk.StringVar(value="กำลังเชื่อมต่อ VoxWeaveTTS API...")
        self.sources = tk.StringVar(value="กำลังอ่านสถานะต้นทาง...")
        self.last_job = tk.StringVar(value="ยังไม่มีงานสร้างเสียง")
        self.broadcast = tk.StringVar(value="ยังไม่มีลิงก์รับฟัง")
        self.listen_url: str | None = None
        self.cached_output_list: tuple[tuple[str, str], ...] = ()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(75, self._process)
        self.root.after(100, self._poll)
        threading.Thread(target=self._start_service, daemon=True).start()

    def _build(self) -> None:
        area = ttk.Frame(self.root, padding=20)
        area.pack(fill="both", expand=True)
        ttk.Label(area, text="VoxWeaveTTS", font=("Segoe UI", 21, "bold")).pack(anchor="w")
        ttk.Label(area, text="Desktop UI · ส่งคำสั่งผ่าน Local API เท่านั้น").pack(anchor="w", pady=(2, 14))
        tabs = ttk.Notebook(area)
        tabs.pack(fill="both", expand=True)
        panel = ttk.Frame(tabs, padding=15)
        settings = ttk.Frame(tabs, padding=15)
        tabs.add(panel, text="สถานะและควบคุม")
        tabs.add(settings, text="ตั้งค่า")

        ttk.Label(panel, textvariable=self.status, wraplength=690, justify="left").pack(anchor="w", pady=(0, 12))
        ttk.Label(panel, textvariable=self.sources, wraplength=690, justify="left").pack(anchor="w", pady=(0, 12))
        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="ข้อความใหม่สำหรับสร้างเสียง", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.text = tk.Text(panel, height=4, wrap="word", font=("Segoe UI", 11))
        self.text.pack(fill="x", pady=(6, 8))
        actions = ttk.Frame(panel)
        actions.pack(fill="x")
        ttk.Button(actions, text="ส่งข้อความเข้า TTS ผ่าน API",
                   command=self.submit_text).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="เล่นซ้ำเสียงล่าสุด",
                   command=lambda: self._command("/v1/runtime/replay", {}, "replay-computer-audio")).pack(side="left", padx=6)
        ttk.Button(actions, text="หยุดเสียง",
                   command=lambda: self._command("/v1/runtime/playback", {"action": "stop"},
                                                "control-computer-playback")).pack(side="left", padx=6)
        ttk.Label(panel, textvariable=self.last_job, wraplength=680).pack(anchor="w", pady=12)
        ttk.Button(panel, text="เปิด Web UI เต็มรูปแบบ",
                   command=lambda: webbrowser.open(f"http://{(lambda h: '127.0.0.1' if h == '0.0.0.0' else h)(load_network_settings().host)}:{self.port}/")).pack(anchor="w")

        ttk.Label(settings, text="รูปแบบการทำงาน", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 7))
        ttk.Radiobutton(settings, text="ผ่านเว็บแบบเดิม", variable=self.mode,
                        value="browser", command=self.change_mode).pack(anchor="w")
        ttk.Radiobutton(settings, text="ทำงานบนคอมพิวเตอร์ต่อเนื่อง",
                        variable=self.mode, value="computer",
                        command=self.change_mode).pack(anchor="w", pady=(0, 14))
        ttk.Label(settings, text="อุปกรณ์ส่งเสียงออก", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.outputs = ttk.Combobox(settings, textvariable=self.output,
                                    state="readonly", width=63)
        self.outputs.pack(fill="x", pady=(8, 10))
        self.outputs.bind("<<ComboboxSelected>>", self.change_output)
        ttk.Label(settings, textvariable=self.broadcast, wraplength=680,
                  justify="left").pack(anchor="w", pady=(5, 8))
        link_row = ttk.Frame(settings)
        link_row.pack(fill="x")
        ttk.Button(link_row, text="เปิดหน้าผู้ฟังเสียงสด",
                   command=self.open_listener).pack(side="left", padx=(0, 8))
        ttk.Button(link_row, text="คัดลอกลิงก์สำหรับโทรศัพท์",
                   command=self.copy_listener).pack(side="left")
        ttk.Label(settings, text=(
            "การตั้งค่าบันทึกในโฟลเดอร์โปรแกรม · เมื่อปิดหน้าต่างนี้ "
            "Core และคิวเสียงยังทำงานต่อไปจนกว่าจะสั่งหยุดเซิร์ฟเวอร์"
        ), wraplength=670).pack(anchor="w", pady=(22, 0))

    def _start_service(self) -> None:
        try:
            launch_server(self.port)
        except Exception as exc:
            self.inbox.put(("error", f"เริ่ม Core ไม่สำเร็จ: {type(exc).__name__}"))

    def _command(self, route: str, body: dict[str, Any], intent: str) -> None:
        def work():
            try:
                request_body = dict(body)
                if route == "/v1/jobs":
                    saved = api(self.port, "/v1/settings/mode-voices")
                    # The native UI and browser use the same saved studio
                    # Engine/Voice/DSP profile, without a second settings store.
                    request_body.update(saved.get("modes", {}).get("studio", {}))
                result = api(self.port, route, request_body, intent)
                self.inbox.put(("result", (route, result)))
            except Exception as exc:
                self.inbox.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def submit_text(self) -> None:
        content = self.text.get("1.0", "end").strip()
        if not content:
            self.status.set("กรุณากรอกข้อความ")
            return
        self._command("/v1/jobs", {"text": content, "source": "manual", "mode": "studio"},
                      "queue-speech")

    def change_mode(self) -> None:
        self._command("/v1/runtime/mode", {"mode": self.mode.get()}, "set-runtime-mode")

    def change_output(self, _event=None) -> None:
        choice = self.output.get()
        for identifier, label in self.cached_output_list:
            if label == choice:
                self._command("/v1/runtime/output", {"output": identifier},
                              "set-runtime-output")
                break

    def open_listener(self) -> None:
        if self.listen_url:
            webbrowser.open(self.listen_url)

    def copy_listener(self) -> None:
        if self.listen_url:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.listen_url)
            self.status.set("คัดลอกลิงก์รับฟังแล้ว · ใช้ในเครือข่ายส่วนตัวเท่านั้น")

    def _poll(self) -> None:
        if self.closed:
            return
        if not self.fetching:
            self.fetching = True
            def work():
                try:
                    status = api(self.port, "/v1/runtime/state")
                    jobs = api(self.port, "/v1/jobs")
                    self.inbox.put(("state", (status, jobs)))
                except Exception as exc:
                    self.inbox.put(("error", "API ยังไม่พร้อม: " + str(exc)))
                finally:
                    self.inbox.put(("poll_complete", None))
            threading.Thread(target=work, daemon=True).start()
        self.root.after(1400, self._poll)

    def _apply(self, data: dict[str, Any], jobs: dict[str, Any]) -> None:
        mode = data.get("mode", "browser")
        self.mode.set(mode)
        self.status.set(
            f"Core {'ทำงาน' if data.get('worker_running') else 'ไม่พร้อม'} · "
            f"โหมด {mode} · เอาต์พุต {data.get('output')} · "
            f"กำลังเล่น {data.get('active_speech_id') or '-'} · "
            f"ค้าง {data.get('pending_source_messages', 0)} · "
            f"จบ {data.get('completed', 0)} · ผิดพลาด {data.get('failed', 0)}"
        )
        labels = {"live": "YouTube API", "youtube_browser": "YouTube Browser",
                  "tiktok_browser": "TikTok Extension", "discord": "Discord",
                  "discord_client": "Discord Client"}
        self.sources.set("ต้นทาง: " + " · ".join(
            f"{labels.get(k,k)}={v.get('state','idle')} ({v.get('pending',0)} รอ)"
            for k,v in data.get("sources", {}).items()
        ))
        devices = tuple((item["id"], item["label"])
                        for item in data.get("available_outputs", []))
        if devices != self.cached_output_list:
            self.cached_output_list = devices
            self.outputs.configure(values=[name for _,name in devices])
        if self.root.focus_get() is not self.outputs:
            selected = next((label for id_,label in devices
                             if id_ == data.get("output")), "Windows default output")
            self.output.set(selected)
        self.listen_url = data.get("listen_url")
        self.broadcast.set(
            f"ผู้ฟังสด {data.get('listeners',0)} เครื่อง"
            + (f" · ลิงก์ LAN พร้อมใช้งาน: {self.listen_url.split('#')[0]}"
               if self.listen_url else " · ลิงก์ LAN ยังไม่พร้อม")
        )
        entries = jobs.get("jobs", [])
        if entries:
            last = entries[-1]
            self.last_job.set(f"งานล่าสุด {last.get('speech_id','')[:8]} · "
                              f"{last.get('state','unknown')} · "
                              f"{last.get('display_text','')[:160]}")
        else:
            self.last_job.set("ยังไม่มีงานสร้างเสียง")

    def _process(self) -> None:
        if self.closed:
            return
        for _ in range(30):
            try:
                kind, payload = self.inbox.get_nowait()
            except Empty:
                break
            if kind == "state":
                self._apply(*payload)
            elif kind == "result":
                route, result = payload
                if route == "/v1/jobs":
                    self.last_job.set("ส่งงานแล้ว: " + result.get("speech_id", "")[:8])
                elif route == "/v1/runtime/replay":
                    self.last_job.set("ส่งคำสั่งเล่นซ้ำไปยัง Core แล้ว")
            elif kind == "error":
                self.status.set(str(payload))
            elif kind == "poll_complete":
                self.fetching = False
        self.root.after(120, self._process)

    def close(self) -> None:
        self.closed = True
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="VoxWeaveTTS desktop API controller")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    DesktopClient(args.port if args.port is not None else load_network_settings().port).run()


if __name__ == "__main__":
    main()
