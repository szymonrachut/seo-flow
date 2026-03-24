from __future__ import annotations

from dataclasses import dataclass

from scrapy.http import Response

from app.crawler.extraction.content_extractor import extract_content_metrics, extract_simplified_visible_text
from app.crawler.extraction.heading_extractor import extract_first_h1, extract_heading_counts
from app.crawler.extraction.links_extractor import ExtractedLink, extract_links
from app.crawler.extraction.media_extractor import extract_image_metrics
from app.crawler.extraction.meta_extractor import (
    extract_canonical_url,
    extract_meta_description,
    extract_robots_meta,
    extract_title,
    extract_x_robots_tag,
)
from app.crawler.extraction.schema_extractor import extract_schema_summary


@dataclass(slots=True)
class ExtractedPageData:
    title: str | None
    title_length: int | None
    meta_description: str | None
    meta_description_length: int | None
    h1: str | None
    h1_count: int | None
    h2_count: int | None
    canonical_url: str | None
    robots_meta: str | None
    x_robots_tag: str | None
    word_count: int | None
    content_text_hash: str | None
    visible_text: str
    images_count: int | None
    images_missing_alt_count: int | None
    schema_present: bool
    schema_count: int
    schema_types_json: list[str]
    links: list[ExtractedLink]


def extract_page_data(
    response: Response,
    *,
    site_registered_domain: str,
    blocked_extensions: tuple[str, ...],
) -> ExtractedPageData:
    title = extract_title(response)
    meta_description = extract_meta_description(response)
    h1 = extract_first_h1(response)
    h1_count, h2_count = extract_heading_counts(response)
    canonical_url = extract_canonical_url(response)
    robots_meta = extract_robots_meta(response)
    x_robots_tag = extract_x_robots_tag(response)
    visible_text = extract_simplified_visible_text(response)
    word_count, content_text_hash = extract_content_metrics(response, visible_text=visible_text)
    images_count, images_missing_alt_count = extract_image_metrics(response)
    schema_summary = extract_schema_summary(response)
    links = extract_links(
        response=response,
        site_registered_domain=site_registered_domain,
        blocked_extensions=blocked_extensions,
    )

    return ExtractedPageData(
        title=title,
        title_length=len(title) if title else None,
        meta_description=meta_description,
        meta_description_length=len(meta_description) if meta_description else None,
        h1=h1,
        h1_count=h1_count,
        h2_count=h2_count,
        canonical_url=canonical_url,
        robots_meta=robots_meta,
        x_robots_tag=x_robots_tag,
        word_count=word_count,
        content_text_hash=content_text_hash,
        visible_text=visible_text,
        images_count=images_count,
        images_missing_alt_count=images_missing_alt_count,
        schema_present=schema_summary.present,
        schema_count=schema_summary.count,
        schema_types_json=schema_summary.types,
        links=links,
    )
