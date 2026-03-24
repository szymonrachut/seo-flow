from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.gsc import GscDateRangeLabel
from app.schemas.internal_linking import InternalLinkingIssueType
from app.schemas.opportunities import OpportunityType, PriorityLevel
from app.schemas.trends import CrawlCompareChangeType


CompareDeltaTrend = Literal["improved", "worsened", "flat"]
AuditCompareSectionStatus = Literal["resolved", "new", "improved", "worsened", "unchanged"]
OpportunityCompareHighlight = Literal[
    "NEW_URL",
    "MISSING_URL",
    "NEW_OPPORTUNITY",
    "RESOLVED_OPPORTUNITY",
    "PRIORITY_UP",
    "PRIORITY_DOWN",
    "ENTERED_ACTIONABLE",
    "LEFT_ACTIONABLE",
]
InternalLinkingCompareHighlight = Literal[
    "NEW_ORPHAN_LIKE",
    "RESOLVED_ORPHAN_LIKE",
    "WEAKLY_LINKED_IMPROVED",
    "WEAKLY_LINKED_WORSENED",
    "LINK_EQUITY_IMPROVED",
    "LINK_EQUITY_WORSENED",
    "LINKING_PAGES_UP",
    "LINKING_PAGES_DOWN",
    "ANCHOR_DIVERSITY_IMPROVED",
    "ANCHOR_DIVERSITY_WORSENED",
    "BOILERPLATE_IMPROVED",
    "BOILERPLATE_WORSENED",
]


class SiteCompareCrawlResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    root_url: str | None = None


class SiteCompareContextResponse(BaseModel):
    site_id: int
    site_domain: str
    active_crawl_id: int | None = None
    baseline_crawl_id: int | None = None
    compare_available: bool
    compare_unavailable_reason: str | None = None
    active_crawl: SiteCompareCrawlResponse | None = None
    baseline_crawl: SiteCompareCrawlResponse | None = None


class SitePagesCompareSummaryResponse(BaseModel):
    active_urls: int
    baseline_urls: int
    shared_urls: int
    new_urls: int
    missing_urls: int
    changed_urls: int
    improved_urls: int
    worsened_urls: int
    unchanged_urls: int
    status_changed_urls: int
    title_changed_urls: int
    meta_description_changed_urls: int
    h1_changed_urls: int
    canonical_changed_urls: int
    noindex_changed_urls: int
    priority_improved_urls: int
    priority_worsened_urls: int
    internal_linking_improved_urls: int
    internal_linking_worsened_urls: int
    content_growth_urls: int
    content_drop_urls: int


class SitePagesCompareRowResponse(BaseModel):
    url: str
    normalized_url: str
    active_page_id: int | None = None
    baseline_page_id: int | None = None
    change_type: CrawlCompareChangeType
    changed_fields: list[str] = Field(default_factory=list)
    change_rationale: str
    active_status_code: int | None = None
    baseline_status_code: int | None = None
    status_code_changed: bool = False
    active_title: str | None = None
    baseline_title: str | None = None
    title_changed: bool = False
    active_meta_description: str | None = None
    baseline_meta_description: str | None = None
    meta_description_changed: bool = False
    active_h1: str | None = None
    baseline_h1: str | None = None
    h1_changed: bool = False
    active_canonical_url: str | None = None
    baseline_canonical_url: str | None = None
    canonical_changed: bool = False
    active_noindex_like: bool | None = None
    baseline_noindex_like: bool | None = None
    noindex_changed: bool = False
    active_word_count: int | None = None
    baseline_word_count: int | None = None
    delta_word_count: int | None = None
    word_count_trend: CompareDeltaTrend | None = None
    active_response_time_ms: int | None = None
    baseline_response_time_ms: int | None = None
    delta_response_time_ms: int | None = None
    response_time_trend: CompareDeltaTrend | None = None
    active_incoming_internal_links: int | None = None
    baseline_incoming_internal_links: int | None = None
    delta_incoming_internal_links: int | None = None
    active_incoming_internal_linking_pages: int | None = None
    baseline_incoming_internal_linking_pages: int | None = None
    delta_incoming_internal_linking_pages: int | None = None
    internal_linking_trend: CompareDeltaTrend | None = None
    active_priority_score: int | None = None
    baseline_priority_score: int | None = None
    delta_priority_score: int | None = None
    priority_trend: CompareDeltaTrend | None = None
    active_priority_level: PriorityLevel | None = None
    baseline_priority_level: PriorityLevel | None = None
    active_primary_opportunity_type: OpportunityType | None = None


class PaginatedSitePagesCompareResponse(BaseModel):
    context: SiteCompareContextResponse
    gsc_date_range: GscDateRangeLabel
    summary: SitePagesCompareSummaryResponse
    items: list[SitePagesCompareRowResponse] = Field(default_factory=list)
    page: int
    page_size: int
    total_items: int
    total_pages: int


class AuditCompareSummaryResponse(BaseModel):
    total_sections: int
    resolved_sections: int
    new_sections: int
    improved_sections: int
    worsened_sections: int
    unchanged_sections: int
    resolved_issues_total: int
    new_issues_total: int
    active_issues_total: int
    baseline_issues_total: int


