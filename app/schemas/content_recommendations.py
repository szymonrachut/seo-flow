from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.cannibalization import CannibalizationSeverity
from app.schemas.gsc import GscDateRangeLabel
from app.schemas.internal_linking import InternalLinkingIssueType
from app.schemas.opportunities import EffortLevel, ImpactLevel
from app.schemas.trends import CrawlCompareChangeType


PageType = Literal[
    "home",
    "category",
    "product",
    "service",
    "blog_article",
    "blog_index",
    "contact",
    "about",
    "faq",
    "location",
    "legal",
    "utility",
    "other",
]
PageBucket = Literal["commercial", "informational", "utility", "trust", "other"]
ContentRecommendationType = Literal[
    "MISSING_SUPPORTING_CONTENT",
    "THIN_CLUSTER",
    "EXPAND_EXISTING_PAGE",
    "MISSING_STRUCTURAL_PAGE_TYPE",
    "INTERNAL_LINKING_SUPPORT",
]
ContentRecommendationSegment = Literal[
    "create_new_page",
    "expand_existing_page",
    "strengthen_cluster",
    "improve_internal_support",
]
ContentRecommendationHelperCompareSignalKey = Literal[
    "url_presence",
    "technical_issues",
    "internal_linking_issues",
    "linking_pages",
    "gsc_clicks",
    "gsc_position",
    "top_queries",
    "cannibalization",
]
ContentRecommendationOutcomeKind = Literal[
    "gsc",
    "cannibalization",
    "issue_flags",
    "internal_linking",
    "mixed",
    "unknown",
]
ContentRecommendationOutcomeStatus = Literal[
    "improved",
    "unchanged",
    "pending",
    "too_early",
    "limited",
    "unavailable",
    "worsened",
]
ContentRecommendationOutcomeWindow = Literal["7d", "30d", "90d", "all"]
ImplementedContentRecommendationSort = Literal[
    "implemented_at_desc",
    "implemented_at_asc",
    "outcome",
    "recommendation_type",
    "title",
]


class ContentRecommendationCrawlContextResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    root_url: str | None = None


class ContentRecommendationContextResponse(BaseModel):
    site_id: int
    site_domain: str
    active_crawl_id: int | None = None
    baseline_crawl_id: int | None = None
    gsc_date_range: GscDateRangeLabel
    active_crawl: ContentRecommendationCrawlContextResponse | None = None
    baseline_crawl: ContentRecommendationCrawlContextResponse | None = None


class ContentRecommendationUrlImprovementGscContextResponse(BaseModel):
    available: bool
    impressions: int
    clicks: int
    ctr: float
    position: float | None = None
    top_queries_count: int
    notes: list[str] = Field(default_factory=list)


class ContentRecommendationUrlImprovementInternalLinkingContextResponse(BaseModel):
    internal_linking_score: int
    issue_count: int
    issue_types: list[InternalLinkingIssueType] = Field(default_factory=list)
    incoming_internal_links: int
    incoming_internal_linking_pages: int
    link_equity_score: float
    anchor_diversity_score: float


class ContentRecommendationUrlImprovementCannibalizationContextResponse(BaseModel):
    has_active_signals: bool
    severity: CannibalizationSeverity | None = None
    competing_urls_count: int
    common_queries_count: int
    strongest_competing_url: str | None = None
    shared_top_queries: list[str] = Field(default_factory=list)


class ContentRecommendationUrlImprovementCompareSignalResponse(BaseModel):
    key: ContentRecommendationHelperCompareSignalKey
    label: str
    status: CrawlCompareChangeType
    detail: str


class ContentRecommendationUrlImprovementCompareContextResponse(BaseModel):
    baseline_crawl_id: int
    signals: list[ContentRecommendationUrlImprovementCompareSignalResponse] = Field(default_factory=list)


class ContentRecommendationUrlImprovementHelperResponse(BaseModel):
    target_url: str
    title: str | None = None
    page_type: PageType
    page_bucket: PageBucket | None = None
    open_issues: list[str] = Field(default_factory=list)
    improvement_actions: list[str] = Field(default_factory=list)
    supporting_signals: list[str] = Field(default_factory=list)
    gsc_context: ContentRecommendationUrlImprovementGscContextResponse
    internal_linking_context: ContentRecommendationUrlImprovementInternalLinkingContextResponse
    cannibalization_context: ContentRecommendationUrlImprovementCannibalizationContextResponse
    compare_context: ContentRecommendationUrlImprovementCompareContextResponse | None = None


