"""Real Chrome DOM regression for TikTok extension rank/comment separation.

Uses only a local HTML fixture, an isolated temporary Chrome profile, and a
stubbed extension transport. No TikTok network, login, or user Chrome tabs.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from voxweavetts.youtube_browser import _CDPWebSocket, find_chromium

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / "extensions" / "tiktok-live-connector" / "content.js"
FIXTURE = """<!doctype html><meta charset="utf-8">
<style>.header,.body{display:block}.badge{display:inline-block}</style>
<div class="DivChatMessageList" id="list">
 <div class="DivChatMessageItem" data-id="old">
   <div class="header"><span class="SpanUserName">Old</span></div>
   <div class="body"><span class="SpanChatMessageText">ข้อความเดิม</span></div>
 </div>
</div>"""


def evaluate(ws, seq, js):
    ws.send(json.dumps({
        "id": seq, "method": "Runtime.evaluate",
        "params": {"expression": js, "returnByValue": True, "awaitPromise": True},
    }, ensure_ascii=False).encode("utf-8"))
    for _ in range(100):
        response = json.loads(ws.receive())
        if response.get("id") != seq:
            continue
        entry = response.get("result", {})
        if entry.get("exceptionDetails"):
            raise RuntimeError("Chrome JS exception: " + repr(entry["exceptionDetails"])[:800])
        return entry.get("result", {}).get("value")
    raise RuntimeError("Chrome CDP did not return a matching response")


def main():
    (ROOT / "cache").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vw-rank-dom-", dir=ROOT/"cache",
                                     ignore_cleanup_errors=True) as tmp:
        base=Path(tmp)
        profile=base/"profile"
        fixture=base/"fixture.html"
        fixture.write_text(FIXTURE,encoding="utf-8")
        command=[
            find_chromium(), "--headless=new", "--disable-gpu",
            "--no-first-run", "--no-default-browser-check",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
            f"--user-data-dir={profile}", fixture.as_uri(),
        ]
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        ws=None
        try:
            port_file=profile/"DevToolsActivePort"
            deadline=time.monotonic()+9
            while not port_file.exists() and time.monotonic()<deadline:
                if process.poll() is not None:
                    raise RuntimeError("Isolated Chrome ended before startup")
                time.sleep(.1)
            if not port_file.exists():
                raise RuntimeError("Isolated Chrome CDP port not ready")
            port=int(port_file.read_text(encoding="utf-8").splitlines()[0])
            with urlopen(f"http://127.0.0.1:{port}/json/list",timeout=2) as resp:
                tabs=json.load(resp)
            target=next(t for t in tabs if t.get("type")=="page"
                        and t.get("url","").startswith("file:"))
            ws=_CDPWebSocket(target["webSocketDebuggerUrl"])
            # A file: target can appear before the initial navigation ends.
            for step in range(30):
                if evaluate(ws,10+step,
                    'document.readyState==="complete" && !!document.getElementById("list")'):
                    break
                time.sleep(.1)
            else:
                raise RuntimeError("Local Chrome fixture DOM did not load")
            reader=READER.read_text(encoding="utf-8")
            setup="""(()=>{
              window.__vw_messages=[];
              window.__vw_listener=null;
              const chrome={runtime:{
                id:"abcdefghijklmnopabcdefghijklmnop",
                onMessage:{addListener(fn){window.__vw_listener=fn;}},
                sendMessage(message,done){
                  window.__vw_messages.push(message);
                  if(done)done({ok:true});
                }
              }};
              READER_BODY
              window.__vw_listener({kind:"vw-start"});
              return window.__vw_messages.length;
            })()""".replace("READER_BODY",reader)
            assert evaluate(ws,51,setup)>=1
            assert evaluate(ws,52,"window.__vw_messages.at(-1).items.length")==0
            append="""(()=>{
              const list=document.getElementById("list");
              list.insertAdjacentHTML("beforeend", `
                <div class="DivChatMessageItem" data-id="rank-comment">
                 <div class="header">
                   <span class="SpanUserName">maitreewongthawik</span>
                   <span class="BadgeRank" data-e2e="rank-badge">No. 2</span>
                 </div>
                 <div class="body"><span class="SpanChatMessageText">Trum up Trum up!! 😮</span></div>
                </div>
                <div class="DivChatMessageItem" data-id="plain-comment">
                 <div class="header"><span class="SpanUserName">Riskies</span></div>
                 <div class="body"><span class="SpanChatMessageText">No. 2 เป็นชื่อเพลงที่ชอบ</span></div>
                </div>
                <div class="DivChatMessageItem" data-id="rank-generic">
                 <div class="header">
                   <span class="SpanUserName">PorchJoy Kabsee</span>
                   <span class="BadgeRank" data-e2e="rank-badge">No. 2</span>
                 </div>
                 <div class="body"><span>แพ้ใจ</span></div>
                </div>
                <div class="DivSystemMessage" data-id="gift-system">
                   <span class="SpanUserName">น้องเอม</span>
                   <span>sent Heart Me 🧸 × 1</span>
                </div>
                <div class="DivSystemMessage" data-id="gift-system-x">
                   <span class="SpanUserName">ผู้ชม Gift</span>
                   <span>sent Rose x 4</span>
                </div>
                <div class="DivChatMessageItem" data-id="gift-generic">
                   <span class="SpanUserName">Sprite Pam</span>
                   <span>sent Go Popular 🎉 × 2</span>
                </div>
                <div class="DivChatMessageItem" data-id="not-gift">
                   <span class="SpanUserName">Guest</span>
                   <span class="SpanChatMessageText">sent Heart Me × 3</span>
                </div>
                <div class="DivChatMessageItem" data-id="emoji-chat">
                   <span class="SpanUserName">EmojiViewer</span>
                   <span class="SpanChatMessageText">สวัสดี <img alt="😂">
                     <img alt="GGWP"> และ <img alt="❤️"></span>
                </div>
              `);
              return [...list.querySelectorAll(".DivChatMessageItem")].map(x=>x.innerText);
            })()"""
            native_lines=evaluate(ws,53,append)
            time.sleep(.4)
            batches=evaluate(ws,54,"window.__vw_messages.flatMap(m=>m.items)")
            messages={x["id"]:x for x in batches}
            assert len(messages)==5,(native_lines,batches)
            assert messages["rank-comment"]["text"]=="Trum up Trum up!! 😮",messages
            assert messages["rank-comment"]["rank"]=="2",messages
            assert messages["plain-comment"]["text"]=="No. 2 เป็นชื่อเพลงที่ชอบ",messages
            assert messages["rank-generic"]["text"]=="แพ้ใจ",messages
            assert messages["rank-generic"]["rank"]=="2",messages
            assert messages["not-gift"]["kind"]=="comment",messages
            assert messages["not-gift"]["text"]=="sent Heart Me × 3",messages
            assert messages["emoji-chat"]["kind"]=="comment",messages
            assert messages["emoji-chat"]["text"]=="สวัสดี 😂 GGWP และ ❤️",messages
            assert not any(key in messages for key in
                ("gift-system","gift-system-x","gift-generic")),messages
            print("PASS: Chrome DOM isolates chat, preserves emoji-image alt "
                  "labels and named emotes, excludes gifts")
        finally:
            if ws:
                try: ws.close()
                except Exception: pass
            if os.name=="nt":
                subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
            elif process.poll() is None:process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill()


if __name__=="__main__":
    main()
