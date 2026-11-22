"""Standalone portable remote Desktop API client; no VoxWeaveTTS Core dependencies."""
from __future__ import annotations

import base64
import ipaddress
import json
from pathlib import Path
import re
from queue import Empty, Queue
import threading
import tkinter as tk
from tkinter import ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "client-connection.json"


def validate_client_host(host: str) -> str:
    if host == "localhost":
        return "127.0.0.1"
    try:
        address = ipaddress.IPv4Address(host)
    except (ipaddress.AddressValueError, TypeError):
        raise ValueError("Server IP must be an IPv4 address") from None
    if address.is_multicast or address.is_unspecified or address.is_reserved or str(address) == "255.255.255.255":
        raise ValueError("invalid server IP")
    return str(address)


class RemoteAPI:
    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = validate_client_host(host)
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Server port must be 1..65535")
        if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,31}", username):
            raise ValueError("invalid username")
        if not isinstance(password, str) or not 4 <= len(password) <= 128:
            raise ValueError("password must be at least 4 characters")
        self.port, self.username, self.password = port, username, password

    def request(self, path: str, body: dict[str, Any] | None = None,
                intent: str = "") -> dict[str, Any]:
        if not path.startswith("/v1/") or "?" in path or "#" in path:
            raise ValueError("invalid API path")
        credentials = base64.b64encode(
            (self.username + ":" + self.password).encode("utf-8")
        ).decode("ascii")
        headers = {"Authorization": "Basic " + credentials, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers.update({"Content-Type": "application/json",
                            "X-VoxWeaveTTS-Intent": intent})
        request = Request(f"http://{self.host}:{self.port}{path}",
                          headers=headers, data=data,
                          method="POST" if body is not None else "GET")
        try:
            with urlopen(request, timeout=6) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"API {error.code}: {json.load(error).get('error','request denied')}") from None
        except (URLError, OSError, TimeoutError):
            raise RuntimeError("Cannot connect to selected server IP/port") from None

    def get(self, path: str) -> dict[str, Any]:
        return self.request(path)

    def post(self, path: str, body: dict[str, Any], intent: str) -> dict[str, Any]:
        return self.request(path, body, intent)


def read_connection(path: Path = CONFIG_PATH) -> dict[str, Any]:
    default = {"host": "127.0.0.1", "port": 8776, "username": "voxweave"}
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        result = {**default, **{k: values[k] for k in default if k in values}}
        validate_client_host(result["host"])
        if type(result["port"]) is not int or not 1 <= result["port"] <= 65535:
            raise ValueError("port")
        return result
    except (OSError, ValueError, TypeError, KeyError):
        return default


def save_connection(host: str, port: int, username: str, path: Path = CONFIG_PATH) -> None:
    # Never store the password on the Client disk.
    validate_client_host(host)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid port")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,31}", username):
        raise ValueError("invalid username")
    path.parent.mkdir(parents=True, exist_ok=True)
    import os
    import tempfile
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".client-", suffix=".tmp", delete=False) as f:
            temporary = Path(f.name)
            json.dump({"host": host, "port": port, "username": username}, f)
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


class ClientWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VoxWeaveTTS Client — Remote API")
        self.root.geometry("750x570")
        self.root.minsize(660, 520)
        self.messages: Queue[tuple[str, Any]] = Queue()
        self.api: RemoteAPI | None = None
        self.connected = False
        self.fetching = False
        connection = read_connection()
        self.host = tk.StringVar(value=connection["host"])
        self.port = tk.StringVar(value=str(connection["port"]))
        self.username = tk.StringVar(value=connection["username"])
        self.password = tk.StringVar()
        self.mode = tk.StringVar(value="computer")
        self.output = tk.StringVar()
        self.status = tk.StringVar(value="กรอก IP / Port / Username / Password แล้วกดเชื่อมต่อ")
        self.source_info = tk.StringVar(value="")
        self.cached_outputs: tuple[tuple[str,str], ...] = ()
        self._build()
        self.root.after(100, self._process)
        self.root.after(1000, self._poll)

    def _build(self):
        panel=ttk.Frame(self.root,padding=16)
        panel.pack(fill="both",expand=True)
        ttk.Label(panel,text="VoxWeaveTTS Remote Client",font=("Segoe UI",19,"bold")).pack(anchor="w")
        fields=ttk.Frame(panel);fields.pack(fill="x",pady=10)
        for i,(name,var,width) in enumerate((
            ("Server IP",self.host,18),("Port",self.port,8),
            ("Username",self.username,18),("Password",self.password,18)
        )):
            col=ttk.Frame(fields);col.grid(row=0,column=i,padx=(0,8),sticky="ew")
            ttk.Label(col,text=name).pack(anchor="w")
            opt={"show":"*"} if name=="Password" else {}
            ttk.Entry(col,textvariable=var,width=width,**opt).pack(fill="x")
            fields.grid_columnconfigure(i,weight=1)
        ttk.Button(panel,text="เชื่อมต่อ Server",command=self.connect).pack(anchor="w")
        ttk.Label(panel,textvariable=self.status,wraplength=700).pack(anchor="w",pady=10)
        ttk.Label(panel,textvariable=self.source_info,wraplength=700).pack(anchor="w")
        ttk.Separator(panel).pack(fill="x",pady=12)
        settings=ttk.Frame(panel);settings.pack(fill="x")
        ttk.Label(settings,text="โหมดทำงาน").pack(side="left")
        self.mode_box=ttk.Combobox(settings,textvariable=self.mode,
                                  values=("computer","browser"),state="readonly",width=16)
        self.mode_box.pack(side="left",padx=8)
        ttk.Button(settings,text="เปลี่ยนโหมด",command=self.change_mode).pack(side="left")
        ttk.Label(settings,text="ส่งเสียงออกทาง").pack(side="left",padx=(15,4))
        self.outputs=ttk.Combobox(settings,textvariable=self.output,state="readonly",width=28)
        self.outputs.pack(side="left",fill="x",expand=True)
        self.outputs.bind("<<ComboboxSelected>>",self.change_output)
        ttk.Label(panel,text="ส่งข้อความเพื่อสร้างเสียงใน Server").pack(anchor="w",pady=(16,3))
        self.text=tk.Text(panel,height=5,wrap="word")
        self.text.pack(fill="both",expand=True)
        row=ttk.Frame(panel);row.pack(fill="x",pady=(12,0))
        for caption,cb in (
            ("ส่งข้อความ",self.speak),
            ("เล่นซ้ำเสียงล่าสุด",lambda:self.command("/v1/runtime/replay",{},"replay-computer-audio")),
            ("หยุดเสียง",lambda:self.command("/v1/runtime/playback",{"action":"stop"},"control-computer-playback")),
        ):
            ttk.Button(row,text=caption,command=cb).pack(side="left",padx=(0,8))
        ttk.Label(panel,text="Client เป็นเพียงตัวควบคุม ไม่ติดตั้งโมเดล/ไม่รับไฟล์ WAV · ปิดได้โดยไม่หยุด Server",
                  wraplength=700).pack(anchor="w",pady=12)

    def connect(self):
        try:
            client=RemoteAPI(self.host.get().strip(),int(self.port.get()),
                             self.username.get().strip(),self.password.get())
            save_connection(client.host,client.port,client.username)
        except (ValueError,TypeError) as err:
            self.status.set(str(err))
            return
        self.connected=False
        def work():
            try:
                state=client.get("/v1/runtime/state")
                self.messages.put(("connected",(client,state)))
            except Exception as err:
                self.messages.put(("error",str(err)))
        threading.Thread(target=work,daemon=True).start()
        self.status.set("กำลังเชื่อมต่อ ...")

    def command(self,path,body,intent):
        client=self.api
        if not client:
            self.status.set("ยังไม่ได้เชื่อมต่อ Server");return
        def work():
            try:
                if path=="/v1/jobs":
                    # Server owns its stored voice settings and TTS execution.
                    response=client.post(path,body,intent)
                else:response=client.post(path,body,intent)
                self.messages.put(("result",(path,response)))
            except Exception as exc:self.messages.put(("error",str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def speak(self):
        text=self.text.get("1.0","end").strip()
        if text:
            self.command("/v1/jobs",{"text":text,"mode":"studio","source":"manual"},"queue-speech")

    def change_mode(self):
        self.command("/v1/runtime/mode",{"mode":self.mode.get()},"set-runtime-mode")

    def change_output(self,event=None):
        target=next((ident for ident,name in self.cached_outputs if name==self.output.get()),None)
        if target:self.command("/v1/runtime/output",{"output":target},"set-runtime-output")

    def _poll(self):
        if self.connected and not self.fetching and self.api:
            self.fetching=True
            api=self.api
            def work():
                try:self.messages.put(("state",api.get("/v1/runtime/state")))
                except Exception as exc:self.messages.put(("error",str(exc)))
                finally:self.messages.put(("poll_complete",None))
            threading.Thread(target=work,daemon=True).start()
        self.root.after(1300,self._poll)

    def _show_state(self,state):
        self.mode.set(state.get("mode","computer"))
        self.status.set("เชื่อมต่อ: "+self.host.get()+":"+self.port.get()+
            " · "+state.get("audio_state","idle")+
            " · อ่านจบ "+str(state.get("completed",0))+
            " · ข้อผิดพลาด "+str(state.get("failed",0)))
        self.source_info.set("แหล่งข้อมูล: "+", ".join(
            f"{mode}:{item.get('state','idle')}"
            for mode,item in state.get("sources",{}).items()))
        devices=tuple((x["id"],x["label"]) for x in state.get("available_outputs",[]))
        if devices!=self.cached_outputs:
            self.cached_outputs=devices
            self.outputs.configure(values=[name for _,name in devices])
        if self.root.focus_get() is not self.outputs:
            self.output.set(next((name for ident,name in devices
                                  if ident==state.get("output")),""))

    def _process(self):
        for _ in range(30):
            try:kind,value=self.messages.get_nowait()
            except Empty:break
            if kind=="connected":
                self.api,state=value;self.connected=True
                self._show_state(state)
            elif kind=="state":self._show_state(value)
            elif kind=="result":
                self.status.set("Server ยืนยันคำสั่ง "+value[0])
            elif kind=="error":
                self.status.set(value)
            elif kind=="poll_complete":self.fetching=False
        self.root.after(150,self._process)

    def run(self):self.root.mainloop()


def main():
    ClientWindow().run()


if __name__=="__main__":
    main()
