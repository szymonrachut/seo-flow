from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.gsc import GscDateRangeLabel
from app.schemas.opportunities import OpportunityType, PriorityLevel


CrawlCompareChangeType = Literal["improved", "worsened", "unchanged", "new", "missing"]
MetricTrend = Literal["improved", "worsened", "flat"]


class TrendJobOptionResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    root_url: str | None = None


class TrendsOverviewResponse(BaseModel):
    crawl_job_id: int
    site_id: int
    site_domain: str
    default_baseline_job_id: int | None = None
    baseline_candidates: list[TrendJobOptionResponse]
    available_gsc_ranges: list[GscDateRangeLabel]


class CrawlCompareSummaryResponse(BaseModel):
    baseline_job_id: int
    target_job_id: int
    gsc_date_range: GscDateRangeLabel
    shared_urls: int
    new_urls: int
    missing_urls: int
    improved_urls: int
    worsened_urls: int
    unchanged_urls: int
    resolved_issues_total: int
    added_issues_total: int


class CrawlCompareRowResponse(BaseModel):
    url: str
    normalized_url: str
    baseline_page_id: int | None = None
    target_page_id: int | None = None
    new_in_target: bool
    missing_in_target: bool
    present_in_both: bool
    change_type: CrawlCompareChangeType
    issues_resolved_count: int
    issues_added_count: int
    resolved_issues: list[str] = Field(default_factory=list)
    added_issues: list[str] = Field(default_factory=list)
    changed_fields: list[str] = Field(default_factory=list)
    change_rationale: str
    baseline_status_code: int | None = None
    target_status_code: int | None = None
    status_code_changed: bool = False
    baseline_title: str | None = None
    target_title: str | None = None
    title_changed: bool = False
    baseline_meta_description: str | None = None
    target_meta_description: str | None = None
    meta_description_changed: bool = False
    baseline_h1: str | None = None
    target_h1: str | None = None
    h1_changed: bool = False
    baseline_canonical_url: str | None = None
    target_canonical_url: str | None = None
    canonical_url_changed: bool = False
    baseline_noindex_like: bool | None = None
    target_noindex_like: bool | None = None
    noindex_like_changed: bool = False
    baseline_non_indexable_like: bool | None = None
    target_non_indexable_like: bool | None = None
    baseline_title_length: int | None = None
    target_title_length: int | None = None
    baseline_meta_description_length: int | None = None
    target_meta_description_length: int | None = None
    baseline_h1_count: int | None = None
    target_h1_count: int | None = None
    baseline_word_count: int | None = None
    target_word_count: int | None = None
    baseline_images_missing_alt_count: int | None = None
    target_images_missing_alt_count: int | None = None
    baseline_schema_count: int | None = None
    target_schema_count: int | None = None
    baseline_html_size_bytes: int | None = None
    target_html_size_bytes: int | None = None
    baseline_was_rendered: bool | None = None
    target_was_rendered: bool | None = None
    baseline_js_heavy_like: bool | None = None
    target_js_heavy_like: bool | None = None
    baseline_response_time_ms: int | None = None
    target_response_time_ms: int | None = None
    baseline_incoming_internal_links: int | None = None
    target_incoming_internal_links: int | None = None
    baseline_incoming_internal_linking_pages: int | None = None
    target_incoming_internal_linking_pages: int | None = None
    baseline_priority_score: int | None = None
    target_priority_score: int | None = None
    baseline_priority_level: PriorityLevel | None = None
    target_priority_level: PriorityLevel | None = None
    baseline_opportunity_count: int | None = None
    target_opportunity_count: int | None = None
    baseline_primary_opportunity_type: OpportunityType | None = None
    target_primary_opportunity_type: OpportunityType | None = None
    baseline_opportunity_types: list[OpportunityType] = Field(default_factory=list)
    target_opportunity_types: list[OpportunityType] = Field(default_factory=list)
    delta_priority_score: int | None = None
    delta_word_count: int | None = None
    delta_schema_count: int | None = None
    delta_response_time_ms: int | None = None
    delta_incoming_internal_links: int | None = None
    delta_incoming_internal_linking_pages: int | None = None


class PaginatedCrawlCompareResponse(BaseModel):
    baseline_job: TrendJobOptionResponse
    target_job: TrendJobOptionResponse
    summary: CrawlCompareSummaryResponse
    items: list[CrawlCompareRowResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class GscCompareTotalsResponse(BaseModel):
    clicks: int
    impressions: int
    ctr: float
    position: float | None = None
    top_queries_count: int


class GscCompareSummaryResponse(BaseModel):
    crawl_job_id: int
    baseline_gsc_range: GscDateRangeLabel
    target_gsc_range: GscDateRangeLabel
    baseline: GscCompareTotalsResponse
    target: GscCompareTotalsResponse
    delta_clicks: int
    delta_impressions: int
    delta_ctr: float
    delta_position: float | None = None
    delta_top_queries_count: int
    improved_urls: int
    worsened_urls: int
    flat_urls: int


class GscCompareRowResponse(BaseModel):
    page_id: int
    url: str
    normalized_url: str
    has_baseline_data: bool
    has_target_data: bool
    baseline_clicks: int
    target_clicks: int
    delta_clicks: int
    baseline_impressions: int
    target_impressions: int
    delta_impressions: int
    baseline_ctr: float
    target_ctr: float
    delta_ctr: float
    baseline_position: float | None = None
    target_position: float | None = None
    delta_position: float | None = None
    baseline_top_queries_count: int
    target_top_queries_count: int
    delta_top_queries_count: int
    overall_trend: MetricTrend
    clicks_trend: MetricTrend
    impressions_trend: MetricTrend
    ctr_trend: MetricTrend
    position_trend: MetricTrend
    top_queries_trend: MetricTrend
    rationale: str
    has_technical_issue: bool
    priority_score: int
    priority_level: PriorityLevel
    primary_opportunity_type: OpportunityType | None = None


class PaginatedGscCompareResponse(BaseModel):
    summary: GscCompareSummaryResponse
    items: list[GscCompareRowResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
