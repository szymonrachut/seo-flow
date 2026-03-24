from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.text_processing import collapse_whitespace, normalize_text_for_hash
from app.db.models import (
    Page,
    Site,
    SiteCompetitor,
    SiteCompetitorSemanticCandidate,
    SiteCompetitorSemanticDecision,
    SiteCompetitorSemanticRun,
)
from app.db.session import SessionLocal
from app.integrations.openai.client import OpenAiConfigurationError, OpenAiIntegrationError, OpenAiLlmClient
from app.services import (
    competitive_gap_semantic_run_service,
    competitive_gap_semantic_service,
    priority_service,
    site_service,
)
from app.services.competitive_gap_language_service import output_language_instruction
from app.services.competitive_gap_semantic_card_service import CLUSTER_VERSION, COVERAGE_VERSION, SEMANTIC_CARD_VERSION
from app.services.seo_analysis import build_page_records


logger = logging.getLogger(__name__)

SEMANTIC_ARBITER_PROMPT_VERSION = "competitive-gap-semantic-arbiter-v1"
SEMANTIC_ARBITER_COMPLETION_LIMITS = (1200, 1800)
SEMANTIC_TOP_K_LIMIT = 10
AMBIGUOUS_CONFIDENCE_THRESHOLD = 0.6
MERGE_DECISION_TYPE = "merge"
OWN_MATCH_DECISION_TYPE = "own_match"
MERGE_NO_CANDIDATES_LABEL = "different_topic"
OWN_MATCH_NO_CANDIDATES_LABEL = "no_meaningful_match"


class CompetitiveGapSemanticArbiterError(RuntimeError):
    def __init__(self, message: str, *, code: str = "semantic_arbiter_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class SemanticRunPlan:
    site_id: int
    competitor_id: int
    mode: str
    active_crawl_id: int | None
    source_candidate_ids: list[int]


@dataclass(slots=True)
class SemanticArbiterRunResult:
    site_id: int
    competitor_id: int
    active_crawl_id: int | None
    source_candidate_ids: list[int]
    semantic_candidates_count: int
    semantic_llm_jobs_count: int
    semantic_resolved_count: int
    semantic_cache_hits: int
    semantic_fallback_count: int
    merge_pairs_count: int
    own_match_pairs_count: int
    batch_size: int
    cluster_count: int
    low_confidence_count: int
    semantic_cards_count: int
    own_page_profiles_count: int
    canonical_pages_count: int
    duplicate_pages_count: int
    near_duplicate_pages_count: int
    semantic_version: str | None
    cluster_version: str | None
    coverage_version: str | None
    llm_provider: str | None
    llm_model: str | None
    prompt_version: str

    def to_summary_payload(self) -> dict[str, Any]:
        return {
            "semantic_candidates_count": self.semantic_candidates_count,
            "semantic_llm_jobs_count": self.semantic_llm_jobs_count,
            "semantic_resolved_count": self.semantic_resolved_count,
            "semantic_cache_hits": self.semantic_cache_hits,
            "semantic_fallback_count": self.semantic_fallback_count,
            "merge_pairs_count": self.merge_pairs_count,
            "own_match_pairs_count": self.own_match_pairs_count,
            "batch_size": self.batch_size,
            "cluster_count": self.cluster_count,
            "low_confidence_count": self.low_confidence_count,
            "semantic_cards_count": self.semantic_cards_count,
            "own_page_profiles_count": self.own_page_profiles_count,
            "canonical_pages_count": self.canonical_pages_count,
            "duplicate_pages_count": self.duplicate_pages_count,
            "near_duplicate_pages_count": self.near_duplicate_pages_count,
            "semantic_version": self.semantic_version,
            "cluster_version": self.cluster_version,
            "coverage_version": self.coverage_version,
        }


@dataclass(slots=True)
class _StageCounters:
    cache_hits: int = 0
    llm_jobs: int = 0
    fallback_count: int = 0
    pair_count: int = 0


class _MergeDecisionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_index: int = Field(ge=1, le=SEMANTIC_TOP_K_LIMIT)
    relation: Literal["same_topic", "related_subtopic", "different_topic"]
    confidence: float = Field(ge=0.0, le=1.0)
    merge_rationale: str = Field(min_length=1, max_length=280)


class _MergeArbiterOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_topic_label: str = Field(min_length=1, max_length=255)
    decisions: list[_MergeDecisionItem] = Field(default_factory=list, max_length=SEMANTIC_TOP_K_LIMIT)


class _OwnMatchDecisionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_index: int = Field(ge=1, le=SEMANTIC_TOP_K_LIMIT)
    relation: Literal["exact_match", "semantic_match", "partial_coverage", "no_meaningful_match"]
    confidence: float = Field(ge=0.0, le=1.0)
    match_rationale: str = Field(min_length=1, max_length=280)


class _OwnMatchArbiterOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_topic_label: str = Field(min_length=1, max_length=255)
    decisions: list[_OwnMatchDecisionItem] = Field(default_factory=list, max_length=SEMANTIC_TOP_K_LIMIT)


def queue_site_semantic_rerun(
    session: Session,
    site_id: int,
    *,
    mode: str,
    active_crawl_id: int | None = None,
) -> dict[str, Any]:
    normalized_mode = _normalize_mode(mode)
    _get_site_or_raise(session, site_id)
    resolved_active_crawl_id = _resolve_active_crawl_id(session, site_id, active_crawl_id)
    competitors = session.scalars(
        select(SiteCompetitor)
        .where(
            SiteCompetitor.site_id == site_id,
            SiteCompetitor.is_active.is_(True),
        )
        .order_by(SiteCompetitor.id.asc())
    ).all()
    if not competitors:
        raise CompetitiveGapSemanticArbiterError(
            f"Site {site_id} has no active competitors for semantic matching.",
            code="no_competitors",
        )

    queued_runs: list[dict[str, Any]] = []
    queued_ids: list[int] = []
    already_running_ids: list[int] = []
    skipped_ids: list[int] = []
    for competitor in competitors:
        try:
            foundation_refresh = competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
                session,
                site_id,
                competitor.id,
            )
            queued_run = queue_competitor_semantic_run(
                session,
                site_id=site_id,
                competitor_id=competitor.id,
                mode=normalized_mode,
                active_crawl_id=resolved_active_crawl_id,
                trigger_source=f"manual_{normalized_mode}",
                preferred_candidate_ids=list(foundation_refresh.changed_candidate_ids or []),
            )
        except CompetitiveGapSemanticArbiterError as exc:
            if exc.code == "already_running":
                already_running_ids.append(competitor.id)
                continue
            if exc.code == "no_semantic_work":
                skipped_ids.append(competitor.id)
                continue
            raise
        queued_runs.append(queued_run)
        queued_ids.append(competitor.id)

    if not queued_runs:
        raise CompetitiveGapSemanticArbiterError(
            "No competitors have pending semantic work for the requested rerun.",
            code="no_semantic_work",
        )

    return {
        "site_id": site_id,
        "mode": normalized_mode,
        "active_crawl_id": resolved_active_crawl_id,
        "queued_competitor_ids": queued_ids,
        "already_running_competitor_ids": already_running_ids,
        "skipped_competitor_ids": skipped_ids,
        "queued_count": len(queued_ids),
        "queued_runs": queued_runs,
    }


def queue_competitor_semantic_run(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    mode: str,
    active_crawl_id: int | None,
    trigger_source: str,
    preferred_candidate_ids: list[int] | None = None,
) -> dict[str, Any]:
    plan = build_semantic_run_plan(
        session,
        site_id=site_id,
        competitor_id=competitor_id,
        mode=mode,
        active_crawl_id=active_crawl_id,
        preferred_candidate_ids=preferred_candidate_ids,
    )
    if not plan.source_candidate_ids:
        raise CompetitiveGapSemanticArbiterError(
            "No semantic candidates require processing for this competitor.",
            code="no_semantic_work",
        )

    llm_model = get_settings().openai_model_competitor_merge
    try:
        return competitive_gap_semantic_run_service.queue_semantic_run(
            session,
            site_id=site_id,
            competitor_id=competitor_id,
            trigger_source=trigger_source,
            mode=plan.mode,
            active_crawl_id=plan.active_crawl_id,
            source_candidate_ids=plan.source_candidate_ids,
            llm_provider=OpenAiLlmClient.provider_name,
            llm_model=llm_model,
            prompt_version=SEMANTIC_ARBITER_PROMPT_VERSION,
        )
    except competitive_gap_semantic_run_service.CompetitiveGapSemanticRunServiceError as exc:
        raise CompetitiveGapSemanticArbiterError(str(exc), code=exc.code) from exc


