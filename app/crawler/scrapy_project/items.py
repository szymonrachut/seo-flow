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
    meta_description: str | None
    h1: str | None
    canonical_url: str | None
    robots_meta: str | None
    content_type: str | None
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
