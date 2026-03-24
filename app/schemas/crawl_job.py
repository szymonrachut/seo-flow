from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings

settings = get_settings()


class CrawlJobCreateRequest(BaseModel):
    root_url: str
    max_urls: int = Field(default=500, ge=1)
    max_depth: int = Field(default=settings.crawl_default_max_depth, ge=0)
    delay: float = Field(default=0.25, ge=0)
    render_mode: Literal["never", "auto", "always"] = Field(default=settings.crawl_default_render_mode)
    render_timeout_ms: int = Field(default=settings.crawl_default_render_timeout_ms, ge=1)
    max_rendered_pages_per_job: int = Field(default=settings.crawl_default_max_rendered_pages_per_job, ge=1)


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


class CrawlJobListItemResponse(BaseModel):
    id: int
    status: str
    root_url: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    total_pages: int
    total_internal_links: int
    total_external_links: int
    total_errors: int


class CrawlJobSummaryCounts(BaseModel):
    total_pages: int
    total_links: int
    total_internal_links: int
    total_external_links: int
    pages_missing_title: int
    pages_missing_meta_description: int
    pages_missing_h1: int
    pages_non_indexable_like: int
    rendered_pages: int
    js_heavy_like_pages: int
    pages_with_render_errors: int
    pages_with_schema: int
    pages_with_x_robots_tag: int
    pages_with_gsc_28d: int
    pages_with_gsc_90d: int
    gsc_opportunities_28d: int
    gsc_opportunities_90d: int
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
