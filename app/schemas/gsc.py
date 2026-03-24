from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


GscDateRangeLabel = Literal["last_28_days", "last_90_days"]


class GscPropertyOptionResponse(BaseModel):
    property_uri: str
    permission_level: str | None = None
    matches_site: bool
    is_selected: bool


class GscPropertySelectionRequest(BaseModel):
    property_uri: str


class GscSelectedPropertyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    property_uri: str
    permission_level: str | None = None
    created_at: datetime
    updated_at: datetime


class GscImportRequest(BaseModel):
    date_ranges: list[GscDateRangeLabel] = Field(default_factory=lambda: ["last_28_days", "last_90_days"])
    top_queries_limit: int | None = None


class GscImportRangeSummary(BaseModel):
    date_range_label: GscDateRangeLabel
    imported_url_metrics: int
    imported_top_queries: int
    pages_with_top_queries: int
    failed_pages: int
    errors: list[str]


class GscImportResponse(BaseModel):
    crawl_job_id: int
    property_uri: str
    imported_at: datetime
    ranges: list[GscImportRangeSummary]


class GscRangeCoverageResponse(BaseModel):
    date_range_label: GscDateRangeLabel
    imported_pages: int
    pages_with_impressions: int
    pages_with_clicks: int
    pages_with_top_queries: int
    total_top_queries: int
    opportunities_with_impressions: int
    opportunities_with_clicks: int
    last_imported_at: datetime | None = None


class GscSummaryResponse(BaseModel):
    crawl_job_id: int
    site_id: int
    auth_connected: bool
    selected_property_uri: str | None = None
    selected_property_permission_level: str | None = None
    available_date_ranges: list[GscDateRangeLabel]
    ranges: list[GscRangeCoverageResponse]


class GscActiveCrawlContextResponse(BaseModel):
    id: int
    site_id: int
    status: str
    root_url: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class GscSiteSummaryResponse(BaseModel):
    site_id: int
    site_domain: str
    site_root_url: str
    auth_connected: bool
    selected_property_uri: str | None = None
    selected_property_permission_level: str | None = None
    available_date_ranges: list[GscDateRangeLabel]
    active_crawl_id: int | None = None
    active_crawl_has_gsc_data: bool = False
    active_crawl: GscActiveCrawlContextResponse | None = None
    ranges: list[GscRangeCoverageResponse]


class GscTopQueryRowResponse(BaseModel):
    id: int
    page_id: int | None = None
    url: str
    date_range_label: GscDateRangeLabel
    query: str
    clicks: int
    impressions: int
    ctr: float | None = None
    position: float | None = None
    fetched_at: datetime


class GscTopQueriesPageContextResponse(BaseModel):
    id: int
    url: str
    normalized_url: str
    title: str | None = None
    clicks_28d: int | None = None
    impressions_28d: int | None = None
    ctr_28d: float | None = None
    position_28d: float | None = None
    clicks_90d: int | None = None
    impressions_90d: int | None = None
    ctr_90d: float | None = None
    position_90d: float | None = None
    has_technical_issue: bool
    technical_issue_count: int
    top_queries_count_28d: int
    top_queries_count_90d: int


class PaginatedGscTopQueriesResponse(BaseModel):
    items: list[GscTopQueryRowResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    page_context: GscTopQueriesPageContextResponse | None = None