def run_site_competitor_semantic_task(
    site_id: int,
    competitor_id: int,
    run_id: int,
    output_language: str = "en",
) -> None:
    with SessionLocal() as session:
        if not competitive_gap_semantic_run_service.claim_semantic_run(
            session,
            site_id=site_id,
            competitor_id=competitor_id,
            run_id=run_id,
        ):
            return

        try:
            result = run_competitor_semantic_arbiter(
                session,
                site_id=site_id,
                competitor_id=competitor_id,
                semantic_run_id=run_id,
                persist_progress=True,
                output_language=output_language,
            )
        except Exception as exc:  # pragma: no cover - defensive background fallback
            session.rollback()
            error_code, error_message = _normalize_semantic_error(exc)
            competitive_gap_semantic_run_service.fail_semantic_run(
                site_id,
                competitor_id,
                run_id,
                error_code=error_code,
                error_message_safe=error_message,
                summary_payload=competitive_gap_semantic_run_service.build_empty_semantic_summary_payload(),
                llm_provider=OpenAiLlmClient.provider_name,
                llm_model=get_settings().openai_model_competitor_merge,
                prompt_version=SEMANTIC_ARBITER_PROMPT_VERSION,
            )
            return

    competitive_gap_semantic_run_service.complete_semantic_run(
        site_id,
        competitor_id,
        run_id,
        summary_payload=result.to_summary_payload(),
        llm_provider=result.llm_provider,
        llm_model=result.llm_model,
        prompt_version=result.prompt_version,
    )


def run_competitor_semantic_arbiter(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    mode: str | None = None,
    active_crawl_id: int | None = None,
    source_candidate_ids: list[int] | None = None,
    semantic_run_id: int | None = None,
    persist_progress: bool = False,
    client: OpenAiLlmClient | None = None,
    output_language: str = "en",
) -> SemanticArbiterRunResult:
    run_row = _load_semantic_run(session, site_id=site_id, competitor_id=competitor_id, run_id=semantic_run_id)
    resolved_mode = _normalize_mode(mode or (run_row.mode if run_row is not None else "incremental"))
    preferred_candidate_ids = source_candidate_ids or (
        [int(candidate_id) for candidate_id in (run_row.source_candidate_ids_json or [])]
        if run_row is not None
        else []
    )
    resolved_active_crawl_id = (
        active_crawl_id
        if active_crawl_id is not None
        else (run_row.active_crawl_id if run_row is not None else None)
    )
    plan = build_semantic_run_plan(
        session,
        site_id=site_id,
        competitor_id=competitor_id,
        mode=resolved_mode,
        active_crawl_id=resolved_active_crawl_id,
        preferred_candidate_ids=preferred_candidate_ids,
    )

    llm_provider = OpenAiLlmClient.provider_name
    llm_model = get_settings().openai_model_competitor_merge
    if not plan.source_candidate_ids:
        return SemanticArbiterRunResult(
            site_id=site_id,
            competitor_id=competitor_id,
            active_crawl_id=plan.active_crawl_id,
            source_candidate_ids=[],
            semantic_candidates_count=0,
            semantic_llm_jobs_count=0,
            semantic_resolved_count=0,
            semantic_cache_hits=0,
            semantic_fallback_count=0,
            merge_pairs_count=0,
            own_match_pairs_count=0,
            batch_size=0,
            cluster_count=0,
            low_confidence_count=0,
            semantic_cards_count=0,
            own_page_profiles_count=0,
            canonical_pages_count=0,
            duplicate_pages_count=0,
            near_duplicate_pages_count=0,
            semantic_version=SEMANTIC_CARD_VERSION,
            cluster_version=CLUSTER_VERSION,
            coverage_version=COVERAGE_VERSION,
            llm_provider=llm_provider,
            llm_model=llm_model,
            prompt_version=SEMANTIC_ARBITER_PROMPT_VERSION,
        )

    source_candidates = _load_source_candidates(session, plan.source_candidate_ids)
    if len(source_candidates) != len(plan.source_candidate_ids):
        raise CompetitiveGapSemanticArbiterError(
            "Semantic run references missing source candidates.",
            code="missing_candidates",
        )
    source_candidates_by_id = {candidate.id: candidate for candidate in source_candidates}

    merge_groups = competitive_gap_semantic_service.list_competitor_merge_candidates(
        session,
        site_id,
        source_candidate_ids=plan.source_candidate_ids,
        limit=SEMANTIC_TOP_K_LIMIT,
    )
    merge_groups_by_source_id = {group.source_candidate_id: group for group in merge_groups}

    own_groups_by_source_id: dict[int, competitive_gap_semantic_service.OwnSiteMatchCandidateGroup] = {}
    own_page_records_by_id: dict[int, dict[str, Any]] = {}
    merge_counters = _StageCounters()
    own_counters = _StageCounters()
    resolved_count = 0
    resolved_client = client or OpenAiLlmClient()

    def _build_progress_summary_payload() -> dict[str, Any]:
        return {
            "semantic_candidates_count": len(plan.source_candidate_ids),
            "semantic_llm_jobs_count": merge_counters.llm_jobs + own_counters.llm_jobs,
            "semantic_resolved_count": resolved_count,
            "semantic_cache_hits": merge_counters.cache_hits + own_counters.cache_hits,
            "semantic_fallback_count": merge_counters.fallback_count + own_counters.fallback_count,
            "merge_pairs_count": merge_counters.pair_count,
            "own_match_pairs_count": own_counters.pair_count,
            "batch_size": len(plan.source_candidate_ids),
            "cluster_count": 0,
            "low_confidence_count": 0,
            "semantic_cards_count": len(plan.source_candidate_ids),
            "own_page_profiles_count": len(own_page_records_by_id),
            "canonical_pages_count": len(plan.source_candidate_ids),
            "duplicate_pages_count": 0,
            "near_duplicate_pages_count": 0,
            "semantic_version": SEMANTIC_CARD_VERSION,
            "cluster_version": CLUSTER_VERSION,
            "coverage_version": COVERAGE_VERSION,
        }

    def _touch_progress(stage: str) -> None:
        if not persist_progress or semantic_run_id is None:
            return
        competitive_gap_semantic_run_service.touch_semantic_run(
            session,
            site_id=site_id,
            competitor_id=competitor_id,
            run_id=semantic_run_id,
            stage=stage,
            summary_payload=_build_progress_summary_payload(),
            llm_provider=llm_provider,
            llm_model=llm_model,
            prompt_version=SEMANTIC_ARBITER_PROMPT_VERSION,
        )

    if persist_progress and semantic_run_id is not None:
        _touch_progress("prepare_candidates")

    if plan.active_crawl_id is not None:
        _touch_progress("own_semantic_profiling")
        own_groups = competitive_gap_semantic_service.list_own_site_match_candidates(
            session,
            site_id,
            plan.active_crawl_id,
            source_candidate_ids=plan.source_candidate_ids,
            limit=SEMANTIC_TOP_K_LIMIT,
        )
        own_groups_by_source_id = {group.source_candidate_id: group for group in own_groups}
        own_page_records_by_id = _load_own_page_records_by_id(session, plan.active_crawl_id)

    for index, source_candidate_id in enumerate(plan.source_candidate_ids, start=1):
        source_candidate = source_candidates_by_id[source_candidate_id]
        merge_group = merge_groups_by_source_id.get(source_candidate_id)
        _touch_progress("merge_topics")
        merge_stage = _resolve_merge_stage(
            session,
            source_candidate=source_candidate,
            group=merge_group,
            use_cache=plan.mode == "incremental",
            client=resolved_client,
            llm_model=llm_model,
            output_language=output_language,
        )
        merge_counters.cache_hits += merge_stage.cache_hits
        merge_counters.llm_jobs += merge_stage.llm_jobs
        merge_counters.fallback_count += merge_stage.fallback_count
        merge_counters.pair_count += merge_stage.pair_count

        _touch_progress("canonicalization")
        _touch_progress("cluster_to_own_match")
        own_stage = _resolve_own_match_stage(
            session,
            source_candidate=source_candidate,
            active_crawl_id=plan.active_crawl_id,
            group=own_groups_by_source_id.get(source_candidate_id),
            own_page_records_by_id=own_page_records_by_id,
            use_cache=plan.mode == "incremental",
            client=resolved_client,
            llm_model=llm_model,
            output_language=output_language,
        )
        own_counters.cache_hits += own_stage.cache_hits
        own_counters.llm_jobs += own_stage.llm_jobs
        own_counters.fallback_count += own_stage.fallback_count
        own_counters.pair_count += own_stage.pair_count
        resolved_count += 1

        if index == len(plan.source_candidate_ids):
            _touch_progress("cluster_build")
            _touch_progress("final_synthesis")

    session.flush()
    return SemanticArbiterRunResult(
        site_id=site_id,
        competitor_id=competitor_id,
        active_crawl_id=plan.active_crawl_id,
        source_candidate_ids=list(plan.source_candidate_ids),
        semantic_candidates_count=len(plan.source_candidate_ids),
        semantic_llm_jobs_count=merge_counters.llm_jobs + own_counters.llm_jobs,
        semantic_resolved_count=resolved_count,
        semantic_cache_hits=merge_counters.cache_hits + own_counters.cache_hits,
        semantic_fallback_count=merge_counters.fallback_count + own_counters.fallback_count,
        merge_pairs_count=merge_counters.pair_count,
        own_match_pairs_count=own_counters.pair_count,
        batch_size=len(plan.source_candidate_ids),
        cluster_count=0,
        low_confidence_count=0,
        semantic_cards_count=len(plan.source_candidate_ids),
        own_page_profiles_count=len(own_page_records_by_id),
        canonical_pages_count=len(plan.source_candidate_ids),
        duplicate_pages_count=0,
        near_duplicate_pages_count=0,
        semantic_version=SEMANTIC_CARD_VERSION,
        cluster_version=CLUSTER_VERSION,
        coverage_version=COVERAGE_VERSION,
        llm_provider=llm_provider,
        llm_model=llm_model,
        prompt_version=SEMANTIC_ARBITER_PROMPT_VERSION,
    )


