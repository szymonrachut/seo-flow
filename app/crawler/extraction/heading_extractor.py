from __future__ import annotations

from scrapy.http import Response


def extract_first_h1(response: Response) -> str | None:
    first_h1 = response.css("h1::text").get()
    if first_h1 is None:
        return None
    cleaned = " ".join(first_h1.split())
    return cleaned if cleaned else None


def extract_heading_counts(response: Response) -> tuple[int, int]:
    return len(response.css("h1")), len(response.css("h2"))
