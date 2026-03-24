from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.schemas.crawl_job import CrawlJobDetailResponse, CrawlJobListItemResponse

settings = get_settings()


class SiteSummaryResponse(BaseModel):
    total_crawls: int
    pending_crawls: int
    running_crawls: int
    finished_crawls: int
    failed_crawls: int
    stopped_crawls: int
    first_crawl_at: datetime | None
    last_crawl_at: datetime | None


class SiteCrawlListItemResponse(CrawlJobListItemResponse):
    site_id: int


class SiteListItemResponse(BaseModel):
    id: int
    domain: str
    root_url: str
    created_at: datetime
    selected_gsc_property_uri: str | None = None
    summary: SiteSummaryResponse
    latest_crawl: SiteCrawlListItemResponse | None = None


class SiteDetailResponse(BaseModel):
    id: int
    domain: str
    root_url: str
    created_at: datetime
    selected_gsc_property_uri: str | None = None
    selected_gsc_property_permission_level: str | None = None
    summary: SiteSummaryResponse
    active_crawl_id: int | None = None
    baseline_crawl_id: int | None = None
    active_crawl: CrawlJobDetailResponse | None = None
    baseline_crawl: CrawlJobDetailResponse | None = None
    crawl_history: list[SiteCrawlListItemResponse] = Field(default_factory=list)


class SiteCrawlCreateRequest(BaseModel):
    root_url: str | None = None
    max_urls: int = Field(default=500, ge=1)
    max_depth: int = Field(default=settings.crawl_default_max_depth, ge=0)
    delay: float = Field(default=0.25, ge=0)
    render_mode: Literal["never", "auto", "always"] = Field(default=settings.crawl_default_render_mode)
    render_timeout_ms: int = Field(default=settings.crawl_default_render_timeout_ms, ge=1)
    max_rendered_pages_per_job: int = Field(default=settings.crawl_default_max_rendered_pages_per_job, ge=1)
