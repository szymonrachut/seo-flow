from __future__ import annotations

from scrapy.http import Response

from app.crawler.normalization.urls import normalize_url


def extract_title(response: Response) -> str | None:
    return _clean_text(response.css("title::text").get())


def extract_meta_description(response: Response) -> str | None:
    content = response.xpath(
        "//meta[translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='description']/@content"
    ).get()
    return _clean_text(content)


def extract_canonical_url(response: Response) -> str | None:
    canonical_href = response.xpath(
        "//link[contains(concat(' ', normalize-space(translate(@rel, "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')), ' '), ' canonical ')]/@href"
    ).get()
    if canonical_href is None:
        return None

    absolute_url = response.urljoin(canonical_href.strip())
    normalized = normalize_url(absolute_url)
    if normalized:
        return normalized
    cleaned = absolute_url.strip()
    return cleaned if cleaned else None


def extract_robots_meta(response: Response) -> str | None:
    content = response.xpath(
        "//meta[translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='robots']/@content"
    ).get()
    return _clean_text(content)


def extract_x_robots_tag(response: Response) -> str | None:
    values = response.headers.getlist("X-Robots-Tag") or response.headers.getlist(b"X-Robots-Tag")
    if not values:
        return None

    decoded_values = [value.decode("latin-1") if isinstance(value, bytes) else str(value) for value in values]
    return _clean_text(", ".join(decoded_values))


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned if cleaned else None
