from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from math import ceil
from typing import Any, Iterable, Literal
from urllib.parse import unquote, urlsplit

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.text_processing import collapse_whitespace, dedupe_preserve_order, normalize_text_for_hash, tokenize_topic_text
from app.db.models import (
    Page,
    SiteCompetitor,
    SiteCompetitorPage,
    SiteCompetitorPageExtraction,
    SiteCompetitorSemanticCandidate,
    SiteCompetitorSemanticDecision,
    SiteCompetitorSemanticRun,
    SiteContentGapCandidate,
    SiteContentGapItem,
    SiteContentGapReviewRun,
)
from app.schemas.competitive_gap import CompetitiveGapType, SemanticCoverageType, SemanticOwnMatchStatus
from app.services import (
    competitive_gap_cluster_state_service,
    competitive_gap_own_semantic_service,
    crawl_job_service,
    priority_service,
    site_content_strategy_service,
    site_service,
)
from app.services.competitive_gap_semantic_card_service import (
    CLUSTER_VERSION,
    COVERAGE_VERSION,
    OWN_PAGE_SEMANTIC_PROFILE_VERSION,
    SEMANTIC_CARD_VERSION,
    build_semantic_card,
    build_primary_topic_key,
    build_semantic_match_terms,
    build_topic_labels,
    normalize_semantic_card,
    semantic_card_similarity,
)
from app.services.competitive_gap_semantic_rules import resolve_semantic_exclusion_reason
from app.services.competitive_gap_keys import build_competitive_gap_key
from app.services.competitive_gap_page_diagnostics import get_page_word_count
from app.services.page_taxonomy_service import PAGE_TYPES
from app.services.seo_analysis import build_page_records, text_value_missing


SEGMENT_BY_GAP_TYPE: dict[str, str] = {
    "NEW_TOPIC": "create_new_page",
    "EXPAND_EXISTING_TOPIC": "expand_existing_page",
    "MISSING_SUPPORTING_PAGE": "strengthen_cluster",
}
COMMERCIAL_TYPES = {"home", "category", "product", "service", "location"}
SUPPORTING_TYPES = {"blog_article", "blog_index", "faq"}
IGNORED_TOPIC_TOKENS = {
    "blog",
    "page",
    "pages",
    "post",
    "posts",
    "index",
    "tag",
    "category",
    "categories",
    "service",
    "services",
    "product",
    "products",
}
ContentGapReadModelMode = Literal["legacy", "hybrid", "reviewed_preferred"]
ContentGapSourceMode = Literal["legacy", "raw_candidates", "reviewed"]
# Semantic clustering is still available as a legacy/auxiliary path, but for very
# large candidate sets we prefer a fast fallback rather than doing heavy read-time
# clustering work inside the request/CSV path.
SEMANTIC_READ_MODEL_MAX_CANDIDATES = 250


class CompetitiveGapServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class OwnPageTopicProfile:
    page_id: int
    url: str
    normalized_url: str
    title: str | None
    h1: str | None
    meta_description: str | None
    page_type: str
    page_bucket: str
    priority_score: int
    impressions: int
    clicks: int
    word_count: int
    semantic_input_hash: str
    semantic_card: dict[str, Any]
    dominant_intent: str
    page_role: str
    content_format: str
    geo_scope: str | None
    entities: list[str]
    supporting_subtopics: list[str]
    topic_key: str
    topic_tokens: set[str]


@dataclass(slots=True)
class CompetitorTopicCluster:
    topic_key: str
    topic_label: str
    topic_tokens: set[str]
    competitor_ids: list[int]
    competitor_urls: list[str]
    page_types: Counter[str]
    page_roles: Counter[str]
    page_count: int
    competitor_count: int
    average_confidence: float


@dataclass(slots=True)
class SemanticGapCluster:
    semantic_cluster_key: str
    topic_key: str
    topic_label: str
    canonical_topic_label: str | None
    candidate_ids: list[int]
    competitor_ids: list[int]
    competitor_urls: list[str]
    page_types: Counter[str]
    page_count: int
    competitor_count: int
    merged_topic_count: int
    raw_topic_keys: list[str]
    source_topic_labels: list[str]
    semantic_card: dict[str, Any]
    cluster_confidence: float
    cluster_intent_profile: str | None
    cluster_role_summary: dict[str, int]
    cluster_entities: list[str]
    cluster_geo_scope: str | None
    supporting_evidence: list[str]
    own_match_status: SemanticOwnMatchStatus
    own_match_source: str | None
    coverage_type: SemanticCoverageType
    coverage_confidence: float
    coverage_rationale: str
    coverage_reason_code: str | None
    coverage_debug: dict[str, Any]
    coverage_best_own_urls: list[str]
    mismatch_notes: list[str]
    gap_detail_type: str | None
    own_page_id: int | None
    own_page_type: str | None
    own_page_title: str | None
    matched_own_page_ids: list[int]
    own_page_tokens: set[str]
    topic_tokens: set[str]


