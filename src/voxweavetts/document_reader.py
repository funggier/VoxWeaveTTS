"""Engine-independent TXT/Markdown narrator with stable paging and chapter offsets.

The server never reads or retains source files: clients send decoded UTF-8 text.
Offsets refer to the normalized narration text, NOT byte offsets in the file.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from .processing import InputError

MAX_DOCUMENT_CHARS = 300_000
MAX_DOCUMENT_REQUEST_BYTES = 1_250_000
MAX_CHAPTERS = 500
MAX_CHUNKS = 2_500
DEFAULT_CHUNK_CHARS = 350
MIN_CHUNK_CHARS = 100
MAX_CHUNK_CHARS = 450
DEFAULT_PAGE_SIZE = 15
MAX_PAGE_SIZE = 30

_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_TXT_HEADING = re.compile(
    r"^(?:บทที่|ตอนที่)\s*[0-9๐-๙]+(?:\s|[.:：\-]|$)"
    r"|^chapter\s+[0-9]+(?:\s|[.:：\-]|$)", re.IGNORECASE
)
_FENCE = re.compile(r"^\s{0,3}(" + re.escape(chr(96)) + r"{3,}|~{3,})")
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_INLINE_CODE = re.compile(r"(" + re.escape(chr(96)) + r"+)[^" + chr(96) + r"\n]*?\1")
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_HTML_COMMENT = re.compile(r"<!--.*?-->")
_AUTO_LINK = re.compile(r"<(?:https?://|mailto:)[^>]+>")
_MD_RULE = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
_MD_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_BREAKS = set("\n.!?。！？;；ฯ")


def _clean_line(line: str, fmt: str) -> str:
    line = line.strip()
    if not line:
        return ""
    if fmt == "md":
        if _MD_RULE.fullmatch(line) or _MD_TABLE_RULE.fullmatch(line):
            return ""
        line = _MD_HEADING.sub(r"\1", line)
        line = re.sub(r"^\s{0,3}(?:>\s*)+", "", line)
        line = re.sub(r"^\s{0,3}(?:[-+*]\s+|\d+[.)]\s+)", "", line)
        line = _HTML_COMMENT.sub("", line)
        line = _MARKDOWN_IMAGE.sub("", line)
        line = _MARKDOWN_LINK.sub(r"\1", line)
        line = _MARKDOWN_INLINE_CODE.sub("", line)
        line = _AUTO_LINK.sub("", line)
        line = _HTML_TAG.sub("", line)
        line = line.replace("**", "").replace("__", "").replace("~~", "")
        line = re.sub(r"(?<!\w)[*_](?=\S)|(?<=\S)[*_](?!\w)", "", line)
    return re.sub(r"[ \t\u00a0]+", " ", line).strip()


def _chapters(raw: str, fmt: str) -> list[tuple[str, str]]:
    """Split at headings and ignore fenced code, HTML code and YAML frontmatter."""
    result: list[tuple[str, str]] = []
    heading = ""
    lines: list[str] = []
    fence_marker: str | None = None
    source_lines = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").split("\n")
    in_yaml = fmt == "md" and bool(source_lines) and source_lines[0].strip() == "---"
    in_html: str | None = None

    def finish() -> None:
        nonlocal lines
        if lines:
            text = "\n".join(lines).strip()
            if text:
                result.append((heading or "เนื้อหา", text))
        lines = []

    for index, raw_line in enumerate(source_lines):
        line = raw_line.strip()
        if fmt == "md" and in_yaml:
            if index > 0 and line in ("---", "..."):
                in_yaml = False
            continue
        if fmt == "md":
            if in_html:
                if re.search(r"</" + in_html + r"\s*>", line, flags=re.I):
                    in_html = None
                continue
            open_tag = re.match(r"^\s*<(script|style|pre)\b", raw_line, flags=re.I)
            if open_tag:
                tag = open_tag.group(1)
                if not re.search(r"</" + tag + r"\s*>", raw_line, flags=re.I):
                    in_html = tag
                continue
            fence = _FENCE.match(raw_line)
            if fence:
                marker = fence.group(1)
                if fence_marker is None:
                    fence_marker = marker
                elif marker[0] == fence_marker[0] and len(marker) >= len(fence_marker):
                    fence_marker = None
                continue
            if fence_marker is not None:
                continue
        heading_match = _MD_HEADING.match(raw_line) if fmt == "md" else None
        if fmt == "md" and heading_match:
            title = _clean_line(heading_match.group(1), fmt)
        elif fmt == "txt" and _TXT_HEADING.match(line) and len(line) <= 140:
            title = line
        else:
            title = ""
        if title:
            finish()
            heading = title[:140]
            lines.append(title)
            continue
        cleaned = _clean_line(raw_line, fmt)
        if cleaned:
            lines.append(cleaned)
    finish()
    if not result:
        raise InputError("document has no narratable text")
    if len(result) > MAX_CHAPTERS:
        raise InputError(f"document exceeds {MAX_CHAPTERS} chapters")
    return result


def _unsafe_unicode_boundary(text: str, index: int) -> bool:
    """Avoid splitting common Thai combining and emoji composition sequences."""
    if index <= 0 or index >= len(text):
        return False
    previous, following = text[index-1], text[index]
    code = ord(following)
    if (unicodedata.combining(following)
        or unicodedata.category(following) in ("Mn", "Mc", "Me")
        or following == "\u200d" or previous == "\u200d"
        or 0xFE00 <= code <= 0xFE0F
        or 0xE0100 <= code <= 0xE01EF
        or 0x1F3FB <= code <= 0x1F3FF):
        return True
    # Don't split the two regional-indicator codepoints of a country flag.
    if 0x1F1E6 <= ord(previous) <= 0x1F1FF and 0x1F1E6 <= code <= 0x1F1FF:
        run = 0
        cursor = index-1
        while cursor >= 0 and 0x1F1E6 <= ord(text[cursor]) <= 0x1F1FF:
            run += 1
            cursor -= 1
        return run % 2 == 1
    return False


def _split_text(text: str, limit: int) -> list[tuple[int, int]]:
    """Partition a cleaned chapter while preserving Unicode sequence boundaries."""
    ranges = []
    pos = 0
    while pos < len(text):
        end = min(len(text), pos + limit)
        if end < len(text):
            sentence = max(
                (i + 1 for i in range(pos, end) if text[i] in _BREAKS), default=0
            )
            if sentence > pos + limit // 3:
                end = sentence
            else:
                whitespace = max(
                    (i + 1 for i in range(pos, end) if text[i].isspace()), default=0
                )
                if whitespace > pos + limit // 2:
                    end = whitespace
            while end > pos + 1 and _unsafe_unicode_boundary(text, end):
                end -= 1
        if end <= pos:
            raise InputError("unable to split document")
        ranges.append((pos, end))
        pos = end
    return ranges


def prepare_document(
    text: Any, fmt: Any, *, title: Any = "",
    chunk_chars: Any = DEFAULT_CHUNK_CHARS,
    page_index: Any = 0, page_size: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    if fmt not in ("txt", "md"):
        raise InputError("document format must be txt or md")
    if not isinstance(text, str) or not text:
        raise InputError("document text must be a non-empty UTF-8 string")
    if len(text) > MAX_DOCUMENT_CHARS:
        raise InputError(f"document exceeds {MAX_DOCUMENT_CHARS} characters")
    if "\x00" in text:
        raise InputError("document contains binary data")
    if not isinstance(title, str) or len(title) > 160:
        raise InputError("document title must be at most 160 characters")
    for key, value, low, high in (
        ("chunk_chars", chunk_chars, MIN_CHUNK_CHARS, MAX_CHUNK_CHARS),
        ("page_size", page_size, 1, MAX_PAGE_SIZE),
    ):
        if type(value) is not int or not low <= value <= high:
            raise InputError(f"{key} must be {low}–{high}")
    if type(page_index) is not int or page_index < 0:
        raise InputError("page_index must be a non-negative integer")

    chapters = _chapters(text, fmt)
    normalized_parts: list[str] = []
    summaries: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    offset = 0
    for chapter_index, (chapter_title, chapter_text) in enumerate(chapters):
        if normalized_parts:
            normalized_parts.append("\n")
            offset += 1
        start = offset
        normalized_parts.append(chapter_text)
        chunk_begin = len(chunks)
        for relative_start, relative_end in _split_text(chapter_text, chunk_chars):
            chunks.append({
                "index": len(chunks),
                "chapter_index": chapter_index,
                "chapter_title": chapter_title,
                "start": start + relative_start,
                "end": start + relative_end,
                "text": chapter_text[relative_start:relative_end],
            })
            if len(chunks) > MAX_CHUNKS:
                raise InputError(f"document exceeds {MAX_CHUNKS} narration chunks")
        offset += len(chapter_text)
        summaries.append({
            "index": chapter_index,
            "title": chapter_title,
            "start": start,
            "end": offset,
            "chunk_start": chunk_begin,
            "chunk_end": len(chunks),
        })
    normalized = "".join(normalized_parts)
    identifier = hashlib.sha256((fmt + "\0" + normalized).encode("utf-8")).hexdigest()
    begin = page_index * page_size
    if begin >= len(chunks):
        raise InputError("page_index is beyond document end")
    end = min(begin + page_size, len(chunks))
    return {
        "schema_version": 1,
        "document_id": identifier,
        "title": title,
        "format": fmt,
        "normalized_characters": len(normalized),
        "chapter_total": len(summaries),
        "chunk_total": len(chunks),
        "chunk_chars": chunk_chars,
        "page_index": page_index,
        "page_size": page_size,
        "has_next": end < len(chunks),
        "chapters": summaries,
        "chunks": chunks[begin:end],
        "offset_basis": "normalized_narration_text",
    }