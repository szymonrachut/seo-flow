from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
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
    fetched_at: datetime | None
    error_message: str | None
    created_at: datetime


class PaginatedPageResponse(BaseModel):
    items: list[PageResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
