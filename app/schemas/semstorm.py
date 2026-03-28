from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SemstormDiscoveryRequestParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_competitors: int = Field(default=5, ge=1, le=50)
    max_keywords_per_competitor: int = Field(default=10, ge=1, le=50)
    result_type: Literal["organic", "paid"] = "organic"
    include_basic_stats: bool = False
    competitors_type: Literal["all", "similar"] = "all"


class SemstormDiscoveryPreviewRequest(SemstormDiscoveryRequestParams):
    pass


class SemstormDiscoveryRunCreateRequest(SemstormDiscoveryRequestParams):
    max_competitors: int = Field(default=10, ge=1, le=50)
    max_keywords_per_competitor: int = Field(default=25, ge=1, le=50)
    include_basic_stats: bool = True


class SemstormKeywordBasicStatsResponse(BaseModel):
    keywords: int = 0
    keywords_top: int = 0
    traffic: int = 0
    traffic_potential: int = 0
    search_volume: int = 0
    search_volume_top: int = 0


class SemstormTopQueryResponse(BaseModel):
    keyword: str
    position: int | None = None
    position_change: int | None = None
    url: str | None = None
    traffic: int | None = None
    traffic_change: int | None = None
    volume: int | None = None
    competitors: int | None = None
    cpc: float | None = None
    trends: list[int] = Field(default_factory=list)


class SemstormCompetitorDiscoveryResponse(BaseModel):
    rank: int | None = None
    domain: str
    common_keywords: int = 0
    traffic: int = 0
    queries_count: int = 0
    basic_stats: SemstormKeywordBasicStatsResponse | None = None
    top_queries: list[SemstormTopQueryResponse] = Field(default_factory=list)


class SemstormDiscoveryPreviewResponse(BaseModel):
    site_id: int
    source_domain: str
    semstorm_enabled: bool
    result_type: Literal["organic", "paid"]
    competitors_type: Literal["all", "similar"]
    include_basic_stats: bool
    max_competitors: int
    max_keywords_per_competitor: int
    competitors: list[SemstormCompetitorDiscoveryResponse] = Field(default_factory=list)


class SemstormDiscoveryRunParamsResponse(BaseModel):
    max_competitors: int
    max_keywords_per_competitor: int
    result_type: Literal["organic", "paid"]
    include_basic_stats: bool
    competitors_type: Literal["all", "similar"]


class SemstormDiscoveryRunSummaryResponse(BaseModel):
    total_competitors: int = 0
    total_queries: int = 0
    unique_keywords: int = 0
    created_at: datetime


class SemstormDiscoveryRunListItemResponse(BaseModel):
    id: int
    site_id: int
    run_id: int
    status: str
    stage: str
    source_domain: str
    params: SemstormDiscoveryRunParamsResponse
    summary: SemstormDiscoveryRunSummaryResponse
    error_code: str | None = None
    error_message_safe: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SemstormDiscoveryRunResponse(SemstormDiscoveryRunListItemResponse):
    competitors: list[SemstormCompetitorDiscoveryResponse] = Field(default_factory=list)


class SemstormOpportunitySeedsSummaryResponse(BaseModel):
    total_items: int = 0
    bucket_counts: dict[str, int] = Field(default_factory=dict)
    decision_type_counts: dict[str, int] = Field(default_factory=dict)
    coverage_status_counts: dict[str, int] = Field(default_factory=dict)
    state_counts: dict[str, int] = Field(default_factory=dict)
    total_competitors: int = 0
    total_queries: int = 0
    unique_keywords: int = 0
    created_at: datetime


class SemstormMatchedPageResponse(BaseModel):
    page_id: int
    url: str
    title: str | None = None
    match_signals: list[str] = Field(default_factory=list)


class SemstormGscSummaryResponse(BaseModel):
    clicks: int
    impressions: int
    ctr: float | None = None
    avg_position: float | None = None


class SemstormOpportunitySeedItemResponse(BaseModel):
    keyword: str
    competitor_count: int
    best_position: int | None = None
    max_traffic: int = 0
    max_volume: int = 0
    avg_cpc: float | None = None
    bucket: Literal["quick_win", "core_opportunity", "watchlist"]
    decision_type: Literal["create_new_page", "expand_existing_page", "monitor_only"]
    opportunity_score_v1: int
    opportunity_score_v2: int
    coverage_status: Literal["missing", "weak_coverage", "covered"]
    coverage_score_v1: int
    matched_pages_count: int = 0
    best_match_page: SemstormMatchedPageResponse | None = None
    gsc_signal_status: Literal["none", "weak", "present"]
    gsc_summary: SemstormGscSummaryResponse | None = None
    state_status: Literal["new", "accepted", "dismissed", "promoted"] = "new"
    state_note: str | None = None
    can_promote: bool = False
    can_dismiss: bool = False
    can_accept: bool = False
    sample_competitors: list[str] = Field(default_factory=list)


