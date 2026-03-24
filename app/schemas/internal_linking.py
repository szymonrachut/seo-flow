from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.gsc import GscDateRangeLabel
from app.schemas.opportunities import OpportunityType, PriorityLevel


InternalLinkingIssueType = Literal[
    "ORPHAN_LIKE",
    "WEAKLY_LINKED_IMPORTANT",
    "LOW_ANCHOR_DIVERSITY",
    "EXACT_MATCH_ANCHOR_CONCENTRATION",
    "BOILERPLATE_DOMINATED",
    "LOW_LINK_EQUITY",
]


class AnchorSampleResponse(BaseModel):
    anchor_text: str
    links: int
    linking_pages: int
    exact_match: bool
    boilerplate_likely: bool


class InternalLinkingOverviewResponse(BaseModel):
    crawl_job_id: int
    gsc_date_range: GscDateRangeLabel
    total_internal_pages: int
    issue_pages: int
    orphan_like_pages: int
    weakly_linked_important_pages: int
    low_anchor_diversity_pages: int
    exact_match_anchor_concentration_pages: int
    boilerplate_dominated_pages: int
    low_link_equity_pages: int
    median_link_equity_score: float
    average_anchor_diversity_score: float
    average_body_like_share: float


class InternalLinkingIssueRowResponse(BaseModel):
    page_id: int
    url: str
    normalized_url: str
    priority_score: int
    priority_level: PriorityLevel
    priority_rationale: str
    primary_opportunity_type: OpportunityType | None = None
    opportunity_types: list[OpportunityType] = Field(default_factory=list)
    technical_issue_count: int
    clicks: int
    impressions: int
    ctr: float
    position: float | None = None
    incoming_internal_links: int
    incoming_internal_linking_pages: int
    incoming_follow_links: int
    incoming_follow_linking_pages: int
    incoming_nofollow_links: int
    body_like_links: int
    body_like_linking_pages: int
    boilerplate_like_links: int
    boilerplate_like_linking_pages: int
    body_like_share: float
    boilerplate_like_share: float
    unique_anchor_count: int
    anchor_diversity_score: float
    exact_match_anchor_count: int
    exact_match_anchor_ratio: float
    link_equity_score: float
    link_equity_rank: int
    internal_linking_score: int
    issue_count: int
    orphan_like: bool
    weakly_linked_important: bool
    low_anchor_diversity: bool
    exact_match_anchor_concentration: bool
    boilerplate_dominated: bool
    low_link_equity: bool
    issue_types: list[InternalLinkingIssueType]
    primary_issue_type: InternalLinkingIssueType
    top_anchor_samples: list[AnchorSampleResponse] = Field(default_factory=list)
    rationale: str


class PaginatedInternalLinkingIssuesResponse(BaseModel):
    crawl_job_id: int
    gsc_date_range: GscDateRangeLabel
    items: list[InternalLinkingIssueRowResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
