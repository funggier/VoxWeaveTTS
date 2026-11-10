"""Engine-independent TXT/Markdown narrator with stable paging and chapter offsets.

The server never reads or retains source files: clients send decoded UTF-8 text.
Offsets refer to the normalized narration text, NOT byte offsets in the file.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from .processing import InputError
from .text_boundaries import natural_break_positions, thai_leading_vowel_fallbacks, unsafe_unicode_boundary, SENTENCE_ENDS, SOFT_PUNCTUATION

MAX_DOCUMENT_CHARS = 300_000
MAX_DOCUMENT_REQUEST_BYTES = 1_250_000
MAX_CHAPTERS = 500
MAX_CHUNKS = 2_500
DEFAULT_CHUNK_CHARS = 350
MIN_CHUNK_CHARS = 100
MAX_CHUNK_CHARS = 450
DEFAULT_PAGE_SIZE = 15
MAX_PAGE_SIZE = 30
CHUNKER_REVISION = "thai_boundary_v2"

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


_unsafe_unicode_boundary = unsafe_unicode_boundary

def _split_text(text: str, limit: int) -> list[tuple[int, int, str]]:
    """Use natural punctuation/whitespace, then a documented best-effort fallback.

    Hard-limit chunking of long unspaced Thai cannot promise word boundaries
    without a dictionary. Such cases are labelled in the output.
    """
    ranges: list[tuple[int, int, str]] = []
    pos = 0
    length = len(text)
    while pos < length:
        end = min(length, pos + limit)
        quality = "end_of_chapter"
        if end < length:
            local = text[pos:min(length, end + 1)]
            options = [pos + i for i in natural_break_positions(local)]
            punctuation = [i for i in options
                           if text[i-1] in SENTENCE_ENDS
                           or text[i-1] in SOFT_PUNCTUATION]
            spaces = [i for i in options if text[i-1].isspace()]
            preferred_punctuation = [i for i in punctuation
                                     if i >= pos + max(1, limit // 3)]
            preferred_space = [i for i in spaces
                               if i >= pos + max(1, limit // 2)]
            if preferred_punctuation:
                end = preferred_punctuation[-1]
                quality = "punctuation"
            elif preferred_space:
                end = preferred_space[-1]
                quality = "whitespace"
            elif options:
                # A short natural chunk is safer than splitting a Thai word.
                end = options[-1]
                quality = "whitespace" if text[end-1].isspace() else "punctuation"
            else:
                hints = thai_leading_vowel_fallbacks(
                    text, pos + max(1, (2*limit)//3), end
                )
                if hints:
                    end = hints[-1]
                    quality = "thai_preposed_vowel_hint"
                else:
                    while end > pos + 1 and unsafe_unicode_boundary(text, end):
                        end -= 1
                    quality = "unicode_only_fallback"
        if end <= pos:
            raise InputError("unable to split document")
        ranges.append((pos, end, quality))
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
        start_boundary_quality = "chapter_start"
        for relative_start, relative_end, boundary_quality in _split_text(chapter_text, chunk_chars):
            chunks.append({
                "index": len(chunks),
                "chapter_index": chapter_index,
                "chapter_title": chapter_title,
                "start": start + relative_start,
                "end": start + relative_end,
                "text": chapter_text[relative_start:relative_end],
                "boundary_quality": boundary_quality,
                "start_boundary_quality": start_boundary_quality,
            })
            start_boundary_quality = boundary_quality
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
    identifier = hashlib.sha256((CHUNKER_REVISION + "\0" + fmt + "\0" + normalized).encode("utf-8")).hexdigest()
    begin = page_index * page_size
    if begin >= len(chunks):
        raise InputError("page_index is beyond document end")
    end = min(begin + page_size, len(chunks))
    return {
        "schema_version": 1,
        "chunker_revision": CHUNKER_REVISION,
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