from __future__ import annotations

from datetime import datetime
from typing import TypedDict

import scrapy


class PagePayload(TypedDict):
    crawl_job_id: int
    url: str
    normalized_url: str
    final_url: str | None
    status_code: int | None
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
    content_type: str | None
    word_count: int | None
    content_text_hash: str | None
    images_count: int | None
    images_missing_alt_count: int | None
    html_size_bytes: int | None
    was_rendered: bool
    render_attempted: bool
    fetch_mode_used: str | None
    js_heavy_like: bool
    render_reason: str | None
    render_error_message: str | None
    schema_present: bool
    schema_count: int | None
    schema_types_json: list[str] | None
    response_time_ms: int | None
    is_internal: bool
    depth: int
    fetched_at: datetime
    error_message: str | None


class LinkPayload(TypedDict):
    crawl_job_id: int
    source_url: str
    target_url: str
    target_normalized_url: str | None
    target_domain: str | None
    anchor_text: str | None
    rel_attr: str | None
    is_nofollow: bool
    is_internal: bool


class PageWithLinksItem(scrapy.Item):
    page = scrapy.Field()
    links = scrapy.Field()
