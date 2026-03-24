from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.opportunities import ImpactLevel, OpportunityType, PriorityLevel
from app.schemas.cannibalization import CannibalizationRecommendationType, CannibalizationSeverity


class PageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    crawl_job_id: int
    url: str
    normalized_url: str
    final_url: str | None
    status_code: int | None
    title: str | None
    title_length: int | None = None
    meta_description: str | None
    meta_description_length: int | None = None
    h1: str | None
    h1_length: int | None = None
    h1_count: int | None = None
    h2_count: int | None = None
    canonical_url: str | None
    canonical_target_url: str | None = None
    canonical_target_status_code: int | None = None
    robots_meta: str | None
    x_robots_tag: str | None = None
    content_type: str | None
    word_count: int | None = None
    content_text_hash: str | None = None
    images_count: int | None = None
    images_missing_alt_count: int | None = None
    html_size_bytes: int | None = None
    was_rendered: bool
    render_attempted: bool
    fetch_mode_used: str | None = None
    js_heavy_like: bool
    render_reason: str | None = None
    render_error_message: str | None = None
    schema_present: bool
    schema_count: int | None = None
    schema_types_json: list[str] | None = None
    schema_types_text: str = ""
    page_type: str
    page_bucket: str
    page_type_confidence: float
    page_type_version: str
    page_type_rationale: str | None = None
    has_render_error: bool
    has_x_robots_tag: bool
    response_time_ms: int | None
    is_internal: bool
    depth: int
    fetched_at: datetime | None
    error_message: str | None
    title_missing: bool
    meta_description_missing: bool
    h1_missing: bool
    title_too_short: bool
    title_too_long: bool
    meta_description_too_short: bool
    meta_description_too_long: bool
    multiple_h1: bool
    missing_h2: bool
    canonical_missing: bool
    self_canonical: bool
    canonical_to_other_url: bool
    canonical_to_non_200: bool
    canonical_to_redirect: bool
    noindex_like: bool
    non_indexable_like: bool
    thin_content: bool
    duplicate_title: bool
    duplicate_meta_description: bool
    duplicate_content: bool
    missing_alt_images: bool
    no_images: bool
    oversized: bool
    clicks_28d: int | None = None
    impressions_28d: int | None = None
    ctr_28d: float | None = None
    position_28d: float | None = None
    gsc_fetched_at_28d: datetime | None = None
    top_queries_count_28d: int = 0
    has_gsc_28d: bool = False
    clicks_90d: int | None = None
    impressions_90d: int | None = None
    ctr_90d: float | None = None
    position_90d: float | None = None
    gsc_fetched_at_90d: datetime | None = None
    top_queries_count_90d: int = 0
    has_gsc_90d: bool = False
    has_technical_issue: bool = False
    technical_issue_count: int = 0
    incoming_internal_links: int = 0
    incoming_internal_linking_pages: int = 0
    priority_score: int = 0
    priority_level: PriorityLevel = "low"
    priority_rationale: str = ""
    traffic_component: int = 0
    issue_component: int = 0
    opportunity_component: int = 0
    internal_linking_component: int = 0
    opportunity_count: int = 0
    primary_opportunity_type: OpportunityType | None = None
    opportunity_types: list[OpportunityType] = Field(default_factory=list)
    has_cannibalization: bool = False
    cannibalization_cluster_id: str | None = None
    cannibalization_severity: CannibalizationSeverity | None = None
    cannibalization_impact_level: ImpactLevel | None = None
    cannibalization_recommendation_type: CannibalizationRecommendationType | None = None
    cannibalization_rationale: str | None = None
    cannibalization_competing_urls_count: int = 0
    cannibalization_strongest_competing_url: str | None = None
    cannibalization_strongest_competing_page_id: int | None = None
    cannibalization_dominant_competing_url: str | None = None
    cannibalization_dominant_competing_page_id: int | None = None
    cannibalization_common_queries_count: int = 0
    cannibalization_weighted_overlap_by_impressions: float = 0.0
    cannibalization_weighted_overlap_by_clicks: float = 0.0
    cannibalization_overlap_ratio: float = 0.0
    cannibalization_overlap_strength: float = 0.0
    cannibalization_shared_top_queries: list[str] = Field(default_factory=list)
    created_at: datetime


class PaginatedPageResponse(BaseModel):
    items: list[PageResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    available_status_codes: list[int] = Field(default_factory=list)
    has_gsc_integration: bool = False


class PageTaxonomySummaryResponse(BaseModel):
    crawl_job_id: int
    page_type_version: str
    total_pages: int
    classified_pages: int
    counts_by_page_type: dict[str, int] = Field(default_factory=dict)
    counts_by_page_bucket: dict[str, int] = Field(default_factory=dict)
