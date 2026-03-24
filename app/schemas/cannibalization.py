from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.gsc import GscDateRangeLabel
from app.schemas.opportunities import ImpactLevel, OpportunityType, PriorityLevel


CannibalizationSeverity = Literal["low", "medium", "high", "critical"]
CannibalizationRecommendationType = Literal[
    "MERGE_CANDIDATE",
    "SPLIT_INTENT_CANDIDATE",
    "REINFORCE_PRIMARY_URL",
    "QUERY_CLUSTER_WITHOUT_CLEAR_PRIMARY",
    "LOW_VALUE_OVERLAP",
    "HIGH_IMPACT_CANNIBALIZATION",
]


class CannibalizationClusterCandidateUrlResponse(BaseModel):
    page_id: int
    url: str
    priority_score: int
    priority_level: PriorityLevel
    primary_opportunity_type: OpportunityType | None = None
    clicks: int
    impressions: int
    position: float | None = None
    query_count: int
    shared_query_count: int
    exclusive_query_count: int
    click_share: float
    impression_share: float
    avg_shared_position: float | None = None
    strongest_competing_url: str | None = None
    is_dominant: bool


class CannibalizationClusterResponse(BaseModel):
    cluster_id: str
    urls_count: int
    shared_queries_count: int
    shared_query_impressions: int
    shared_query_clicks: int
    weighted_overlap: float
    severity: CannibalizationSeverity
    impact_level: ImpactLevel
    recommendation_type: CannibalizationRecommendationType
    has_clear_primary: bool
    dominant_url: str | None = None
    dominant_url_page_id: int | None = None
    dominant_url_confidence: float
    dominant_url_score: float
    sample_queries: list[str] = Field(default_factory=list)
    candidate_urls: list[CannibalizationClusterCandidateUrlResponse] = Field(default_factory=list)
    rationale: str


class CannibalizationSummaryResponse(BaseModel):
    crawl_job_id: int
    gsc_date_range: GscDateRangeLabel
    total_candidate_pages: int
    pages_in_conflicts: int
    clusters_count: int
    critical_clusters: int
    high_severity_clusters: int
    high_impact_clusters: int
    no_clear_primary_clusters: int
    merge_candidates: int
    split_intent_candidates: int
    reinforce_primary_candidates: int
    low_value_overlap_clusters: int
    average_weighted_overlap: float


class PaginatedCannibalizationClustersResponse(BaseModel):
    summary: CannibalizationSummaryResponse
    items: list[CannibalizationClusterResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class CannibalizationOverlapRowResponse(BaseModel):
    competing_page_id: int
    competing_url: str
    common_queries_count: int
    weighted_overlap_by_impressions: float
    weighted_overlap_by_clicks: float
    overlap_ratio: float
    pair_overlap_score: float
    shared_query_impressions: int
    shared_query_clicks: int
    shared_top_queries: list[str] = Field(default_factory=list)
    dominant_url: str | None = None
    dominance_score: float
    dominance_confidence: float
    competitor_priority_score: int
    competitor_priority_level: PriorityLevel
    competitor_primary_opportunity_type: OpportunityType | None = None
    competitor_clicks: int
    competitor_impressions: int
    competitor_position: float | None = None


class CannibalizationPageDetailsResponse(BaseModel):
    crawl_job_id: int
    gsc_date_range: GscDateRangeLabel
    page_id: int
    url: str
    normalized_url: str
    has_cannibalization: bool
    cluster_id: str | None = None
    severity: CannibalizationSeverity | None = None
    impact_level: ImpactLevel | None = None
    recommendation_type: CannibalizationRecommendationType | None = None
    rationale: str | None = None
    competing_urls_count: int
    strongest_competing_url: str | None = None
    strongest_competing_page_id: int | None = None
    common_queries_count: int
    weighted_overlap_by_impressions: float
    weighted_overlap_by_clicks: float
    overlap_ratio: float
    overlap_strength: float
    shared_top_queries: list[str] = Field(default_factory=list)
    dominant_competing_url: str | None = None
    dominant_competing_page_id: int | None = None
    overlaps: list[CannibalizationOverlapRowResponse] = Field(default_factory=list)