def build_semantic_run_plan(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    mode: str,
    active_crawl_id: int | None,
    preferred_candidate_ids: list[int] | None = None,
) -> SemanticRunPlan:
    normalized_mode = _normalize_mode(mode)
    resolved_active_crawl_id = _resolve_active_crawl_id(session, site_id, active_crawl_id)
    source_candidates = session.scalars(
        select(SiteCompetitorSemanticCandidate)
        .where(
            SiteCompetitorSemanticCandidate.site_id == site_id,
            SiteCompetitorSemanticCandidate.competitor_id == competitor_id,
            SiteCompetitorSemanticCandidate.current.is_(True),
        )
        .order_by(SiteCompetitorSemanticCandidate.id.asc())
    ).all()
    if not source_candidates:
        return SemanticRunPlan(
            site_id=site_id,
            competitor_id=competitor_id,
            mode=normalized_mode,
            active_crawl_id=resolved_active_crawl_id,
            source_candidate_ids=[],
        )

    current_candidate_ids = {candidate.id for candidate in source_candidates}
    if normalized_mode == "full":
        return SemanticRunPlan(
            site_id=site_id,
            competitor_id=competitor_id,
            mode=normalized_mode,
            active_crawl_id=resolved_active_crawl_id,
            source_candidate_ids=sorted(current_candidate_ids),
        )

    candidate_ids: set[int] = {
        int(candidate_id)
        for candidate_id in preferred_candidate_ids or []
        if int(candidate_id) in current_candidate_ids
    }
    for candidate in source_candidates:
        if _candidate_has_ambiguous_or_missing_work(
            session,
            site_id=site_id,
            candidate=candidate,
            active_crawl_id=resolved_active_crawl_id,
        ):
            candidate_ids.add(candidate.id)
    return SemanticRunPlan(
        site_id=site_id,
        competitor_id=competitor_id,
        mode=normalized_mode,
        active_crawl_id=resolved_active_crawl_id,
        source_candidate_ids=sorted(candidate_ids),
    )


def _candidate_has_ambiguous_or_missing_work(
    session: Session,
    *,
    site_id: int,
    candidate: SiteCompetitorSemanticCandidate,
    active_crawl_id: int | None,
) -> bool:
    merge_group = competitive_gap_semantic_service.list_competitor_merge_candidates(
        session,
        site_id,
        source_candidate_ids=[candidate.id],
        limit=SEMANTIC_TOP_K_LIMIT,
    )
    if _decision_group_requires_work(
        session,
        source_candidate=candidate,
        decision_type=MERGE_DECISION_TYPE,
        group=merge_group[0] if merge_group else None,
        active_crawl_id=None,
    ):
        return True

    own_page_records_by_id: dict[int, dict[str, Any]] = {}
    own_group = None
    if active_crawl_id is not None:
        own_groups = competitive_gap_semantic_service.list_own_site_match_candidates(
            session,
            site_id,
            active_crawl_id,
            source_candidate_ids=[candidate.id],
            limit=SEMANTIC_TOP_K_LIMIT,
        )
        own_group = own_groups[0] if own_groups else None
        own_page_records_by_id = _load_own_page_records_by_id(session, active_crawl_id)
    return _decision_group_requires_work(
        session,
        source_candidate=candidate,
        decision_type=OWN_MATCH_DECISION_TYPE,
        group=own_group,
        active_crawl_id=active_crawl_id,
        own_page_records_by_id=own_page_records_by_id,
    )


def _decision_group_requires_work(
    session: Session,
    *,
    source_candidate: SiteCompetitorSemanticCandidate,
    decision_type: str,
    group: Any | None,
    active_crawl_id: int | None,
    own_page_records_by_id: dict[int, dict[str, Any]] | None = None,
) -> bool:
    if decision_type == MERGE_DECISION_TYPE:
        suggestions = list(group.candidates) if group is not None else []
        if not suggestions:
            row = _load_decision_by_key(session, _build_merge_no_candidates_key(source_candidate))
            return row is None or _decision_is_ambiguous(row) or row.source_semantic_input_hash != source_candidate.semantic_input_hash
        target_map = _load_target_candidate_map(session, suggestions)
        for suggestion in suggestions:
            row = _load_decision_by_key(session, _build_merge_decision_key(source_candidate, suggestion))
            target_candidate = target_map.get(suggestion.candidate_id)
            if (
                row is None
                or target_candidate is None
                or not _merge_row_matches_candidates(row, source_candidate, target_candidate)
                or _decision_is_ambiguous(row)
            ):
                return True
        return False

    suggestions = list(group.candidates) if group is not None else []
    if not suggestions:
        row = _load_decision_by_key(session, _build_own_match_no_candidates_key(source_candidate, active_crawl_id))
        return row is None or _decision_is_ambiguous(row)
    for suggestion in suggestions:
        own_page_hash = _build_own_page_semantic_hash((own_page_records_by_id or {}).get(suggestion.page_id, {}))
        row = _load_decision_by_key(
            session,
            _build_own_match_decision_key(
                source_candidate,
                suggestion.page_id,
                active_crawl_id=active_crawl_id,
                own_page_hash=own_page_hash,
            ),
        )
        if row is None or _decision_is_ambiguous(row):
            return True
    return False


