from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.gsc import GscDateRangeLabel


CompetitiveGapType = Literal["NEW_TOPIC", "EXPAND_EXISTING_TOPIC", "MISSING_SUPPORTING_PAGE"]
CompetitiveGapDetailType = Literal[
    "NEW_TOPIC",
    "EXPAND_EXISTING_PAGE",
    "MISSING_SUPPORTING_CONTENT",
    "MISSING_MONEY_PAGE",
    "INTENT_MISMATCH",
    "FORMAT_GAP",
    "GEO_GAP",
]
CompetitiveGapSegment = Literal["create_new_page", "expand_existing_page", "strengthen_cluster"]
SemanticOwnMatchStatus = Literal["exact_match", "semantic_match", "partial_coverage", "no_meaningful_match"]
SemanticCoverageType = Literal[
    "exact_coverage",
    "strong_semantic_coverage",
    "partial_coverage",
    "wrong_intent_coverage",
    "commercial_missing_supporting",
    "informational_missing_commercial",
    "no_meaningful_coverage",
]
SiteCompetitorReviewStatus = Literal["accepted", "rejected"]
CompetitiveGapDiagnosticFlag = Literal["strategy", "active_crawl", "competitors", "competitor_pages", "competitor_extractions", "own_pages"]
CompetitiveGapEmptyStateReason = Literal[
    "no_active_crawl",
    "no_competitors",
    "no_competitor_pages",
    "no_competitor_extractions",
    "no_own_pages",
    "filters_excluded_all",
]
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


class NormalizedCompetitiveGapStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["competitive_gap_strategy_v1"] = "competitive_gap_strategy_v1"
    business_summary: str = Field(min_length=1, max_length=280)
    target_audiences: list[str] = Field(default_factory=list)
    primary_goals: list[str] = Field(default_factory=list)
    priority_topics: list[str] = Field(default_factory=list)
    supporting_topics: list[str] = Field(default_factory=list)
    priority_page_types: list[PageType] = Field(default_factory=list)
    geographic_focus: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    differentiation_points: list[str] = Field(default_factory=list)


class CompetitiveGapStrategyUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_user_input: str = Field(min_length=1)
    normalized_strategy_json: NormalizedCompetitiveGapStrategy | None = None


class CompetitiveGapStrategyResponse(BaseModel):
    id: int
    site_id: int
    raw_user_input: str
    normalized_strategy_json: NormalizedCompetitiveGapStrategy | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    prompt_version: str | None = None
    normalization_status: str
    last_normalization_attempt_at: datetime | None = None
    normalization_fallback_used: bool = False
    normalization_debug_code: str | None = None
    normalization_debug_message: str | None = None
    normalized_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SiteCompetitorCreateRequest(BaseModel):
    root_url: str = Field(min_length=1)
    label: str | None = None
    notes: str | None = None
    is_active: bool = True


class SiteCompetitorUpdateRequest(BaseModel):
    root_url: str | None = None
    label: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class SiteCompetitorSyncSummaryResponse(BaseModel):
    visited_urls_count: int = 0
    stored_pages_count: int = 0
    extracted_pages_count: int = 0
    skipped_urls_count: int = 0
    skipped_non_html_count: int = 0
    skipped_non_indexable_count: int = 0
    skipped_out_of_scope_count: int = 0
    skipped_filtered_count: int = 0
    skipped_low_value_count: int = 0
    skipped_duplicate_url_count: int = 0
    skipped_fetch_error_count: int = 0
    extraction_created_count: int = 0
    extraction_skipped_unchanged_count: int = 0
    extraction_failed_count: int = 0
    sample_urls_by_reason: dict[str, list[str]] = Field(default_factory=dict)


class SiteCompetitorSyncRunResponse(BaseModel):
    id: int
    site_id: int
    competitor_id: int
    run_id: int
    status: str
    stage: str
    trigger_source: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None
    error_code: str | None = None
    error_message_safe: str | None = None
    summary_json: SiteCompetitorSyncSummaryResponse = Field(default_factory=SiteCompetitorSyncSummaryResponse)
    retry_of_run_id: int | None = None
    processed_urls: int
    url_limit: int
    processed_extraction_pages: int
    total_extractable_pages: int
    progress_percent: int
    created_at: datetime
    updated_at: datetime


class ContentGapReviewRunResponse(BaseModel):
    id: int
    site_id: int
    basis_crawl_job_id: int
    run_id: int
    status: str
    stage: str
    trigger_source: str
    scope_type: str
    selected_candidate_ids_json: list[int] = Field(default_factory=list)
    candidate_count: int
    candidate_set_hash: str
    candidate_generation_version: str
    own_context_hash: str
    gsc_context_hash: str | None = None
    context_summary_json: dict[str, Any] = Field(default_factory=dict)
    output_language: str
    llm_provider: str | None = None
    llm_model: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    batch_size: int
    batch_count: int
    completed_batch_count: int
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    error_message_safe: str | None = None
    retry_of_run_id: int | None = None
    created_at: datetime
    updated_at: datetime


