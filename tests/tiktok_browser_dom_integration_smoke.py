"""Opt-in integration smoke: launch isolated headless Chrome against a local chat fixture.

Run: python tests/tiktok_browser_dom_integration_smoke.py
No TikTok network access or user browser profile is used.
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
from voxweavetts.tiktok_browser import TIKTOK_CHAT_SCRIPT


def main():
    with tempfile.TemporaryDirectory(prefix="voxweave-cdp-", dir=Path(__file__).resolve().parents[1] / "cache", ignore_cleanup_errors=True) as directory:
        base = Path(directory)
        profile = base / "profile"
        html = base / "fixture.html"
        html.write_text(
            '<html><head></head><body><video autoplay></video>'
            '<div class="DivChatMessageList">'
            '<div data-e2e="chat-message" data-id="msg-a">'
            '<a href="/@tester" class="SpanUserName">Tester</a>'
            '<span class="SpanChatMessageText">สวัสดีครับ</span></div>'
            '<div data-e2e="gift" data-id="gift-a">Gift Notification</div>'
            '</div></body></html>', encoding="utf-8")
        args = [find_chromium(), "--headless=new", "--disable-gpu",
                "--remote-debugging-address=127.0.0.1",
                "--remote-debugging-port=0", f"--user-data-dir={profile}",
                "--no-first-run", "--no-default-browser-check", html.as_uri()]
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            portfile = profile / "DevToolsActivePort"
            deadline = time.monotonic() + 8
            while not portfile.exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Chrome stopped before CDP port available")
                time.sleep(0.1)
            if not portfile.exists():
                raise RuntimeError("Chrome debugging endpoint did not start")
            port = int(portfile.read_text(encoding="ascii").splitlines()[0])
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as resp:
                targets = json.load(resp)
            target = next(t for t in targets if t.get("type") == "page"
                          and t.get("url", "").startswith("file:"))
            ws = _CDPWebSocket(target["webSocketDebuggerUrl"])
            try:
                for attempt in range(25):
                    ws.send(json.dumps({"id": attempt + 1, "method": "Runtime.evaluate",
                                        "params": {"expression": TIKTOK_CHAT_SCRIPT,
                                                   "returnByValue": True}}).encode())
                    while True:
                        data = json.loads(ws.receive())
                        if data.get("id") == attempt + 1:
                            break
                    result = data["result"]["result"].get("value", {})
                    if result.get("ready"):
                        break
                    time.sleep(0.2)
                assert result["ready"] is True, result
                assert result["items"][0]["text"] == "สวัสดีครับ", result
                assert result["items"][0]["author"] == "Tester", result
                assert len(result["items"]) == 1, result
                # A live page can show "Comments off" even while the
                # message list exists: status must not be "ready".
                def evaluate(call_id, expression):
                    ws.send(json.dumps({"id": call_id, "method": "Runtime.evaluate",
                                        "params": {"expression": expression,
                                                   "returnByValue": True}}).encode())
                    while True:
                        frame = json.loads(ws.receive())
                        if frame.get("id") == call_id:
                            return frame["result"]["result"].get("value", {})

                evaluate(101, """document.body.insertAdjacentHTML(
                    "beforeend", '<div id="fixture-off">Comments off</div>'
                )""")
                off = evaluate(102, TIKTOK_CHAT_SCRIPT)
                assert off["ready"] is False and off["status"] == "comments_off", off
                evaluate(103, "document.getElementById('fixture-off').remove()")
                on = evaluate(104, TIKTOK_CHAT_SCRIPT)
                assert on["ready"] is True, on
                evaluate(105, """document.body.insertAdjacentHTML(
                    "beforeend", '<input id="fixture-off" placeholder="Comments off">'
                )""")
                off_input = evaluate(106, TIKTOK_CHAT_SCRIPT)
                assert off_input["status"] == "comments_off", off_input
                evaluate(107, """document.body.insertAdjacentHTML(
                    "beforeend", '<button id="fixture-login">Log in</button>'
                )""")
                login = evaluate(108, TIKTOK_CHAT_SCRIPT)
                assert login["status"] == "comments_off_login_prompt", login
                evaluate(109, """document.querySelector(".DivChatMessageList").remove();
                    document.getElementById('fixture-off').remove();
                    document.getElementById('fixture-login').remove();
                    document.body.insertAdjacentHTML(
                      "beforeend",
                      '<div data-e2e="live-chat-container"><div class="overflow-y-scroll">'
                      + '<div data-e2e="chat-message" data-id="modern1">'
                      + '<span class="SpanUserName">Viewer</span>'
                      + '<span class="SpanChatMessageText">สวัสดีจาก TikTok ใหม่</span>'
                      + '</div></div><div data-e2e="room-chat-input-field" '
                      + 'contenteditable="plaintext-only" placeholder="Say something nice"></div></div>'
                    )""")
                modern = evaluate(110, TIKTOK_CHAT_SCRIPT)
                assert modern["ready"] is True, modern
                assert len(modern["items"]) == 1, modern
                assert modern["items"][0]["text"] == "สวัสดีจาก TikTok ใหม่", modern

            finally:
                ws.close()
            print("PASS: isolated Chrome CDP, TikTok-style comment DOM extraction (no gifts)")
        finally:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=4)
            elif process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            time.sleep(0.4)


if __name__ == "__main__":
    main()