def _resolve_merge_stage(
    session: Session,
    *,
    source_candidate: SiteCompetitorSemanticCandidate,
    group: competitive_gap_semantic_service.CompetitorMergeCandidateGroup | None,
    use_cache: bool,
    client: OpenAiLlmClient,
    llm_model: str,
    output_language: str,
) -> _StageCounters:
    counters = _StageCounters()
    suggestions = list(group.candidates) if group is not None else []
    counters.pair_count = len(suggestions) if suggestions else 1

    if not suggestions:
        row = _load_decision_by_key(session, _build_merge_no_candidates_key(source_candidate))
        if (
            use_cache
            and row is not None
            and row.source_semantic_input_hash == source_candidate.semantic_input_hash
            and row.prompt_version == SEMANTIC_ARBITER_PROMPT_VERSION
            and not _decision_is_ambiguous(row)
        ):
            counters.cache_hits += 1
            return counters
        fallback = _fallback_merge_without_candidates(source_candidate)
        _upsert_semantic_decision(
            session,
            decision_key=_build_merge_no_candidates_key(source_candidate),
            site_id=source_candidate.site_id,
            source_candidate_id=source_candidate.id,
            source_competitor_id=source_candidate.competitor_id,
            decision_type=MERGE_DECISION_TYPE,
            source_semantic_input_hash=source_candidate.semantic_input_hash,
            target_candidate_id=None,
            target_competitor_id=None,
            target_semantic_input_hash=None,
            own_page_id=None,
            active_crawl_id=None,
            own_page_semantic_hash=None,
            candidate_rank=0,
            candidate_score=0,
            decision_label=fallback["decision_label"],
            canonical_topic_label=fallback["canonical_topic_label"],
            decision_rationale=fallback["decision_rationale"],
            confidence=fallback["confidence"],
            llm_provider=None,
            llm_model=None,
            prompt_version=SEMANTIC_ARBITER_PROMPT_VERSION,
            fallback_used=False,
            fallback_reason="no_candidates",
            debug_code=None,
            debug_message="No merge candidates available.",
        )
        return counters

    pending: list[competitive_gap_semantic_service.CompetitorMergeCandidateSuggestion] = []
    target_map = _load_target_candidate_map(session, suggestions)
    if use_cache:
        for suggestion in suggestions:
            cached = _load_decision_by_key(session, _build_merge_decision_key(source_candidate, suggestion))
            target_candidate = target_map.get(suggestion.candidate_id)
            if (
                cached is not None
                and target_candidate is not None
                and _merge_row_matches_candidates(cached, source_candidate, target_candidate)
                and not _decision_is_ambiguous(cached)
            ):
                counters.cache_hits += 1
            else:
                pending.append(suggestion)
    else:
        pending = list(suggestions)

    if not pending:
        return counters

    target_map = _load_target_candidate_map(session, pending)
    llm_output = _call_merge_arbiter_llm(
        source_candidate=source_candidate,
        suggestions=pending,
            target_map=target_map,
            client=client,
            llm_model=llm_model,
            output_language=output_language,
        )
    if llm_output["used_llm"]:
        counters.llm_jobs += 1
    if llm_output["fallback_used"]:
        counters.fallback_count += len(pending)

    for position, suggestion in enumerate(pending, start=1):
        target_candidate = target_map.get(suggestion.candidate_id)
        if target_candidate is None:
            continue
        decision = llm_output["decisions"].get(position) or _fallback_merge_pair(source_candidate, suggestion, target_candidate)
        ordered_source, ordered_target = _ordered_candidate_pair(source_candidate, target_candidate)
        _upsert_semantic_decision(
            session,
            decision_key=_build_merge_decision_key(source_candidate, suggestion),
            site_id=source_candidate.site_id,
            source_candidate_id=ordered_source.id,
            source_competitor_id=ordered_source.competitor_id,
            decision_type=MERGE_DECISION_TYPE,
            source_semantic_input_hash=ordered_source.semantic_input_hash,
            target_candidate_id=ordered_target.id,
            target_competitor_id=ordered_target.competitor_id,
            target_semantic_input_hash=ordered_target.semantic_input_hash,
            own_page_id=None,
            active_crawl_id=None,
            own_page_semantic_hash=None,
            candidate_rank=suggestion.shared_terms,
            candidate_score=suggestion.score,
            decision_label=decision["decision_label"],
            canonical_topic_label=llm_output["canonical_topic_label"] or decision["canonical_topic_label"],
            decision_rationale=decision["decision_rationale"],
            confidence=decision["confidence"],
            llm_provider=OpenAiLlmClient.provider_name if llm_output["used_llm"] else None,
            llm_model=llm_model if llm_output["used_llm"] else None,
            prompt_version=SEMANTIC_ARBITER_PROMPT_VERSION,
            fallback_used=decision["fallback_used"],
            fallback_reason=decision["fallback_reason"],
            debug_code=llm_output["debug_code"],
            debug_message=llm_output["debug_message"],
        )
    return counters


def _resolve_own_match_stage(
    session: Session,
    *,
    source_candidate: SiteCompetitorSemanticCandidate,
    active_crawl_id: int | None,
    group: competitive_gap_semantic_service.OwnSiteMatchCandidateGroup | None,
    own_page_records_by_id: dict[int, dict[str, Any]],
    use_cache: bool,
    client: OpenAiLlmClient,
    llm_model: str,
    output_language: str,
) -> _StageCounters:
    counters = _StageCounters()
    suggestions = list(group.candidates) if group is not None else []
    counters.pair_count = len(suggestions) if suggestions else 1

    if active_crawl_id is None:
        row = _load_decision_by_key(session, _build_own_match_no_candidates_key(source_candidate, None))
        if use_cache and row is not None and not _decision_is_ambiguous(row):
            counters.cache_hits += 1
            return counters
        fallback = _fallback_own_without_active_crawl(source_candidate)
        _upsert_semantic_decision(
            session,
            decision_key=_build_own_match_no_candidates_key(source_candidate, None),
            site_id=source_candidate.site_id,
            source_candidate_id=source_candidate.id,
            source_competitor_id=source_candidate.competitor_id,
            decision_type=OWN_MATCH_DECISION_TYPE,
            source_semantic_input_hash=source_candidate.semantic_input_hash,
            target_candidate_id=None,
            target_competitor_id=None,
            target_semantic_input_hash=None,
            own_page_id=None,
            active_crawl_id=None,
            own_page_semantic_hash=None,
            candidate_rank=0,
            candidate_score=0,
            decision_label=fallback["decision_label"],
            canonical_topic_label=fallback["canonical_topic_label"],
            decision_rationale=fallback["decision_rationale"],
            confidence=fallback["confidence"],
            llm_provider=None,
            llm_model=None,
            prompt_version=SEMANTIC_ARBITER_PROMPT_VERSION,
            fallback_used=True,
            fallback_reason="no_active_crawl",
            debug_code="no_active_crawl",
            debug_message="No active crawl was available for own-site semantic matching.",
        )
        counters.fallback_count += 1
        return counters

    if not suggestions:
        row = _load_decision_by_key(session, _build_own_match_no_candidates_key(source_candidate, active_crawl_id))
        if use_cache and row is not None and not _decision_is_ambiguous(row):
            counters.cache_hits += 1
            return counters
        fallback = _fallback_own_without_candidates(source_candidate)
        _upsert_semantic_decision(
            session,
            decision_key=_build_own_match_no_candidates_key(source_candidate, active_crawl_id),
            site_id=source_candidate.site_id,
            source_candidate_id=source_candidate.id,
            source_competitor_id=source_candidate.competitor_id,
            decision_type=OWN_MATCH_DECISION_TYPE,
            source_semantic_input_hash=source_candidate.semantic_input_hash,
            target_candidate_id=None,
            target_competitor_id=None,
            target_semantic_input_hash=None,
            own_page_id=None,
            active_crawl_id=active_crawl_id,
            own_page_semantic_hash=None,
            candidate_rank=0,
            candidate_score=0,
            decision_label=fallback["decision_label"],
            canonical_topic_label=fallback["canonical_topic_label"],
            decision_rationale=fallback["decision_rationale"],
            confidence=fallback["confidence"],
            llm_provider=None,
            llm_model=None,
            prompt_version=SEMANTIC_ARBITER_PROMPT_VERSION,
            fallback_used=False,
            fallback_reason="no_candidates",
            debug_code=None,
            debug_message="No own-site candidates available for semantic matching.",
        )
        return counters

    pending: list[competitive_gap_semantic_service.OwnSiteMatchCandidateSuggestion] = []
    own_page_hashes = {
        suggestion.page_id: _build_own_page_semantic_hash(own_page_records_by_id.get(suggestion.page_id, {}))
        for suggestion in suggestions
    }
    if use_cache:
        for suggestion in suggestions:
            cached = _load_decision_by_key(
                session,
                _build_own_match_decision_key(
                    source_candidate,
                    suggestion.page_id,
                    active_crawl_id=active_crawl_id,
                    own_page_hash=own_page_hashes.get(suggestion.page_id),
                ),
            )
            if cached is not None and not _decision_is_ambiguous(cached):
                counters.cache_hits += 1
            else:
                pending.append(suggestion)
    else:
        pending = list(suggestions)

    if not pending:
        return counters

    llm_output = _call_own_match_arbiter_llm(
        source_candidate=source_candidate,
        suggestions=pending,
            own_page_records_by_id=own_page_records_by_id,
            client=client,
            llm_model=llm_model,
            output_language=output_language,
        )
    if llm_output["used_llm"]:
        counters.llm_jobs += 1
    if llm_output["fallback_used"]:
        counters.fallback_count += len(pending)

    for position, suggestion in enumerate(pending, start=1):
        own_page_record = own_page_records_by_id.get(suggestion.page_id) or {}
        decision = llm_output["decisions"].get(position) or _fallback_own_pair(source_candidate, suggestion)
        own_page_hash = own_page_hashes.get(suggestion.page_id) or _build_own_page_semantic_hash(own_page_record)
        _upsert_semantic_decision(
            session,
            decision_key=_build_own_match_decision_key(
                source_candidate,
                suggestion.page_id,
                active_crawl_id=active_crawl_id,
                own_page_hash=own_page_hash,
            ),
            site_id=source_candidate.site_id,
            source_candidate_id=source_candidate.id,
            source_competitor_id=source_candidate.competitor_id,
            decision_type=OWN_MATCH_DECISION_TYPE,
            source_semantic_input_hash=source_candidate.semantic_input_hash,
            target_candidate_id=None,
            target_competitor_id=None,
            target_semantic_input_hash=None,
            own_page_id=suggestion.page_id,
            active_crawl_id=active_crawl_id,
            own_page_semantic_hash=own_page_hash,
            candidate_rank=suggestion.shared_terms,
            candidate_score=suggestion.score,
            decision_label=decision["decision_label"],
            canonical_topic_label=llm_output["canonical_topic_label"] or decision["canonical_topic_label"],
            decision_rationale=decision["decision_rationale"],
            confidence=decision["confidence"],
            llm_provider=OpenAiLlmClient.provider_name if llm_output["used_llm"] else None,
            llm_model=llm_model if llm_output["used_llm"] else None,
            prompt_version=SEMANTIC_ARBITER_PROMPT_VERSION,
            fallback_used=decision["fallback_used"],
            fallback_reason=decision["fallback_reason"],
            debug_code=llm_output["debug_code"],
            debug_message=llm_output["debug_message"],
        )
    return counters