class SiteCompetitorSemanticSummaryResponse(BaseModel):
    semantic_candidates_count: int = 0
    semantic_llm_jobs_count: int = 0
    semantic_resolved_count: int = 0
    semantic_cache_hits: int = 0
    semantic_fallback_count: int = 0
    merge_pairs_count: int = 0
    own_match_pairs_count: int = 0
    batch_size: int = 0
    cluster_count: int = 0
    low_confidence_count: int = 0
    semantic_cards_count: int = 0
    own_page_profiles_count: int = 0
    canonical_pages_count: int = 0
    duplicate_pages_count: int = 0
    near_duplicate_pages_count: int = 0
    semantic_version: str | None = None
    cluster_version: str | None = None
    coverage_version: str | None = None


class SiteCompetitorSemanticRunResponse(BaseModel):
    id: int
    site_id: int
    competitor_id: int
    run_id: int
    status: str
    stage: str
    trigger_source: str
    mode: str
    active_crawl_id: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None
    error_code: str | None = None
    error_message_safe: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    prompt_version: str | None = None
    source_candidate_ids: list[int] = Field(default_factory=list)
    summary_json: SiteCompetitorSemanticSummaryResponse = Field(default_factory=SiteCompetitorSemanticSummaryResponse)
    progress_percent: int
    created_at: datetime
    updated_at: datetime


class SiteCompetitorResponse(BaseModel):
    id: int
    site_id: int
    label: str
    root_url: str
    domain: str
    is_active: bool
    notes: str | None = None
    last_sync_run_id: int
    last_sync_status: str
    last_sync_stage: str
    last_sync_started_at: datetime | None = None
    last_sync_finished_at: datetime | None = None
    last_sync_error_code: str | None = None
    last_sync_error: str | None = None
    last_sync_processed_urls: int
    last_sync_url_limit: int
    last_sync_processed_extraction_pages: int
    last_sync_total_extractable_pages: int
    last_sync_progress_percent: int
    last_sync_summary: SiteCompetitorSyncSummaryResponse = Field(default_factory=SiteCompetitorSyncSummaryResponse)
    pages_count: int
    accepted_pages_count: int = 0
    rejected_pages_count: int = 0
    extracted_pages_count: int
    last_extracted_at: datetime | None = None
    semantic_status: str
    semantic_analysis_mode: str = "not_started"
    last_semantic_stage: str | None = None
    last_semantic_run_started_at: datetime | None = None
    last_semantic_run_finished_at: datetime | None = None
    last_semantic_heartbeat_at: datetime | None = None
    last_semantic_lease_expires_at: datetime | None = None
    last_semantic_error_code: str | None = None
    last_semantic_error: str | None = None
    semantic_candidates_count: int
    semantic_run_scope_candidates_count: int = 0
    semantic_llm_jobs_count: int
    semantic_resolved_count: int
    semantic_run_scope_resolved_count: int = 0
    semantic_progress_percent: int = 0
    semantic_cache_hits: int
    semantic_fallback_count: int
    semantic_llm_merged_urls_count: int = 0
    semantic_cluster_count: int = 0
    semantic_low_confidence_count: int = 0
    semantic_cards_count: int = 0
    semantic_own_page_profiles_count: int = 0
    semantic_canonical_pages_count: int = 0
    semantic_duplicate_pages_count: int = 0
    semantic_near_duplicate_pages_count: int = 0
    semantic_version: str | None = None
    semantic_cluster_version: str | None = None
    semantic_coverage_version: str | None = None
    semantic_model: str | None = None
    semantic_prompt_version: str | None = None
    created_at: datetime
    updated_at: datetime


class SiteCompetitorSyncAllResponse(BaseModel):
    site_id: int
    queued_competitor_ids: list[int]
    already_running_competitor_ids: list[int] = Field(default_factory=list)
    queued_count: int
    queued_runs: list[SiteCompetitorSyncRunResponse] = Field(default_factory=list)


class SiteCompetitorReviewSummaryResponse(BaseModel):
    total_pages: int = 0
    accepted_pages: int = 0
    rejected_pages: int = 0
    current_extractions_count: int = 0
    counts_by_reason: dict[str, int] = Field(default_factory=dict)