class SemstormOpportunitySeedsResponse(BaseModel):
    site_id: int
    run_id: int
    source_domain: str
    active_crawl_id: int | None = None
    summary: SemstormOpportunitySeedsSummaryResponse
    items: list[SemstormOpportunitySeedItemResponse] = Field(default_factory=list)


class SemstormOpportunityActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: int | None = Field(default=None, ge=1)
    keywords: list[str] = Field(default_factory=list, min_length=1, max_length=200)
    note: str | None = None


class SemstormOpportunityActionSkippedItemResponse(BaseModel):
    keyword: str
    reason: str


class SemstormPromotedItemResponse(BaseModel):
    id: int
    site_id: int
    opportunity_key: str
    source_run_id: int
    keyword: str
    normalized_keyword: str
    bucket: Literal["quick_win", "core_opportunity", "watchlist"]
    decision_type: Literal["create_new_page", "expand_existing_page", "monitor_only"]
    opportunity_score_v2: int
    coverage_status: Literal["missing", "weak_coverage", "covered"]
    best_match_page_url: str | None = None
    gsc_signal_status: Literal["none", "weak", "present"]
    promotion_status: Literal["active", "archived"]
    has_plan: bool = False
    plan_id: int | None = None
    plan_state_status: Literal["planned", "in_progress", "done", "archived"] | None = None
    created_at: datetime
    updated_at: datetime


class SemstormOpportunityActionResponse(BaseModel):
    action: Literal["accept", "dismiss", "promote"]
    site_id: int
    run_id: int
    note: str | None = None
    requested_count: int = 0
    updated_count: int = 0
    promoted_count: int = 0
    state_status: Literal["accepted", "dismissed", "promoted"]
    updated_keywords: list[str] = Field(default_factory=list)
    promoted_items: list[SemstormPromotedItemResponse] = Field(default_factory=list)
    skipped_count: int = 0
    skipped: list[SemstormOpportunityActionSkippedItemResponse] = Field(default_factory=list)


class SemstormPromotedItemsSummaryResponse(BaseModel):
    total_items: int = 0
    promotion_status_counts: dict[str, int] = Field(default_factory=dict)


class SemstormPromotedItemsResponse(BaseModel):
    site_id: int
    summary: SemstormPromotedItemsSummaryResponse
    items: list[SemstormPromotedItemResponse] = Field(default_factory=list)


class SemstormCreatePlanDefaultsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_page_type: Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"] | None = None


class SemstormCreatePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    promoted_item_ids: list[int] = Field(default_factory=list, min_length=1, max_length=200)
    defaults: SemstormCreatePlanDefaultsRequest | None = None


class SemstormCreatePlanSkippedItemResponse(BaseModel):
    promoted_item_id: int
    keyword: str | None = None
    reason: str


class SemstormPlanItemResponse(BaseModel):
    id: int
    site_id: int
    promoted_item_id: int
    keyword: str
    normalized_keyword: str
    source_run_id: int
    state_status: Literal["planned", "in_progress", "done", "archived"]
    decision_type_snapshot: Literal["create_new_page", "expand_existing_page", "monitor_only"]
    bucket_snapshot: Literal["quick_win", "core_opportunity", "watchlist"]
    coverage_status_snapshot: Literal["missing", "weak_coverage", "covered"]
    opportunity_score_v2_snapshot: int
    best_match_page_url_snapshot: str | None = None
    gsc_signal_status_snapshot: Literal["none", "weak", "present"]
    plan_title: str | None = None
    plan_note: str | None = None
    target_page_type: Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"]
    proposed_slug: str | None = None
    proposed_primary_keyword: str | None = None
    proposed_secondary_keywords: list[str] = Field(default_factory=list)
    has_brief: bool = False
    brief_id: int | None = None
    brief_state_status: Literal["draft", "ready", "in_execution", "completed", "archived"] | None = None
    created_at: datetime
    updated_at: datetime


class SemstormCreatePlanResponse(BaseModel):
    site_id: int
    requested_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    items: list[SemstormPlanItemResponse] = Field(default_factory=list)
    skipped: list[SemstormCreatePlanSkippedItemResponse] = Field(default_factory=list)


class SemstormPlanItemsSummaryResponse(BaseModel):
    total_count: int = 0
    state_counts: dict[str, int] = Field(default_factory=dict)
    target_page_type_counts: dict[str, int] = Field(default_factory=dict)


