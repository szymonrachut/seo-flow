from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    crawl_job_id: int
    source_page_id: int
    source_url: str
    target_url: str
    target_normalized_url: str | None
    target_domain: str | None
    anchor_text: str | None
    rel_attr: str | None
    is_nofollow: bool
    is_internal: bool
    created_at: datetime


class PaginatedLinkResponse(BaseModel):
    items: list[LinkResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