class SiteCompetitorReviewRecordResponse(BaseModel):
    id: int
    url: str
    normalized_url: str
    final_url: str | None = None
    status_code: int | None = None
    title: str | None = None
    meta_description: str | None = None
    h1: str | None = None
    page_type: PageType
    page_bucket: str
    page_type_confidence: float
    semantic_eligible: bool
    semantic_exclusion_reason: str | None = None
    review_status: SiteCompetitorReviewStatus
    review_reason_code: str
    review_reason_detail: str
    has_current_extraction: bool = False
    current_extraction_topic_label: str | None = None
    current_extraction_confidence: float | None = None
    last_extracted_at: datetime | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime | None = None
    updated_at: datetime


class PaginatedSiteCompetitorReviewResponse(BaseModel):
    site_id: int
    competitor_id: int
    review_status: SiteCompetitorReviewStatus | Literal["all"] = "all"
    summary: SiteCompetitorReviewSummaryResponse = Field(default_factory=SiteCompetitorReviewSummaryResponse)
    items: list[SiteCompetitorReviewRecordResponse] = Field(default_factory=list)
    page: int
    page_size: int
    total_items: int
    total_pages: int


class CompetitiveGapSemanticRerunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["incremental", "full"] = "incremental"
    active_crawl_id: int | None = Field(default=None, ge=1)


class CompetitiveGapSemanticRerunResponse(BaseModel):
    site_id: int
    mode: Literal["incremental", "full"]
    active_crawl_id: int | None = None
    queued_competitor_ids: list[int] = Field(default_factory=list)
    already_running_competitor_ids: list[int] = Field(default_factory=list)
    skipped_competitor_ids: list[int] = Field(default_factory=list)
    queued_count: int
    queued_runs: list[SiteCompetitorSemanticRunResponse] = Field(default_factory=list)


class CompetitiveGapCompetitorExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["competitive_gap_competitor_extraction_v2"] = "competitive_gap_competitor_extraction_v2"
    primary_topic: str = Field(min_length=1, max_length=255)
    topic_labels: list[str] = Field(default_factory=list, max_length=8)
    core_problem: str = Field(min_length=1, max_length=280)
    dominant_intent: Literal["informational", "commercial", "transactional", "navigational", "mixed", "other"]
    secondary_intents: list[str] = Field(default_factory=list, max_length=4)
    page_role: Literal["money_page", "supporting_page", "hub_page", "trust_page", "utility_page", "other"]
    content_format: Literal[
        "service_page",
        "landing_page",
        "blog_article",
        "blog_index",
        "faq",
        "category",
        "product",
        "location",
        "about",
        "contact",
        "legal",
        "utility",
        "other",
    ]
    target_audience: str | None = Field(default=None, max_length=280)
    entities: list[str] = Field(default_factory=list, max_length=10)
    geo_scope: str | None = Field(default=None, max_length=280)
    supporting_subtopics: list[str] = Field(default_factory=list, max_length=8)
    what_this_page_is_about: str = Field(min_length=1, max_length=280)
    what_this_page_is_not_about: str = Field(min_length=1, max_length=280)
    commerciality: Literal["low", "medium", "high", "neutral"]
    evidence_snippets: list[str] = Field(default_factory=list, max_length=4)
    confidence: float = Field(ge=0.0, le=1.0)


class CompetitiveGapSemanticDiagnosticsResponse(BaseModel):
    semantic_version: str | None = None
    cluster_version: str | None = None
    coverage_version: str | None = None
    competitor_semantic_cards_count: int = 0
    own_page_semantic_profiles_count: int = 0
    canonical_pages_count: int = 0
    duplicate_pages_count: int = 0
    near_duplicate_pages_count: int = 0
    clusters_count: int = 0
    low_confidence_clusters_count: int = 0
    latest_failure_stage: str | None = None
    latest_failure_error_code: str | None = None
    latest_failure_error_message: str | None = None
    coverage_breakdown: dict[SemanticCoverageType, int] = Field(default_factory=dict)


class CompetitiveGapCanonicalizationSummaryResponse(BaseModel):
    canonical_pages_count: int = 0
    duplicate_pages_count: int = 0
    near_duplicate_pages_count: int = 0
    filtered_leftovers_count: int = 0


class CompetitiveGapClusterQualitySummaryResponse(BaseModel):
    clusters_count: int = 0
    low_confidence_clusters_count: int = 0
    average_cluster_confidence: float = 0.0
    average_cluster_member_count: float = 0.0


class CompetitiveGapCrawlContextResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    root_url: str | None = None