class SemstormPlanItemsResponse(BaseModel):
    site_id: int
    summary: SemstormPlanItemsSummaryResponse
    items: list[SemstormPlanItemResponse] = Field(default_factory=list)


class SemstormPlanStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_status: Literal["planned", "in_progress", "done", "archived"]


class SemstormPlanUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_status: Literal["planned", "in_progress", "done", "archived"] | None = None
    plan_title: str | None = None
    plan_note: str | None = None
    target_page_type: Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"] | None = None
    proposed_slug: str | None = None
    proposed_primary_keyword: str | None = None
    proposed_secondary_keywords: list[str] | None = None


class SemstormCreateBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_item_ids: list[int] = Field(default_factory=list, min_length=1, max_length=200)


class SemstormCreateBriefSkippedItemResponse(BaseModel):
    plan_item_id: int
    brief_title: str | None = None
    reason: str


class SemstormBriefListItemResponse(BaseModel):
    id: int
    site_id: int
    plan_item_id: int
    brief_title: str | None = None
    primary_keyword: str
    brief_type: Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"]
    search_intent: Literal["informational", "commercial", "transactional", "navigational", "mixed"]
    state_status: Literal["draft", "ready", "in_execution", "completed", "archived"]
    execution_status: Literal["draft", "ready", "in_execution", "completed", "archived"]
    assignee: str | None = None
    execution_note: str | None = None
    ready_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    archived_at: datetime | None = None
    implementation_status: Literal["too_early", "implemented", "evaluated", "archived"] | None = None
    implemented_at: datetime | None = None
    last_outcome_checked_at: datetime | None = None
    recommended_page_title: str | None = None
    proposed_url_slug: str | None = None
    decision_type_snapshot: Literal["create_new_page", "expand_existing_page", "monitor_only"] | None = None
    bucket_snapshot: Literal["quick_win", "core_opportunity", "watchlist"] | None = None
    coverage_status_snapshot: Literal["missing", "weak_coverage", "covered"] | None = None
    gsc_signal_status_snapshot: Literal["none", "weak", "present"] | None = None
    opportunity_score_v2_snapshot: int = 0
    created_at: datetime
    updated_at: datetime


class SemstormBriefItemResponse(SemstormBriefListItemResponse):
    secondary_keywords: list[str] = Field(default_factory=list)
    target_url_existing: str | None = None
    implementation_url_override: str | None = None
    evaluation_note: str | None = None
    recommended_h1: str | None = None
    content_goal: str | None = None
    angle_summary: str | None = None
    sections: list[str] = Field(default_factory=list)
    internal_link_targets: list[str] = Field(default_factory=list)
    source_notes: list[str] = Field(default_factory=list)


class SemstormCreateBriefResponse(BaseModel):
    site_id: int
    requested_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    items: list[SemstormBriefItemResponse] = Field(default_factory=list)
    skipped: list[SemstormCreateBriefSkippedItemResponse] = Field(default_factory=list)


class SemstormBriefItemsSummaryResponse(BaseModel):
    total_count: int = 0
    state_counts: dict[str, int] = Field(default_factory=dict)
    brief_type_counts: dict[str, int] = Field(default_factory=dict)
    intent_counts: dict[str, int] = Field(default_factory=dict)


class SemstormBriefItemsResponse(BaseModel):
    site_id: int
    summary: SemstormBriefItemsSummaryResponse
    items: list[SemstormBriefListItemResponse] = Field(default_factory=list)


class SemstormBriefStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_status: Literal["draft", "ready", "in_execution", "completed", "archived"]


class SemstormBriefExecutionStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_status: Literal["draft", "ready", "in_execution", "completed", "archived"]


class SemstormBriefUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_status: Literal["draft", "ready", "in_execution", "completed", "archived"] | None = None
    brief_title: str | None = None
    brief_type: Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"] | None = None
    primary_keyword: str | None = None
    secondary_keywords: list[str] | None = None
    search_intent: Literal["informational", "commercial", "transactional", "navigational", "mixed"] | None = None
    target_url_existing: str | None = None
    proposed_url_slug: str | None = None
    recommended_page_title: str | None = None
    recommended_h1: str | None = None
    content_goal: str | None = None
    angle_summary: str | None = None
    sections: list[str] | None = None
    internal_link_targets: list[str] | None = None
    source_notes: list[str] | None = None


class SemstormBriefExecutionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee: str | None = None
    execution_note: str | None = None


class SemstormBriefImplementationStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    implementation_status: Literal["implemented", "archived"]
    evaluation_note: str | None = None
    implementation_url_override: str | None = None