def _call_merge_arbiter_llm(
    *,
    source_candidate: SiteCompetitorSemanticCandidate,
    suggestions: list[competitive_gap_semantic_service.CompetitorMergeCandidateSuggestion],
    target_map: dict[int, SiteCompetitorSemanticCandidate],
    client: OpenAiLlmClient,
    llm_model: str,
    output_language: str,
) -> dict[str, Any]:
    fallback = _fallback_merge_bundle(source_candidate, suggestions, target_map)
    if not client.is_available():
        return {
            "used_llm": False,
            "fallback_used": True,
            "debug_code": _resolve_unavailable_code(),
            "debug_message": _resolve_unavailable_message(),
            **fallback,
        }

    try:
        parsed = None
        for completion_limit in SEMANTIC_ARBITER_COMPLETION_LIMITS:
            try:
                parsed = client.parse_chat_completion(
                    model=llm_model,
                    system_prompt=_merge_system_prompt(output_language=output_language),
                    user_prompt=_merge_user_prompt(source_candidate, suggestions, target_map),
                    response_format=_MergeArbiterOutput,
                    max_completion_tokens=completion_limit,
                    reasoning_effort="minimal",
                )
                break
            except OpenAiIntegrationError as exc:
                if exc.code == "length_limit" and completion_limit != SEMANTIC_ARBITER_COMPLETION_LIMITS[-1]:
                    continue
                raise
    except (OpenAiConfigurationError, OpenAiIntegrationError) as exc:
        return {
            "used_llm": False,
            "fallback_used": True,
            "debug_code": exc.code,
            "debug_message": str(exc),
            **fallback,
        }

    if parsed is None:
        return {
            "used_llm": False,
            "fallback_used": True,
            "debug_code": "structured_output_missing",
            "debug_message": "Semantic merge arbiter returned no structured output.",
            **fallback,
        }

    decisions: dict[int, dict[str, Any]] = {}
    for item in parsed.decisions:
        decisions[item.candidate_index] = {
            "decision_label": item.relation,
            "canonical_topic_label": _normalize_canonical_label(parsed.canonical_topic_label, source_candidate),
            "decision_rationale": item.merge_rationale.strip(),
            "confidence": round(float(item.confidence), 2),
            "fallback_used": False,
            "fallback_reason": None,
        }
    return {
        "used_llm": True,
        "fallback_used": False,
        "debug_code": None,
        "debug_message": None,
        "canonical_topic_label": _normalize_canonical_label(parsed.canonical_topic_label, source_candidate),
        "decisions": decisions,
    }


def _call_own_match_arbiter_llm(
    *,
    source_candidate: SiteCompetitorSemanticCandidate,
    suggestions: list[competitive_gap_semantic_service.OwnSiteMatchCandidateSuggestion],
    own_page_records_by_id: dict[int, dict[str, Any]],
    client: OpenAiLlmClient,
    llm_model: str,
    output_language: str,
) -> dict[str, Any]:
    fallback = _fallback_own_bundle(source_candidate, suggestions)
    if not client.is_available():
        return {
            "used_llm": False,
            "fallback_used": True,
            "debug_code": _resolve_unavailable_code(),
            "debug_message": _resolve_unavailable_message(),
            **fallback,
        }

    try:
        parsed = None
        for completion_limit in SEMANTIC_ARBITER_COMPLETION_LIMITS:
            try:
                parsed = client.parse_chat_completion(
                    model=llm_model,
                    system_prompt=_own_match_system_prompt(output_language=output_language),
                    user_prompt=_own_match_user_prompt(source_candidate, suggestions, own_page_records_by_id),
                    response_format=_OwnMatchArbiterOutput,
                    max_completion_tokens=completion_limit,
                    reasoning_effort="minimal",
                )
                break
            except OpenAiIntegrationError as exc:
                if exc.code == "length_limit" and completion_limit != SEMANTIC_ARBITER_COMPLETION_LIMITS[-1]:
                    continue
                raise
    except (OpenAiConfigurationError, OpenAiIntegrationError) as exc:
        return {
            "used_llm": False,
            "fallback_used": True,
            "debug_code": exc.code,
            "debug_message": str(exc),
            **fallback,
        }

    if parsed is None:
        return {
            "used_llm": False,
            "fallback_used": True,
            "debug_code": "structured_output_missing",
            "debug_message": "Own-site semantic arbiter returned no structured output.",
            **fallback,
        }

    decisions: dict[int, dict[str, Any]] = {}
    for item in parsed.decisions:
        decisions[item.candidate_index] = {
            "decision_label": item.relation,
            "canonical_topic_label": _normalize_canonical_label(parsed.canonical_topic_label, source_candidate),
            "decision_rationale": item.match_rationale.strip(),
            "confidence": round(float(item.confidence), 2),
            "fallback_used": False,
            "fallback_reason": None,
        }
    return {
        "used_llm": True,
        "fallback_used": False,
        "debug_code": None,
        "debug_message": None,
        "canonical_topic_label": _normalize_canonical_label(parsed.canonical_topic_label, source_candidate),
        "decisions": decisions,
    }


def _merge_system_prompt(*, output_language: str) -> str:
    return (
        "You arbitrate semantic overlap between competitor content topics. "
        "Use only the provided deterministic payload. "
        "Page type and page bucket are helpful hints but never hard blockers. "
        "Return only JSON. Label each candidate as same_topic, related_subtopic, or different_topic. "
        "Return one canonical topic label for the source topic cluster. "
        f"{output_language_instruction(output_language)}"
    )


