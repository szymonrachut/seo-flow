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
    target_status_code: int | None = None
    final_url: str | None = None
    redirect_hops: int | None = None
    target_canonical_url: str | None = None
    target_noindex_like: bool = False
    target_non_indexable_like: bool = False
    target_canonicalized: bool = False
    broken_internal: bool = False
    redirecting_internal: bool = False
    unresolved_internal: bool = False
    to_noindex_like: bool = False
    to_canonicalized: bool = False
    redirect_chain: bool = False
    created_at: datetime


class PaginatedLinkResponse(BaseModel):
    items: list[LinkResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