class AuditCompareSectionResponse(BaseModel):
    key: str
    area: Literal["pages", "links", "duplicates"]
    active_count: int
    baseline_count: int
    delta: int
    status: AuditCompareSectionStatus
    resolved_items_count: int
    new_items_count: int
    sample_resolved_items: list[str] = Field(default_factory=list)
    sample_new_items: list[str] = Field(default_factory=list)


class SiteAuditCompareResponse(BaseModel):
    context: SiteCompareContextResponse
    summary: AuditCompareSummaryResponse
    sections: list[AuditCompareSectionResponse] = Field(default_factory=list)


class OpportunitiesCompareSummaryResponse(BaseModel):
    total_urls: int
    active_urls_with_opportunities: int
    active_actionable_urls: int
    new_opportunity_urls: int
    resolved_opportunity_urls: int
    priority_up_urls: int
    priority_down_urls: int
    entered_actionable_urls: int
    left_actionable_urls: int


class OpportunitiesCompareRowResponse(BaseModel):
    url: str
    normalized_url: str
    active_page_id: int | None = None
    baseline_page_id: int | None = None
    change_type: CrawlCompareChangeType
    highlights: list[OpportunityCompareHighlight] = Field(default_factory=list)
    active_priority_score: int | None = None
    baseline_priority_score: int | None = None
    delta_priority_score: int | None = None
    active_priority_level: PriorityLevel | None = None
    baseline_priority_level: PriorityLevel | None = None
    active_opportunity_count: int = 0
    baseline_opportunity_count: int = 0
    active_primary_opportunity_type: OpportunityType | None = None
    baseline_primary_opportunity_type: OpportunityType | None = None
    active_opportunity_types: list[OpportunityType] = Field(default_factory=list)
    baseline_opportunity_types: list[OpportunityType] = Field(default_factory=list)
    new_opportunity_types: list[OpportunityType] = Field(default_factory=list)
    resolved_opportunity_types: list[OpportunityType] = Field(default_factory=list)
    entered_actionable: bool = False
    left_actionable: bool = False
    change_rationale: str


class PaginatedSiteOpportunitiesCompareResponse(BaseModel):
    context: SiteCompareContextResponse
    gsc_date_range: GscDateRangeLabel
    actionable_priority_score_threshold: int
    summary: OpportunitiesCompareSummaryResponse
    items: list[OpportunitiesCompareRowResponse] = Field(default_factory=list)
    page: int
    page_size: int
    total_items: int
    total_pages: int


class InternalLinkingCompareSummaryResponse(BaseModel):
    total_urls: int
    issue_urls_in_active: int
    new_orphan_like_urls: int
    resolved_orphan_like_urls: int
    weakly_linked_improved_urls: int
    weakly_linked_worsened_urls: int
    link_equity_improved_urls: int
    link_equity_worsened_urls: int
    linking_pages_up_urls: int
    linking_pages_down_urls: int
    anchor_diversity_improved_urls: int
    anchor_diversity_worsened_urls: int
    boilerplate_improved_urls: int
    boilerplate_worsened_urls: int


class InternalLinkingCompareRowResponse(BaseModel):
    url: str
    normalized_url: str
    active_page_id: int | None = None
    baseline_page_id: int | None = None
    change_type: CrawlCompareChangeType
    highlights: list[InternalLinkingCompareHighlight] = Field(default_factory=list)
    active_issue_types: list[InternalLinkingIssueType] = Field(default_factory=list)
    baseline_issue_types: list[InternalLinkingIssueType] = Field(default_factory=list)
    new_issue_types: list[InternalLinkingIssueType] = Field(default_factory=list)
    resolved_issue_types: list[InternalLinkingIssueType] = Field(default_factory=list)
    active_internal_linking_score: int | None = None
    baseline_internal_linking_score: int | None = None
    delta_internal_linking_score: int | None = None
    active_link_equity_score: float | None = None
    baseline_link_equity_score: float | None = None
    delta_link_equity_score: float | None = None
    active_incoming_follow_linking_pages: int | None = None
    baseline_incoming_follow_linking_pages: int | None = None
    delta_incoming_follow_linking_pages: int | None = None
    active_anchor_diversity_score: float | None = None
    baseline_anchor_diversity_score: float | None = None
    delta_anchor_diversity_score: float | None = None
    active_boilerplate_like_share: float | None = None
    baseline_boilerplate_like_share: float | None = None
    delta_boilerplate_like_share: float | None = None
    active_orphan_like: bool | None = None
    baseline_orphan_like: bool | None = None
    active_weakly_linked_important: bool | None = None
    baseline_weakly_linked_important: bool | None = None
    change_rationale: str


class PaginatedSiteInternalLinkingCompareResponse(BaseModel):
    context: SiteCompareContextResponse
    gsc_date_range: GscDateRangeLabel
    summary: InternalLinkingCompareSummaryResponse
    items: list[InternalLinkingCompareRowResponse] = Field(default_factory=list)
    page: int
    page_size: int
    total_items: int
    total_pages: int
