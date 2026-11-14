"""End-to-end local UI smoke for YouTube Browser and TikTok Extension pairing.

Requires a development server (VOXWEAVE_TEST_BASE_URL, default port 8765) and installed
Chrome/Edge. Uses an isolated headless profile and an invalid video ID; never
navigates to a real YouTube live stream.
"""
from __future__ import annotations
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
BASE_URL = os.environ.get("VOXWEAVE_TEST_BASE_URL", "http://127.0.0.1:8765").rstrip("/")


def main():
    with urlopen(BASE_URL + "/v1/status", timeout=3) as response:
        assert response.status == 200, response.status
    with tempfile.TemporaryDirectory(prefix="vw-browser-ui-", dir=ROOT / "cache",
                                     ignore_cleanup_errors=True) as dirname:
        folder = Path(dirname)
        profile = folder / "profile"
        process = subprocess.Popen(
            [find_chromium(), "--headless=new", "--disable-gpu",
             "--no-first-run", "--no-default-browser-check",
             "--remote-debugging-address=127.0.0.1",
             "--remote-debugging-port=0", f"--user-data-dir={profile}",
             BASE_URL + "/"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ws = None
        try:
            file = profile / "DevToolsActivePort"
            until = time.monotonic() + 10
            while not file.exists() and time.monotonic() < until:
                if process.poll() is not None:
                    raise AssertionError("Chrome exited before opening the UI")
                time.sleep(.15)
            assert file.exists(), "CDP port not open"
            port = int(file.read_text(encoding="ascii").splitlines()[0])
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3) as r:
                targets = json.load(r)
            target = next(t for t in targets if t.get("type") == "page" and
                          t.get("url", "").startswith(BASE_URL))
            ws = _CDPWebSocket(target["webSocketDebuggerUrl"])
            seq = 0
            def evaluate(expr):
                nonlocal seq
                seq += 1
                ticket = seq
                ws.send(json.dumps({"id": ticket, "method": "Runtime.evaluate",
                    "params": {"expression": expr, "returnByValue": True,
                               "awaitPromise": True}}).encode())
                while True:
                    result = json.loads(ws.receive())
                    if result.get("id") == ticket:
                        if result.get("result", {}).get("exceptionDetails"):
                            raise AssertionError(result["result"]["exceptionDetails"])
                        return result.get("result", {}).get("result", {}).get("value")

            until = time.monotonic() + 12
            while time.monotonic() < until:
                if evaluate("document.readyState==='complete' && !!document.getElementById('youtubeBrowserFeedStart') && typeof VoxSourceFeed!=='undefined'"):
                    break
                time.sleep(.2)
            else:
                raise AssertionError("UI did not finish loading")
            # Configuration UI renders independently of active mode. Read-only
            # inspection only: this test must never overwrite real voice settings.
            required = (
                "liveFeedSenderPrefix", "youtubeBrowserFeedSenderPrefix",
                "liveFeedFormatread_name_at", "youtubeBrowserFeedFormatread_name_at",
                "liveFeedSeparator", "youtubeBrowserFeedSeparator",
                "tiktokBrowserFeedSenderPrefix", "tiktokBrowserFeedSeparator",
                "tiktokBrowserFeedFormatread_comments",
                "liveFeedFormatread_emojis", "youtubeBrowserFeedFormatread_emojis",
                "discordFeedFormatread_emojis", "discordClientFeedFormatread_emojis",
                "tiktokFeedFormatread_emojis", "tiktokBrowserFeedFormatread_emojis",
                "liveFeedEmojiMappings", "youtubeBrowserFeedEmojiMappings",
                "discordFeedEmojiMappings", "discordClientFeedEmojiMappings",
                "tiktokFeedEmojiMappings", "tiktokBrowserFeedEmojiMappings",
            )
            for element_id in required:
                exists = evaluate("!!document.getElementById("
                                  + json.dumps(element_id) + ")")
                assert exists, "missing source speech option: " + element_id
            # Existing live checkboxes must be physically moved into the
            # speech-format details panel, not duplicated or recreated.
            for source in ("live", "youtubeBrowser", "tiktok", "tiktokBrowser",
                           "discord", "discordClient"):
                for suffix in ("FeedAuto", "FeedReadSender"):
                    control_id=source+suffix
                    expr=("(()=>{const el=document.getElementById("
                          +json.dumps(control_id)
                          +"); return !!el && !!el.closest('.source-format-settings') "
                          "&& document.querySelectorAll('#'+el.id).length===1;})()")
                    assert evaluate(expr), "checkbox not relocated correctly: "+control_id
            for obsolete in ("tiktokBrowserFeedGiftSeparator",
                             "tiktokFeedGiftSeparator",
                             "tiktokBrowserFeedFormatread_gifts",
                             "tiktokFeedFormatread_gifts",
                             "tiktokBrowserFeedFormatread_levels",
                             "tiktokBrowserFeedFormatread_ranks",
                             "tiktokBrowserFeedFormatread_badges",
                             "tiktokBrowserFeedFormatread_gift_count",
                             "tiktokBrowserFeedFormatread_name_emojis"):
                assert not evaluate("!!document.getElementById("+json.dumps(obsolete)+")"),obsolete
            for source in ("live","youtubeBrowser","tiktok","tiktokBrowser",
                           "discord","discordClient"):
                enabled=evaluate("document.getElementById("+
                                 json.dumps(source+"FeedFormatread_emojis")+
                                 ").checked")
                assert isinstance(enabled, bool),source+" emoji reading control invalid"
            # Editing the browser DOM is safe: do not POST/save user settings.
            example=evaluate("""(()=>{
              const area=document.getElementById('liveFeedEmojiMappings');
              const toggle=document.getElementById('liveFeedFormatread_emojis');
              area.value='😂 = หัวเราะ\\nGGWP = เก่งมาก'; toggle.checked=true;
              area.dispatchEvent(new Event('input',{bubbles:true}));
              toggle.dispatchEvent(new Event('change',{bubbles:true}));
              return document.querySelector('[data-mode-view="live"] '
                +'.source-format-settings p.small:last-of-type')?.textContent;
            })()""")
            assert example and "หัวเราะ" in example and "เก่งมาก" in example, example
            for name,mode in (("tiktok","tiktok"),("tiktokBrowser","tiktok_browser")):
                example=evaluate("""(()=>{
                  const prefix=SOURCE_PREFIX,mode=SOURCE_MODE;
                  const area=document.getElementById(prefix+'FeedEmojiMappings');
                  const toggle=document.getElementById(prefix+'FeedFormatread_emojis');
                  area.value='😂 = ขำ TikTok\\nGGWP = เก่ง TikTok';
                  toggle.checked=true;
                  area.dispatchEvent(new Event('input',{bubbles:true}));
                  toggle.dispatchEvent(new Event('change',{bubbles:true}));
                  return document.querySelector('[data-mode-view="'+mode+'"] '
                    +'.source-format-settings p.small:last-of-type')?.textContent;
                })()""".replace("SOURCE_PREFIX",json.dumps(name))
                         .replace("SOURCE_MODE",json.dumps(mode)))
                assert example and "ขำ TikTok" in example and "เก่ง TikTok" in example,example
            neutral_help=evaluate("""[...document.querySelectorAll(
              '[data-mode-view="live"] .source-format-settings small'
            )].map(e=>e.textContent).find(s=>s.includes('สูงสุด 64 รายการ'))""")
            assert neutral_help and "ชื่ออีโมจิ" in neutral_help,neutral_help
            assert "Discord" not in neutral_help and "YouTube" not in neutral_help,neutral_help
            prefix=evaluate("document.getElementById('liveFeedSenderPrefix').value")
            assert isinstance(prefix,str),prefix
            for source in ("live","youtubeBrowser"):
                at=evaluate("document.getElementById("+json.dumps(source+"FeedFormatread_name_at")+
                            ").checked")
                assert isinstance(at,bool),source+" sender @ control invalid"
            assert not evaluate("!!document.getElementById('tiktokBrowserFeedFormatread_name_at')"), (
                "name @ control only belongs in YouTube modes")
            preview = evaluate(
                "document.querySelector('[data-mode-view=tiktok_browser] "
                ".source-format-settings p.small:last-of-type')?.textContent")
            assert preview and "ตัวอย่างแชท" in preview, preview
            evaluate("document.querySelector('[data-mode-target=youtube_browser]').click()")
            until = time.monotonic() + 6
            while time.monotonic() < until:
                if evaluate("modeRuntime?.guard('youtube_browser')===true"):
                    break
                time.sleep(.2)
            else:
                raise AssertionError("Browser mode ownership was not acquired")
            evaluate("document.getElementById('youtubeBrowserFeedSourceId').value=''; document.getElementById('youtubeBrowserFeedStart').click();")
            until = time.monotonic() + 4
            while time.monotonic() < until:
                status = evaluate("document.getElementById('youtubeBrowserFeedStatus').textContent")
                if "YouTube Video ID" in status:
                    break
                time.sleep(.15)
            else:
                raise AssertionError("click did not display a validation error: "+str(status))
            count = evaluate("document.getElementById('youtubeBrowserFeedProgress').children.length")
            assert count >= 2, ("no progress history", count)
            evaluate("document.getElementById('youtubeBrowserFeedSourceId').value='invalid-video'; document.getElementById('youtubeBrowserFeedStart').click();")
            until = time.monotonic() + 6
            while time.monotonic() < until:
                status = evaluate("document.getElementById('youtubeBrowserFeedStatus').textContent")
                if "เชื่อมต่อไม่สำเร็จ" in status and "youtube" in status.lower():
                    break
                time.sleep(.2)
            else:
                raise AssertionError("backend validation feedback not displayed: "+str(status))
            # TikTok Extension reuses the old internal mode ID but never opens a browser.
            # and invalid URL validation must not launch a TikTok live page.
            evaluate("document.querySelector('[data-mode-target=tiktok_browser]').click()")
            until = time.monotonic() + 6
            while time.monotonic() < until:
                if evaluate("modeRuntime?.guard('tiktok_browser')===true"):
                    break
                time.sleep(.2)
            else:
                raise AssertionError("TikTok Extension mode ownership was not acquired")
            evaluate("document.getElementById('tiktokBrowserFeedSourceId').value=''; document.getElementById('tiktokBrowserFeedStart').click();")
            until = time.monotonic() + 4
            while time.monotonic() < until:
                status = evaluate("document.getElementById('tiktokBrowserFeedStatus').textContent")
                if "TikTok Username" in status:
                    break
                time.sleep(.15)
            else:
                raise AssertionError("TikTok button did not display missing username: "+str(status))
            progress = evaluate("document.getElementById('tiktokBrowserFeedProgress').children.length")
            assert progress >= 2, ("TikTok progress timeline missing", progress)
            evaluate("document.getElementById('tiktokBrowserFeedSourceId').value='https://wrong.example.com/@user/live'; document.getElementById('tiktokBrowserFeedStart').click();")
            until = time.monotonic() + 6
            while time.monotonic() < until:
                status = evaluate("document.getElementById('tiktokBrowserFeedStatus').textContent")
                if "เชื่อมต่อไม่สำเร็จ" in status and "tiktok" in status.lower():
                    break
                time.sleep(.2)
            else:
                raise AssertionError("TikTok backend validation feedback not displayed: "+str(status))
            # Successful pairing produces a code without launching TikTok.
            evaluate("document.getElementById('tiktokBrowserFeedSourceId').value='@demo_stream'; document.getElementById('tiktokBrowserFeedStart').click();")
            until = time.monotonic() + 5
            pair = ""
            while time.monotonic() < until:
                pair = evaluate("document.getElementById('tiktokBrowserFeedPairingCode').value")
                if isinstance(pair, str) and len(pair) >= 24:
                    break
                time.sleep(.15)
            else:
                raise AssertionError("TikTok Extension did not show a pairing code")
            mode = evaluate("document.querySelector('[data-mode-target=tiktok_browser]').textContent")
            assert "Extension" in mode, mode
            evaluate("document.getElementById('tiktokBrowserFeedStop').click()")
            until = time.monotonic() + 4
            while time.monotonic() < until:
                if evaluate("document.getElementById('tiktokBrowserFeedPairingCode').value") == "":
                    break
                time.sleep(.15)
            else:
                raise AssertionError("TikTok Extension pairing code was not cleared on stop")
            # Rich Rules quick-add: exercise actual UI in isolated Chrome,
            # but never press Save (real data/filters/rules.json is untouched).
            result = evaluate("""(()=>{
              const $=id=>document.getElementById(id);
              document.querySelector('[data-mode-target="rules"]').click();
              $('rule').value='[]';
              const change=(id,value)=>{
                const node=$(id);node.value=value;
                node.dispatchEvent(new Event('change',{bubbles:true}));
              };
              change('ruleMatchMode','five_run');
              change('ruleMode','silence');
              change('ruleSilenceMs','1250');
              change('ruleDisplay','[พัก]');
              const sources=[...document.querySelectorAll(
                '#ruleSourceChoices input[type=checkbox]')];
              const check=sources.find(c=>c.value==='tiktok-live-extension');
              if(!check)throw Error('Missing TikTok Extension source filter');
              check.checked=true;
              check.dispatchEvent(new Event('change',{bubbles:true}));
              const preview=JSON.parse($('ruleQuickPreview').textContent);
              $('ruleAdd').click();
              return {rules:JSON.parse($('rule').value),preview,
                spokenHidden:$('ruleSpokenGroup').hidden,
                silenceHidden:$('ruleSilenceGroup').hidden,
                sourceCount:$('rulesTestSource').options.length,
                status:$('ruleQuickStatus').textContent};
            })()""")
            expected={"match":"555","mode":"silence","match_mode":"five_run",
                      "display":"[พัก]","silence_ms":1250,
                      "sources":["tiktok-live-extension"]}
            assert result["rules"]==[expected],result
            assert result["preview"]==expected,result
            assert result["spokenHidden"] is True and result["silenceHidden"] is False,result
            assert result["sourceCount"]==7,result
            assert "ยังไม่ได้บันทึก" in result["status"],result
            evaluate("""(()=>{
              document.getElementById('rulesTestText').value='55555';
              document.getElementById('rulesTestSource').value='tiktok-live-extension';
              document.getElementById('run').click();
            })()""")
            until=time.monotonic()+5
            while time.monotonic()<until:
                display=evaluate("document.getElementById('display').textContent")
                if display=="[พัก]":break
                time.sleep(.1)
            else:
                raise AssertionError("source-filtered rule test did not apply: "+str(display))
            assert evaluate("JSON.parse(document.getElementById('segments').textContent)[0].silence_ms")==1250
            evaluate("""(()=>{
              document.getElementById('rulesTestSource').value='youtube-live';
              document.getElementById('run').click();
            })()""")
            until=time.monotonic()+5
            while time.monotonic()<until:
                display=evaluate("document.getElementById('display').textContent")
                if display=="55555":break
                time.sleep(.1)
            else:
                raise AssertionError("source filter leaked into YouTube: "+str(display))
            print("PASS: real YouTube/TikTok UI and full Rules builder with source-filtered test")
        finally:
            if ws:
                ws.close()
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=5)
            elif process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
