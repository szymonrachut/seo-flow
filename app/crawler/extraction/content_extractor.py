from __future__ import annotations

import hashlib

from scrapy.http import Response


def extract_content_metrics(response: Response, *, visible_text: str | None = None) -> tuple[int, str | None]:
    simplified_text = visible_text if visible_text is not None else extract_simplified_visible_text(response)
    if not simplified_text:
        return 0, None

    return len(simplified_text.split()), hashlib.sha256(simplified_text.encode("utf-8")).hexdigest()


def extract_html_size_bytes(response: Response) -> int:
    return len(response.body or b"")


def extract_simplified_visible_text(response: Response) -> str:
    nodes = response.xpath(
        "//body//text()[normalize-space() and "
        "not(ancestor::script) and "
        "not(ancestor::style) and "
        "not(ancestor::noscript)]"
    ).getall()
    return " ".join(" ".join(node.split()) for node in nodes if node and node.strip()).strip()