def build_competitive_gap_payload(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
    gsc_date_range: str = "last_28_days",
    page: int = 1,
    page_size: int = 25,
    sort_by: str = "priority_score",
    sort_order: str = "desc",
    gap_type: str | None = None,
    segment: str | None = None,
    competitor_id: int | None = None,
    page_type: str | None = None,
    own_match_status: str | None = None,
    topic: str | None = None,
    priority_score_min: int | None = None,
    consensus_min: int | None = None,
) -> dict[str, Any]:
    payload = _build_competitive_gap_read_model(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        gsc_date_range=gsc_date_range,
    )
    filtered = _filter_gap_rows(
        payload["items"],
        gap_type=gap_type,
        segment=segment,
        competitor_id=competitor_id,
        page_type=page_type,
        own_match_status=own_match_status,
        topic=topic,
        priority_score_min=priority_score_min,
        consensus_min=consensus_min,
    )
    _sort_gap_rows(filtered, sort_by=sort_by, sort_order=sort_order)

    total_items = len(filtered)
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    start = (page - 1) * page_size
    end = start + page_size
    response_context = dict(payload["context"])
    if total_items == 0 and payload["items"]:
        response_context["empty_state_reason"] = "filters_excluded_all"
    return {
        "context": response_context,
        "summary": payload["summary"],
        "items": filtered[start:end],
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def get_competitive_gap_row(
    session: Session,
    site_id: int,
    *,
    gap_key: str,
    active_crawl_id: int | None = None,
    gsc_date_range: str = "last_28_days",
) -> dict[str, Any]:
    payload = _build_competitive_gap_read_model(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        gsc_date_range=gsc_date_range,
    )
    for item in payload["items"]:
        if item["gap_key"] == gap_key:
            return item
    raise CompetitiveGapServiceError(f"Competitive gap '{gap_key}' not found for site {site_id}.")


def get_all_competitive_gap_rows(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
    gsc_date_range: str = "last_28_days",
    sort_by: str = "priority_score",
    sort_order: str = "desc",
    gap_type: str | None = None,
    segment: str | None = None,
    competitor_id: int | None = None,
    page_type: str | None = None,
    own_match_status: str | None = None,
    topic: str | None = None,
    priority_score_min: int | None = None,
    consensus_min: int | None = None,
) -> list[dict[str, Any]]:
    payload = _build_competitive_gap_read_model(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        gsc_date_range=gsc_date_range,
    )
    filtered = _filter_gap_rows(
        payload["items"],
        gap_type=gap_type,
        segment=segment,
        competitor_id=competitor_id,
        page_type=page_type,
        own_match_status=own_match_status,
        topic=topic,
        priority_score_min=priority_score_min,
        consensus_min=consensus_min,
    )
    _sort_gap_rows(filtered, sort_by=sort_by, sort_order=sort_order)
    return filtered


def _build_competitive_gap_read_model(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None,
    gsc_date_range: str,
) -> dict[str, Any]:
    for source_mode in _resolve_competitive_gap_source_mode_order():
        payload = _build_competitive_gap_read_model_for_source_mode(
            source_mode,
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            gsc_date_range=gsc_date_range,
        )
        if payload is not None:
            return payload
    raise CompetitiveGapServiceError("Competitive Gap read model returned no payload for any configured source mode.")


def _resolve_competitive_gap_source_mode_order() -> tuple[ContentGapSourceMode, ...]:
    mode: ContentGapReadModelMode = get_settings().content_gap_read_model_mode
    if mode == "hybrid":
        return ("reviewed", "raw_candidates", "legacy")
    if mode == "reviewed_preferred":
        return ("reviewed", "raw_candidates", "legacy")
    return ("legacy",)


def _build_competitive_gap_read_model_for_source_mode(
    source_mode: ContentGapSourceMode,
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None,
    gsc_date_range: str,
) -> dict[str, Any] | None:
    if source_mode == "reviewed":
        return _build_reviewed_content_gap_read_model(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            gsc_date_range=gsc_date_range,
        )
    if source_mode == "raw_candidates":
        return _build_raw_candidate_content_gap_read_model(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            gsc_date_range=gsc_date_range,
        )
    return _build_current_competitive_gap_read_model(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        gsc_date_range=gsc_date_range,
    )


def _build_reviewed_content_gap_read_model(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None,
    gsc_date_range: str,
) -> dict[str, Any] | None:
    base = _build_content_gap_read_model_base(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        gsc_date_range=gsc_date_range,
    )
    active_crawl = base["active_crawl"]
    if active_crawl is None:
        return None

    latest_run = _load_latest_content_gap_review_run(
        session,
        site_id=site_id,
        basis_crawl_job_id=int(active_crawl.id),
    )
    completed_run = _load_latest_completed_content_gap_review_run_with_items(
        session,
        site_id=site_id,
        basis_crawl_job_id=int(active_crawl.id),
    )
    if completed_run is None:
        return None

    active_items = session.scalars(
        select(SiteContentGapItem)
        .where(
            SiteContentGapItem.site_id == site_id,
            SiteContentGapItem.review_run_id == completed_run.id,
            SiteContentGapItem.basis_crawl_job_id == int(active_crawl.id),
            SiteContentGapItem.item_status == "active",
        )
        .options(selectinload(SiteContentGapItem.source_candidate))
        .order_by(SiteContentGapItem.id.asc())
    ).all()
    if not active_items:
        return None

    visible_items = [item for item in active_items if bool(item.visible_in_results)]
    review_group_counts = Counter(str(item.review_group_key or item.source_candidate_key or item.id) for item in active_items)
    competitor_page_url_map = _load_competitor_page_url_map_for_candidates(
        session,
        [item.source_candidate for item in active_items if item.source_candidate is not None],
    )
    rows = [
        _build_reviewed_gap_row(
            item,
            competitor_page_url_map=competitor_page_url_map,
            review_group_counts=review_group_counts,
        )
        for item in visible_items
        if item.source_candidate is not None
    ]
    normalized_rows = [
        _normalize_competitive_gap_row(row, semantic_mode=False)
        for row in rows
    ]
    normalized_rows = _dedupe_equivalent_gap_rows(normalized_rows)
    counts_by_coverage_type = _build_counts_by_coverage_type(normalized_rows)
    context = dict(base["context"])
    context.update(
        {
            "data_source_mode": "reviewed",
            "basis_crawl_job_id": int(active_crawl.id),
            "is_outdated_for_active_crawl": False,
            "review_run_status": str(latest_run.status) if latest_run is not None else None,
        }
    )
    if not normalized_rows:
        context["empty_state_reason"] = None
    return {
        "context": context,
        "summary": _build_summary(
            normalized_rows,
            competitors_considered=len(base["active_competitors"]),
            counts_by_coverage_type=counts_by_coverage_type,
        ),
        "items": normalized_rows,
    }


def _build_raw_candidate_content_gap_read_model(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None,
    gsc_date_range: str,
) -> dict[str, Any] | None:
    base = _build_content_gap_read_model_base(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        gsc_date_range=gsc_date_range,
    )
    active_crawl = base["active_crawl"]
    if active_crawl is None:
        return None

    candidates = session.scalars(
        select(SiteContentGapCandidate)
        .where(
            SiteContentGapCandidate.site_id == site_id,
            SiteContentGapCandidate.basis_crawl_job_id == int(active_crawl.id),
            SiteContentGapCandidate.current.is_(True),
            SiteContentGapCandidate.status == "active",
        )
        .order_by(SiteContentGapCandidate.id.asc())
    ).all()
    if not candidates:
        return None

    competitor_page_url_map = _load_competitor_page_url_map_for_candidates(session, candidates)
    rows = [
        _build_raw_candidate_gap_row(
            candidate,
            competitor_page_url_map=competitor_page_url_map,
        )
        for candidate in candidates
    ]
    normalized_rows = [
        _normalize_competitive_gap_row(row, semantic_mode=False)
        for row in rows
    ]
    normalized_rows = _dedupe_equivalent_gap_rows(normalized_rows)
    latest_run = _load_latest_content_gap_review_run(
        session,
        site_id=site_id,
        basis_crawl_job_id=int(active_crawl.id),
    )
    context = dict(base["context"])
    context.update(
        {
            "data_source_mode": "raw_candidates",
            "basis_crawl_job_id": int(active_crawl.id),
            "is_outdated_for_active_crawl": False,
            "review_run_status": str(latest_run.status) if latest_run is not None else None,
        }
    )
    return {
        "context": context,
        "summary": _build_summary(
            normalized_rows,
            competitors_considered=len(base["active_competitors"]),
            counts_by_coverage_type=_build_counts_by_coverage_type(normalized_rows),
        ),
        "items": normalized_rows,
    }


def _build_current_competitive_gap_read_model(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None,
    gsc_date_range: str,
) -> dict[str, Any]:
    semantic_payload = _build_semantic_competitive_gap_read_model(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        gsc_date_range=gsc_date_range,
    )
    if semantic_payload is not None:
        semantic_context = dict(semantic_payload.get("context") or {})
        semantic_context.setdefault("data_source_mode", "legacy")
        semantic_context.setdefault("basis_crawl_job_id", semantic_context.get("active_crawl_id"))
        semantic_context.setdefault(
            "is_outdated_for_active_crawl",
            _has_outdated_content_gap_state(
                session,
                site_id=site_id,
                active_crawl_id=int(semantic_context["active_crawl_id"]) if semantic_context.get("active_crawl_id") else None,
            ),
        )
        semantic_context.setdefault("review_run_status", None)
        semantic_payload["context"] = semantic_context
        return semantic_payload
    return _build_legacy_competitive_gap_read_model(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        gsc_date_range=gsc_date_range,
    )


def _build_content_gap_read_model_base(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None,
    gsc_date_range: str,
) -> dict[str, Any]:
    context = site_service.resolve_site_workspace_context(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
    )
    site = context["site"]
    active_crawl = context["active_crawl"]
    active_competitors = session.scalars(
        select(SiteCompetitor)
        .where(SiteCompetitor.site_id == site_id, SiteCompetitor.is_active.is_(True))
        .order_by(SiteCompetitor.id.asc())
    ).all()
    strategy = site_content_strategy_service.get_site_content_strategy(session, site_id)
    competitor_readiness = _load_competitor_data_readiness(
        session,
        competitor_ids=[competitor.id for competitor in active_competitors],
    )
    own_pages_count = None
    if active_crawl is not None:
        own_pages_count = int(
            session.scalar(
                select(func.count(Page.id)).where(Page.crawl_job_id == int(active_crawl.id))
            )
            or 0
        )
    response_context = {
        "site_id": site.id,
        "site_domain": site.domain,
        "active_crawl_id": active_crawl.id if active_crawl else None,
        "gsc_date_range": gsc_date_range,
        "active_crawl": _serialize_site_crawl_context(active_crawl, site.root_url),
        "strategy_present": strategy is not None,
        "active_competitor_count": len(active_competitors),
        "data_readiness": _build_data_readiness(
            has_active_crawl=active_crawl is not None,
            has_strategy=strategy is not None,
            active_competitors_count=len(active_competitors),
            competitors_with_pages_count=competitor_readiness["competitors_with_pages_count"],
            competitors_with_current_extractions_count=competitor_readiness["competitors_with_current_extractions_count"],
            total_competitor_pages_count=competitor_readiness["total_competitor_pages_count"],
            total_current_extractions_count=competitor_readiness["total_current_extractions_count"],
            own_pages_count=own_pages_count,
        ),
        "empty_state_reason": None,
        "data_source_mode": "legacy",
        "basis_crawl_job_id": active_crawl.id if active_crawl else None,
        "is_outdated_for_active_crawl": _has_outdated_content_gap_state(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl.id if active_crawl else None,
        ),
        "review_run_status": None,
    }
    return {
        "site": site,
        "active_crawl": active_crawl,
        "active_competitors": active_competitors,
        "strategy": strategy,
        "competitor_readiness": competitor_readiness,
        "context": response_context,
    }


def _load_latest_content_gap_review_run(
    session: Session,
    *,
    site_id: int,
    basis_crawl_job_id: int,
) -> SiteContentGapReviewRun | None:
    return session.scalar(
        select(SiteContentGapReviewRun)
        .where(
            SiteContentGapReviewRun.site_id == site_id,
            SiteContentGapReviewRun.basis_crawl_job_id == basis_crawl_job_id,
        )
        .order_by(SiteContentGapReviewRun.id.desc())
        .limit(1)
    )


def _load_latest_completed_content_gap_review_run_with_items(
    session: Session,
    *,
    site_id: int,
    basis_crawl_job_id: int,
) -> SiteContentGapReviewRun | None:
    completed_runs = session.scalars(
        select(SiteContentGapReviewRun)
        .where(
            SiteContentGapReviewRun.site_id == site_id,
            SiteContentGapReviewRun.basis_crawl_job_id == basis_crawl_job_id,
            SiteContentGapReviewRun.status == "completed",
        )
        .order_by(SiteContentGapReviewRun.id.desc())
    ).all()
    for run in completed_runs:
        active_item_count = int(
            session.scalar(
                select(func.count(SiteContentGapItem.id)).where(
                    SiteContentGapItem.review_run_id == int(run.id),
                    SiteContentGapItem.item_status == "active",
                )
            )
            or 0
        )
        if active_item_count > 0:
            return run
    return None


def _has_outdated_content_gap_state(
    session: Session,
    *,
    site_id: int,
    active_crawl_id: int | None,
) -> bool:
    if active_crawl_id is None:
        return False
    has_current_items = bool(
        session.scalar(
            select(SiteContentGapItem.id)
            .where(
                SiteContentGapItem.site_id == site_id,
                SiteContentGapItem.basis_crawl_job_id == active_crawl_id,
                SiteContentGapItem.item_status == "active",
            )
            .limit(1)
        )
    )
    has_current_candidates = bool(
        session.scalar(
            select(SiteContentGapCandidate.id)
            .where(
                SiteContentGapCandidate.site_id == site_id,
                SiteContentGapCandidate.basis_crawl_job_id == active_crawl_id,
                SiteContentGapCandidate.current.is_(True),
                SiteContentGapCandidate.status == "active",
            )
            .limit(1)
        )
    )
    if has_current_items or has_current_candidates:
        return False
    has_other_items = bool(
        session.scalar(
            select(SiteContentGapItem.id)
            .where(
                SiteContentGapItem.site_id == site_id,
                SiteContentGapItem.basis_crawl_job_id != active_crawl_id,
                SiteContentGapItem.item_status == "active",
            )
            .limit(1)
        )
    )
    has_other_candidates = bool(
        session.scalar(
            select(SiteContentGapCandidate.id)
            .where(
                SiteContentGapCandidate.site_id == site_id,
                SiteContentGapCandidate.basis_crawl_job_id != active_crawl_id,
                SiteContentGapCandidate.current.is_(True),
                SiteContentGapCandidate.status == "active",
            )
            .limit(1)
        )
    )
    return bool(has_other_items or has_other_candidates)


def _load_competitor_page_url_map_for_candidates(
    session: Session,
    candidates: Iterable[SiteContentGapCandidate],
) -> dict[int, str]:
    page_ids = sorted(
        {
            int(page_id)
            for candidate in candidates
            for page_id in (candidate.source_competitor_page_ids_json or [])
            if page_id is not None
        }
    )
    if not page_ids:
        return {}
    rows = session.execute(
        select(SiteCompetitorPage.id, SiteCompetitorPage.url)
        .where(SiteCompetitorPage.id.in_(page_ids))
        .order_by(SiteCompetitorPage.id.asc())
    ).all()
    return {
        int(row.id): str(row.url)
        for row in rows
        if row.url
    }


def _build_reviewed_gap_row(
    item: SiteContentGapItem,
    *,
    competitor_page_url_map: dict[int, str],
    review_group_counts: Counter[str],
) -> dict[str, Any]:
    candidate = item.source_candidate
    if candidate is None:
        raise CompetitiveGapServiceError("Reviewed Content Gap item is missing its source candidate.")
    base_row = _build_candidate_backed_gap_row(
        candidate,
        competitor_page_url_map=competitor_page_url_map,
    )
    semantic_cluster_key = str(item.review_group_key or candidate.source_cluster_key or candidate.candidate_key)
    topic_key = (
        collapse_whitespace(item.reviewed_normalized_topic_key)
        or collapse_whitespace(candidate.normalized_topic_key)
        or "topic"
    )
    topic_label = (
        collapse_whitespace(item.reviewed_topic_label)
        or collapse_whitespace(item.reviewed_phrase)
        or collapse_whitespace(candidate.original_topic_label)
        or collapse_whitespace(candidate.original_phrase)
        or topic_key
    )
    gap_type = _normalize_read_model_gap_type(item.reviewed_gap_type or candidate.gap_type)
    page_type = _normalize_page_type(_suggested_page_type_for_gap_type(gap_type))
    target_url = _extract_review_alignment_url(item.own_site_alignment_json)
    coverage_confidence = round(max(0.0, min(1.0, float(item.confidence or 0.0))), 2)
    own_match_status = _own_match_status_from_hint(candidate.own_coverage_hint)
    coverage_type = _coverage_type_from_own_match_status(own_match_status)
    supporting_evidence = _review_summary_values(item.competitor_evidence_json) or [candidate.rationale_summary]
    signals = dict(base_row.get("signals") or {})
    review_signals = {
        "decision_action": item.decision_action,
        "review_run_id": item.review_run_id,
        "fit_score": float(item.fit_score or 0.0),
        "confidence": coverage_confidence,
        "visible_in_results": bool(item.visible_in_results),
        "merge_target_phrase": item.merge_target_phrase,
        "remove_reason_text": item.remove_reason_text,
        "rewrite_reason_text": item.rewrite_reason_text,
        "source_mode": "reviewed",
    }
    signals["review"] = review_signals
    return {
        **base_row,
        "gap_key": build_competitive_gap_key(
            gap_type=gap_type,
            topic_key=semantic_cluster_key,
            target_page_id=None,
            suggested_page_type=page_type,
        ),
        "semantic_cluster_key": semantic_cluster_key,
        "gap_type": gap_type,
        "segment": SEGMENT_BY_GAP_TYPE[gap_type],
        "topic_key": topic_key,
        "topic_label": topic_label,
        "canonical_topic_label": topic_label,
        "merged_topic_count": max(1, int(review_group_counts.get(semantic_cluster_key, 1))),
        "coverage_confidence": coverage_confidence,
        "coverage_rationale": item.decision_reason_text,
        "coverage_best_own_urls": _review_summary_values(item.own_site_alignment_json),
        "mismatch_notes": [item.remove_reason_text] if item.remove_reason_text else [],
        "own_match_source": target_url,
        "gap_detail_type": _gap_detail_from_gap_type(gap_type),
        "target_page_id": None,
        "target_url": target_url,
        "page_type": page_type,
        "target_page_type": None,
        "suggested_page_type": page_type,
        "cluster_member_count": max(1, len(candidate.source_competitor_page_ids_json or [])),
        "cluster_confidence": round(max(0.35, coverage_confidence), 2),
        "cluster_intent_profile": "commercial",
        "cluster_role_summary": _cluster_role_summary_from_page_type(page_type),
        "cluster_entities": [],
        "cluster_geo_scope": None,
        "supporting_evidence": supporting_evidence,
        "competitor_count": max(1, int(candidate.competitor_count or 0)),
        "consensus_score": min(100, 30 + max(1, int(candidate.competitor_count or 0)) * 18),
        "competitor_coverage_score": min(
            100,
            25 + max(1, int(candidate.competitor_count or 0)) * 18 + len(candidate.source_competitor_page_ids_json or []) * 5,
        ),
        "own_coverage_score": _own_coverage_score_from_hint(candidate.own_coverage_hint),
        "strategy_alignment_score": int(round(min(100.0, float(item.fit_score or candidate.deterministic_priority_score or 0)))),
        "business_value_score": int(round(min(100.0, float(item.fit_score or candidate.deterministic_priority_score or 0)))),
        "priority_score": int(round(min(100.0, float(item.sort_score if item.sort_score is not None else item.fit_score or candidate.deterministic_priority_score or 0)))),
        "confidence": coverage_confidence,
        "rationale": item.decision_reason_text,
        "signals": signals,
        "decision_action": item.decision_action,
        "reviewed_phrase": item.reviewed_phrase,
        "reviewed_topic_label": item.reviewed_topic_label,
        "fit_score": float(item.fit_score or 0.0),
        "remove_reason_text": item.remove_reason_text,
        "merge_target_phrase": item.merge_target_phrase,
    }


def _build_raw_candidate_gap_row(
    candidate: SiteContentGapCandidate,
    *,
    competitor_page_url_map: dict[int, str],
) -> dict[str, Any]:
    base_row = _build_candidate_backed_gap_row(
        candidate,
        competitor_page_url_map=competitor_page_url_map,
    )
    signals = dict(base_row.get("signals") or {})
    signals["review"] = {
        "decision_action": None,
        "review_run_id": None,
        "fit_score": None,
        "confidence": None,
        "source_mode": "raw_candidates",
    }
    return {
        **base_row,
        "signals": signals,
        "decision_action": None,
        "reviewed_phrase": None,
        "reviewed_topic_label": None,
        "fit_score": None,
        "remove_reason_text": None,
        "merge_target_phrase": None,
    }


def _build_candidate_backed_gap_row(
    candidate: SiteContentGapCandidate,
    *,
    competitor_page_url_map: dict[int, str],
) -> dict[str, Any]:
    semantic_signals = dict((candidate.signals_json or {}).get("semantic") or {})
    gap_type = _normalize_read_model_gap_type(candidate.gap_type)
    own_match_status = _own_match_status_from_hint(candidate.own_coverage_hint)
    coverage_type = str(semantic_signals.get("coverage_type") or _coverage_type_from_own_match_status(own_match_status))
    coverage_confidence = float(semantic_signals.get("coverage_confidence") or 0.0)
    page_type = _resolve_candidate_page_type(candidate)
    competitor_urls = dedupe_preserve_order(
        [
            competitor_page_url_map[int(page_id)]
            for page_id in (candidate.source_competitor_page_ids_json or [])
            if int(page_id) in competitor_page_url_map
        ]
    )
    signals = dict(candidate.signals_json or {})
    semantic_signals.setdefault("source_candidate_ids", list(semantic_signals.get("source_candidate_ids") or []))
    semantic_signals.setdefault("source_competitor_ids", list(candidate.source_competitor_ids_json or []))
    semantic_signals.setdefault("source_competitor_page_ids", list(candidate.source_competitor_page_ids_json or []))
    semantic_signals.setdefault("source_mode", "raw_candidates")
    signals["semantic"] = semantic_signals
    return {
        "gap_key": candidate.candidate_key,
        "semantic_cluster_key": candidate.source_cluster_key,
        "gap_type": gap_type,
        "segment": SEGMENT_BY_GAP_TYPE[gap_type],
        "topic_key": candidate.normalized_topic_key,
        "topic_label": candidate.original_topic_label,
        "canonical_topic_label": candidate.original_topic_label,
        "merged_topic_count": max(1, len(candidate.source_competitor_page_ids_json or []) or int(candidate.competitor_count or 0)),
        "own_match_status": own_match_status,
        "coverage_type": coverage_type if coverage_type in _empty_coverage_counts() else _coverage_type_from_own_match_status(own_match_status),
        "coverage_confidence": round(max(0.0, min(1.0, coverage_confidence)), 2),
        "coverage_rationale": candidate.rationale_summary,
        "coverage_best_own_urls": [],
        "mismatch_notes": [],
        "own_match_source": None,
        "gap_detail_type": _gap_detail_from_gap_type(gap_type),
        "target_page_id": None,
        "target_url": None,
        "page_type": page_type,
        "target_page_type": None,
        "suggested_page_type": page_type,
        "cluster_member_count": max(1, len(candidate.source_competitor_page_ids_json or [])),
        "cluster_confidence": round(max(0.35, coverage_confidence or 0.0), 2),
        "cluster_intent_profile": "commercial",
        "cluster_role_summary": _cluster_role_summary_from_page_type(page_type),
        "cluster_entities": [],
        "cluster_geo_scope": None,
        "supporting_evidence": [candidate.rationale_summary],
        "competitor_ids": [int(value) for value in (candidate.source_competitor_ids_json or []) if value is not None],
        "competitor_count": max(1, int(candidate.competitor_count or 0)),
        "competitor_urls": competitor_urls,
        "consensus_score": min(100, 25 + max(1, int(candidate.competitor_count or 0)) * 18),
        "competitor_coverage_score": min(
            100,
            25 + max(1, int(candidate.competitor_count or 0)) * 18 + len(candidate.source_competitor_page_ids_json or []) * 5,
        ),
        "own_coverage_score": _own_coverage_score_from_hint(candidate.own_coverage_hint),
        "strategy_alignment_score": int(max(0, min(100, int(candidate.deterministic_priority_score or 0)))),
        "business_value_score": int(max(0, min(100, int(candidate.deterministic_priority_score or 0)))),
        "priority_score": int(max(0, min(100, int(candidate.deterministic_priority_score or 0)))),
        "confidence": round(max(0.35, min(0.95, coverage_confidence or (int(candidate.deterministic_priority_score or 0) / 100.0))), 2),
        "rationale": candidate.rationale_summary,
        "signals": signals,
    }


def _normalize_read_model_gap_type(value: Any) -> CompetitiveGapType:
    normalized = str(value or "").strip().upper()
    if normalized == "NEW_TOPIC":
        return "NEW_TOPIC"
    if normalized in {"MISSING_SUPPORTING_PAGE", "MISSING_SUPPORTING_CONTENT"}:
        return "MISSING_SUPPORTING_PAGE"
    return "EXPAND_EXISTING_TOPIC"


def _own_match_status_from_hint(value: Any) -> SemanticOwnMatchStatus:
    hint = str(value or "").strip().lower()
    if hint == "existing_strong":
        return "semantic_match"
    if hint == "partial":
        return "partial_coverage"
    return "no_meaningful_match"


def _own_coverage_score_from_hint(value: Any) -> int:
    hint = str(value or "").strip().lower()
    if hint == "existing_strong":
        return 72
    if hint == "partial":
        return 44
    return 8


def _resolve_candidate_page_type(candidate: SiteContentGapCandidate) -> str:
    semantic_signals = dict((candidate.signals_json or {}).get("semantic") or {})
    competitor_page_types = dict((candidate.signals_json or {}).get("competitor_page_types") or {})
    if competitor_page_types:
        dominant = _dominant_page_type(Counter({str(key): int(value or 0) for key, value in competitor_page_types.items()}))
        normalized = _normalize_page_type(dominant)
        if normalized != "other":
            return normalized
    if semantic_signals.get("gap_detail_type") == "MISSING_SUPPORTING_CONTENT":
        return "faq"
    if _normalize_read_model_gap_type(candidate.gap_type) == "MISSING_SUPPORTING_PAGE":
        return "faq"
    return "service"


def _normalize_page_type(value: Any) -> str:
    normalized = str(value or "").strip()
    if normalized in PAGE_TYPES:
        return normalized
    return "other"


def _suggested_page_type_for_gap_type(gap_type: CompetitiveGapType) -> str:
    if gap_type == "MISSING_SUPPORTING_PAGE":
        return "faq"
    return "service"


def _cluster_role_summary_from_page_type(page_type: str) -> dict[str, int]:
    if page_type in SUPPORTING_TYPES or page_type == "faq":
        return {"supporting_page": 1}
    return {"money_page": 1}


def _extract_review_alignment_url(payload: dict[str, Any] | None) -> str | None:
    for value in _review_summary_values(payload):
        if str(value).startswith("http"):
            return str(value)
    return None


def _review_summary_values(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    summary = payload.get("summary")
    if not isinstance(summary, list):
        return []
    values: list[str] = []
    for value in summary:
        text = collapse_whitespace(value)
        if text:
            values.append(text)
    return values


def _build_legacy_competitive_gap_read_model(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None,
    gsc_date_range: str,
) -> dict[str, Any]:
    context = site_service.resolve_site_workspace_context(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
    )
    site = context["site"]
    active_crawl = context["active_crawl"]
    active_competitors = session.scalars(
        select(SiteCompetitor)
        .where(SiteCompetitor.site_id == site_id, SiteCompetitor.is_active.is_(True))
        .order_by(SiteCompetitor.id.asc())
    ).all()
    strategy = site_content_strategy_service.get_site_content_strategy(session, site_id)
    competitor_readiness = _load_competitor_data_readiness(
        session,
        competitor_ids=[competitor.id for competitor in active_competitors],
    )

    response_context = {
        "site_id": site.id,
        "site_domain": site.domain,
        "active_crawl_id": active_crawl.id if active_crawl else None,
        "gsc_date_range": gsc_date_range,
        "active_crawl": _serialize_site_crawl_context(active_crawl, site.root_url),
        "strategy_present": strategy is not None,
        "active_competitor_count": len(active_competitors),
        "data_readiness": _build_data_readiness(
            has_active_crawl=active_crawl is not None,
            has_strategy=strategy is not None,
            active_competitors_count=len(active_competitors),
            competitors_with_pages_count=competitor_readiness["competitors_with_pages_count"],
            competitors_with_current_extractions_count=competitor_readiness["competitors_with_current_extractions_count"],
            total_competitor_pages_count=competitor_readiness["total_competitor_pages_count"],
            total_current_extractions_count=competitor_readiness["total_current_extractions_count"],
            own_pages_count=None,
        ),
        "empty_state_reason": None,
        "data_source_mode": "legacy",
        "basis_crawl_job_id": active_crawl.id if active_crawl else None,
        "is_outdated_for_active_crawl": _has_outdated_content_gap_state(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl.id if active_crawl else None,
        ),
        "review_run_status": None,
    }
    if active_crawl is None:
        response_context["empty_state_reason"] = "no_active_crawl"
        return {
            "context": response_context,
            "summary": _empty_summary(len(active_competitors)),
            "items": [],
        }
    if not active_competitors:
        response_context["empty_state_reason"] = "no_competitors"
        return {
            "context": response_context,
            "summary": _empty_summary(len(active_competitors)),
            "items": [],
        }

    suffix = _resolve_gsc_suffix(gsc_date_range)
    page_records = build_page_records(session, active_crawl.id)
    priority_service.apply_priority_metadata(page_records, gsc_date_range=gsc_date_range)
    own_semantic_profiles = competitive_gap_own_semantic_service.load_current_own_page_semantic_profiles(
        session,
        site_id,
        active_crawl.id,
        gsc_date_range=gsc_date_range,
        page_records=page_records,
        refresh_mode="if_missing",
    )
    own_semantic_profile_map = {
        int(row.page_id): dict(row.semantic_card_json or {})
        for row in own_semantic_profiles
    }
    own_semantic_hash_map = {
        int(row.page_id): str(row.semantic_input_hash or "")
        for row in own_semantic_profiles
    }
    own_pages = _build_own_page_profiles(
        page_records,
        suffix=suffix,
        semantic_profile_map=own_semantic_profile_map,
        semantic_input_hash_map=own_semantic_hash_map,
    )
    own_pages_by_id = {page.page_id: page for page in own_pages}
    own_term_index = _build_own_page_term_index(own_pages)
    response_context["data_readiness"] = _build_data_readiness(
        has_active_crawl=True,
        has_strategy=strategy is not None,
        active_competitors_count=len(active_competitors),
        competitors_with_pages_count=competitor_readiness["competitors_with_pages_count"],
        competitors_with_current_extractions_count=competitor_readiness["competitors_with_current_extractions_count"],
        total_competitor_pages_count=competitor_readiness["total_competitor_pages_count"],
        total_current_extractions_count=competitor_readiness["total_current_extractions_count"],
        own_pages_count=len(own_pages),
    )
    if not own_pages:
        response_context["empty_state_reason"] = "no_own_pages"
        return {
            "context": response_context,
            "summary": _empty_summary(len(active_competitors)),
            "items": [],
        }

    clusters = _load_competitor_topic_clusters(
        session,
        site_id,
        competitor_ids=[competitor.id for competitor in active_competitors],
    )
    strategy_tokens = _extract_strategy_tokens(strategy)
    rows = _prune_low_value_gap_rows(_build_legacy_gap_rows(own_pages, clusters, strategy_tokens))
    if not rows:
        if competitor_readiness["total_competitor_pages_count"] == 0:
            response_context["empty_state_reason"] = "no_competitor_pages"
        elif competitor_readiness["total_current_extractions_count"] == 0:
            response_context["empty_state_reason"] = "no_competitor_extractions"
    return {
        "context": response_context,
        "summary": _build_summary(rows, competitors_considered=len(active_competitors)),
        "items": rows,
    }


def _build_own_page_profiles(
    page_records: list[dict[str, Any]],
    *,
    suffix: str,
    semantic_profile_map: dict[int, dict[str, Any]] | None = None,
    semantic_input_hash_map: dict[int, str] | None = None,
) -> list[OwnPageTopicProfile]:
    profiles: list[OwnPageTopicProfile] = []
    semantic_profile_map = semantic_profile_map or {}
    semantic_input_hash_map = semantic_input_hash_map or {}
    for record in page_records:
        if not _page_is_gap_eligible(record):
            continue
        page_id = int(record["id"])
        semantic_card = normalize_semantic_card(semantic_profile_map.get(page_id) or {})
        if semantic_card.get("primary_topic"):
            topic_key = build_primary_topic_key(semantic_card)
            topic_tokens = set(build_semantic_match_terms(semantic_card))
        else:
            topic_key, topic_tokens = _derive_topic_key(
                record.get("normalized_url"),
                record.get("title"),
                record.get("h1"),
            )
            semantic_card = {
                "primary_topic": collapse_whitespace(record.get("h1"))
                or collapse_whitespace(record.get("title"))
                or _prettify_topic_key(topic_key or "topic"),
                "topic_labels": [
                    value
                    for value in [
                        collapse_whitespace(record.get("h1")),
                        collapse_whitespace(record.get("title")),
                    ]
                    if value
                ],
                "core_problem": collapse_whitespace(record.get("meta_description"))
                or collapse_whitespace(record.get("h1"))
                or collapse_whitespace(record.get("title"))
                or _prettify_topic_key(topic_key or "topic"),
                "dominant_intent": "commercial"
                if str(record.get("page_bucket") or "") == "commercial"
                else "informational",
                "secondary_intents": [],
                "page_role": "money_page"
                if str(record.get("page_type") or "") in COMMERCIAL_TYPES
                else "supporting_page",
                "content_format": str(record.get("page_type") or "other"),
                "target_audience": None,
                "entities": [],
                "geo_scope": None,
                "supporting_subtopics": [],
                "what_this_page_is_about": collapse_whitespace(record.get("meta_description"))
                or collapse_whitespace(record.get("h1"))
                or collapse_whitespace(record.get("title"))
                or _prettify_topic_key(topic_key or "topic"),
                "what_this_page_is_not_about": "Unclear boundary.",
                "commerciality": "high"
                if str(record.get("page_type") or "") in COMMERCIAL_TYPES
                else "low",
                "evidence_snippets": [
                    value
                    for value in [
                        collapse_whitespace(record.get("title")),
                        collapse_whitespace(record.get("h1")),
                    ]
                    if value
                ][:4],
                "confidence": 0.55,
                "semantic_version": OWN_PAGE_SEMANTIC_PROFILE_VERSION,
                "semantic_input_hash": semantic_input_hash_map.get(page_id, ""),
            }
        if topic_key is None:
            continue
        profiles.append(
            OwnPageTopicProfile(
                page_id=page_id,
                url=str(record["url"]),
                normalized_url=str(record["normalized_url"]),
                title=collapse_whitespace(record.get("title")),
                h1=collapse_whitespace(record.get("h1")),
                meta_description=collapse_whitespace(record.get("meta_description")),
                page_type=str(record.get("page_type") or "other"),
                page_bucket=str(record.get("page_bucket") or "other"),
                priority_score=int(record.get("priority_score") or 0),
                impressions=int(record.get(f"impressions_{suffix}") or 0),
                clicks=int(record.get(f"clicks_{suffix}") or 0),
                word_count=int(record.get("word_count") or 0),
                semantic_input_hash=str(
                    semantic_input_hash_map.get(page_id)
                    or semantic_card.get("semantic_input_hash")
                    or ""
                ),
                semantic_card=semantic_card,
                dominant_intent=str(semantic_card.get("dominant_intent") or "other"),
                page_role=str(semantic_card.get("page_role") or "other"),
                content_format=str(semantic_card.get("content_format") or "other"),
                geo_scope=(
                    str(semantic_card.get("geo_scope"))
                    if semantic_card.get("geo_scope") not in (None, "")
                    else None
                ),
                entities=[str(value) for value in (semantic_card.get("entities") or []) if value],
                supporting_subtopics=[
                    str(value) for value in (semantic_card.get("supporting_subtopics") or []) if value
                ],
                topic_key=topic_key,
                topic_tokens=topic_tokens,
            )
        )
    return profiles


def _load_competitor_topic_clusters(
    session: Session,
    site_id: int,
    *,
    competitor_ids: list[int],
) -> list[CompetitorTopicCluster]:
    if not competitor_ids:
        return []
    rows = session.scalars(
        select(SiteCompetitorPageExtraction)
        .options(
            selectinload(SiteCompetitorPageExtraction.competitor_page),
            selectinload(SiteCompetitorPageExtraction.competitor),
        )
        .where(
            SiteCompetitorPageExtraction.site_id == site_id,
            SiteCompetitorPageExtraction.competitor_id.in_(competitor_ids),
        )
        .order_by(
            SiteCompetitorPageExtraction.competitor_page_id.asc(),
            SiteCompetitorPageExtraction.extracted_at.desc(),
            SiteCompetitorPageExtraction.id.desc(),
        )
    ).all()
    latest_by_page_id: dict[int, SiteCompetitorPageExtraction] = {}
    for row in rows:
        if row.competitor_page_id not in latest_by_page_id:
            latest_by_page_id[row.competitor_page_id] = row

    grouped: dict[str, list[SiteCompetitorPageExtraction]] = defaultdict(list)
    for extraction in latest_by_page_id.values():
        if extraction.competitor_page is None:
            continue
        if not bool(extraction.competitor_page.semantic_eligible):
            continue
        if extraction.competitor_page.content_text_hash != extraction.content_hash_at_extraction:
            continue
        normalized_topic_key = _normalize_topic_key(extraction.topic_key)
        if normalized_topic_key is None:
            continue
        grouped[normalized_topic_key].append(extraction)

    clusters: list[CompetitorTopicCluster] = []
    for topic_key, extractions in grouped.items():
        labels = [
            str(extraction.topic_label).strip()
            for extraction in extractions
            if not text_value_missing(extraction.topic_label)
        ]
        label = Counter(labels).most_common(1)[0][0] if labels else _prettify_topic_key(topic_key)
        competitor_ids_for_topic = sorted({int(extraction.competitor_id) for extraction in extractions})
        competitor_urls = dedupe_preserve_order(
            [
                str(extraction.competitor_page.url)
                for extraction in extractions
                if extraction.competitor_page is not None
            ]
        )[:5]
        page_types = Counter(
            str(extraction.competitor_page.page_type or "other")
            for extraction in extractions
            if extraction.competitor_page is not None
        )
        page_roles = Counter(
            str(extraction.page_role)
            for extraction in extractions
            if not text_value_missing(extraction.page_role)
        )
        average_confidence = round(
            sum(float(extraction.confidence or 0.0) for extraction in extractions) / len(extractions),
            2,
        )
        clusters.append(
            CompetitorTopicCluster(
                topic_key=topic_key,
                topic_label=label,
                topic_tokens=set(tokenize_topic_text(topic_key)),
                competitor_ids=competitor_ids_for_topic,
                competitor_urls=competitor_urls,
                page_types=page_types,
                page_roles=page_roles,
                page_count=len(extractions),
                competitor_count=len(competitor_ids_for_topic),
                average_confidence=average_confidence,
            )
        )
    clusters.sort(key=lambda cluster: (-cluster.competitor_count, cluster.topic_key))
    return clusters


def _build_legacy_gap_rows(
    own_pages: list[OwnPageTopicProfile],
    clusters: list[CompetitorTopicCluster],
    strategy_tokens: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    exact_match_map: dict[str, list[OwnPageTopicProfile]] = defaultdict(list)
    for page in own_pages:
        exact_match_map[page.topic_key].append(page)

    for cluster in clusters:
        matches = exact_match_map.get(cluster.topic_key) or _fuzzy_match_pages(cluster, own_pages)
        gap_type_value, target_page, suggested_page_type = _classify_gap(cluster, matches)
        if gap_type_value is None:
            continue

        competitor_coverage_score = _competitor_coverage_score(cluster)
        own_coverage_score = _own_coverage_score(matches)
        consensus_score = _consensus_score(cluster)
        strategy_alignment_score = _strategy_alignment_score(cluster, strategy_tokens)
        business_value_score = _business_value_score(matches, cluster)
        priority_score = _priority_score(
            competitor_coverage_score=competitor_coverage_score,
            own_coverage_score=own_coverage_score,
            consensus_score=consensus_score,
            strategy_alignment_score=strategy_alignment_score,
            business_value_score=business_value_score,
        )
        confidence = _confidence_score(cluster, matches, gap_type_value)
        target_page_type = target_page.page_type if target_page is not None else None
        effective_page_type = suggested_page_type or target_page_type or "other"
        gap_key = build_competitive_gap_key(
            gap_type=gap_type_value,
            topic_key=cluster.topic_key,
            target_page_id=target_page.page_id if target_page is not None else None,
            suggested_page_type=suggested_page_type,
        )
        rows.append(
            {
                "gap_key": gap_key,
                "gap_type": gap_type_value,
                "segment": SEGMENT_BY_GAP_TYPE[gap_type_value],
                "topic_key": cluster.topic_key,
                "topic_label": cluster.topic_label,
                "target_page_id": target_page.page_id if target_page is not None else None,
                "target_url": target_page.url if target_page is not None else None,
                "page_type": effective_page_type,
                "target_page_type": target_page_type,
                "suggested_page_type": suggested_page_type,
                "competitor_ids": cluster.competitor_ids,
                "competitor_count": cluster.competitor_count,
                "competitor_urls": cluster.competitor_urls,
                "consensus_score": consensus_score,
                "competitor_coverage_score": competitor_coverage_score,
                "own_coverage_score": own_coverage_score,
                "strategy_alignment_score": strategy_alignment_score,
                "business_value_score": business_value_score,
                "priority_score": priority_score,
                "confidence": confidence,
                "rationale": _build_rationale(cluster, matches, gap_type_value, suggested_page_type),
                "signals": {
                    "competitor_pages": cluster.page_count,
                    "competitor_page_types": dict(cluster.page_types),
                    "competitor_page_roles": dict(cluster.page_roles),
                    "own_matched_pages": len(matches),
                    "own_page_types": sorted({page.page_type for page in matches}),
                    "average_competitor_confidence": cluster.average_confidence,
                },
            }
        )

    rows = [_normalize_competitive_gap_row(row, semantic_mode=False) for row in rows]
    rows = _dedupe_equivalent_gap_rows(rows)
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        existing = deduped.get(row["gap_key"])
        if existing is None or int(row["priority_score"]) > int(existing["priority_score"]):
            deduped[row["gap_key"]] = row
    return list(deduped.values())


def _classify_gap(
    cluster: CompetitorTopicCluster,
    matches: list[OwnPageTopicProfile],
) -> tuple[CompetitiveGapType | None, OwnPageTopicProfile | None, str | None]:
    dominant_page_type = _dominant_page_type(cluster.page_types)
    if not matches:
        suggested_page_type = dominant_page_type or "service"
        return "NEW_TOPIC", None, suggested_page_type

    target_page = max(
        matches,
        key=lambda page: (page.priority_score, page.impressions, page.clicks, -page.page_id),
    )
    own_page_types = {page.page_type for page in matches}
    missing_support_types = [
        page_type
        for page_type, _count in cluster.page_types.most_common()
        if page_type in SUPPORTING_TYPES and page_type not in own_page_types
    ]
    if missing_support_types and target_page.page_type in COMMERCIAL_TYPES:
        return "MISSING_SUPPORTING_PAGE", target_page, missing_support_types[0]

    if _competitor_coverage_score(cluster) - _own_coverage_score(matches) >= 18:
        return "EXPAND_EXISTING_TOPIC", target_page, None

    return None, target_page, None


def _fuzzy_match_pages(cluster: CompetitorTopicCluster, own_pages: list[OwnPageTopicProfile]) -> list[OwnPageTopicProfile]:
    matches: list[OwnPageTopicProfile] = []
    if not cluster.topic_tokens:
        return matches
    for page in own_pages:
        overlap = cluster.topic_tokens & page.topic_tokens
        required = max(1, min(2, ceil(len(cluster.topic_tokens) / 2)))
        if len(overlap) >= required:
            matches.append(page)
    return matches


def _competitor_coverage_score(cluster: CompetitorTopicCluster) -> int:
    score = 22
    score += min(28, cluster.competitor_count * 16)
    score += min(18, cluster.page_count * 7)
    score += min(16, len(cluster.page_types) * 6)
    score += min(8, len(cluster.page_roles) * 4)
    score += min(8, int(round(cluster.average_confidence * 10)))
    return max(0, min(100, score))


def _own_coverage_score(matches: list[OwnPageTopicProfile]) -> int:
    if not matches:
        return 0
    page_type_diversity = len({page.page_type for page in matches})
    max_priority_score = max(page.priority_score for page in matches)
    max_impressions = max(page.impressions for page in matches)
    score = 18
    score += min(20, len(matches) * 10)
    score += min(16, page_type_diversity * 6)
    score += min(24, max_priority_score // 3)
    score += min(12, max_impressions // 40)
    return max(0, min(100, score))


def _consensus_score(cluster: CompetitorTopicCluster) -> int:
    score = 15 + min(55, cluster.competitor_count * 22) + min(
        20,
        max(0, cluster.page_count - cluster.competitor_count) * 6,
    )
    return max(0, min(100, score))


def _strategy_alignment_score(cluster: CompetitorTopicCluster, strategy_tokens: set[str]) -> int:
    if not strategy_tokens or not cluster.topic_tokens:
        return 0
    overlap = cluster.topic_tokens & strategy_tokens
    if not overlap:
        return 0
    return max(10, min(100, int(round((len(overlap) / len(cluster.topic_tokens)) * 100))))


def _business_value_score(matches: list[OwnPageTopicProfile], cluster: CompetitorTopicCluster) -> int:
    if not matches:
        return max(20, min(70, 18 + cluster.competitor_count * 12 + cluster.page_count * 6))
    best_match = max(matches, key=lambda page: (page.priority_score, page.impressions, page.clicks))
    score = 10
    score += min(50, best_match.priority_score)
    score += min(20, best_match.impressions // 30)
    score += min(20, best_match.clicks * 2)
    return max(0, min(100, score))


def _priority_score(
    *,
    competitor_coverage_score: int,
    own_coverage_score: int,
    consensus_score: int,
    strategy_alignment_score: int,
    business_value_score: int,
) -> int:
    score = 0.25 * competitor_coverage_score
    score += 0.20 * consensus_score
    score += 0.25 * max(0, 100 - own_coverage_score)
    score += 0.15 * strategy_alignment_score
    score += 0.15 * business_value_score
    return max(0, min(100, int(round(score))))


def _confidence_score(
    cluster: CompetitorTopicCluster,
    matches: list[OwnPageTopicProfile],
    gap_type: CompetitiveGapType,
) -> float:
    confidence = 0.42
    confidence += min(0.22, cluster.competitor_count * 0.08)
    confidence += min(0.12, cluster.average_confidence * 0.12)
    if matches:
        confidence += 0.08
    if gap_type == "MISSING_SUPPORTING_PAGE":
        confidence += 0.05
    return round(max(0.35, min(0.95, confidence)), 2)


def _build_rationale(
    cluster: CompetitorTopicCluster,
    matches: list[OwnPageTopicProfile],
    gap_type: CompetitiveGapType,
    suggested_page_type: str | None,
) -> str:
    if gap_type == "NEW_TOPIC":
        return (
            f"Competitors cover '{cluster.topic_label}' across {cluster.competitor_count} domains, "
            "while the current site does not show a matching topic cluster."
        )
    if gap_type == "MISSING_SUPPORTING_PAGE":
        return (
            f"The site already covers '{cluster.topic_label}', but competitors also support this topic with "
            f"{suggested_page_type or 'additional'} content that is missing locally."
        )
    return (
        f"The site has some coverage for '{cluster.topic_label}', but competitor breadth is stronger "
        f"({cluster.page_count} competitor pages vs {len(matches)} matching own pages)."
    )


def _build_semantic_rationale(
    cluster: SemanticGapCluster,
    matches: list[OwnPageTopicProfile],
    gap_type: CompetitiveGapType,
    suggested_page_type: str | None,
    target_page: OwnPageTopicProfile | None,
) -> str:
    label = cluster.canonical_topic_label or cluster.topic_label
    if gap_type == "NEW_TOPIC":
        return (
            f"Semantic merge grouped {cluster.merged_topic_count} competitor topic variants into '{label}', "
            f"covering {cluster.competitor_count} domains while the site has no clear matching page."
        )
    if gap_type == "MISSING_SUPPORTING_PAGE":
        target_fragment = f" mapped to '{target_page.page_type}'" if target_page is not None else ""
        return (
            f"'{label}' is already covered by the site{target_fragment}, but competitors also reinforce the topic with "
            f"{suggested_page_type or 'additional'} supporting content."
        )
    return (
        f"'{label}' merges {cluster.merged_topic_count} related competitor topics and still shows stronger breadth "
        f"than the current site coverage ({cluster.page_count} competitor pages vs {len(matches)} own matches)."
    )


def _page_is_gap_eligible(record: dict[str, Any]) -> bool:
    if not bool(record.get("is_internal")):
        return False
    if bool(record.get("non_indexable_like")):
        return False
    page_type = str(record.get("page_type") or "other")
    if page_type in {"utility", "legal", "other"}:
        return False
    return True


def _derive_topic_key(*values: Any) -> tuple[str | None, set[str]]:
    collected_tokens: list[str] = []
    for value in values:
        if text_value_missing(value):
            continue
        if isinstance(value, str) and value.startswith("http"):
            collected_tokens.extend(_topic_tokens_from_url(value))
            continue
        collected_tokens.extend(tokenize_topic_text(str(value)))
    normalized_tokens = [
        token
        for token in dedupe_preserve_order(collected_tokens)
        if token not in IGNORED_TOPIC_TOKENS
    ]
    if not normalized_tokens:
        return None, set()
    topic_tokens = normalized_tokens[:3]
    return "-".join(topic_tokens), set(topic_tokens)


def _topic_tokens_from_url(url: str) -> list[str]:
    parsed = urlsplit(url)
    path = unquote(parsed.path or "/")
    return tokenize_topic_text(path.replace("/", " "))


def _normalize_topic_key(value: str | None) -> str | None:
    if text_value_missing(value):
        return None
    tokens = tokenize_topic_text(str(value))
    if not tokens:
        normalized = normalize_text_for_hash(str(value)).replace(" ", "-")
        normalized = "-".join(token for token in normalized.split("-") if token)
        return normalized or None
    return "-".join(tokens[:4])


def _prettify_topic_key(topic_key: str) -> str:
    return " ".join(part.capitalize() for part in topic_key.split("-") if part)


def _dominant_page_type(page_types: Counter[str]) -> str | None:
    if not page_types:
        return None
    return page_types.most_common(1)[0][0]


def _extract_strategy_tokens(strategy: dict[str, Any] | None) -> set[str]:
    if not strategy:
        return set()
    token_source = list(_iter_text_values(strategy.get("normalized_strategy_json")))
    if not token_source:
        token_source = [strategy.get("raw_user_input") or ""]
    tokens: list[str] = []
    for value in token_source:
        tokens.extend(tokenize_topic_text(value))
    return set(dedupe_preserve_order(tokens))


def _iter_text_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            yield stripped
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from _iter_text_values(nested)
        return
    if isinstance(value, list):
        for nested in value:
            yield from _iter_text_values(nested)


def _load_competitor_data_readiness(
    session: Session,
    *,
    competitor_ids: list[int],
) -> dict[str, int]:
    if not competitor_ids:
        return {
            "competitors_with_pages_count": 0,
            "competitors_with_current_extractions_count": 0,
            "total_competitor_pages_count": 0,
            "total_current_extractions_count": 0,
        }

    pages = session.scalars(
        select(SiteCompetitorPage)
        .where(SiteCompetitorPage.competitor_id.in_(competitor_ids))
        .order_by(SiteCompetitorPage.id.asc())
    ).all()
    page_by_id = {page.id: page for page in pages}
    competitors_with_pages = {page.competitor_id for page in pages}

    rows = session.scalars(
        select(SiteCompetitorPageExtraction)
        .where(SiteCompetitorPageExtraction.competitor_id.in_(competitor_ids))
        .order_by(
            SiteCompetitorPageExtraction.competitor_page_id.asc(),
            SiteCompetitorPageExtraction.extracted_at.desc(),
            SiteCompetitorPageExtraction.id.desc(),
        )
    ).all()
    current_extracted_page_ids: set[int] = set()
    competitors_with_current_extractions: set[int] = set()
    seen_page_ids: set[int] = set()
    for row in rows:
        if row.competitor_page_id in seen_page_ids:
            continue
        seen_page_ids.add(row.competitor_page_id)
        page = page_by_id.get(row.competitor_page_id)
        if page is None:
            continue
        if not bool(page.semantic_eligible):
            continue
        if page.content_text_hash != row.content_hash_at_extraction:
            continue
        current_extracted_page_ids.add(row.competitor_page_id)
        competitors_with_current_extractions.add(row.competitor_id)

    return {
        "competitors_with_pages_count": len(competitors_with_pages),
        "competitors_with_current_extractions_count": len(competitors_with_current_extractions),
        "total_competitor_pages_count": len(pages),
        "total_current_extractions_count": len(current_extracted_page_ids),
    }


def _build_data_readiness(
    *,
    has_active_crawl: bool,
    has_strategy: bool,
    active_competitors_count: int,
    competitors_with_pages_count: int,
    competitors_with_current_extractions_count: int,
    total_competitor_pages_count: int,
    total_current_extractions_count: int,
    own_pages_count: int | None,
) -> dict[str, Any]:
    missing_inputs: list[str] = []
    if not has_strategy:
        missing_inputs.append("strategy")
    if not has_active_crawl:
        missing_inputs.append("active_crawl")
    if active_competitors_count == 0:
        missing_inputs.append("competitors")
    elif total_competitor_pages_count == 0:
        missing_inputs.append("competitor_pages")
    elif total_current_extractions_count == 0:
        missing_inputs.append("competitor_extractions")
    if own_pages_count is not None and own_pages_count == 0:
        missing_inputs.append("own_pages")
    return {
        "has_active_crawl": has_active_crawl,
        "has_strategy": has_strategy,
        "has_active_competitors": active_competitors_count > 0,
        "gap_ready": (
            has_active_crawl
            and active_competitors_count > 0
            and total_current_extractions_count > 0
            and (own_pages_count is None or own_pages_count > 0)
        ),
        "missing_inputs": missing_inputs,
        "active_competitors_count": active_competitors_count,
        "competitors_with_pages_count": competitors_with_pages_count,
        "competitors_with_current_extractions_count": competitors_with_current_extractions_count,
        "total_competitor_pages_count": total_competitor_pages_count,
        "total_current_extractions_count": total_current_extractions_count,
    }


def _filter_gap_rows(
    items: list[dict[str, Any]],
    *,
    gap_type: str | None,
    segment: str | None,
    competitor_id: int | None,
    page_type: str | None,
    own_match_status: str | None,
    topic: str | None,
    priority_score_min: int | None,
    consensus_min: int | None,
) -> list[dict[str, Any]]:
    filtered = list(items)
    if gap_type:
        filtered = [item for item in filtered if item["gap_type"] == gap_type]
    if segment:
        filtered = [item for item in filtered if item["segment"] == segment]
    if competitor_id is not None:
        filtered = [item for item in filtered if competitor_id in item["competitor_ids"]]
    if page_type:
        filtered = [item for item in filtered if item["page_type"] == page_type]
    if own_match_status:
        filtered = [item for item in filtered if str(item.get("own_match_status") or "") == own_match_status]
    if topic:
        topic_filter = normalize_text_for_hash(topic)
        filtered = [
            item
            for item in filtered
            if topic_filter in normalize_text_for_hash(str(item["topic_label"]))
            or topic_filter in normalize_text_for_hash(str(item.get("canonical_topic_label") or ""))
            or topic_filter in normalize_text_for_hash(str(item["topic_key"]).replace("-", " "))
        ]
    if priority_score_min is not None:
        filtered = [item for item in filtered if int(item["priority_score"]) >= priority_score_min]
    if consensus_min is not None:
        filtered = [item for item in filtered if int(item["consensus_score"]) >= consensus_min]
    return filtered


def _sort_gap_rows(items: list[dict[str, Any]], *, sort_by: str, sort_order: str) -> None:
    reverse = sort_order == "desc"
    items.sort(
        key=lambda item: (_normalize_sort_value(item.get(sort_by)), _normalize_sort_value(item.get("gap_key"))),
        reverse=reverse,
    )


def _normalize_sort_value(value: Any) -> tuple[int, Any]:
    if value is None:
        return (1, "")
    if isinstance(value, str):
        return (0, value.lower())
    return (0, value)


def _prune_low_value_gap_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if not _is_low_value_gap_row(row)]


def _is_low_value_gap_row(row: dict[str, Any]) -> bool:
    topic_tokens = set(tokenize_topic_text(str(row.get("topic_key") or "")))
    topic_tokens.update(tokenize_topic_text(str(row.get("topic_label") or "")))
    topic_tokens.update(tokenize_topic_text(str(row.get("canonical_topic_label") or "")))

    candidate_page_type = row.get("suggested_page_type") or row.get("target_page_type") or row.get("page_type") or "other"
    competitor_urls = [str(url) for url in (row.get("competitor_urls") or []) if url]
    combined_url = " ".join(competitor_urls[:5]) or str(row.get("target_url") or "")
    combined_title = " ".join(
        part
        for part in [
            str(row.get("canonical_topic_label") or ""),
            str(row.get("topic_label") or ""),
            str(row.get("topic_key") or ""),
        ]
        if part
    )
    synthetic_page = {
        "status_code": 200,
        "robots_meta": None,
        "x_robots_tag": None,
        "page_type": candidate_page_type,
        "normalized_url": combined_url,
        "final_url": str(row.get("target_url") or combined_url),
        "title": combined_title,
        "h1": combined_title,
        "word_count": 500,
        "visible_text_chars": 2_000,
    }
    exclusion_reason = resolve_semantic_exclusion_reason(synthetic_page, match_terms=topic_tokens)
    if exclusion_reason in {
        "privacy_policy",
        "terms",
        "contact",
        "cart",
        "checkout",
        "account",
        "login",
        "register",
        "search",
        "tag",
        "archive",
        "utility_page",
        "low_value",
    }:
        return True
    page_type = str(candidate_page_type or "other")
    return page_type in {"about", "contact", "legal", "utility"}


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _build_summary(
    items: list[dict[str, Any]],
    *,
    competitors_considered: int,
    counts_by_coverage_type: dict[str, int] | None = None,
    canonicalization_summary: dict[str, Any] | None = None,
    cluster_quality_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    counts_by_type = {
        "NEW_TOPIC": 0,
        "EXPAND_EXISTING_TOPIC": 0,
        "MISSING_SUPPORTING_PAGE": 0,
    }
    counts_by_gap_detail_type = {
        "NEW_TOPIC": 0,
        "EXPAND_EXISTING_PAGE": 0,
        "MISSING_SUPPORTING_CONTENT": 0,
        "MISSING_MONEY_PAGE": 0,
        "INTENT_MISMATCH": 0,
        "FORMAT_GAP": 0,
        "GEO_GAP": 0,
    }
    counts_by_page_type = {page_type: 0 for page_type in PAGE_TYPES}
    topics_covered: set[str] = set()
    for item in items:
        counts_by_type[item["gap_type"]] += 1
        gap_detail_type = str(item.get("gap_detail_type") or "NEW_TOPIC")
        if gap_detail_type in counts_by_gap_detail_type:
            counts_by_gap_detail_type[gap_detail_type] += 1
        counts_by_page_type[item["page_type"]] = counts_by_page_type.get(item["page_type"], 0) + 1
        topics_covered.add(str(item.get("semantic_cluster_key") or item.get("topic_key") or "topic"))
    return {
        "total_gaps": len(items),
        "high_priority_gaps": sum(1 for item in items if int(item["priority_score"]) >= 70),
        "competitors_considered": competitors_considered,
        "topics_covered": len(topics_covered),
        "counts_by_type": counts_by_type,
        "counts_by_gap_detail_type": counts_by_gap_detail_type,
        "counts_by_coverage_type": counts_by_coverage_type or _empty_coverage_counts(),
        "counts_by_page_type": counts_by_page_type,
        "canonicalization_summary": canonicalization_summary or {
            "canonical_pages_count": 0,
            "duplicate_pages_count": 0,
            "near_duplicate_pages_count": 0,
            "filtered_leftovers_count": 0,
        },
        "cluster_quality_summary": cluster_quality_summary or {
            "clusters_count": 0,
            "low_confidence_clusters_count": 0,
            "average_cluster_confidence": 0.0,
            "average_cluster_member_count": 0.0,
        },
    }


def _empty_summary(competitors_considered: int) -> dict[str, Any]:
    return {
        "total_gaps": 0,
        "high_priority_gaps": 0,
        "competitors_considered": competitors_considered,
        "topics_covered": 0,
        "counts_by_type": {
            "NEW_TOPIC": 0,
            "EXPAND_EXISTING_TOPIC": 0,
            "MISSING_SUPPORTING_PAGE": 0,
        },
        "counts_by_gap_detail_type": {
            "NEW_TOPIC": 0,
            "EXPAND_EXISTING_PAGE": 0,
            "MISSING_SUPPORTING_CONTENT": 0,
            "MISSING_MONEY_PAGE": 0,
            "INTENT_MISMATCH": 0,
            "FORMAT_GAP": 0,
            "GEO_GAP": 0,
        },
        "counts_by_coverage_type": _empty_coverage_counts(),
        "counts_by_page_type": {page_type: 0 for page_type in PAGE_TYPES},
        "canonicalization_summary": {
            "canonical_pages_count": 0,
            "duplicate_pages_count": 0,
            "near_duplicate_pages_count": 0,
            "filtered_leftovers_count": 0,
        },
        "cluster_quality_summary": {
            "clusters_count": 0,
            "low_confidence_clusters_count": 0,
            "average_cluster_confidence": 0.0,
            "average_cluster_member_count": 0.0,
        },
    }


def _empty_coverage_counts() -> dict[str, int]:
    return {
        "exact_coverage": 0,
        "strong_semantic_coverage": 0,
        "partial_coverage": 0,
        "wrong_intent_coverage": 0,
        "commercial_missing_supporting": 0,
        "informational_missing_commercial": 0,
        "no_meaningful_coverage": 0,
    }


def _build_counts_by_coverage_type(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = _empty_coverage_counts()
    for row in rows:
        coverage_type = str(row.get("coverage_type") or "")
        if coverage_type in counts:
            counts[coverage_type] += 1
    return counts


def _build_cluster_quality_summary(clusters: list[SemanticGapCluster]) -> dict[str, Any]:
    if not clusters:
        return {
            "clusters_count": 0,
            "low_confidence_clusters_count": 0,
            "average_cluster_confidence": 0.0,
            "average_cluster_member_count": 0.0,
        }
    average_cluster_confidence = round(
        sum(float(cluster.cluster_confidence or 0.0) for cluster in clusters) / len(clusters),
        2,
    )
    average_cluster_member_count = round(
        sum(int(cluster.page_count or 0) for cluster in clusters) / len(clusters),
        2,
    )
    return {
        "clusters_count": len(clusters),
        "low_confidence_clusters_count": sum(1 for cluster in clusters if float(cluster.cluster_confidence or 0.0) < 0.68),
        "average_cluster_confidence": average_cluster_confidence,
        "average_cluster_member_count": average_cluster_member_count,
    }


def _normalize_competitive_gap_row(row: dict[str, Any], *, semantic_mode: bool) -> dict[str, Any]:
    normalized = dict(row)
    semantic_cluster_key = str(normalized.get("semantic_cluster_key") or "").strip()
    if not semantic_cluster_key:
        semantic_cluster_key = _build_fallback_semantic_cluster_key(normalized)
    normalized["semantic_cluster_key"] = semantic_cluster_key

    canonical_topic_label = normalized.get("canonical_topic_label")
    if text_value_missing(canonical_topic_label):
        canonical_topic_label = normalized.get("topic_label")
    normalized["canonical_topic_label"] = canonical_topic_label

    merged_topic_count = normalized.get("merged_topic_count")
    if text_value_missing(merged_topic_count):
        merged_topic_count = max(1, int(normalized.get("competitor_count") or 0))
    normalized["merged_topic_count"] = int(merged_topic_count or 1)

    own_match_status = normalized.get("own_match_status")
    if own_match_status not in {"exact_match", "semantic_match", "partial_coverage", "no_meaningful_match"}:
        own_match_status = _fallback_own_match_status_for_gap_type(
            str(normalized.get("gap_type") or ""),
            target_page_id=normalized.get("target_page_id"),
        )
    normalized["own_match_status"] = own_match_status
    coverage_type = str(normalized.get("coverage_type") or "").strip()
    if coverage_type not in _empty_coverage_counts():
        coverage_type = _coverage_type_from_own_match_status(own_match_status)
    normalized["coverage_type"] = coverage_type
    normalized["coverage_confidence"] = float(normalized.get("coverage_confidence") or normalized.get("confidence") or 0.0)
    normalized["coverage_rationale"] = normalized.get("coverage_rationale") or normalized.get("rationale")
    normalized["coverage_best_own_urls"] = [
        str(value)
        for value in (normalized.get("coverage_best_own_urls") or [])
        if value
    ]
    normalized["mismatch_notes"] = [str(value) for value in (normalized.get("mismatch_notes") or []) if value]
    gap_detail_type = str(normalized.get("gap_detail_type") or "").strip()
    if not gap_detail_type:
        gap_detail_type = _gap_detail_from_gap_type(str(normalized.get("gap_type") or "NEW_TOPIC"))
    normalized["gap_detail_type"] = gap_detail_type

    if text_value_missing(normalized.get("own_match_source")):
        normalized["own_match_source"] = normalized.get("target_url")

    normalized["cluster_member_count"] = int(normalized.get("cluster_member_count") or normalized.get("merged_topic_count") or 0)
    normalized["cluster_confidence"] = float(normalized.get("cluster_confidence") or normalized.get("confidence") or 0.0)
    normalized["cluster_intent_profile"] = normalized.get("cluster_intent_profile") or "other"
    normalized["cluster_role_summary"] = dict(normalized.get("cluster_role_summary") or {})
    normalized["cluster_entities"] = [str(value) for value in (normalized.get("cluster_entities") or []) if value]
    normalized["cluster_geo_scope"] = normalized.get("cluster_geo_scope")
    normalized["supporting_evidence"] = [str(value) for value in (normalized.get("supporting_evidence") or []) if value]

    if not semantic_mode or text_value_missing(normalized.get("gap_key")):
        normalized["gap_key"] = build_competitive_gap_key(
            gap_type=str(normalized.get("gap_type") or "NEW_TOPIC"),
            topic_key=semantic_cluster_key,
            target_page_id=normalized.get("target_page_id"),
            suggested_page_type=normalized.get("suggested_page_type"),
        )

    signals = dict(normalized.get("signals") or {})
    semantic_signals = dict(signals.get("semantic") or {})
    semantic_signals.setdefault("semantic_cluster_key", semantic_cluster_key)
    semantic_signals.setdefault("canonical_topic_label", canonical_topic_label)
    semantic_signals.setdefault("merged_topic_count", normalized["merged_topic_count"])
    semantic_signals.setdefault("source_candidate_ids", [])
    semantic_signals.setdefault("source_competitor_ids", normalized.get("competitor_ids") or [])
    semantic_signals.setdefault(
        "source_topic_keys",
        [normalized.get("topic_key")] if normalized.get("topic_key") else [],
    )
    semantic_signals.setdefault("own_match_status", own_match_status)
    semantic_signals.setdefault("coverage_type", coverage_type)
    semantic_signals.setdefault("coverage_confidence", normalized.get("coverage_confidence"))
    semantic_signals.setdefault("coverage_reason_code", None)
    semantic_signals.setdefault("coverage_debug", {})
    semantic_signals.setdefault("gap_detail_type", normalized.get("gap_detail_type"))
    semantic_signals.setdefault("own_match_source", normalized.get("own_match_source"))
    signals["semantic"] = semantic_signals
    normalized["signals"] = signals
    return normalized


def _normalized_recommendation_topic_key(row: dict[str, Any]) -> str:
    label = (
        collapse_whitespace(row.get("canonical_topic_label"))
        or collapse_whitespace(row.get("topic_label"))
        or str(row.get("topic_key") or "")
    )
    tokens = tokenize_topic_text(label)
    if tokens:
        return "-".join(tokens[:6])
    return normalize_text_for_hash(str(row.get("topic_key") or "topic")).replace(" ", "-") or "topic"


def _dominant_role_bucket(role_summary: dict[str, Any]) -> str:
    if not isinstance(role_summary, dict) or not role_summary:
        return "other"
    normalized_counts = {
        str(key): int(value or 0)
        for key, value in role_summary.items()
        if str(key)
    }
    if not normalized_counts:
        return "other"
    return min(
        normalized_counts.items(),
        key=lambda item: (-item[1], len(item[0]), item[0]),
    )[0]


def _rows_are_dedupe_equivalent(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if str(left.get("gap_type") or "") != str(right.get("gap_type") or ""):
        return False
    if str(left.get("gap_detail_type") or "") != str(right.get("gap_detail_type") or ""):
        return False
    if str(left.get("coverage_type") or "") != str(right.get("coverage_type") or ""):
        return False
    left_target = left.get("target_page_id")
    right_target = right.get("target_page_id")
    if left_target is not None and right_target is not None and int(left_target) != int(right_target):
        return False
    left_topic_key = _normalized_recommendation_topic_key(left)
    right_topic_key = _normalized_recommendation_topic_key(right)
    if left_topic_key != right_topic_key:
        left_topic_tokens = set(tokenize_topic_text(left_topic_key.replace("-", " ")))
        right_topic_tokens = set(tokenize_topic_text(right_topic_key.replace("-", " ")))
        if _token_overlap_ratio(left_topic_tokens, right_topic_tokens) < 0.72:
            return False
    left_intent = str(left.get("cluster_intent_profile") or "other")
    right_intent = str(right.get("cluster_intent_profile") or "other")
    if left_intent != right_intent and "other" not in {left_intent, right_intent}:
        return False
    left_role = _dominant_role_bucket(dict(left.get("cluster_role_summary") or {}))
    right_role = _dominant_role_bucket(dict(right.get("cluster_role_summary") or {}))
    if left_role != right_role and "other" not in {left_role, right_role}:
        return False
    return True


def _choose_preferred_gap_row(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return max(
        [left, right],
        key=lambda row: (
            int(row.get("priority_score") or 0),
            int(row.get("competitor_count") or 0),
            float(row.get("coverage_confidence") or row.get("confidence") or 0.0),
            float(row.get("cluster_confidence") or row.get("confidence") or 0.0),
            str(row.get("gap_key") or ""),
        ),
    )


def _merge_equivalent_gap_rows(preferred: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    merged = dict(preferred)
    merged["competitor_ids"] = dedupe_preserve_order(
        [int(value) for value in (preferred.get("competitor_ids") or []) if value is not None]
        + [int(value) for value in (other.get("competitor_ids") or []) if value is not None]
    )
    merged["competitor_urls"] = dedupe_preserve_order(
        [str(value) for value in (preferred.get("competitor_urls") or []) if value]
        + [str(value) for value in (other.get("competitor_urls") or []) if value]
    )
    merged["coverage_best_own_urls"] = dedupe_preserve_order(
        [str(value) for value in (preferred.get("coverage_best_own_urls") or []) if value]
        + [str(value) for value in (other.get("coverage_best_own_urls") or []) if value]
    )
    merged["supporting_evidence"] = dedupe_preserve_order(
        [str(value) for value in (preferred.get("supporting_evidence") or []) if value]
        + [str(value) for value in (other.get("supporting_evidence") or []) if value]
    )[:8]
    merged["cluster_entities"] = dedupe_preserve_order(
        [str(value) for value in (preferred.get("cluster_entities") or []) if value]
        + [str(value) for value in (other.get("cluster_entities") or []) if value]
    )[:12]
    merged["competitor_count"] = len(merged["competitor_ids"])
    merged["merged_topic_count"] = max(
        int(preferred.get("merged_topic_count") or 0),
        int(other.get("merged_topic_count") or 0),
    )
    merged["cluster_member_count"] = max(
        int(preferred.get("cluster_member_count") or 0),
        int(other.get("cluster_member_count") or 0),
    )

    preferred_signals = dict(merged.get("signals") or {})
    semantic_signals = dict(preferred_signals.get("semantic") or {})
    merged_gap_keys = dedupe_preserve_order(
        [str(value) for value in (semantic_signals.get("dedupe_merged_gap_keys") or []) if value]
        + [str(preferred.get("gap_key") or "")]
        + [str(other.get("gap_key") or "")]
    )
    merged_cluster_keys = dedupe_preserve_order(
        [str(value) for value in (semantic_signals.get("dedupe_merged_cluster_keys") or []) if value]
        + [str(preferred.get("semantic_cluster_key") or "")]
        + [str(other.get("semantic_cluster_key") or "")]
    )
    source_candidate_ids = dedupe_preserve_order(
        [int(value) for value in (semantic_signals.get("source_candidate_ids") or []) if value is not None]
        + [int(value) for value in ((other.get("signals") or {}).get("semantic", {}).get("source_candidate_ids") or []) if value is not None]
    )
    source_topic_keys = dedupe_preserve_order(
        [str(value) for value in (semantic_signals.get("source_topic_keys") or []) if value]
        + [str(value) for value in ((other.get("signals") or {}).get("semantic", {}).get("source_topic_keys") or []) if value]
    )
    semantic_signals["source_candidate_ids"] = source_candidate_ids
    semantic_signals["source_topic_keys"] = source_topic_keys
    semantic_signals["dedupe_reason"] = (
        "Merged equivalent recommendation rows with matching canonical topic, gap detail, coverage type, "
        "intent profile and role summary."
    )
    semantic_signals["dedupe_merged_gap_keys"] = merged_gap_keys
    semantic_signals["dedupe_merged_cluster_keys"] = merged_cluster_keys
    semantic_signals["dedupe_count"] = len(merged_gap_keys)
    preferred_signals["semantic"] = semantic_signals
    merged["signals"] = preferred_signals
    return merged


def _dedupe_equivalent_gap_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    for row in rows:
        merged = False
        for index, existing in enumerate(deduped):
            if not _rows_are_dedupe_equivalent(existing, row):
                continue
            preferred = _choose_preferred_gap_row(existing, row)
            other = row if preferred is existing else existing
            deduped[index] = _merge_equivalent_gap_rows(preferred, other)
            merged = True
            break
        if not merged:
            deduped.append(dict(row))
    return deduped


def _build_fallback_semantic_cluster_key(row: dict[str, Any]) -> str:
    payload = {
        "gap_type": row.get("gap_type"),
        "segment": row.get("segment"),
        "topic_key": row.get("topic_key"),
        "target_page_id": row.get("target_page_id"),
        "suggested_page_type": row.get("suggested_page_type"),
        "page_type": row.get("page_type"),
        "target_page_type": row.get("target_page_type"),
        "competitor_ids": sorted(int(value) for value in (row.get("competitor_ids") or []) if value is not None),
        "competitor_count": row.get("competitor_count"),
    }
    return f"sg:{_hash_payload(payload)[:20]}"


def _fallback_own_match_status_for_gap_type(
    gap_type: str,
    *,
    target_page_id: Any,
) -> SemanticOwnMatchStatus:
    if gap_type == "NEW_TOPIC" or target_page_id is None:
        return "no_meaningful_match"
    if gap_type == "MISSING_SUPPORTING_PAGE":
        return "partial_coverage"
    if gap_type == "EXPAND_EXISTING_TOPIC":
        return "semantic_match"
    return "no_meaningful_match"


def _coverage_type_from_own_match_status(own_match_status: str) -> str:
    mapping = {
        "exact_match": "exact_coverage",
        "semantic_match": "strong_semantic_coverage",
        "partial_coverage": "partial_coverage",
        "no_meaningful_match": "no_meaningful_coverage",
    }
    return mapping.get(own_match_status, "no_meaningful_coverage")


def _gap_detail_from_gap_type(gap_type: str) -> str:
    mapping = {
        "NEW_TOPIC": "NEW_TOPIC",
        "EXPAND_EXISTING_TOPIC": "EXPAND_EXISTING_PAGE",
        "MISSING_SUPPORTING_PAGE": "MISSING_SUPPORTING_CONTENT",
    }
    return mapping.get(gap_type, "NEW_TOPIC")


def _resolve_gsc_suffix(gsc_date_range: str) -> str:
    suffix = crawl_job_service.GSC_DATE_RANGE_SUFFIX.get(gsc_date_range)
    if suffix is None:
        raise CompetitiveGapServiceError(f"Unsupported gsc_date_range '{gsc_date_range}'.")
    return suffix


def _serialize_site_crawl_context(crawl_job: Any, default_root_url: str) -> dict[str, Any] | None:
    if crawl_job is None:
        return None
    root_url = default_root_url
    if isinstance(getattr(crawl_job, "settings_json", None), dict):
        root_url = str(crawl_job.settings_json.get("start_url") or default_root_url)
    status_value = crawl_job.status.value if hasattr(crawl_job.status, "value") else str(crawl_job.status)
    return {
        "id": crawl_job.id,
        "status": status_value,
        "created_at": crawl_job.created_at,
        "started_at": crawl_job.started_at,
        "finished_at": crawl_job.finished_at,
        "root_url": root_url,
    }


def _build_semantic_competitive_gap_read_model(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None,
    gsc_date_range: str,
) -> dict[str, Any] | None:
    context = site_service.resolve_site_workspace_context(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
    )
    site = context["site"]
    active_crawl = context["active_crawl"]
    active_competitors = session.scalars(
        select(SiteCompetitor)
        .where(SiteCompetitor.site_id == site_id, SiteCompetitor.is_active.is_(True))
        .order_by(SiteCompetitor.id.asc())
    ).all()
    strategy = site_content_strategy_service.get_site_content_strategy(session, site_id)
    competitor_readiness = _load_competitor_data_readiness(
        session,
        competitor_ids=[competitor.id for competitor in active_competitors],
    )

    response_context = {
        "site_id": site.id,
        "site_domain": site.domain,
        "active_crawl_id": active_crawl.id if active_crawl else None,
        "gsc_date_range": gsc_date_range,
        "active_crawl": _serialize_site_crawl_context(active_crawl, site.root_url),
        "strategy_present": strategy is not None,
        "active_competitor_count": len(active_competitors),
        "data_readiness": _build_data_readiness(
            has_active_crawl=active_crawl is not None,
            has_strategy=strategy is not None,
            active_competitors_count=len(active_competitors),
            competitors_with_pages_count=competitor_readiness["competitors_with_pages_count"],
            competitors_with_current_extractions_count=competitor_readiness["competitors_with_current_extractions_count"],
            total_competitor_pages_count=competitor_readiness["total_competitor_pages_count"],
            total_current_extractions_count=competitor_readiness["total_current_extractions_count"],
            own_pages_count=None,
        ),
        "empty_state_reason": None,
    }
    if active_crawl is None:
        response_context["empty_state_reason"] = "no_active_crawl"
        return {
            "context": response_context,
            "summary": _empty_summary(len(active_competitors)),
            "items": [],
        }
    if not active_competitors:
        response_context["empty_state_reason"] = "no_competitors"
        return {
            "context": response_context,
            "summary": _empty_summary(len(active_competitors)),
            "items": [],
        }

    suffix = _resolve_gsc_suffix(gsc_date_range)
    page_records = build_page_records(session, active_crawl.id)
    priority_service.apply_priority_metadata(page_records, gsc_date_range=gsc_date_range)
    own_semantic_profiles = competitive_gap_own_semantic_service.load_current_own_page_semantic_profiles(
        session,
        site_id,
        active_crawl.id,
        gsc_date_range=gsc_date_range,
        page_records=page_records,
        refresh_mode="if_missing",
    )
    own_semantic_profile_map = {
        int(row.page_id): dict(row.semantic_card_json or {})
        for row in own_semantic_profiles
    }
    own_semantic_hash_map = {
        int(row.page_id): str(row.semantic_input_hash or "")
        for row in own_semantic_profiles
    }
    own_pages = _build_own_page_profiles(
        page_records,
        suffix=suffix,
        semantic_profile_map=own_semantic_profile_map,
        semantic_input_hash_map=own_semantic_hash_map,
    )
    own_pages_by_id = {page.page_id: page for page in own_pages}
    own_term_index = _build_own_page_term_index(own_pages)
    response_context["data_readiness"] = _build_data_readiness(
        has_active_crawl=True,
        has_strategy=strategy is not None,
        active_competitors_count=len(active_competitors),
        competitors_with_pages_count=competitor_readiness["competitors_with_pages_count"],
        competitors_with_current_extractions_count=competitor_readiness["competitors_with_current_extractions_count"],
        total_competitor_pages_count=competitor_readiness["total_competitor_pages_count"],
        total_current_extractions_count=competitor_readiness["total_current_extractions_count"],
        own_pages_count=len(own_pages),
    )
    if not own_pages:
        response_context["empty_state_reason"] = "no_own_pages"
        return {
            "context": response_context,
            "summary": _empty_summary(len(active_competitors)),
            "items": [],
        }

    current_candidates = _load_current_semantic_candidates(session, site_id, [competitor.id for competitor in active_competitors])
    if not current_candidates:
        return None
    if _should_skip_semantic_read_model(current_candidates):
        return None
    if not _site_has_semantic_readiness(
        session,
        active_competitors=active_competitors,
        current_candidates=current_candidates,
    ):
        return None

    extraction_by_page_id = _load_latest_valid_extractions_by_page_id(
        session,
        site_id=site_id,
        competitor_page_ids=[int(candidate.competitor_page_id) for candidate in current_candidates],
    )
    semantic_card_by_candidate_id = {
        candidate.id: _candidate_semantic_card(candidate, extraction_by_page_id)
        for candidate in current_candidates
    }

    semantic_clusters, canonicalization_summary = _build_semantic_clusters(
        session,
        site_id,
        active_crawl.id,
        current_candidates,
        own_pages=own_pages,
        own_pages_by_id=own_pages_by_id,
        own_term_index=own_term_index,
        page_records=page_records,
        strategy=strategy,
        semantic_card_by_candidate_id=semantic_card_by_candidate_id,
    )
    rows = _build_semantic_gap_rows(
        semantic_clusters,
        own_pages=own_pages,
        strategy_tokens=_extract_strategy_tokens(strategy),
    )
    rows = _prune_low_value_gap_rows([_normalize_competitive_gap_row(row, semantic_mode=True) for row in rows])
    rows = _dedupe_equivalent_gap_rows(rows)
    counts_by_coverage_type = _build_counts_by_coverage_type(rows)
    cluster_quality_summary = _build_cluster_quality_summary(semantic_clusters)
    response_context["semantic_diagnostics"] = {
        "semantic_version": SEMANTIC_CARD_VERSION,
        "cluster_version": CLUSTER_VERSION,
        "coverage_version": COVERAGE_VERSION,
        "competitor_semantic_cards_count": sum(1 for value in semantic_card_by_candidate_id.values() if value),
        "own_page_semantic_profiles_count": len(own_semantic_profiles),
        "canonical_pages_count": canonicalization_summary["canonical_pages_count"],
        "duplicate_pages_count": canonicalization_summary["duplicate_pages_count"],
        "near_duplicate_pages_count": canonicalization_summary["near_duplicate_pages_count"],
        "clusters_count": cluster_quality_summary["clusters_count"],
        "low_confidence_clusters_count": cluster_quality_summary["low_confidence_clusters_count"],
        "latest_failure_stage": None,
        "latest_failure_error_code": None,
        "latest_failure_error_message": None,
        "coverage_breakdown": counts_by_coverage_type,
    }
    if not rows:
        if competitor_readiness["total_competitor_pages_count"] == 0:
            response_context["empty_state_reason"] = "no_competitor_pages"
        elif competitor_readiness["total_current_extractions_count"] == 0:
            response_context["empty_state_reason"] = "no_competitor_extractions"
    return {
        "context": response_context,
        "summary": _build_summary(
            rows,
            competitors_considered=len(active_competitors),
            counts_by_coverage_type=counts_by_coverage_type,
            canonicalization_summary=canonicalization_summary,
            cluster_quality_summary=cluster_quality_summary,
        ),
        "items": rows,
    }


def _should_skip_semantic_read_model(
    candidates: Sequence[SiteCompetitorSemanticCandidate],
) -> bool:
    return len(candidates) > SEMANTIC_READ_MODEL_MAX_CANDIDATES


def _load_current_semantic_candidates(
    session: Session,
    site_id: int,
    competitor_ids: list[int],
) -> list[SiteCompetitorSemanticCandidate]:
    if not competitor_ids:
        return []
    return session.scalars(
        select(SiteCompetitorSemanticCandidate)
        .options(selectinload(SiteCompetitorSemanticCandidate.competitor_page))
        .where(
            SiteCompetitorSemanticCandidate.site_id == site_id,
            SiteCompetitorSemanticCandidate.current.is_(True),
            SiteCompetitorSemanticCandidate.competitor_id.in_(competitor_ids),
        )
        .order_by(SiteCompetitorSemanticCandidate.id.asc())
    ).all()


def _site_has_semantic_readiness(
    session: Session,
    *,
    active_competitors: list[SiteCompetitor],
    current_candidates: list[SiteCompetitorSemanticCandidate],
) -> bool:
    if not active_competitors:
        return False
    candidate_counts = Counter(int(candidate.competitor_id) for candidate in current_candidates)
    missing_competitor_ids = [
        int(competitor.id)
        for competitor in active_competitors
        if candidate_counts.get(int(competitor.id), 0) <= 0
    ]
    if not missing_competitor_ids:
        return True

    latest_runs = session.scalars(
        select(SiteCompetitorSemanticRun)
        .where(SiteCompetitorSemanticRun.competitor_id.in_(missing_competitor_ids))
        .order_by(
            SiteCompetitorSemanticRun.competitor_id.asc(),
            SiteCompetitorSemanticRun.id.desc(),
        )
    ).all()
    latest_status_by_competitor_id: dict[int, str] = {}
    for run in latest_runs:
        latest_status_by_competitor_id.setdefault(int(run.competitor_id), str(run.status or ""))

    return all(
        latest_status_by_competitor_id.get(competitor_id) == "completed"
        for competitor_id in missing_competitor_ids
    )


def _load_current_semantic_decisions(
    session: Session,
    site_id: int,
    *,
    candidate_ids: list[int],
    active_crawl_id: int,
) -> tuple[list[SiteCompetitorSemanticDecision], list[SiteCompetitorSemanticDecision]]:
    if not candidate_ids:
        return [], []
    decision_rows = session.scalars(
        select(SiteCompetitorSemanticDecision)
        .where(
            SiteCompetitorSemanticDecision.site_id == site_id,
            or_(
                SiteCompetitorSemanticDecision.source_candidate_id.in_(candidate_ids),
                SiteCompetitorSemanticDecision.target_candidate_id.in_(candidate_ids),
            ),
        )
        .order_by(SiteCompetitorSemanticDecision.id.asc())
    ).all()
    merge_rows = [row for row in decision_rows if row.decision_type == "merge"]
    own_rows = [
        row
        for row in decision_rows
        if row.decision_type == "own_match" and row.active_crawl_id == active_crawl_id
    ]
    return merge_rows, own_rows


def _load_latest_valid_extractions_by_page_id(
    session: Session,
    *,
    site_id: int,
    competitor_page_ids: list[int],
) -> dict[int, SiteCompetitorPageExtraction]:
    normalized_page_ids = sorted({int(page_id) for page_id in competitor_page_ids if page_id})
    if not normalized_page_ids:
        return {}
    rows = session.scalars(
        select(SiteCompetitorPageExtraction)
        .options(selectinload(SiteCompetitorPageExtraction.competitor_page))
        .where(
            SiteCompetitorPageExtraction.site_id == site_id,
            SiteCompetitorPageExtraction.competitor_page_id.in_(normalized_page_ids),
        )
        .order_by(
            SiteCompetitorPageExtraction.competitor_page_id.asc(),
            SiteCompetitorPageExtraction.extracted_at.desc(),
            SiteCompetitorPageExtraction.id.desc(),
        )
    ).all()
    latest_by_page_id: dict[int, SiteCompetitorPageExtraction] = {}
    for row in rows:
        page = row.competitor_page
        if page is None:
            continue
        if not bool(page.semantic_eligible):
            continue
        if page.content_text_hash != row.content_hash_at_extraction:
            continue
        page_id = int(row.competitor_page_id)
        if page_id not in latest_by_page_id:
            latest_by_page_id[page_id] = row
    return latest_by_page_id


def _candidate_semantic_card(
    candidate: SiteCompetitorSemanticCandidate,
    extraction_by_page_id: dict[int, SiteCompetitorPageExtraction],
) -> dict[str, Any]:
    extraction = extraction_by_page_id.get(int(candidate.competitor_page_id))
    if extraction is not None and extraction.semantic_card_json:
        return normalize_semantic_card(dict(extraction.semantic_card_json or {}))
    return normalize_semantic_card(
        build_semantic_card(
            primary_topic=candidate.raw_topic_label or candidate.raw_topic_key or "Topic",
            topic_labels=[candidate.raw_topic_label] if candidate.raw_topic_label else [],
            core_problem=candidate.raw_topic_label or candidate.raw_topic_key or "Topic",
            dominant_intent="commercial" if str(candidate.page_bucket or "other") == "commercial" else "informational",
            secondary_intents=[],
            page_role="money_page" if str(candidate.page_type or "") in COMMERCIAL_TYPES else "supporting_page",
            content_format=str(candidate.page_type or "other"),
            target_audience=None,
            entities=[],
            geo_scope=None,
            supporting_subtopics=[],
            what_this_page_is_about=candidate.raw_topic_label or candidate.raw_topic_key or "Topic",
            what_this_page_is_not_about="Unclear boundary.",
            commerciality="high" if str(candidate.page_type or "") in COMMERCIAL_TYPES else "low",
            evidence_snippets=[candidate.raw_topic_label] if candidate.raw_topic_label else [],
            confidence=min(0.95, max(0.45, float(candidate.quality_score or 0) / 100)),
            semantic_version=SEMANTIC_CARD_VERSION,
        )
    )


def _canonicalize_candidates_per_competitor(
    candidate_map: dict[int, SiteCompetitorSemanticCandidate],
    *,
    semantic_card_by_candidate_id: dict[int, dict[str, Any] | None],
) -> dict[str, Any]:
    canonical_candidate_by_id = {candidate_id: candidate_id for candidate_id in candidate_map}
    duplicate_count = 0
    near_duplicate_count = 0
    candidates_by_competitor: dict[int, list[SiteCompetitorSemanticCandidate]] = defaultdict(list)
    for candidate in candidate_map.values():
        candidates_by_competitor[int(candidate.competitor_id)].append(candidate)

    for competitor_candidates in candidates_by_competitor.values():
        ordered = sorted(competitor_candidates, key=lambda item: item.id)
        for index, candidate in enumerate(ordered):
            if canonical_candidate_by_id[candidate.id] != candidate.id:
                continue
            candidate_page = candidate.competitor_page
            candidate_card = semantic_card_by_candidate_id.get(candidate.id)
            for other in ordered[index + 1 :]:
                if canonical_candidate_by_id[other.id] != other.id:
                    continue
                other_page = other.competitor_page
                other_card = semantic_card_by_candidate_id.get(other.id)
                relation = _candidate_canonicalization_relation(
                    candidate_page=candidate_page,
                    candidate_card=candidate_card,
                    other_page=other_page,
                    other_card=other_card,
                )
                if relation is None:
                    continue
                winner, loser = _pick_canonical_candidate(candidate, other, semantic_card_by_candidate_id)
                canonical_candidate_by_id[loser.id] = winner.id
                if relation == "duplicate":
                    duplicate_count += 1
                else:
                    near_duplicate_count += 1

    canonical_pages_count = len({canonical_candidate_by_id[candidate_id] for candidate_id in canonical_candidate_by_id})
    return {
        "canonical_candidate_by_id": canonical_candidate_by_id,
        "summary": {
            "canonical_pages_count": canonical_pages_count,
            "duplicate_pages_count": duplicate_count,
            "near_duplicate_pages_count": near_duplicate_count,
            "filtered_leftovers_count": 0,
        },
    }


def _candidate_canonicalization_relation(
    *,
    candidate_page: SiteCompetitorPage | None,
    candidate_card: dict[str, Any] | None,
    other_page: SiteCompetitorPage | None,
    other_card: dict[str, Any] | None,
) -> str | None:
    if candidate_page is None or other_page is None:
        return None
    if normalize_text_for_hash(candidate_page.normalized_url) == normalize_text_for_hash(other_page.normalized_url):
        return "duplicate"
    similarity = semantic_card_similarity(candidate_card, other_card)
    if similarity["score"] >= 90 and similarity["primary_match"] and similarity["intent_match"]:
        return "duplicate"
    if similarity["score"] >= 80 and (similarity["primary_match"] or similarity["topic_overlap"] >= 0.72):
        return "near_duplicate"
    return None


def _pick_canonical_candidate(
    left: SiteCompetitorSemanticCandidate,
    right: SiteCompetitorSemanticCandidate,
    semantic_card_by_candidate_id: dict[int, dict[str, Any] | None],
) -> tuple[SiteCompetitorSemanticCandidate, SiteCompetitorSemanticCandidate]:
    def sort_key(candidate: SiteCompetitorSemanticCandidate) -> tuple[float, int, int, int]:
        card = semantic_card_by_candidate_id.get(candidate.id) or {}
        return (
            float(card.get("confidence") or 0.0),
            int(candidate.quality_score or 0),
            get_page_word_count(candidate.competitor_page) if candidate.competitor_page is not None else 0,
            -int(candidate.id),
        )

    if sort_key(left) >= sort_key(right):
        return left, right
    return right, left


def _aggregate_cluster_semantic_card(
    members: list[SiteCompetitorSemanticCandidate],
    *,
    semantic_card_by_candidate_id: dict[int, dict[str, Any] | None],
) -> dict[str, Any]:
    cards = [
        normalize_semantic_card(semantic_card_by_candidate_id.get(candidate.id) or {})
        for candidate in members
    ]
    primary_topics = [
        str(card.get("primary_topic") or "").strip()
        for card in cards
        if str(card.get("primary_topic") or "").strip()
    ]
    dominant_intents = [
        str(card.get("dominant_intent") or "other")
        for card in cards
        if str(card.get("dominant_intent") or "").strip()
    ]
    page_roles = [
        str(card.get("page_role") or "other")
        for card in cards
        if str(card.get("page_role") or "").strip()
    ]
    content_formats = [
        str(card.get("content_format") or "other")
        for card in cards
        if str(card.get("content_format") or "").strip()
    ]
    geo_values = [
        str(card.get("geo_scope") or "").strip()
        for card in cards
        if str(card.get("geo_scope") or "").strip()
    ]
    confidence = round(
        sum(float(card.get("confidence") or 0.0) for card in cards) / max(1, len(cards)),
        2,
    )
    return normalize_semantic_card(
        build_semantic_card(
            primary_topic=_most_common_value(primary_topics) or "Topic",
            topic_labels=dedupe_preserve_order(
                label
                for card in cards
                for label in build_topic_labels(card)
            ),
            core_problem=_most_common_value(
                [
                    str(card.get("core_problem") or "").strip()
                    for card in cards
                    if str(card.get("core_problem") or "").strip()
                ]
            )
            or _most_common_value(primary_topics)
            or "Topic",
            dominant_intent=_most_common_value(dominant_intents) or "other",
            secondary_intents=dedupe_preserve_order(
                intent
                for card in cards
                for intent in (card.get("secondary_intents") or [])
            )[:4],
            page_role=_most_common_value(page_roles) or "other",
            content_format=_most_common_value(content_formats) or "other",
            target_audience=_most_common_value(
                [
                    str(card.get("target_audience") or "").strip()
                    for card in cards
                    if str(card.get("target_audience") or "").strip()
                ]
            ),
            entities=dedupe_preserve_order(
                value
                for card in cards
                for value in (card.get("entities") or [])
                if value
            )[:10],
            geo_scope=_most_common_value(geo_values),
            supporting_subtopics=dedupe_preserve_order(
                value
                for card in cards
                for value in (card.get("supporting_subtopics") or [])
                if value
            )[:8],
            what_this_page_is_about=_most_common_value(
                [
                    str(card.get("what_this_page_is_about") or "").strip()
                    for card in cards
                    if str(card.get("what_this_page_is_about") or "").strip()
                ]
            )
            or _most_common_value(primary_topics)
            or "Topic",
            what_this_page_is_not_about=_most_common_value(
                [
                    str(card.get("what_this_page_is_not_about") or "").strip()
                    for card in cards
                    if str(card.get("what_this_page_is_not_about") or "").strip()
                ]
            )
            or "Unclear boundary.",
            commerciality=_most_common_value(
                [
                    str(card.get("commerciality") or "neutral")
                    for card in cards
                    if str(card.get("commerciality") or "").strip()
                ]
            )
            or "neutral",
            evidence_snippets=dedupe_preserve_order(
                value
                for card in cards
                for value in (card.get("evidence_snippets") or [])
                if value
            )[:4],
            confidence=confidence,
            semantic_version=CLUSTER_VERSION,
        )
    )


def _cluster_role_summary(
    members: list[SiteCompetitorSemanticCandidate],
    *,
    semantic_card_by_candidate_id: dict[int, dict[str, Any] | None],
) -> dict[str, int]:
    counts = Counter(
        str((semantic_card_by_candidate_id.get(candidate.id) or {}).get("page_role") or "other")
        for candidate in members
    )
    return dict(counts)


def _token_overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def _topic_tokens_from_values(*values: Any) -> set[str]:
    tokens: list[str] = []
    for value in values:
        tokens.extend(tokenize_topic_text(str(value or "")))
    return {
        token
        for token in dedupe_preserve_order(tokens)
        if token and token not in IGNORED_TOPIC_TOKENS
    }


def _semantic_card_anchor_tokens(card: dict[str, Any]) -> set[str]:
    return _topic_tokens_from_values(
        card.get("primary_topic"),
        *(card.get("topic_labels") or [])[:2],
        card.get("core_problem"),
    )


def _own_page_anchor_tokens(page: OwnPageTopicProfile) -> set[str]:
    return _topic_tokens_from_values(
        page.title,
        page.h1,
        page.meta_description,
        page.topic_key,
        page.semantic_card.get("primary_topic"),
    )


def _build_own_page_term_index(own_pages: list[OwnPageTopicProfile]) -> dict[str, set[int]]:
    index: dict[str, set[int]] = defaultdict(set)
    for page in own_pages:
        page_terms = set(page.topic_tokens)
        page_terms.update(_own_page_anchor_tokens(page))
        page_terms.update(_topic_tokens_from_values(*(page.entities or []), *(page.supporting_subtopics or [])))
        for term in page_terms:
            normalized = normalize_text_for_hash(term).replace(" ", "-")
            if normalized:
                index[normalized].add(page.page_id)
    return index


def _cluster_related_own_pages(
    cluster_card: dict[str, Any],
    *,
    own_pages: list[OwnPageTopicProfile],
    own_pages_by_id: dict[int, OwnPageTopicProfile],
    own_term_index: dict[str, set[int]],
) -> list[OwnPageTopicProfile]:
    cluster_terms = set(build_semantic_match_terms(cluster_card))
    cluster_terms.update(_semantic_card_anchor_tokens(cluster_card))
    cluster_terms.update(_topic_tokens_from_values(*(cluster_card.get("entities") or []), *(cluster_card.get("supporting_subtopics") or [])))
    related_page_ids: set[int] = set()
    for term in cluster_terms:
        normalized = normalize_text_for_hash(term).replace(" ", "-")
        if normalized:
            related_page_ids.update(own_term_index.get(normalized, set()))
    if not related_page_ids:
        return list(own_pages)
    return [
        own_pages_by_id[page_id]
        for page_id in sorted(related_page_ids)
        if page_id in own_pages_by_id
    ]


def _resolve_cluster_coverage(
    *,
    cluster_card: dict[str, Any],
    cluster_members: list[SiteCompetitorSemanticCandidate],
    own_pages: list[OwnPageTopicProfile],
) -> dict[str, Any]:
    cluster_terms = set(build_semantic_match_terms(cluster_card))
    cluster_anchor_tokens = _semantic_card_anchor_tokens(cluster_card)
    ranked_matches: list[tuple[int, dict[str, Any], dict[str, Any], OwnPageTopicProfile]] = []
    for page in own_pages:
        similarity = semantic_card_similarity(cluster_card, page.semantic_card)
        anchor_overlap_score = _token_overlap_ratio(cluster_anchor_tokens, _own_page_anchor_tokens(page))
        term_overlap_score = _token_overlap_ratio(cluster_terms, set(page.topic_tokens))
        intent_alignment = bool(similarity["intent_match"]) or (
            normalize_text_for_hash(cluster_card.get("dominant_intent"))
            == normalize_text_for_hash(page.dominant_intent)
        )
        role_alignment = (
            normalize_text_for_hash(cluster_card.get("page_role"))
            == normalize_text_for_hash(page.page_role)
        )
        if (
            similarity["score"] < 36
            and anchor_overlap_score < 0.2
            and term_overlap_score < 0.18
            and not similarity["primary_match"]
        ):
            continue
        combined_score = int(similarity["score"])
        combined_score += int(round(anchor_overlap_score * 18))
        combined_score += int(round(term_overlap_score * 14))
        if intent_alignment:
            combined_score += 8
        if role_alignment:
            combined_score += 6
        ranked_matches.append(
            (
                combined_score,
                similarity,
                {
                    "anchor_overlap_score": round(anchor_overlap_score, 2),
                    "term_overlap_score": round(term_overlap_score, 2),
                    "intent_alignment": intent_alignment,
                    "role_alignment": role_alignment,
                },
                page,
            )
        )
    ranked_matches.sort(
        key=lambda item: (
            -int(item[0]),
            -int(item[1]["score"]),
            -int(item[3].priority_score),
            -int(item[3].impressions),
            int(item[3].page_id),
        )
    )
    matched_pages = [page for _score, _similarity, _signals, page in ranked_matches[:3]]
    best_similarity = ranked_matches[0][1] if ranked_matches else None
    best_match_signals = ranked_matches[0][2] if ranked_matches else None
    best_page = ranked_matches[0][3] if ranked_matches else None
    role_summary = Counter(
        "commercial" if str(member.page_type or "other") in COMMERCIAL_TYPES else "supporting"
        for member in cluster_members
    )
    mismatch_notes: list[str] = []
    coverage_type: str = "no_meaningful_coverage"
    gap_detail_type: str | None = "NEW_TOPIC"
    coverage_reason_code: str | None = "no_relevant_match"
    coverage_debug: dict[str, Any] = {}
    coverage_confidence = round(float(cluster_card.get("confidence") or 0.0), 2)
    if best_similarity is not None and best_page is not None:
        best_anchor_overlap = float((best_match_signals or {}).get("anchor_overlap_score") or 0.0)
        best_term_overlap = float((best_match_signals or {}).get("term_overlap_score") or 0.0)
        best_intent_alignment = bool((best_match_signals or {}).get("intent_alignment"))
        best_role_alignment = bool((best_match_signals or {}).get("role_alignment"))
        coverage_confidence = round(
            min(0.98, (float(cluster_card.get("confidence") or 0.0) + (int(best_similarity["score"]) / 100)) / 2),
            2,
        )
        coverage_debug = {
            "similarity_score": int(best_similarity["score"]),
            "primary_match": bool(best_similarity["primary_match"]),
            "intent_alignment": best_intent_alignment,
            "role_alignment": best_role_alignment,
            "anchor_overlap_score": round(best_anchor_overlap, 2),
            "term_overlap_score": round(best_term_overlap, 2),
            "best_page_type": best_page.page_type,
            "best_page_role": best_page.page_role,
            "best_page_intent": best_page.dominant_intent,
        }
        if (
            not best_intent_alignment
            and (
                int(best_similarity["score"]) >= 58
                or best_anchor_overlap >= 0.34
                or best_term_overlap >= 0.32
            )
        ):
            coverage_type = "wrong_intent_coverage"
            gap_detail_type = "INTENT_MISMATCH"
            coverage_reason_code = "intent_mismatch_with_real_overlap"
            mismatch_notes.append("Closest own-page match targets a different dominant intent.")
        elif (
            role_summary.get("commercial", 0) > 0
            and best_page.page_type in SUPPORTING_TYPES
            and (
                int(best_similarity["score"]) >= 56
                or best_anchor_overlap >= 0.3
                or best_term_overlap >= 0.28
            )
        ):
            coverage_type = "informational_missing_commercial"
            gap_detail_type = "MISSING_MONEY_PAGE"
            coverage_reason_code = "supporting_only_where_money_page_needed"
            mismatch_notes.append("Own coverage is mostly informational while competitors win with money pages.")
        elif (
            role_summary.get("supporting", 0) > 0
            and best_page.page_type in COMMERCIAL_TYPES
            and (
                int(best_similarity["score"]) >= 56
                or best_anchor_overlap >= 0.3
                or best_term_overlap >= 0.28
            )
        ):
            coverage_type = "commercial_missing_supporting"
            gap_detail_type = "MISSING_SUPPORTING_CONTENT"
            coverage_reason_code = "money_page_only_where_supporting_content_needed"
            mismatch_notes.append("Own coverage lacks supporting informational assets around the topic cluster.")
        elif (
            int(best_similarity["score"]) >= 90
            and best_intent_alignment
            and (best_similarity["primary_match"] or best_anchor_overlap >= 0.55)
        ):
            coverage_type = "exact_coverage"
            gap_detail_type = None
            coverage_reason_code = "exact_semantic_and_anchor_alignment"
        elif (
            (
                int(best_similarity["score"]) >= 68
                and best_intent_alignment
            )
            or (
                bool(best_similarity["primary_match"])
                and best_anchor_overlap >= 0.34
            )
            or (
                best_term_overlap >= 0.42
                and best_intent_alignment
            )
        ):
            coverage_type = "strong_semantic_coverage"
            gap_detail_type = _resolve_gap_detail_from_best_match(cluster_card, best_page, best_similarity)
            coverage_reason_code = "strong_semantic_overlap"
        elif (
            int(best_similarity["score"]) >= 46
            or best_similarity["primary_match"]
            or best_anchor_overlap >= 0.22
            or best_term_overlap >= 0.26
        ):
            coverage_type = "partial_coverage"
            gap_detail_type = _resolve_gap_detail_from_best_match(cluster_card, best_page, best_similarity)
            coverage_reason_code = "partial_semantic_overlap"

    coarse_own_match_status = _coarse_own_match_status(coverage_type)
    return {
        "own_match_status": coarse_own_match_status,
        "own_match_source": best_page.normalized_url if best_page is not None else None,
        "coverage_type": coverage_type,
        "coverage_confidence": coverage_confidence,
        "coverage_rationale": _build_coverage_rationale(
            coverage_type,
            cluster_card,
            best_similarity,
            best_page,
            coverage_reason_code=coverage_reason_code,
            coverage_debug=coverage_debug,
        ),
        "coverage_reason_code": coverage_reason_code,
        "coverage_debug": coverage_debug,
        "coverage_best_own_urls": [page.normalized_url for page in matched_pages],
        "mismatch_notes": mismatch_notes,
        "gap_detail_type": gap_detail_type,
        "own_page_id": best_page.page_id if best_page is not None else None,
        "own_page_type": best_page.page_type if best_page is not None else None,
        "own_page_title": best_page.title or best_page.h1 or best_page.normalized_url if best_page is not None else None,
        "matched_own_page_ids": [page.page_id for page in matched_pages],
        "own_page_tokens": set(best_page.topic_tokens) if best_page is not None else set(),
        "topic_tokens": cluster_terms,
    }


def _resolve_gap_detail_from_best_match(
    cluster_card: dict[str, Any],
    best_page: OwnPageTopicProfile,
    similarity: dict[str, Any],
) -> str:
    cluster_geo = normalize_text_for_hash(cluster_card.get("geo_scope"))
    page_geo = normalize_text_for_hash(best_page.geo_scope)
    if cluster_geo and page_geo and cluster_geo != page_geo:
        return "GEO_GAP"
    cluster_format = normalize_text_for_hash(cluster_card.get("content_format"))
    page_format = normalize_text_for_hash(best_page.content_format)
    if cluster_format and page_format and cluster_format != page_format:
        return "FORMAT_GAP"
    return "EXPAND_EXISTING_PAGE"


def _build_coverage_rationale(
    coverage_type: str,
    cluster_card: dict[str, Any],
    best_similarity: dict[str, Any] | None,
    best_page: OwnPageTopicProfile | None,
    *,
    coverage_reason_code: str | None,
    coverage_debug: dict[str, Any] | None,
) -> str:
    primary_topic = str(cluster_card.get("primary_topic") or "this topic")
    if best_similarity is None or best_page is None:
        return f"No meaningful own-page semantic coverage was found for {primary_topic}."
    coverage_debug = coverage_debug or {}
    best_page_label = best_page.title or best_page.h1 or best_page.normalized_url
    score = int(coverage_debug.get("similarity_score") or best_similarity["score"])
    anchor_overlap = coverage_debug.get("anchor_overlap_score")
    if coverage_reason_code == "intent_mismatch_with_real_overlap":
        return (
            f"{best_page_label} overlaps strongly with {primary_topic}, but it targets a different intent "
            f"(semantic score {score}, anchor overlap {anchor_overlap})."
        )
    if coverage_reason_code == "supporting_only_where_money_page_needed":
        return (
            f"{best_page_label} covers {primary_topic} mainly as supporting content, while competitors win with "
            f"commercial money pages."
        )
    if coverage_reason_code == "money_page_only_where_supporting_content_needed":
        return (
            f"{best_page_label} covers {primary_topic} as a money page, but competitors also reinforce the topic "
            f"with supporting informational assets."
        )
    if coverage_reason_code == "strong_semantic_overlap":
        return (
            f"{best_page_label} already covers {primary_topic} with meaningful semantic overlap "
            f"(semantic score {score}, anchor overlap {anchor_overlap})."
        )
    if coverage_reason_code == "partial_semantic_overlap":
        return (
            f"{best_page_label} partially covers {primary_topic}, but the overlap is incomplete "
            f"(semantic score {score}, anchor overlap {anchor_overlap})."
        )
    if coverage_reason_code == "exact_semantic_and_anchor_alignment":
        return f"{best_page_label} already matches {primary_topic} closely across intent and on-page anchors."
    return (
        f"Best own-page match for {primary_topic} is {best_page_label} "
        f"with semantic score {best_similarity['score']}."
    )


def _coarse_own_match_status(coverage_type: str) -> str:
    if coverage_type == "exact_coverage":
        return "exact_match"
    if coverage_type in {"strong_semantic_coverage", "wrong_intent_coverage"}:
        return "semantic_match"
    if coverage_type in {"partial_coverage", "commercial_missing_supporting", "informational_missing_commercial"}:
        return "partial_coverage"
    return "no_meaningful_match"


def _most_common_value(values: list[str]) -> str | None:
    cleaned = [value for value in values if value]
    if not cleaned:
        return None
    return min(
        Counter(cleaned).items(),
        key=lambda item: (-item[1], len(item[0]), item[0].lower()),
    )[0]

def _build_semantic_clusters(
    session: Session,
    site_id: int,
    active_crawl_id: int,
    candidates: list[SiteCompetitorSemanticCandidate],
    *,
    own_pages: list[OwnPageTopicProfile],
    own_pages_by_id: dict[int, OwnPageTopicProfile],
    own_term_index: dict[str, set[int]],
    page_records: list[dict[str, Any]],
    strategy: dict[str, Any] | None,
    semantic_card_by_candidate_id: dict[int, dict[str, Any] | None],
) -> tuple[list[SemanticGapCluster], dict[str, int]]:
    from app.services import competitive_gap_semantic_service

    candidate_map = {candidate.id: candidate for candidate in candidates}
    if not candidate_map:
        return [], {
            "canonical_pages_count": 0,
            "duplicate_pages_count": 0,
            "near_duplicate_pages_count": 0,
            "filtered_leftovers_count": 0,
        }

    merge_rows, _own_rows = _load_current_semantic_decisions(
        session,
        site_id,
        candidate_ids=list(candidate_map),
        active_crawl_id=active_crawl_id,
    )
    canonicalization = _canonicalize_candidates_per_competitor(
        candidate_map,
        semantic_card_by_candidate_id=semantic_card_by_candidate_id,
    )

    parent = {candidate_id: candidate_id for candidate_id in candidate_map}

    def find(candidate_id: int) -> int:
        while parent[candidate_id] != candidate_id:
            parent[candidate_id] = parent[parent[candidate_id]]
            candidate_id = parent[candidate_id]
        return candidate_id

    def union(left_id: int, right_id: int) -> None:
        left_root = find(left_id)
        right_root = find(right_id)
        if left_root != right_root:
            parent[right_root] = left_root

    for candidate_id, canonical_id in canonicalization["canonical_candidate_by_id"].items():
        if candidate_id != canonical_id and candidate_id in candidate_map and canonical_id in candidate_map:
            union(canonical_id, candidate_id)

    raw_bucket_map: dict[str, list[int]] = defaultdict(list)
    for candidate in candidate_map.values():
        bucket_key = _semantic_bucket_key(
            candidate.raw_topic_key,
            candidate.raw_topic_label,
            candidate.page_type,
            candidate.page_bucket,
        )
        raw_bucket_map[bucket_key].append(candidate.id)
    for ids in raw_bucket_map.values():
        if not ids:
            continue
        head = ids[0]
        for tail in ids[1:]:
            union(head, tail)

    for row in merge_rows:
        if row.decision_label not in {"same_topic", "related_subtopic"}:
            continue
        if row.source_candidate_id not in candidate_map or row.target_candidate_id is None:
            continue
        if row.target_candidate_id not in candidate_map:
            continue
        union(row.source_candidate_id, row.target_candidate_id)

    candidate_items = sorted(candidate_map.values(), key=lambda item: item.id)
    term_index = competitive_gap_semantic_service._build_term_index(candidate_items)
    for source_candidate in candidate_items:
        source_card = semantic_card_by_candidate_id.get(source_candidate.id)
        if not source_card:
            continue
        target_ids = competitive_gap_semantic_service._candidate_ids_from_index(
            term_index,
            competitive_gap_semantic_service._candidate_normalized_terms(source_candidate),
            exclude_id=source_candidate.id,
        )
        for target_id in target_ids:
            if target_id <= source_candidate.id:
                continue
            target_candidate = candidate_map.get(target_id)
            if target_candidate is None:
                continue
            if source_candidate.competitor_id == target_candidate.competitor_id:
                continue
            target_card = semantic_card_by_candidate_id.get(target_candidate.id)
            if not target_card:
                continue
            similarity = semantic_card_similarity(source_card, target_card)
            if (
                similarity["score"] >= 84
                and similarity["intent_match"]
                and (similarity["primary_match"] or similarity["topic_overlap"] >= 0.58)
            ):
                union(source_candidate.id, target_candidate.id)
            elif similarity["score"] >= 76 and similarity["primary_match"]:
                union(source_candidate.id, target_candidate.id)

    components: dict[int, list[SiteCompetitorSemanticCandidate]] = defaultdict(list)
    for candidate in candidate_map.values():
        components[find(candidate.id)].append(candidate)

    prepared_clusters: list[dict[str, Any]] = []
    for members in components.values():
        members.sort(key=lambda candidate: candidate.id)
        member_ids = [candidate.id for candidate in members]
        member_raw_topic_keys = [
            _normalize_semantic_bucket_token(candidate.raw_topic_key) or _normalize_semantic_bucket_token(candidate.raw_topic_label) or f"candidate-{candidate.id}"
            for candidate in members
        ]
        member_labels = [
            collapse_whitespace(candidate.raw_topic_label) or _prettify_topic_key(candidate.raw_topic_key or f"candidate-{candidate.id}")
            for candidate in members
        ]
        cluster_card = _aggregate_cluster_semantic_card(
            members,
            semantic_card_by_candidate_id=semantic_card_by_candidate_id,
        )
        canonical_topic_label = (
            str(cluster_card.get("primary_topic") or "").strip()
            or _choose_canonical_topic_label(members, merge_rows, [])
        )
        semantic_topic_key = _build_semantic_topic_key(canonical_topic_label, member_raw_topic_keys, member_labels)
        semantic_cluster_key = _build_semantic_cluster_key(
            site_id=site_id,
            member_ids=member_ids,
            candidate_map=candidate_map,
        )
        competitor_ids = sorted({candidate.competitor_id for candidate in members})
        competitor_urls = dedupe_preserve_order(
            [
                str(candidate.competitor_page.normalized_url or candidate.competitor_page.url)
                for candidate in members
                if candidate.competitor_page is not None
            ]
        )[:10]
        page_types = Counter(str(candidate.page_type or "other") for candidate in members)
        cluster_role_summary = _cluster_role_summary(members, semantic_card_by_candidate_id=semantic_card_by_candidate_id)
        cluster_summary_payload = {
            "semantic_cluster_key": semantic_cluster_key,
            "topic_key": semantic_topic_key,
            "canonical_topic_label": canonical_topic_label,
            "source_candidate_ids": member_ids,
            "competitor_ids": competitor_ids,
            "raw_topic_keys": member_raw_topic_keys,
            "source_topic_labels": member_labels,
            "cluster_confidence": round(float(cluster_card.get("confidence") or 0.0), 2),
            "cluster_intent_profile": str(cluster_card.get("dominant_intent") or "other"),
            "cluster_role_summary": cluster_role_summary,
        }
        cluster_state_hash = competitive_gap_cluster_state_service.build_cluster_state_hash(
            cluster_summary=cluster_summary_payload,
        )
        related_own_pages = _cluster_related_own_pages(
            cluster_card,
            own_pages=own_pages,
            own_pages_by_id=own_pages_by_id,
            own_term_index=own_term_index,
        )
        coverage_state_hash = competitive_gap_cluster_state_service.build_coverage_state_hash(
            active_crawl_id=active_crawl_id,
            related_own_pages=related_own_pages,
        )
        prepared_clusters.append(
            {
                "members": members,
                "member_ids": member_ids,
                "member_raw_topic_keys": member_raw_topic_keys,
                "member_labels": member_labels,
                "cluster_card": cluster_card,
                "canonical_topic_label": canonical_topic_label,
                "semantic_topic_key": semantic_topic_key,
                "semantic_cluster_key": semantic_cluster_key,
                "competitor_ids": competitor_ids,
                "competitor_urls": competitor_urls,
                "page_types": page_types,
                "cluster_role_summary": cluster_role_summary,
                "cluster_summary_payload": cluster_summary_payload,
                "cluster_state_hash": cluster_state_hash,
                "related_own_pages": related_own_pages,
                "coverage_state_hash": coverage_state_hash,
            }
        )

    cached_states_by_key = competitive_gap_cluster_state_service.load_cluster_state_map(
        session,
        site_id=site_id,
        active_crawl_id=active_crawl_id,
        semantic_cluster_keys=[
            str(cluster["semantic_cluster_key"])
            for cluster in prepared_clusters
        ],
    )

    clusters: list[SemanticGapCluster] = []
    for prepared_cluster in prepared_clusters:
        members = prepared_cluster["members"]
        member_ids = prepared_cluster["member_ids"]
        member_raw_topic_keys = prepared_cluster["member_raw_topic_keys"]
        member_labels = prepared_cluster["member_labels"]
        cluster_card = prepared_cluster["cluster_card"]
        canonical_topic_label = prepared_cluster["canonical_topic_label"]
        semantic_topic_key = prepared_cluster["semantic_topic_key"]
        semantic_cluster_key = prepared_cluster["semantic_cluster_key"]
        competitor_ids = prepared_cluster["competitor_ids"]
        competitor_urls = prepared_cluster["competitor_urls"]
        page_types = prepared_cluster["page_types"]
        cluster_role_summary = prepared_cluster["cluster_role_summary"]
        cluster_summary_payload = prepared_cluster["cluster_summary_payload"]
        cluster_state_hash = prepared_cluster["cluster_state_hash"]
        related_own_pages = prepared_cluster["related_own_pages"]
        coverage_state_hash = prepared_cluster["coverage_state_hash"]
        cached_state = cached_states_by_key.get(semantic_cluster_key)
        if (
            cached_state is not None
            and str(cached_state.cluster_state_hash or "") == cluster_state_hash
            and str(cached_state.coverage_state_hash or "") == coverage_state_hash
        ):
            coverage = competitive_gap_cluster_state_service.normalize_cached_coverage_state(
                dict(cached_state.coverage_state_json or {})
            )
            cached_page_id = coverage.get("own_page_id")
            cached_best_page = (
                own_pages_by_id.get(int(cached_page_id))
                if cached_page_id is not None
                else None
            )
            coverage["own_page_tokens"] = set(cached_best_page.topic_tokens) if cached_best_page is not None else set()
            coverage["topic_tokens"] = set(build_semantic_match_terms(cluster_card))
        else:
            coverage = _resolve_cluster_coverage(
                cluster_card=cluster_card,
                cluster_members=members,
                own_pages=related_own_pages,
            )
            competitive_gap_cluster_state_service.upsert_cluster_state(
                session,
                site_id=site_id,
                active_crawl_id=active_crawl_id,
                semantic_cluster_key=semantic_cluster_key,
                topic_key=semantic_topic_key,
                canonical_topic_label=canonical_topic_label,
                source_candidate_ids=member_ids,
                competitor_ids=competitor_ids,
                cluster_state_hash=cluster_state_hash,
                coverage_state_hash=coverage_state_hash,
                cluster_summary_json=cluster_summary_payload,
                coverage_state_json={
                    "own_match_status": coverage["own_match_status"],
                    "own_match_source": coverage["own_match_source"],
                    "coverage_type": coverage["coverage_type"],
                    "coverage_confidence": coverage["coverage_confidence"],
                    "coverage_rationale": coverage["coverage_rationale"],
                    "coverage_reason_code": coverage["coverage_reason_code"],
                    "coverage_debug": coverage["coverage_debug"],
                    "coverage_best_own_urls": coverage["coverage_best_own_urls"],
                    "mismatch_notes": coverage["mismatch_notes"],
                    "gap_detail_type": coverage["gap_detail_type"],
                    "own_page_id": coverage["own_page_id"],
                    "own_page_type": coverage["own_page_type"],
                    "own_page_title": coverage["own_page_title"],
                    "matched_own_page_ids": coverage["matched_own_page_ids"],
                },
                existing_row=cached_state,
            )
        clusters.append(
            SemanticGapCluster(
                semantic_cluster_key=semantic_cluster_key,
                topic_key=semantic_topic_key,
                topic_label=canonical_topic_label or _prettify_topic_key(semantic_topic_key),
                canonical_topic_label=canonical_topic_label,
                candidate_ids=member_ids,
                competitor_ids=competitor_ids,
                competitor_urls=competitor_urls,
                page_types=page_types,
                page_count=len(member_ids),
                competitor_count=len(competitor_ids),
                merged_topic_count=len(member_ids),
                raw_topic_keys=member_raw_topic_keys,
                source_topic_labels=member_labels,
                semantic_card=cluster_card,
                cluster_confidence=float(cluster_card.get("confidence") or 0.0),
                cluster_intent_profile=str(cluster_card.get("dominant_intent") or "other"),
                cluster_role_summary=cluster_role_summary,
                cluster_entities=[str(value) for value in (cluster_card.get("entities") or []) if value],
                cluster_geo_scope=(
                    str(cluster_card.get("geo_scope")) if cluster_card.get("geo_scope") not in (None, "") else None
                ),
                supporting_evidence=[str(value) for value in (cluster_card.get("evidence_snippets") or []) if value],
                own_match_status=coverage["own_match_status"],
                own_match_source=coverage["own_match_source"],
                coverage_type=coverage["coverage_type"],
                coverage_confidence=coverage["coverage_confidence"],
                coverage_rationale=coverage["coverage_rationale"],
                coverage_reason_code=coverage["coverage_reason_code"],
                coverage_debug=coverage["coverage_debug"],
                coverage_best_own_urls=coverage["coverage_best_own_urls"],
                mismatch_notes=coverage["mismatch_notes"],
                gap_detail_type=coverage["gap_detail_type"],
                own_page_id=coverage["own_page_id"],
                own_page_type=coverage["own_page_type"],
                own_page_title=coverage["own_page_title"],
                matched_own_page_ids=coverage["matched_own_page_ids"],
                own_page_tokens=coverage["own_page_tokens"],
                topic_tokens=coverage["topic_tokens"],
            )
        )

    clusters.sort(key=lambda cluster: (-cluster.competitor_count, -cluster.merged_topic_count, cluster.semantic_cluster_key))
    return clusters, canonicalization["summary"]


def _build_semantic_gap_rows(
    clusters: list[SemanticGapCluster],
    *,
    own_pages: list[OwnPageTopicProfile],
    strategy_tokens: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster in clusters:
        matched_pages = _matched_own_pages_for_cluster(cluster, own_pages)
        gap_type, target_page, suggested_page_type = _classify_semantic_gap(cluster, matched_pages)
        if gap_type is None:
            continue

        competitor_coverage_score = _semantic_competitor_coverage_score(cluster)
        own_coverage_score = _semantic_own_coverage_score(matched_pages)
        consensus_score = _semantic_consensus_score(cluster)
        strategy_alignment_score = _strategy_alignment_score(
            _cluster_as_topic_profile(cluster),
            strategy_tokens,
        )
        business_value_score = _semantic_business_value_score(matched_pages, cluster)
        priority_score = _priority_score(
            competitor_coverage_score=competitor_coverage_score,
            own_coverage_score=own_coverage_score,
            consensus_score=consensus_score,
            strategy_alignment_score=strategy_alignment_score,
            business_value_score=business_value_score,
        )
        confidence = _semantic_confidence_score(cluster, matched_pages, gap_type)
        target_page_type = target_page.page_type if target_page is not None else None
        effective_page_type = suggested_page_type or target_page_type or "other"
        gap_key = build_competitive_gap_key(
            gap_type=gap_type,
            topic_key=cluster.semantic_cluster_key,
            target_page_id=target_page.page_id if target_page is not None else None,
            suggested_page_type=suggested_page_type,
        )
        rows.append(
            {
                "gap_key": gap_key,
                "semantic_cluster_key": cluster.semantic_cluster_key,
                "gap_type": gap_type,
                "segment": SEGMENT_BY_GAP_TYPE[gap_type],
                "topic_key": cluster.topic_key,
                "topic_label": cluster.topic_label,
                "canonical_topic_label": cluster.canonical_topic_label,
                "merged_topic_count": cluster.merged_topic_count,
                "own_match_status": cluster.own_match_status,
                "coverage_type": cluster.coverage_type,
                "coverage_confidence": cluster.coverage_confidence,
                "coverage_rationale": cluster.coverage_rationale,
                "coverage_best_own_urls": cluster.coverage_best_own_urls,
                "mismatch_notes": cluster.mismatch_notes,
                "own_match_source": cluster.own_match_source,
                "gap_detail_type": cluster.gap_detail_type,
                "target_page_id": target_page.page_id if target_page is not None else None,
                "target_url": target_page.url if target_page is not None else None,
                "page_type": effective_page_type,
                "target_page_type": target_page_type,
                "suggested_page_type": suggested_page_type,
                "cluster_member_count": cluster.page_count,
                "cluster_confidence": cluster.cluster_confidence,
                "cluster_intent_profile": cluster.cluster_intent_profile,
                "cluster_role_summary": cluster.cluster_role_summary,
                "cluster_entities": cluster.cluster_entities,
                "cluster_geo_scope": cluster.cluster_geo_scope,
                "supporting_evidence": cluster.supporting_evidence,
                "competitor_ids": cluster.competitor_ids,
                "competitor_count": cluster.competitor_count,
                "competitor_urls": cluster.competitor_urls,
                "consensus_score": consensus_score,
                "competitor_coverage_score": competitor_coverage_score,
                "own_coverage_score": own_coverage_score,
                "strategy_alignment_score": strategy_alignment_score,
                "business_value_score": business_value_score,
                "priority_score": priority_score,
                "confidence": confidence,
                "rationale": _build_semantic_rationale(cluster, matched_pages, gap_type, suggested_page_type, target_page),
                "signals": {
                    "competitor_pages": cluster.page_count,
                    "competitor_page_types": dict(cluster.page_types),
                    "own_matched_pages": len(matched_pages),
                    "own_page_types": sorted({page.page_type for page in matched_pages}),
                    "semantic": {
                        "semantic_cluster_key": cluster.semantic_cluster_key,
                        "canonical_topic_label": cluster.canonical_topic_label,
                        "merged_topic_count": cluster.merged_topic_count,
                        "source_candidate_ids": cluster.candidate_ids,
                        "source_competitor_ids": cluster.competitor_ids,
                        "source_topic_keys": cluster.raw_topic_keys,
                        "own_match_status": cluster.own_match_status,
                        "coverage_type": cluster.coverage_type,
                        "coverage_confidence": cluster.coverage_confidence,
                        "coverage_reason_code": cluster.coverage_reason_code,
                        "coverage_debug": cluster.coverage_debug,
                        "gap_detail_type": cluster.gap_detail_type,
                        "own_match_source": cluster.own_match_source,
                        "evidence_strength": "strong"
                        if float(cluster.cluster_confidence or 0.0) >= 0.72
                        else "weak",
                        "evidence_strength_reason": (
                            "cluster_confidence"
                            if float(cluster.cluster_confidence or 0.0) >= 0.72
                            else "low_cluster_confidence"
                        ),
                    },
                },
            }
        )

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        existing = deduped.get(row["gap_key"])
        if existing is None or int(row["priority_score"]) > int(existing["priority_score"]):
            deduped[row["gap_key"]] = row
    return list(deduped.values())


def _matched_own_pages_for_cluster(
    cluster: SemanticGapCluster,
    own_pages: list[OwnPageTopicProfile],
) -> list[OwnPageTopicProfile]:
    matched_pages: dict[int, OwnPageTopicProfile] = {}
    matched_page_ids = set(cluster.matched_own_page_ids)
    for page in own_pages:
        if page.page_id in matched_page_ids or page.page_id == cluster.own_page_id:
            matched_pages[page.page_id] = page
    return list(matched_pages.values())


def _classify_semantic_gap(
    cluster: SemanticGapCluster,
    matches: list[OwnPageTopicProfile],
) -> tuple[CompetitiveGapType | None, OwnPageTopicProfile | None, str | None]:
    if cluster.coverage_type == "exact_coverage" and cluster.gap_detail_type is None:
        return None, None, None
    dominant_page_type = _dominant_page_type(cluster.page_types)
    if cluster.gap_detail_type in {"NEW_TOPIC", "MISSING_MONEY_PAGE"} or (
        not matches and cluster.coverage_type == "no_meaningful_coverage"
    ):
        suggested_page_type = dominant_page_type or "service"
        return "NEW_TOPIC", None, suggested_page_type

    target_page = max(
        matches,
        key=lambda page: (page.priority_score, page.impressions, page.clicks, -page.page_id),
    )
    if cluster.gap_detail_type == "MISSING_SUPPORTING_CONTENT":
        suggested_support_type = next(
            (
                page_type
                for page_type, _count in cluster.page_types.most_common()
                if page_type in SUPPORTING_TYPES
            ),
            "faq",
        )
        return "MISSING_SUPPORTING_PAGE", target_page, suggested_support_type

    if cluster.gap_detail_type in {"INTENT_MISMATCH", "FORMAT_GAP", "GEO_GAP", "EXPAND_EXISTING_PAGE"} or (
        _semantic_competitor_coverage_score(cluster) - _semantic_own_coverage_score(matches) >= 18
    ):
        return "EXPAND_EXISTING_TOPIC", target_page, None

    return None, target_page, None


def _cluster_as_topic_profile(cluster: SemanticGapCluster) -> SemanticGapCluster:
    return cluster


def _semantic_competitor_coverage_score(cluster: SemanticGapCluster) -> int:
    score = 22
    score += min(28, cluster.competitor_count * 16)
    score += min(18, cluster.page_count * 7)
    score += min(16, len(cluster.page_types) * 6)
    return max(0, min(100, score))


def _semantic_own_coverage_score(matches: list[OwnPageTopicProfile]) -> int:
    if not matches:
        return 0
    page_type_diversity = len({page.page_type for page in matches})
    max_priority_score = max(page.priority_score for page in matches)
    max_impressions = max(page.impressions for page in matches)
    score = 18
    score += min(20, len(matches) * 10)
    score += min(16, page_type_diversity * 6)
    score += min(24, max_priority_score // 3)
    score += min(12, max_impressions // 40)
    return max(0, min(100, score))


def _semantic_consensus_score(cluster: SemanticGapCluster) -> int:
    score = 15 + min(55, cluster.competitor_count * 22) + min(
        20,
        max(0, cluster.page_count - cluster.competitor_count) * 6,
    )
    return max(0, min(100, score))


def _semantic_business_value_score(matches: list[OwnPageTopicProfile], cluster: SemanticGapCluster) -> int:
    if not matches:
        return max(20, min(70, 18 + cluster.competitor_count * 12 + cluster.page_count * 6))
    best_match = max(matches, key=lambda page: (page.priority_score, page.impressions, page.clicks))
    score = 10
    score += min(50, best_match.priority_score)
    score += min(20, best_match.impressions // 30)
    score += min(20, best_match.clicks * 2)
    return max(0, min(100, score))


def _semantic_confidence_score(
    cluster: SemanticGapCluster,
    matches: list[OwnPageTopicProfile],
    gap_type: CompetitiveGapType,
) -> float:
    confidence = 0.42
    confidence += min(0.22, cluster.competitor_count * 0.08)
    confidence += min(0.10, cluster.page_count * 0.02)
    if matches:
        confidence += 0.08
    if gap_type == "MISSING_SUPPORTING_PAGE":
        confidence += 0.05
    return round(max(0.35, min(0.95, confidence)), 2)


def _build_semantic_cluster_key(
    *,
    site_id: int,
    member_ids: list[int],
    candidate_map: dict[int, SiteCompetitorSemanticCandidate],
) -> str:
    member_shapes: list[dict[str, Any]] = []
    for candidate_id in member_ids:
        candidate = candidate_map.get(candidate_id)
        if candidate is None:
            continue
        member_shapes.append(
            {
                "competitor_id": int(candidate.competitor_id),
                "raw_topic_key": _normalize_semantic_bucket_token(candidate.raw_topic_key)
                or _normalize_semantic_bucket_token(candidate.raw_topic_label)
                or "topic",
                "page_type": _normalize_semantic_bucket_token(candidate.page_type) or "other",
                "page_bucket": _normalize_semantic_bucket_token(candidate.page_bucket) or "other",
            }
        )
    payload = {
        "site_id": site_id,
        "member_shapes": sorted(
            member_shapes,
            key=lambda item: (
                int(item["competitor_id"]),
                str(item["raw_topic_key"]),
                str(item["page_type"]),
                str(item["page_bucket"]),
            ),
        ),
    }
    return f"sg:{_hash_payload(payload)[:20]}"


def _build_semantic_topic_key(
    canonical_topic_label: str | None,
    raw_topic_keys: list[str],
    source_topic_labels: list[str],
) -> str:
    if canonical_topic_label:
        tokens = tokenize_topic_text(canonical_topic_label)
        if tokens:
            return "-".join(tokens[:4])
    if raw_topic_keys:
        tokens = tokenize_topic_text(" ".join(raw_topic_keys))
        if tokens:
            return "-".join(tokens[:4])
    if source_topic_labels:
        tokens = tokenize_topic_text(" ".join(source_topic_labels))
        if tokens:
            return "-".join(tokens[:4])
    return "topic"


def _choose_canonical_topic_label(
    members: list[SiteCompetitorSemanticCandidate],
    merge_rows: list[SiteCompetitorSemanticDecision],
    own_rows: list[SiteCompetitorSemanticDecision],
) -> str | None:
    member_ids = {candidate.id for candidate in members}
    labels: list[str] = []
    for row in merge_rows:
        if row.source_candidate_id not in member_ids and row.target_candidate_id not in member_ids:
            continue
        if row.canonical_topic_label:
            labels.append(collapse_whitespace(row.canonical_topic_label) or row.canonical_topic_label)
    for row in own_rows:
        if row.source_candidate_id not in member_ids:
            continue
        if row.canonical_topic_label:
            labels.append(collapse_whitespace(row.canonical_topic_label) or row.canonical_topic_label)
    if labels:
        return min(
            Counter(labels).items(),
            key=lambda item: (-item[1], len(item[0]), item[0].lower()),
        )[0][:255]
    member_labels = [
        collapse_whitespace(candidate.raw_topic_label)
        for candidate in members
        if collapse_whitespace(candidate.raw_topic_label)
    ]
    if member_labels:
        return min(member_labels, key=lambda value: (len(value), value.lower()))[:255]
    raw_topic_keys = [
        candidate.raw_topic_key
        for candidate in members
        if candidate.raw_topic_key
    ]
    if raw_topic_keys:
        return _prettify_topic_key(sorted(raw_topic_keys)[0])[:255]
    return None


def _normalize_semantic_bucket_token(value: Any) -> str | None:
    if text_value_missing(value):
        return None
    tokens = tokenize_topic_text(str(value))
    if not tokens:
        normalized = normalize_text_for_hash(str(value)).replace(" ", "-")
        normalized = "-".join(token for token in normalized.split("-") if token)
        return normalized or None
    return "-".join(tokens[:4])


def _semantic_bucket_key(*values: Any) -> str:
    tokens = [
        token
        for value in values
        if not text_value_missing(value)
        for token in tokenize_topic_text(str(value))
        if token
    ]
    normalized = _normalize_semantic_bucket_token(" ".join(dedupe_preserve_order(tokens)))
    return normalized or "semantic-topic"


def _semantic_own_match_status_from_suggestion(
    suggestion: Any,
) -> SemanticOwnMatchStatus:
    if bool(getattr(suggestion, "exact_topic_key_match", False)):
        return "exact_match"
    if (
        int(getattr(suggestion, "shared_primary_tokens", 0) or 0) >= 2
        or int(getattr(suggestion, "shared_anchor_terms", 0) or 0) >= 2
        or float(getattr(suggestion, "semantic_alignment_score", 0.0) or 0.0) >= 0.62
        or int(getattr(suggestion, "shared_terms", 0) or 0) >= 3
    ):
        return "semantic_match"
    if (
        int(getattr(suggestion, "shared_primary_tokens", 0) or 0) >= 1
        or int(getattr(suggestion, "shared_anchor_terms", 0) or 0) >= 1
        or float(getattr(suggestion, "semantic_alignment_score", 0.0) or 0.0) >= 0.42
        or int(getattr(suggestion, "shared_terms", 0) or 0) >= 2
    ):
        return "partial_coverage"
    return "no_meaningful_match"


def _normalize_own_match_status(value: str) -> SemanticOwnMatchStatus:
    if value in {"exact_match", "semantic_match", "partial_coverage", "no_meaningful_match"}:
        return value  # type: ignore[return-value]
    return "no_meaningful_match"


def _semantic_own_match_confidence_from_suggestion(suggestion: Any) -> float:
    status = _semantic_own_match_status_from_suggestion(suggestion)
    if status == "exact_match":
        return 0.9
    if status == "semantic_match":
        return 0.76
    if status == "partial_coverage":
        return 0.58
    return 0.28


def _semantic_own_match_status_rank(status: str) -> int:
    return {
        "exact_match": 4,
        "semantic_match": 3,
        "partial_coverage": 2,
        "no_meaningful_match": 1,
    }.get(status, 0)


def _semantic_own_match_choice_tuple(choice: dict[str, Any]) -> tuple[int, float, int, int, int]:
    return (
        _semantic_own_match_status_rank(str(choice.get("status"))),
        float(choice.get("confidence") or 0.0),
        int(choice.get("score") or 0),
        int(choice.get("priority_score") or 0),
        int(choice.get("impressions") or 0),
    )
