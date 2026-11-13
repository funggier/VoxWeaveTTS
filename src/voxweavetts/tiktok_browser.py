"""Experimental TikTok LIVE browser DOM comment reader.

Uses the existing isolated, local Chrome CDP adapter; only visible text chat
elements are extracted. The live player remains mounted and is muted rather
than paused, because TikTok may couple chat with its live player. No unofficial API,
credential injection, CAPTCHA bypass, or private endpoint requests.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from .processing import InputError
from .youtube_browser import YouTubeBrowserAdapter


USERNAME = re.compile(r"^[A-Za-z0-9_.]{2,24}$")

# DOM shape is not a published contract; use narrow, visible-chat selectors.
# The DivChatMessageList class is documented in public chat-only CSS examples.
# Critically, do not return gift/follow/join notification rows.
TIKTOK_CHAT_SCRIPT = r"""(() => {
  // TikTok has no official chat-only URL. Do not hide parent containers
  // or pause the player: that can prevent the chat UI from mounting.
  // Mute locally instead; video data may still be loaded by TikTok.
  for (const video of document.querySelectorAll("video")) video.muted = true;
  const loginPrompt = [...document.querySelectorAll("button")].some(button =>
    /^(log\s*in|login|sign\s*in)$/i.test((button.innerText || "").trim())
  );
  // The platform can render "Comments off" in the chat composer even
  // when the message list element is present. Report the visible state, do
  // not pretend the DOM reader is connected or try to change moderation.
  const disabledComment = [...document.querySelectorAll(
    'input, textarea, [role="textbox"], [contenteditable], [placeholder],'
    + ' [data-e2e="room-chat-input-field"]'
  )].some(node => /^(comments\s+off|comments\s+disabled)$/i.test(
    (node.getAttribute("placeholder") || node.getAttribute("aria-label")
     || node.textContent || "").trim()
  ));
  const visibleStatus = (document.body?.innerText || "").split(/\r?\n/)
    .some(line => /^comments\s+(off|disabled)$/i.test(line.trim()));
  if (disabledComment || visibleStatus)
    return {ready: false,
            status: loginPrompt ? "comments_off_login_prompt" : "comments_off",
            items: []};
  // Older TikTok pages expose DivChatMessageList; newer LIVE pages (observed
  // in Nov 2026) have a live-chat-container with an overflow-y-scroll pane.
  const list = document.querySelector(
    '[class*="DivChatMessageList"], [data-e2e="live-chat-message-list"]'
  ) || document.querySelector(
    '[data-e2e="live-chat-container"] [class*="overflow-y-scroll"]'
  );
  if (!list)
    return {ready: false, status: loginPrompt ? "login_prompt" : "waiting_chat_dom",
            items: []};
  const candidates = [...list.querySelectorAll(
    '[data-e2e="chat-message"], [data-e2e="live-chat-message"],'
    + ' [data-e2e="room-chat-message"],'
    + ' div[class*="DivChatMessage"]'
  )].filter(node => node !== list
    && !/DivChatMessageList|DivChatMessageText/.test(String(node.className))
    && !node.matches('[data-e2e*="gift"], [data-e2e*="follow"], [data-e2e*="join"]'));
  const rows = candidates.filter(node =>
    !candidates.some(parent => parent !== node && parent.contains(node))
  ).slice(-100);
  const items = [];
  for (const node of rows) {
    if (node.querySelector('[data-e2e*="gift"], [data-e2e*="follow"]')) continue;
    const textNode = node.querySelector(
      '[data-e2e="message-text"], [data-e2e="comment-content"],'
      + '[data-e2e="chat-message-text"], [class*="SpanChatMessageText"],'
      + '[class*="DivChatMessageText"], [class*="SpanMessageText"]'
    );
    if (!textNode) continue; // Strictly comment text, not chat system events.
    const text = (textNode.textContent || "").trim();
    if (!text) continue;
    const nameNode = node.querySelector(
      '[data-e2e="message-owner-name"], [data-e2e="chat-message-name"],'
      + '[class*="SpanUserName"], a[href^="/@"]'
    );
    const author = (nameNode?.textContent || "").trim();
    let id = node.getAttribute("data-id") || node.getAttribute("data-message-id")
      || node.getAttribute("data-vwtts-id");
    if (!id) {
      window.__vwttsChatSequence = (window.__vwttsChatSequence || 0) + 1;
      window.__vwttsPageId = window.__vwttsPageId
        || (Date.now() + "-" + Math.random().toString(36).slice(2));
      id = "tiktok-" + window.__vwttsPageId + "-" + window.__vwttsChatSequence;
      node.setAttribute("data-vwtts-id", id);
    }
    items.push({id, author, text});
  }
  return {ready: true, items};
})()"""


def username_from_input(source: object) -> str:
    """Only accept explicit usernames or canonical TikTok LIVE URLs."""
    if not isinstance(source, str) or len(source) > 240:
        raise InputError("TikTok LIVE username or URL required")
    value = source.strip()
    if value.startswith("@"):
        value = value[1:]
    if USERNAME.fullmatch(value) and not value.startswith(".") and not value.endswith("."):
        return value
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise InputError("invalid TikTok LIVE URL") from None
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise InputError("use a TikTok https LIVE URL")
    try:
        host, port = parsed.hostname, parsed.port
    except ValueError:
        raise InputError("invalid TikTok LIVE URL") from None
    if host not in ("www.tiktok.com", "tiktok.com") or port is not None:
        raise InputError("only canonical tiktok.com LIVE URLs are supported")
    parts = parsed.path.split("/")
    if len(parts) != 3 or not parts[1].startswith("@") or parts[2] != "live":
        raise InputError("use a TikTok LIVE URL like https://www.tiktok.com/@user/live")
    name = parts[1][1:]
    if not USERNAME.fullmatch(name) or name.startswith(".") or name.endswith("."):
        raise InputError("invalid TikTok username")
    return name


class TikTokBrowserAdapter(YouTubeBrowserAdapter):
    """Capture visible text comments only; does not scrape backstage APIs."""

    profile_name = "tiktok-chat"
    page_label = "TikTok"
    chat_script = TIKTOK_CHAT_SCRIPT

    @staticmethod
    def parse_source(source: str) -> str:
        return username_from_input(source)

    @staticmethod
    def build_chat_url(identifier: str) -> str:
        return f"https://www.tiktok.com/@{identifier}/live"

    def target_matches(self, target: dict) -> bool:
        u = urlsplit(target.get("url", ""))
        return (target.get("type") == "page"
                and u.scheme == "https" and u.hostname in ("www.tiktok.com", "tiktok.com")
                and u.path.lower() == f"/@{self.video_id.lower()}/live")