def _merge_user_prompt(
    source_candidate: SiteCompetitorSemanticCandidate,
    suggestions: list[competitive_gap_semantic_service.CompetitorMergeCandidateSuggestion],
    target_map: dict[int, SiteCompetitorSemanticCandidate],
) -> str:
    payload = {
        "prompt_version": SEMANTIC_ARBITER_PROMPT_VERSION,
        "task": "competitor_topic_merge",
        "source_topic": _serialize_source_candidate(source_candidate),
        "candidates": [
            {
                "candidate_index": index,
                "candidate": _serialize_target_candidate(target_map.get(suggestion.candidate_id)),
                "deterministic_signals": {
                    "score": suggestion.score,
                    "shared_primary_tokens": suggestion.shared_primary_tokens,
                    "shared_nonprimary_terms": suggestion.shared_nonprimary_terms,
                    "shared_terms": suggestion.shared_terms,
                    "exact_topic_key_match": suggestion.exact_topic_key_match,
                    "same_page_type": suggestion.same_page_type,
                    "same_page_bucket": suggestion.same_page_bucket,
                    "quality_bonus": suggestion.quality_bonus,
                },
            }
            for index, suggestion in enumerate(suggestions, start=1)
            if target_map.get(suggestion.candidate_id) is not None
        ],
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _own_match_system_prompt(*, output_language: str) -> str:
    return (
        "You arbitrate semantic overlap between a competitor topic and the site's own pages. "
        "Use only the provided deterministic payload. "
        "Page type is a helper signal only, never a hard blocker. "
        "Return only JSON. Label each own-page candidate as exact_match, semantic_match, partial_coverage, "
        "or no_meaningful_match. Return one canonical topic label for the source topic. "
        f"{output_language_instruction(output_language)}"
    )


def _own_match_user_prompt(
    source_candidate: SiteCompetitorSemanticCandidate,
    suggestions: list[competitive_gap_semantic_service.OwnSiteMatchCandidateSuggestion],
    own_page_records_by_id: dict[int, dict[str, Any]],
) -> str:
    payload = {
        "prompt_version": SEMANTIC_ARBITER_PROMPT_VERSION,
        "task": "competitor_to_own_match",
        "source_topic": _serialize_source_candidate(source_candidate),
        "candidates": [
            {
                "candidate_index": index,
                "own_page": _serialize_own_page_record(own_page_records_by_id.get(suggestion.page_id)),
                "deterministic_signals": {
                    "score": suggestion.score,
                    "shared_primary_tokens": suggestion.shared_primary_tokens,
                    "shared_nonprimary_terms": suggestion.shared_nonprimary_terms,
                    "shared_terms": suggestion.shared_terms,
                    "shared_anchor_terms": suggestion.shared_anchor_terms,
                    "exact_topic_key_match": suggestion.exact_topic_key_match,
                    "same_page_family": suggestion.same_page_family,
                    "same_intent": suggestion.same_intent,
                    "same_page_role": suggestion.same_page_role,
                    "semantic_alignment_score": suggestion.semantic_alignment_score,
                    "priority_score": suggestion.priority_score,
                    "impressions": suggestion.impressions,
                },
            }
            for index, suggestion in enumerate(suggestions, start=1)
            if own_page_records_by_id.get(suggestion.page_id) is not None
        ],
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _serialize_source_candidate(candidate: SiteCompetitorSemanticCandidate) -> dict[str, Any]:
    competitor_page = candidate.competitor_page
    return {
        "candidate_id": candidate.id,
        "url": competitor_page.normalized_url if competitor_page is not None else None,
        "raw_topic_key": candidate.raw_topic_key,
        "raw_topic_label": candidate.raw_topic_label,
        "primary_tokens": competitive_gap_semantic_service._candidate_primary_terms(candidate),
        "secondary_tokens": competitive_gap_semantic_service._candidate_secondary_terms(candidate),
        "page_type": candidate.page_type,
        "page_bucket": candidate.page_bucket,
        "quality_score": candidate.quality_score,
        "title": competitor_page.title if competitor_page is not None else None,
        "h1": competitor_page.h1 if competitor_page is not None else None,
        "meta_description": competitor_page.meta_description if competitor_page is not None else None,
        "dominant_intent_hint": competitive_gap_semantic_service._candidate_dominant_intent(candidate),
        "page_role_hint": competitive_gap_semantic_service._candidate_page_role(candidate),
    }


def _serialize_target_candidate(candidate: SiteCompetitorSemanticCandidate | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    competitor_page = candidate.competitor_page
    return {
        "candidate_id": candidate.id,
        "competitor_id": candidate.competitor_id,
        "url": competitor_page.normalized_url if competitor_page is not None else None,
        "raw_topic_key": candidate.raw_topic_key,
        "raw_topic_label": candidate.raw_topic_label,
        "primary_tokens": competitive_gap_semantic_service._candidate_primary_terms(candidate),
        "secondary_tokens": competitive_gap_semantic_service._candidate_secondary_terms(candidate),
        "page_type": candidate.page_type,
        "page_bucket": candidate.page_bucket,
        "quality_score": candidate.quality_score,
        "title": competitor_page.title if competitor_page is not None else None,
        "h1": competitor_page.h1 if competitor_page is not None else None,
    }


def _serialize_own_page_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not record:
        return None
    return {
        "page_id": record.get("page_id"),
        "normalized_url": record.get("normalized_url"),
        "title": record.get("title"),
        "h1": record.get("h1"),
        "meta_description": record.get("meta_description"),
        "page_type": record.get("page_type"),
        "page_bucket": record.get("page_bucket"),
        "dominant_intent_hint": record.get("dominant_intent_hint"),
        "page_role_hint": record.get("page_role_hint"),
        "topic_key": record.get("topic_key"),
        "topic_tokens": record.get("topic_tokens") or [],
        "priority_score": record.get("priority_score") or 0,
        "impressions": record.get("impressions") or 0,
    }


def _fallback_merge_bundle(
    source_candidate: SiteCompetitorSemanticCandidate,
    suggestions: list[competitive_gap_semantic_service.CompetitorMergeCandidateSuggestion],
    target_map: dict[int, SiteCompetitorSemanticCandidate],
) -> dict[str, Any]:
    decisions: dict[int, dict[str, Any]] = {}
    for index, suggestion in enumerate(suggestions, start=1):
        target_candidate = target_map.get(suggestion.candidate_id)
        if target_candidate is None:
            continue
        decisions[index] = _fallback_merge_pair(source_candidate, suggestion, target_candidate)
    return {
        "canonical_topic_label": _fallback_canonical_label(source_candidate),
        "decisions": decisions,
    }


def _fallback_own_bundle(
    source_candidate: SiteCompetitorSemanticCandidate,
    suggestions: list[competitive_gap_semantic_service.OwnSiteMatchCandidateSuggestion],
) -> dict[str, Any]:
    return {
        "canonical_topic_label": _fallback_canonical_label(source_candidate),
        "decisions": {
            index: _fallback_own_pair(source_candidate, suggestion)
            for index, suggestion in enumerate(suggestions, start=1)
        },
    }


def _fallback_merge_pair(
    source_candidate: SiteCompetitorSemanticCandidate,
    suggestion: competitive_gap_semantic_service.CompetitorMergeCandidateSuggestion,
    target_candidate: SiteCompetitorSemanticCandidate,
) -> dict[str, Any]:
    if suggestion.exact_topic_key_match or suggestion.shared_primary_tokens >= 2:
        decision_label = "same_topic"
        confidence = 0.84
    elif suggestion.shared_primary_tokens >= 1 or suggestion.shared_terms >= 2:
        decision_label = "related_subtopic"
        confidence = 0.66
    else:
        decision_label = "different_topic"
        confidence = 0.32
    return {
        "decision_label": decision_label,
        "canonical_topic_label": _fallback_canonical_label(source_candidate, target_candidate),
        "decision_rationale": (
            f"Fallback merge based on deterministic overlap: shared_primary={suggestion.shared_primary_tokens}, "
            f"shared_terms={suggestion.shared_terms}, exact_key_match={suggestion.exact_topic_key_match}."
        ),
        "confidence": confidence,
        "fallback_used": True,
        "fallback_reason": "deterministic_fallback",
    }


def _fallback_own_pair(
    source_candidate: SiteCompetitorSemanticCandidate,
    suggestion: competitive_gap_semantic_service.OwnSiteMatchCandidateSuggestion,
) -> dict[str, Any]:
    if suggestion.exact_topic_key_match:
        decision_label = "exact_match"
        confidence = 0.9
    elif (
        suggestion.shared_primary_tokens >= 2
        or suggestion.shared_anchor_terms >= 2
        or (suggestion.semantic_alignment_score >= 0.62 and suggestion.same_intent)
        or suggestion.shared_terms >= 3
    ):
        decision_label = "semantic_match"
        confidence = 0.76
    elif (
        suggestion.shared_primary_tokens >= 1
        or suggestion.shared_anchor_terms >= 1
        or suggestion.same_page_role
        or suggestion.semantic_alignment_score >= 0.42
        or suggestion.shared_terms >= 2
    ):
        decision_label = "partial_coverage"
        confidence = 0.58
    else:
        decision_label = "no_meaningful_match"
        confidence = 0.28
    return {
        "decision_label": decision_label,
        "canonical_topic_label": _fallback_canonical_label(source_candidate),
        "decision_rationale": (
            f"Fallback own-match based on deterministic overlap: shared_primary={suggestion.shared_primary_tokens}, "
            f"shared_anchor={suggestion.shared_anchor_terms}, shared_terms={suggestion.shared_terms}, "
            f"semantic_alignment={suggestion.semantic_alignment_score}, "
            f"exact_key_match={suggestion.exact_topic_key_match}."
        ),
        "confidence": confidence,
        "fallback_used": True,
        "fallback_reason": "deterministic_fallback",
    }


def _fallback_merge_without_candidates(source_candidate: SiteCompetitorSemanticCandidate) -> dict[str, Any]:
    return {
        "decision_label": MERGE_NO_CANDIDATES_LABEL,
        "canonical_topic_label": _fallback_canonical_label(source_candidate),
        "decision_rationale": "No merge candidates were available for this source topic.",
        "confidence": 1.0,
    }


def _fallback_own_without_candidates(source_candidate: SiteCompetitorSemanticCandidate) -> dict[str, Any]:
    return {
        "decision_label": OWN_MATCH_NO_CANDIDATES_LABEL,
        "canonical_topic_label": _fallback_canonical_label(source_candidate),
        "decision_rationale": "No own-site candidates were available for this source topic.",
        "confidence": 1.0,
    }


def _fallback_own_without_active_crawl(source_candidate: SiteCompetitorSemanticCandidate) -> dict[str, Any]:
    return {
        "decision_label": OWN_MATCH_NO_CANDIDATES_LABEL,
        "canonical_topic_label": _fallback_canonical_label(source_candidate),
        "decision_rationale": "No active crawl was available, so own-site semantic matching was skipped.",
        "confidence": 1.0,
    }


def _fallback_canonical_label(
    source_candidate: SiteCompetitorSemanticCandidate,
    target_candidate: SiteCompetitorSemanticCandidate | None = None,
) -> str:
    labels = [
        collapse_whitespace(source_candidate.raw_topic_label),
        collapse_whitespace(target_candidate.raw_topic_label if target_candidate is not None else None),
    ]
    cleaned = [label for label in labels if label]
    if cleaned:
        return min(cleaned, key=lambda value: (len(value), value.lower()))
    raw_topic_key = source_candidate.raw_topic_key or (target_candidate.raw_topic_key if target_candidate is not None else None) or "topic"
    return " ".join(part.capitalize() for part in raw_topic_key.split("-") if part)


def _normalize_canonical_label(value: str | None, source_candidate: SiteCompetitorSemanticCandidate) -> str:
    label = collapse_whitespace(value)
    if label:
        return label[:255]
    return _fallback_canonical_label(source_candidate)[:255]


def _decision_is_ambiguous(decision: SiteCompetitorSemanticDecision) -> bool:
    if bool(decision.fallback_used):
        return True
    if decision.confidence is None:
        return True
    return float(decision.confidence) < AMBIGUOUS_CONFIDENCE_THRESHOLD


def _merge_row_matches_candidates(
    row: SiteCompetitorSemanticDecision,
    source_candidate: SiteCompetitorSemanticCandidate,
    target_candidate: SiteCompetitorSemanticCandidate,
) -> bool:
    ordered_source, ordered_target = _ordered_candidate_pair(source_candidate, target_candidate)
    return (
        row.source_candidate_id == ordered_source.id
        and row.target_candidate_id == ordered_target.id
        and row.source_semantic_input_hash == ordered_source.semantic_input_hash
        and row.target_semantic_input_hash == ordered_target.semantic_input_hash
        and row.prompt_version == SEMANTIC_ARBITER_PROMPT_VERSION
    )


def _build_merge_decision_key(
    source_candidate: SiteCompetitorSemanticCandidate,
    suggestion: competitive_gap_semantic_service.CompetitorMergeCandidateSuggestion,
) -> str:
    left_id = min(source_candidate.id, suggestion.candidate_id)
    right_id = max(source_candidate.id, suggestion.candidate_id)
    return _hash_payload(
        {
            "decision_type": MERGE_DECISION_TYPE,
            "left_candidate_id": left_id,
            "right_candidate_id": right_id,
            "prompt_version": SEMANTIC_ARBITER_PROMPT_VERSION,
        }
    )


def _build_merge_no_candidates_key(source_candidate: SiteCompetitorSemanticCandidate) -> str:
    return _hash_payload(
        {
            "decision_type": MERGE_DECISION_TYPE,
            "source_candidate_id": source_candidate.id,
            "source_hash": source_candidate.semantic_input_hash,
            "no_candidates": True,
            "prompt_version": SEMANTIC_ARBITER_PROMPT_VERSION,
        }
    )


def _build_own_match_decision_key(
    source_candidate: SiteCompetitorSemanticCandidate,
    own_page_id: int,
    *,
    active_crawl_id: int | None,
    own_page_hash: str | None,
) -> str:
    return _hash_payload(
        {
            "decision_type": OWN_MATCH_DECISION_TYPE,
            "source_candidate_id": source_candidate.id,
            "source_hash": source_candidate.semantic_input_hash,
            "own_page_id": own_page_id,
            "active_crawl_id": active_crawl_id,
            "own_page_hash": own_page_hash,
            "prompt_version": SEMANTIC_ARBITER_PROMPT_VERSION,
        }
    )


def _build_own_match_no_candidates_key(
    source_candidate: SiteCompetitorSemanticCandidate,
    active_crawl_id: int | None,
) -> str:
    return _hash_payload(
        {
            "decision_type": OWN_MATCH_DECISION_TYPE,
            "source_candidate_id": source_candidate.id,
            "source_hash": source_candidate.semantic_input_hash,
            "active_crawl_id": active_crawl_id,
            "no_candidates": True,
            "prompt_version": SEMANTIC_ARBITER_PROMPT_VERSION,
        }
    )


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _ordered_candidate_pair(
    source_candidate: SiteCompetitorSemanticCandidate,
    target_candidate: SiteCompetitorSemanticCandidate,
) -> tuple[SiteCompetitorSemanticCandidate, SiteCompetitorSemanticCandidate]:
    if source_candidate.id <= target_candidate.id:
        return source_candidate, target_candidate
    return target_candidate, source_candidate


def _load_target_candidate_map(
    session: Session,
    suggestions: list[competitive_gap_semantic_service.CompetitorMergeCandidateSuggestion],
) -> dict[int, SiteCompetitorSemanticCandidate]:
    candidate_ids = sorted({suggestion.candidate_id for suggestion in suggestions})
    rows = session.scalars(
        select(SiteCompetitorSemanticCandidate)
        .options(selectinload(SiteCompetitorSemanticCandidate.competitor_page))
        .where(SiteCompetitorSemanticCandidate.id.in_(candidate_ids))
    ).all()
    return {row.id: row for row in rows}


def _load_source_candidates(
    session: Session,
    source_candidate_ids: list[int],
) -> list[SiteCompetitorSemanticCandidate]:
    return session.scalars(
        select(SiteCompetitorSemanticCandidate)
        .options(selectinload(SiteCompetitorSemanticCandidate.competitor_page))
        .where(SiteCompetitorSemanticCandidate.id.in_(source_candidate_ids))
        .order_by(SiteCompetitorSemanticCandidate.id.asc())
    ).all()


def _load_own_page_records_by_id(session: Session, crawl_job_id: int) -> dict[int, dict[str, Any]]:
    page_rows = session.scalars(
        select(Page)
        .where(Page.crawl_job_id == crawl_job_id)
        .order_by(Page.id.asc())
    ).all()
    page_records = build_page_records(session, crawl_job_id)
    priority_service.apply_priority_metadata(page_records, gsc_date_range="last_28_days")
    page_record_map = {int(record["id"]): record for record in page_records}

    records: dict[int, dict[str, Any]] = {}
    for page in page_rows:
        topic_model = competitive_gap_semantic_service.materialize_page_semantic_topic(
            SiteCompetitorPageProxy.from_page(page)
        )
        record = page_record_map.get(page.id, {})
        records[page.id] = {
            "page_id": page.id,
            "normalized_url": page.normalized_url,
            "title": page.title,
            "h1": page.h1,
            "meta_description": page.meta_description,
            "page_type": page.page_type,
            "page_bucket": page.page_bucket,
            "dominant_intent_hint": "commercial" if str(page.page_bucket or "") == "commercial" else "informational",
            "page_role_hint": "money_page" if str(page.page_type or "") in competitive_gap_semantic_service.COMMERCIAL_PAGE_TYPES else "supporting_page",
            "topic_key": topic_model.raw_topic_key,
            "topic_tokens": topic_model.match_terms,
            "priority_score": int(record.get("priority_score") or 0),
            "impressions": int(record.get("impressions_28d") or 0),
            "content_text_hash": page.content_text_hash,
        }
    return records


def _build_own_page_semantic_hash(record: dict[str, Any]) -> str:
    if not record:
        return ""
    return _hash_payload(
        {
            "page_id": record.get("page_id"),
            "normalized_url": normalize_text_for_hash(record.get("normalized_url")),
            "title": normalize_text_for_hash(record.get("title")),
            "h1": normalize_text_for_hash(record.get("h1")),
            "page_type": normalize_text_for_hash(record.get("page_type")),
            "page_bucket": normalize_text_for_hash(record.get("page_bucket")),
            "topic_key": normalize_text_for_hash(record.get("topic_key")),
            "content_text_hash": normalize_text_for_hash(record.get("content_text_hash")),
        }
    )


def _load_decision_by_key(session: Session, decision_key: str) -> SiteCompetitorSemanticDecision | None:
    return session.scalars(
        select(SiteCompetitorSemanticDecision)
        .where(SiteCompetitorSemanticDecision.decision_key == decision_key)
        .limit(1)
    ).first()


def _upsert_semantic_decision(
    session: Session,
    *,
    decision_key: str,
    site_id: int,
    source_candidate_id: int,
    source_competitor_id: int,
    decision_type: str,
    source_semantic_input_hash: str,
    target_candidate_id: int | None,
    target_competitor_id: int | None,
    target_semantic_input_hash: str | None,
    own_page_id: int | None,
    active_crawl_id: int | None,
    own_page_semantic_hash: str | None,
    candidate_rank: int | None,
    candidate_score: int | None,
    decision_label: str,
    canonical_topic_label: str | None,
    decision_rationale: str | None,
    confidence: float | None,
    llm_provider: str | None,
    llm_model: str | None,
    prompt_version: str | None,
    fallback_used: bool,
    fallback_reason: str | None,
    debug_code: str | None,
    debug_message: str | None,
) -> SiteCompetitorSemanticDecision:
    row = _load_decision_by_key(session, decision_key)
    if row is None:
        row = SiteCompetitorSemanticDecision(
            decision_key=decision_key,
            site_id=site_id,
            source_candidate_id=source_candidate_id,
            source_competitor_id=source_competitor_id,
            decision_type=decision_type,
            source_semantic_input_hash=source_semantic_input_hash,
        )
        session.add(row)
    row.target_candidate_id = target_candidate_id
    row.target_competitor_id = target_competitor_id
    row.target_semantic_input_hash = target_semantic_input_hash
    row.own_page_id = own_page_id
    row.active_crawl_id = active_crawl_id
    row.own_page_semantic_hash = own_page_semantic_hash
    row.candidate_rank = candidate_rank
    row.candidate_score = candidate_score
    row.decision_label = decision_label[:64]
    row.canonical_topic_label = collapse_whitespace(canonical_topic_label) or None
    row.decision_rationale = decision_rationale or None
    row.confidence = round(float(confidence), 2) if confidence is not None else None
    row.llm_provider = llm_provider
    row.llm_model = llm_model
    row.prompt_version = prompt_version
    row.fallback_used = bool(fallback_used)
    row.fallback_reason = fallback_reason or None
    row.debug_code = debug_code or None
    row.debug_message = debug_message or None
    row.resolved_at = competitive_gap_semantic_service.utcnow()
    return row


def _resolve_active_crawl_id(session: Session, site_id: int, active_crawl_id: int | None) -> int | None:
    try:
        context = site_service.resolve_site_workspace_context(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
        )
    except site_service.SiteServiceError as exc:
        raise CompetitiveGapSemanticArbiterError(str(exc), code="active_crawl_mismatch") from exc
    active_crawl = context["active_crawl"]
    return int(active_crawl.id) if active_crawl is not None else None


def _load_semantic_run(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    run_id: int | None,
) -> SiteCompetitorSemanticRun | None:
    if run_id is None:
        return None
    return session.scalars(
        select(SiteCompetitorSemanticRun)
        .where(
            SiteCompetitorSemanticRun.site_id == site_id,
            SiteCompetitorSemanticRun.competitor_id == competitor_id,
            SiteCompetitorSemanticRun.run_id == run_id,
        )
        .limit(1)
    ).first()


def _normalize_mode(mode: str) -> str:
    normalized = str(mode or "incremental").strip().lower()
    if normalized not in {"incremental", "full"}:
        raise CompetitiveGapSemanticArbiterError(
            "Semantic rerun mode must be 'incremental' or 'full'.",
            code="invalid_mode",
        )
    return normalized


def _normalize_semantic_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, CompetitiveGapSemanticArbiterError):
        return exc.code, str(exc)
    if isinstance(exc, competitive_gap_semantic_run_service.CompetitiveGapSemanticRunServiceError):
        return exc.code, str(exc)
    return "semantic_unexpected_error", "Semantic matching failed due to an unexpected backend error."


def _get_site_or_raise(session: Session, site_id: int) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        raise CompetitiveGapSemanticArbiterError(f"Site {site_id} not found.", code="not_found")
    return site


def _resolve_unavailable_code() -> str:
    settings = get_settings()
    if not settings.openai_llm_enabled:
        return "llm_disabled"
    if not settings.openai_api_key:
        return "missing_api_key"
    return "llm_unavailable"


def _resolve_unavailable_message() -> str:
    settings = get_settings()
    if not settings.openai_llm_enabled:
        return "OpenAI semantic arbiter is disabled in backend config."
    if not settings.openai_api_key:
        return "OPENAI_API_KEY is missing in backend config."
    return "OpenAI semantic arbiter is currently unavailable."


class SiteCompetitorPageProxy:
    def __init__(self, page: Page) -> None:
        self.url = page.url
        self.normalized_url = page.normalized_url
        self.final_url = page.final_url
        self.status_code = page.status_code
        self.title = page.title
        self.meta_description = page.meta_description
        self.h1 = page.h1
        self.canonical_url = page.canonical_url
        self.content_type = page.content_type
        self.word_count = page.word_count
        self.visible_text = None
        self.content_text_hash = page.content_text_hash
        self.page_type = page.page_type
        self.page_bucket = page.page_bucket
        self.fetch_diagnostics_json = {
            "robots_meta": page.robots_meta,
            "x_robots_tag": page.x_robots_tag,
            "schema_count": page.schema_count,
            "schema_types": list(page.schema_types_json or []),
        }

    @classmethod
    def from_page(cls, page: Page) -> "SiteCompetitorPageProxy":
        return cls(page)