class ContentRecommendationResponse(BaseModel):
    id: str
    recommendation_key: str
    recommendation_type: ContentRecommendationType
    segment: ContentRecommendationSegment
    cluster_key: str
    cluster_label: str
    target_page_id: int | None = None
    target_url: str | None = None
    page_type: PageType
    target_page_type: PageType
    suggested_page_type: PageType | None = None
    priority_score: int
    confidence: float
    impact: ImpactLevel
    effort: EffortLevel
    cluster_strength: int
    coverage_gap_score: int
    internal_support_score: int
    rationale: str
    signals: list[str]
    reasons: list[str]
    prerequisites: list[str]
    supporting_urls: list[str]
    url_improvement_helper: ContentRecommendationUrlImprovementHelperResponse | None = None
    was_implemented_before: bool = False
    previously_implemented_at: datetime | None = None


class ContentRecommendationOutcomeDetailResponse(BaseModel):
    label: str
    before: str | None = None
    after: str | None = None
    change: str | None = None


class ImplementedContentRecommendationResponse(BaseModel):
    recommendation_key: str
    recommendation_type: ContentRecommendationType
    segment: ContentRecommendationSegment | None = None
    target_url: str | None = None
    normalized_target_url: str | None = None
    target_title_snapshot: str | None = None
    suggested_page_type: PageType | None = None
    cluster_label: str | None = None
    cluster_key: str | None = None
    recommendation_text: str
    signals_snapshot: list[str] = Field(default_factory=list)
    reasons_snapshot: list[str] = Field(default_factory=list)
    helper_snapshot: ContentRecommendationUrlImprovementHelperResponse | None = None
    primary_outcome_kind: ContentRecommendationOutcomeKind
    outcome_status: ContentRecommendationOutcomeStatus
    outcome_summary: str
    outcome_details: list[ContentRecommendationOutcomeDetailResponse] = Field(default_factory=list)
    outcome_window: ContentRecommendationOutcomeWindow
    is_too_early: bool = False
    days_since_implemented: int | None = None
    eligible_for_window: bool = False
    implemented_at: datetime
    implemented_crawl_job_id: int | None = None
    implemented_baseline_crawl_job_id: int | None = None
    times_marked_done: int = 1


class ImplementedContentRecommendationStatusCountsResponse(BaseModel):
    improved: int = 0
    unchanged: int = 0
    pending: int = 0
    too_early: int = 0
    limited: int = 0
    unavailable: int = 0
    worsened: int = 0


class ImplementedContentRecommendationModeCountsResponse(BaseModel):
    gsc: int = 0
    internal_linking: int = 0
    cannibalization: int = 0
    issue_flags: int = 0
    mixed: int = 0
    unknown: int = 0


class ImplementedContentRecommendationSummaryResponse(BaseModel):
    total_count: int = 0
    status_counts: ImplementedContentRecommendationStatusCountsResponse = Field(
        default_factory=ImplementedContentRecommendationStatusCountsResponse
    )
    mode_counts: ImplementedContentRecommendationModeCountsResponse = Field(
        default_factory=ImplementedContentRecommendationModeCountsResponse
    )


class ContentRecommendationMarkDoneRequest(BaseModel):
    recommendation_key: str
    active_crawl_id: int | None = None
    baseline_crawl_id: int | None = None
    gsc_date_range: GscDateRangeLabel = "last_28_days"


class ContentRecommendationMarkDoneResponse(BaseModel):
    recommendation_key: str
    implemented_at: datetime
    implemented_crawl_job_id: int | None = None
    implemented_baseline_crawl_job_id: int | None = None
    primary_outcome_kind: ContentRecommendationOutcomeKind
    times_marked_done: int


class ContentRecommendationSummaryResponse(BaseModel):
    total_recommendations: int
    implemented_recommendations: int
    high_priority_recommendations: int
    clusters_covered: int
    create_new_page_recommendations: int
    expand_existing_page_recommendations: int
    strengthen_cluster_recommendations: int
    improve_internal_support_recommendations: int
    counts_by_type: dict[ContentRecommendationType, int]
    counts_by_page_type: dict[PageType, int]


class PaginatedContentRecommendationsResponse(BaseModel):
    context: ContentRecommendationContextResponse
    summary: ContentRecommendationSummaryResponse
    items: list[ContentRecommendationResponse]
    implemented_items: list[ImplementedContentRecommendationResponse] = Field(default_factory=list)
    implemented_total: int = 0
    implemented_summary: ImplementedContentRecommendationSummaryResponse = Field(
        default_factory=ImplementedContentRecommendationSummaryResponse
    )
    page: int
    page_size: int
    total_items: int
    total_pages: int
