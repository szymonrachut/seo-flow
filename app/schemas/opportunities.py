from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.gsc import GscDateRangeLabel


PriorityLevel = Literal["low", "medium", "high", "critical"]
ImpactLevel = Literal["low", "medium", "high"]
EffortLevel = Literal["low", "medium", "high"]
OpportunityType = Literal[
    "QUICK_WINS",
    "HIGH_IMPRESSIONS_LOW_CTR",
    "TRAFFIC_WITH_TECHNICAL_ISSUES",
    "IMPORTANT_BUT_WEAK",
    "LOW_HANGING_FRUIT",
    "HIGH_RISK_PAGES",
    "UNDERLINKED_OPPORTUNITIES",
]


class OpportunityAssignmentResponse(BaseModel):
    type: OpportunityType
    opportunity_score: int
    impact_level: ImpactLevel
    effort_level: EffortLevel
    rationale: str


class OpportunityPagePreviewResponse(BaseModel):
    page_id: int
    url: str
    priority_score: int
    priority_level: PriorityLevel
    priority_rationale: str
    primary_opportunity_type: OpportunityType | None = None
    opportunity_count: int
    opportunity_types: list[OpportunityType]
    clicks: int
    impressions: int
    ctr: float
    position: float | None = None
    incoming_internal_links: int
    incoming_internal_linking_pages: int
    opportunities: list[OpportunityAssignmentResponse]
    opportunity_score: int | None = None
    impact_level: ImpactLevel | None = None
    effort_level: EffortLevel | None = None
    rationale: str


class OpportunityGroupResponse(BaseModel):
    type: OpportunityType
    count: int
    top_priority_score: int
    top_opportunity_score: int
    top_pages: list[OpportunityPagePreviewResponse]


class OpportunitiesSummaryResponse(BaseModel):
    crawl_job_id: int
    gsc_date_range: GscDateRangeLabel
    total_pages: int
    pages_with_opportunities: int
    high_priority_pages: int
    critical_priority_pages: int
    groups: list[OpportunityGroupResponse]
    top_priority_pages: list[OpportunityPagePreviewResponse]