class CompetitiveGapContextResponse(BaseModel):
    site_id: int
    site_domain: str
    active_crawl_id: int | None = None
    basis_crawl_job_id: int | None = None
    gsc_date_range: GscDateRangeLabel
    active_crawl: CompetitiveGapCrawlContextResponse | None = None
    strategy_present: bool
    active_competitor_count: int
    data_readiness: "CompetitiveGapDataReadinessResponse"
    data_source_mode: Literal["legacy", "raw_candidates", "reviewed"] = "legacy"
    is_outdated_for_active_crawl: bool = False
    review_run_status: str | None = None
    semantic_diagnostics: CompetitiveGapSemanticDiagnosticsResponse = Field(
        default_factory=CompetitiveGapSemanticDiagnosticsResponse
    )
    empty_state_reason: CompetitiveGapEmptyStateReason | None = None


class CompetitiveGapDataReadinessResponse(BaseModel):
    has_active_crawl: bool
    has_strategy: bool
    has_active_competitors: bool
    gap_ready: bool
    missing_inputs: list[CompetitiveGapDiagnosticFlag] = Field(default_factory=list)
    active_competitors_count: int
    competitors_with_pages_count: int
    competitors_with_current_extractions_count: int
    total_competitor_pages_count: int
    total_current_extractions_count: int


class CompetitiveGapRowResponse(BaseModel):
    gap_key: str
    semantic_cluster_key: str
    gap_type: CompetitiveGapType
    segment: CompetitiveGapSegment
    topic_key: str
    topic_label: str
    canonical_topic_label: str | None = None
    merged_topic_count: int = 0
    own_match_status: SemanticOwnMatchStatus | None = None
    coverage_type: SemanticCoverageType | None = None
    coverage_confidence: float | None = None
    coverage_rationale: str | None = None
    coverage_best_own_urls: list[str] = Field(default_factory=list)
    mismatch_notes: list[str] = Field(default_factory=list)
    own_match_source: str | None = None
    gap_detail_type: CompetitiveGapDetailType | None = None
    target_page_id: int | None = None
    target_url: str | None = None
    page_type: PageType
    target_page_type: PageType | None = None
    suggested_page_type: PageType | None = None
    cluster_member_count: int = 0
    cluster_confidence: float | None = None
    cluster_intent_profile: str | None = None
    cluster_role_summary: dict[str, int] = Field(default_factory=dict)
    cluster_entities: list[str] = Field(default_factory=list)
    cluster_geo_scope: str | None = None
    supporting_evidence: list[str] = Field(default_factory=list)
    competitor_ids: list[int]
    competitor_count: int
    competitor_urls: list[str]
    consensus_score: int
    competitor_coverage_score: int
    own_coverage_score: int
    strategy_alignment_score: int
    business_value_score: int
    priority_score: int
    confidence: float
    rationale: str
    signals: dict[str, Any]
    decision_action: Literal["keep", "remove", "merge", "rewrite"] | None = None
    reviewed_phrase: str | None = None
    reviewed_topic_label: str | None = None
    fit_score: float | None = None
    remove_reason_text: str | None = None
    merge_target_phrase: str | None = None


class CompetitiveGapExplanationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gap_key: str = Field(min_length=1)
    active_crawl_id: int = Field(ge=1)
    gsc_date_range: GscDateRangeLabel = "last_28_days"
    gap_signature: str | None = None


class CompetitiveGapExplanationResponse(BaseModel):
    gap_key: str
    gap_signature: str
    semantic_cluster_key: str | None = None
    canonical_topic_label: str | None = None
    merged_topic_count: int | None = None
    own_match_status: SemanticOwnMatchStatus | None = None
    own_match_source: str | None = None
    explanation: str
    bullets: list[str]
    used_llm: bool
    fallback_used: bool
    fallback_reason: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    prompt_version: str


class CompetitiveGapSummaryResponse(BaseModel):
    total_gaps: int
    high_priority_gaps: int
    competitors_considered: int
    topics_covered: int
    counts_by_type: dict[CompetitiveGapType, int]
    counts_by_gap_detail_type: dict[CompetitiveGapDetailType, int] = Field(default_factory=dict)
    counts_by_coverage_type: dict[SemanticCoverageType, int] = Field(default_factory=dict)
    counts_by_page_type: dict[PageType, int]
    canonicalization_summary: CompetitiveGapCanonicalizationSummaryResponse = Field(
        default_factory=CompetitiveGapCanonicalizationSummaryResponse
    )
    cluster_quality_summary: CompetitiveGapClusterQualitySummaryResponse = Field(
        default_factory=CompetitiveGapClusterQualitySummaryResponse
    )


class PaginatedCompetitiveGapResponse(BaseModel):
    context: CompetitiveGapContextResponse
    summary: CompetitiveGapSummaryResponse
    items: list[CompetitiveGapRowResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
