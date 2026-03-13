from __future__ import annotations

from dataclasses import dataclass

from scrapy.http import Response

from app.crawler.normalization.urls import (
    extract_registered_domain,
    is_crawlable_document_url,
    is_http_url,
    is_internal_url,
    normalize_url,
    resolve_url,
    should_skip_href,
)


@dataclass(slots=True)
class ExtractedLink:
    source_url: str
    target_url: str
    target_normalized_url: str | None
    target_domain: str | None
    anchor_text: str
    rel_attr: str
    is_nofollow: bool
    is_internal: bool
    should_crawl: bool


def extract_links(
    response: Response,
    site_registered_domain: str,
    blocked_extensions: tuple[str, ...],
) -> list[ExtractedLink]:
    links: list[ExtractedLink] = []

    for anchor in response.css("a[href]"):
        href = anchor.attrib.get("href")
        if should_skip_href(href):
            continue

        absolute_url = resolve_url(response.url, href.strip())
        if not is_http_url(absolute_url):
            continue

        normalized_url = normalize_url(absolute_url)
        target_domain = extract_registered_domain(absolute_url)
        is_internal = is_internal_url(absolute_url, site_registered_domain=site_registered_domain)

        rel_attr = " ".join(anchor.attrib.get("rel", "").split())
        rel_tokens = {token.lower() for token in rel_attr.split() if token}
        is_nofollow = "nofollow" in rel_tokens

        anchor_text = " ".join(anchor.css("::text").getall()).split()
        compact_anchor_text = " ".join(anchor_text)

        should_crawl = (
            is_internal
            and normalized_url is not None
            and is_crawlable_document_url(normalized_url, blocked_extensions=blocked_extensions)
        )

        links.append(
            ExtractedLink(
                source_url=response.url,
                target_url=absolute_url,
                target_normalized_url=normalized_url,
                target_domain=target_domain,
                anchor_text=compact_anchor_text,
                rel_attr=rel_attr,
                is_nofollow=is_nofollow,
                is_internal=is_internal,
                should_crawl=should_crawl,
            )
        )

    return links
