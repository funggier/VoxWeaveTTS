"""HTML workspaces are structurally separate; global config has one owner."""
from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import unittest


ROOT=Path(__file__).resolve().parents[1]
VOID={"area","base","br","col","embed","hr","img","input","link","meta",
      "param","source","track","wbr"}


class WorkspaceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack=[]
        self.errors=[]
        self.ids={}
        self.mode_counts=Counter()
        self.nav_counts=Counter()

    def handle_starttag(self,tag,attrs):
        data=dict(attrs)
        mode=next((node.get("data-mode-view") for node in reversed(self.stack)
                   if "data-mode-view" in node),None)
        if data.get("id"):
            if data["id"] in self.ids:self.errors.append("duplicate ID "+data["id"])
            self.ids[data["id"]]=(tag,mode,data)
        if "data-mode-view" in data:self.mode_counts[data["data-mode-view"]]+=1
        if "data-mode-target" in data:self.nav_counts[data["data-mode-target"]]+=1
        if tag not in VOID:self.stack.append({"tag":tag,**data})

    def handle_endtag(self,tag):
        if tag in VOID:return
        if not self.stack:
            self.errors.append("orphan end tag "+tag)
        elif self.stack[-1]["tag"]!=tag:
            self.errors.append("mismatched "+tag+" after "+self.stack[-1]["tag"])
            for i in range(len(self.stack)-1,-1,-1):
                if self.stack[i]["tag"]==tag:
                    del self.stack[i:]
                    return
        else:self.stack.pop()


class WorkspaceMarkupTests(unittest.TestCase):
    def test_mode_markup_layout_and_shared_controls(self):
        html=(ROOT/"web"/"index.html").read_text(encoding="utf-8")
        parser=WorkspaceParser()
        parser.feed(html)
        parser.close()
        self.assertEqual(parser.errors,[])
        self.assertEqual(parser.stack,[])
        expected={"studio","reader","youtube_browser","live","tiktok","discord","discord_client","queue","rules","settings"}
        self.assertEqual(set(parser.mode_counts),expected)
        self.assertEqual(set(parser.nav_counts),expected)
        self.assertTrue(all(value==1 for value in parser.mode_counts.values()))
        for name,mode in (
            ("message","studio"),("audioPreview","studio"),
            ("readerChunkPreview","reader"),("readerAudio","reader"),
            ("liveText","live"),("liveAudio","live"),
            ("youtubeBrowserText","youtube_browser"),("youtubeBrowserAudio","youtube_browser"),
            ("youtubeBrowserFeedSourceId","youtube_browser"),
            ("tiktokText","tiktok"),("tiktokAudio","tiktok"),
            ("tiktokFeedSourceId","tiktok"),
            ("discordText","discord"),("discordAudio","discord"),
            ("discordClientText","discord_client"),("discordClientAudio","discord_client"),
            ("discordClientFeedSourceId","discord_client"),
            ("queueText","queue"),("queueAudio","queue"),
            ("rule","rules"),("pron","rules"),
            ("engineSelect",None),("voiceSelect",None),
            ("globalVoiceSave",None),
            ("modelPackageInstall","settings"),
        ):
            with self.subTest(name=name):
                self.assertIn(name,parser.ids)
                self.assertEqual(parser.ids[name][1],mode)
        self.assertEqual(parser.ids["readerChunkPreview"][2].get("readonly"),None)
        self.assertIn("mode_workspace.js",html)
        self.assertIn("mode_inputs.js",html)
        self.assertIn("globalVoiceReload",parser.ids)


if __name__=="__main__":
    unittest.main()