class SemstormExecutionItemResponse(BaseModel):
    brief_id: int
    plan_item_id: int
    brief_title: str | None = None
    primary_keyword: str
    brief_type: Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"]
    search_intent: Literal["informational", "commercial", "transactional", "navigational", "mixed"]
    execution_status: Literal["draft", "ready", "in_execution", "completed", "archived"]
    assignee: str | None = None
    execution_note: str | None = None
    implementation_status: Literal["too_early", "implemented", "evaluated", "archived"] | None = None
    implemented_at: datetime | None = None
    recommended_page_title: str | None = None
    proposed_url_slug: str | None = None
    ready_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    archived_at: datetime | None = None
    decision_type_snapshot: Literal["create_new_page", "expand_existing_page", "monitor_only"] | None = None
    bucket_snapshot: Literal["quick_win", "core_opportunity", "watchlist"] | None = None
    coverage_status_snapshot: Literal["missing", "weak_coverage", "covered"] | None = None
    gsc_signal_status_snapshot: Literal["none", "weak", "present"] | None = None
    opportunity_score_v2_snapshot: int = 0
    updated_at: datetime


class SemstormExecutionSummaryResponse(BaseModel):
    total_count: int = 0
    execution_status_counts: dict[str, int] = Field(default_factory=dict)
    ready_count: int = 0
    in_execution_count: int = 0
    completed_count: int = 0


class SemstormExecutionItemsResponse(BaseModel):
    site_id: int
    summary: SemstormExecutionSummaryResponse
    items: list[SemstormExecutionItemResponse] = Field(default_factory=list)


class SemstormImplementedItemResponse(BaseModel):
    brief_id: int
    plan_item_id: int
    brief_title: str | None = None
    primary_keyword: str
    brief_type: Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"]
    execution_status: Literal["draft", "ready", "in_execution", "completed", "archived"]
    implementation_status: Literal["too_early", "implemented", "evaluated", "archived"]
    implemented_at: datetime | None = None
    evaluation_note: str | None = None
    implementation_url_override: str | None = None
    outcome_status: Literal["too_early", "no_signal", "weak_signal", "positive_signal"]
    page_present_in_active_crawl: bool
    matched_page: SemstormMatchedPageResponse | None = None
    gsc_signal_status: Literal["none", "weak", "present"]
    gsc_summary: SemstormGscSummaryResponse | None = None
    query_match_count: int = 0
    notes: list[str] = Field(default_factory=list)
    decision_type_snapshot: Literal["create_new_page", "expand_existing_page", "monitor_only"] | None = None
    coverage_status_snapshot: Literal["missing", "weak_coverage", "covered"] | None = None
    opportunity_score_v2_snapshot: int = 0
    updated_at: datetime
    last_outcome_checked_at: datetime | None = None


class SemstormImplementedSummaryResponse(BaseModel):
    total_count: int = 0
    implementation_status_counts: dict[str, int] = Field(default_factory=dict)
    outcome_status_counts: dict[str, int] = Field(default_factory=dict)
    too_early_count: int = 0
    positive_signal_count: int = 0


class SemstormImplementedItemsResponse(BaseModel):
    site_id: int
    active_crawl_id: int | None = None
    window_days: int
    summary: SemstormImplementedSummaryResponse
    items: list[SemstormImplementedItemResponse] = Field(default_factory=list)


class SemstormBriefEnrichmentSuggestionsResponse(BaseModel):
    improved_brief_title: str | None = None
    improved_page_title: str | None = None
    improved_h1: str | None = None
    improved_angle_summary: str | None = None
    improved_sections: list[str] = Field(default_factory=list)
    improved_internal_link_targets: list[str] = Field(default_factory=list)
    editorial_notes: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class SemstormBriefEnrichmentRunResponse(BaseModel):
    id: int
    site_id: int
    brief_item_id: int
    status: Literal["completed", "failed"]
    engine_mode: Literal["mock", "llm"]
    model_name: str | None = None
    input_hash: str
    suggestions: SemstormBriefEnrichmentSuggestionsResponse
    error_code: str | None = None
    error_message_safe: str | None = None
    is_applied: bool = False
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SemstormBriefEnrichmentRunsSummaryResponse(BaseModel):
    total_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    applied_count: int = 0


class SemstormBriefEnrichmentRunsResponse(BaseModel):
    site_id: int
    brief_id: int
    summary: SemstormBriefEnrichmentRunsSummaryResponse
    items: list[SemstormBriefEnrichmentRunResponse] = Field(default_factory=list)


class SemstormBriefEnrichmentApplyResponse(BaseModel):
    site_id: int
    brief_id: int
    run_id: int
    applied: bool
    skipped_reason: str | None = None
    applied_fields: list[str] = Field(default_factory=list)
    brief: SemstormBriefItemResponse
    enrichment_run: SemstormBriefEnrichmentRunResponse
