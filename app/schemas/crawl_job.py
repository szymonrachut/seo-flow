from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CrawlJobCreateRequest(BaseModel):
    root_url: str
    max_urls: int = Field(default=500, ge=1)
    max_depth: int = Field(default=3, ge=0)
    delay: float = Field(default=0.25, ge=0)


class CrawlJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    settings_json: dict[str, Any]
    stats_json: dict[str, Any]


class CrawlJobSummaryCounts(BaseModel):
    total_pages: int
    total_links: int
    total_internal_links: int
    total_external_links: int
    pages_missing_title: int
    pages_missing_meta_description: int
    pages_missing_h1: int
    pages_non_indexable_like: int
    broken_internal_links: int
    redirecting_internal_links: int


class CrawlJobProgress(BaseModel):
    visited_pages: int
    queued_urls: int
    discovered_links: int
    internal_links: int
    external_links: int
    errors_count: int


class CrawlJobDetailResponse(CrawlJobResponse):
    summary_counts: CrawlJobSummaryCounts
    progress: CrawlJobProgress
