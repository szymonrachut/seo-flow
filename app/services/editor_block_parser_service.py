from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from html import escape, unescape
from html.parser import HTMLParser


_WHITESPACE_RE = re.compile(r"\s+")
_HEADING_TAGS = {f"h{level}" for level in range(1, 7)}
_SUPPORTED_TAGS = _HEADING_TAGS | {"p", "li"}


def _normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip()


def _build_end_tag(tag: str) -> str:
    return f"</{tag}>"


def _build_content_hash(*, block_type: str, block_level: int | None, text_content: str, context_path: str | None) -> str:
    payload = {
        "block_level": block_level,
        "block_type": block_type,
        "context_path": context_path,
        "text_content": text_content,
    }
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_editor_block_content_hash(
    *,
    block_type: str,
    block_level: int | None,
    text_content: str,
    context_path: str | None,
) -> str:
    normalized_text = _normalize_text(text_content)
    normalized_context_path = _normalize_text(context_path or "") or None
    return _build_content_hash(
        block_type=block_type,
        block_level=block_level,
        text_content=normalized_text,
        context_path=normalized_context_path,
    )


def build_editor_block_html(*, block_type: str, block_level: int | None, text_content: str) -> str:
    normalized_text = _normalize_text(text_content)
    safe_text = escape(normalized_text, quote=False)
    if block_type == "heading":
        heading_level = int(block_level or 2)
        heading_level = max(1, min(6, heading_level))
        tag_name = f"h{heading_level}"
    elif block_type == "paragraph":
        tag_name = "p"
    elif block_type == "list_item":
        tag_name = "li"
    else:
        raise ValueError(f"Unsupported editor block type {block_type!r}.")
    return f"<{tag_name}>{safe_text}</{tag_name}>"


@dataclass(frozen=True)
class ParsedEditorBlock:
    block_key: str
    block_type: str
    block_level: int | None
    parent_block_key: str | None
    position_index: int
    text_content: str
    html_content: str | None
    context_path: str | None
    content_hash: str


@dataclass
class _CapturedBlock:
    tag: str
    start_tag_text: str
    html_parts: list[str]
    text_parts: list[str]
    nested_supported_depth: int = 0


class _SemanticBlockHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.captured_blocks: list[tuple[str, str, str | None]] = []
        self._current_block: _CapturedBlock | None = None

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        tag_name = tag.lower()
        start_tag_text = self.get_starttag_text() or f"<{tag_name}>"
        if self._current_block is None and tag_name in _SUPPORTED_TAGS:
            self._current_block = _CapturedBlock(
                tag=tag_name,
                start_tag_text=start_tag_text,
                html_parts=[],
                text_parts=[],
            )
            return

        if self._current_block is not None:
            if tag_name in _SUPPORTED_TAGS:
                self._current_block.nested_supported_depth += 1
            self._current_block.html_parts.append(start_tag_text)

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        current = self._current_block
        if current is None:
            return

        if tag_name == current.tag and current.nested_supported_depth == 0:
            text_content = _normalize_text("".join(current.text_parts))
            html_content = current.start_tag_text + "".join(current.html_parts) + _build_end_tag(tag_name)
            if text_content:
                self.captured_blocks.append((current.tag, text_content, html_content))
            self._current_block = None
            return

        current.html_parts.append(_build_end_tag(tag_name))
        if tag_name in _SUPPORTED_TAGS and current.nested_supported_depth > 0:
            current.nested_supported_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._current_block is None:
            return
        self._current_block.text_parts.append(data)
        self._current_block.html_parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._current_block is None:
            return
        raw_value = f"&{name};"
        self._current_block.text_parts.append(unescape(raw_value))
        self._current_block.html_parts.append(raw_value)

    def handle_charref(self, name: str) -> None:
        if self._current_block is None:
            return
        raw_value = f"&#{name};"
        self._current_block.text_parts.append(unescape(raw_value))
        self._current_block.html_parts.append(raw_value)


def parse_html_document_into_blocks(html_content: str) -> list[ParsedEditorBlock]:
    parser = _SemanticBlockHtmlParser()
    parser.feed(html_content)
    parser.close()

    blocks: list[ParsedEditorBlock] = []
    heading_stack: list[dict[str, int | str]] = []

    for position_index, (tag_name, text_content, block_html) in enumerate(parser.captured_blocks, start=1):
        block_level = int(tag_name[1]) if tag_name in _HEADING_TAGS else None
        block_type = "heading" if tag_name in _HEADING_TAGS else "paragraph" if tag_name == "p" else "list_item"
        block_prefix = tag_name.upper() if tag_name in _HEADING_TAGS else "P" if tag_name == "p" else "LI"
        block_key = f"{block_prefix}-{position_index:03d}"

        if block_level is not None:
            while heading_stack and int(heading_stack[-1]["level"]) >= block_level:
                heading_stack.pop()
            parent_block_key = str(heading_stack[-1]["block_key"]) if heading_stack else None
            context_titles = [str(item["text"]) for item in heading_stack] + [text_content]
            context_path = " > ".join(context_titles) if context_titles else None
            heading_stack.append(
                {
                    "block_key": block_key,
                    "level": block_level,
                    "text": text_content,
                }
            )
        else:
            parent_block_key = str(heading_stack[-1]["block_key"]) if heading_stack else None
            context_titles = [str(item["text"]) for item in heading_stack]
            context_path = " > ".join(context_titles) if context_titles else None

        blocks.append(
            ParsedEditorBlock(
                block_key=block_key,
                block_type=block_type,
                block_level=block_level,
                parent_block_key=parent_block_key,
                position_index=position_index,
                text_content=text_content,
                html_content=block_html,
                context_path=context_path,
                content_hash=_build_content_hash(
                    block_type=block_type,
                    block_level=block_level,
                    text_content=text_content,
                    context_path=context_path,
                ),
            )
        )

    return blocks
