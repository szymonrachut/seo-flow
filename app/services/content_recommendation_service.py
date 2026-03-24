from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import re
import unicodedata
from typing import Any
from urllib.parse import unquote, urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GscTopQuery, Link, SiteContentRecommendationState, utcnow
from app.schemas.opportunities import EffortLevel, ImpactLevel
from app.services import cannibalization_service, internal_linking_service, site_service
from app.services.content_recommendation_keys import build_content_recommendation_key
from app.services.content_recommendation_rules import (
    CONTENT_RECOMMENDATION_TYPES,
    ContentRecommendationRules,
    ContentRecommendationType,
    get_content_recommendation_rules,
)
from app.services.page_taxonomy_service import PAGE_TYPES
from app.services.priority_service import apply_priority_metadata
from app.services.seo_analysis import build_page_records, text_value_missing

WORD_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
IMPACT_ORDER = {"low": 0, "medium": 1, "high": 2}
EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2}
CANNIBALIZATION_SEVERITY_ORDER = {None: 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

HELPER_SNIPPET_ISSUE_LABELS = {
    "title_missing": "missing title",
    "title_too_short": "title too short",
    "title_too_long": "title too long",
    "meta_description_missing": "missing meta description",
    "meta_description_too_short": "meta description too short",
    "meta_description_too_long": "meta description too long",
}
HELPER_HEADING_ISSUE_LABELS = {
    "h1_missing": "missing H1",
    "multiple_h1": "multiple H1",
    "missing_h2": "missing H2",
}
HELPER_OPPORTUNITY_LABELS = {
    "QUICK_WINS": "quick wins",
    "HIGH_IMPRESSIONS_LOW_CTR": "high impressions / low CTR",
    "TRAFFIC_WITH_TECHNICAL_ISSUES": "traffic with technical issues",
    "IMPORTANT_BUT_WEAK": "important but weak",
    "LOW_HANGING_FRUIT": "low-hanging fruit",
    "HIGH_RISK_PAGES": "high-risk page",
    "UNDERLINKED_OPPORTUNITIES": "underlinked opportunity",
}
HELPER_INTERNAL_ISSUE_LABELS = {
    "ORPHAN_LIKE": "The URL still looks orphan-like in the active snapshot.",
    "WEAKLY_LINKED_IMPORTANT": "The URL is still weakly linked for its current importance.",
    "LOW_LINK_EQUITY": "Link equity remains low for this URL.",
    "BOILERPLATE_DOMINATED": "Internal support is still dominated by boilerplate-like links.",
    "LOW_ANCHOR_DIVERSITY": "Anchor diversity remains low for this URL.",
    "EXACT_MATCH_ANCHOR_CONCENTRATION": "Incoming anchors are still too concentrated around exact-match wording.",
}
OUTCOME_KIND_ORDER = ("gsc", "internal_linking", "cannibalization", "issue_flags", "mixed", "unknown")
OUTCOME_KIND_VALUES = set(OUTCOME_KIND_ORDER)
IMPLEMENTED_OUTCOME_STATUS_ORDER = ("improved", "unchanged", "pending", "too_early", "limited", "unavailable", "worsened")
IMPLEMENTED_OUTCOME_STATUS_VALUES = set(IMPLEMENTED_OUTCOME_STATUS_ORDER)
OUTCOME_WINDOW_DAYS = {"7d": 7, "30d": 30, "90d": 90, "all": 0}
IMPLEMENTED_STATUS_FILTER_VALUES = {"all", *IMPLEMENTED_OUTCOME_STATUS_VALUES}
IMPLEMENTED_MODE_FILTER_VALUES = {"all", *OUTCOME_KIND_VALUES}
IMPLEMENTED_SORT_VALUES = {"implemented_at_desc", "implemented_at_asc", "outcome", "recommendation_type", "title"}
IMPLEMENTED_OUTCOME_STATUS_RANK = {
    status: index for index, status in enumerate(IMPLEMENTED_OUTCOME_STATUS_ORDER)
}
OUTCOME_ISSUE_FLAG_KEYS = (
    "title_missing",
    "title_too_short",
    "title_too_long",
    "meta_description_missing",
    "meta_description_too_short",
    "meta_description_too_long",
    "h1_missing",
    "multiple_h1",
    "missing_h2",
    "canonical_missing",
    "canonical_to_other_url",
    "canonical_to_non_200",
    "canonical_to_redirect",
    "noindex_like",
    "non_indexable_like",
    "thin_content",
    "duplicate_content",
    "missing_alt_images",
    "oversized",
)
OUTCOME_ISSUE_FLAG_LABELS = {
    "title_missing": "Missing title",
    "title_too_short": "Title too short",
    "title_too_long": "Title too long",
    "meta_description_missing": "Missing meta description",
    "meta_description_too_short": "Meta description too short",
    "meta_description_too_long": "Meta description too long",
    "h1_missing": "Missing H1",
    "multiple_h1": "Multiple H1",
    "missing_h2": "Missing H2",
    "canonical_missing": "Missing canonical",
    "canonical_to_other_url": "Canonical points elsewhere",
    "canonical_to_non_200": "Canonical target is non-200",
    "canonical_to_redirect": "Canonical target redirects",
    "noindex_like": "Noindex-like",
    "non_indexable_like": "Non-indexable-like",
    "thin_content": "Thin content",
    "duplicate_content": "Duplicate content",
    "missing_alt_images": "Missing alt text",
    "oversized": "Oversized HTML",
}


class ContentRecommendationServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class PageTopicProfile:
    page_id: int
    url: str
    normalized_url: str
    page_type: str
    page_bucket: str
    page_type_confidence: float
    priority_score: int
    priority_level: str
    priority_rationale: str
    primary_opportunity_type: str | None
    opportunity_types: list[str]
    word_count: int
    technical_issue_count: int
    incoming_internal_links: int
    incoming_internal_linking_pages: int
    impressions: int
    clicks: int
    ctr: float
    position: float | None
    top_queries_count: int
    has_cannibalization: bool
    cannibalization_severity: str | None
    internal_issue_types: list[str]
    internal_linking_score: int
    link_equity_score: float
    anchor_diversity_score: float
    topic_weights: dict[str, float]
    path_primary_token: str | None
    primary_token: str | None
    label_hint: str
    cluster_key: str


@dataclass(slots=True)
class ClusterAnalysis:
    key: str
    label: str
    pages: list[PageTopicProfile]
    stable: bool
    hub_page: PageTopicProfile
    total_pages: int
    commercial_pages: int
    supporting_pages: int
    blog_articles: int
    blog_indexes: int
    faq_pages: int
    category_pages: int
    product_pages: int
    service_pages: int
    location_pages: int
    total_impressions: int
    total_clicks: int
    max_priority_score: int
    average_taxonomy_confidence: float
    cluster_internal_links: int
    cluster_linking_pages: int
    hub_links_from_cluster: int
    hub_linking_pages_from_cluster: int
    cluster_strength: int
    coverage_gap_score: int
    internal_support_score: int
    high_cannibalization_pages: int


@dataclass(slots=True)
class RecommendationAnalysisContext:
    gsc_suffix: str
    page_records: list[dict[str, Any]]
    page_by_id: dict[int, dict[str, Any]]
    page_by_normalized_url: dict[str, dict[str, Any]]
    internal_rows: list[dict[str, Any]]
    internal_by_page_id: dict[int, dict[str, Any]]
    internal_by_normalized_url: dict[str, dict[str, Any]]


def build_site_content_recommendations(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
    baseline_crawl_id: int | None = None,
    gsc_date_range: str = "last_28_days",
    page: int = 1,
    page_size: int = 25,
    sort_by: str = "priority_score",
    sort_order: str = "desc",
    recommendation_type: str | None = None,
    segment: str | None = None,
    page_type: str | None = None,
    cluster: str | None = None,
    confidence_min: float | None = None,
    priority_score_min: int | None = None,
    implemented_outcome_window: str = "30d",
    implemented_status_filter: str = "all",
    implemented_mode_filter: str = "all",
    implemented_search: str | None = None,
    implemented_sort: str = "implemented_at_desc",
    rules: ContentRecommendationRules | None = None,
) -> dict[str, Any]:
    payload = _build_site_content_recommendation_payload(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        baseline_crawl_id=baseline_crawl_id,
        gsc_date_range=gsc_date_range,
        implemented_outcome_window=implemented_outcome_window,
        rules=rules,
    )
    filtered = _filter_recommendations(
        payload["items"],
        recommendation_type=recommendation_type,
        segment=segment,
        page_type=page_type,
        cluster=cluster,
        confidence_min=confidence_min,
        priority_score_min=priority_score_min,
    )
    _sort_recommendations(filtered, sort_by=sort_by, sort_order=sort_order)
    implemented_section = _prepare_implemented_recommendation_section(
        payload["implemented_items"],
        status_filter=implemented_status_filter,
        mode_filter=implemented_mode_filter,
        search=implemented_search,
        sort_by=implemented_sort,
    )

    total_items = len(filtered)
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "context": payload["context"],
        "summary": payload["summary"],
        "items": filtered[start:end],
        "implemented_items": implemented_section["items"],
        "implemented_total": len(implemented_section["items"]),
        "implemented_summary": implemented_section["summary"],
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def _prepare_implemented_recommendation_section(
    recommendations: list[dict[str, Any]],
    *,
    status_filter: str | None,
    mode_filter: str | None,
    search: str | None,
    sort_by: str,
) -> dict[str, Any]:
    base_items = _filter_implemented_recommendations(
        recommendations,
        status_filter=None,
        mode_filter=mode_filter,
        search=search,
    )
    filtered_items = _filter_implemented_recommendations(
        base_items,
        status_filter=status_filter,
        mode_filter=None,
        search=None,
    )
    _sort_implemented_recommendations(filtered_items, sort_by=sort_by)
    return {
        "summary": _build_implemented_summary(base_items),
        "items": filtered_items,
    }


def get_all_site_content_recommendations(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
    baseline_crawl_id: int | None = None,
    gsc_date_range: str = "last_28_days",
    sort_by: str = "priority_score",
    sort_order: str = "desc",
    recommendation_type: str | None = None,
    segment: str | None = None,
    page_type: str | None = None,
    cluster: str | None = None,
    confidence_min: float | None = None,
    priority_score_min: int | None = None,
    implemented_outcome_window: str = "30d",
    implemented_status_filter: str = "all",
    implemented_mode_filter: str = "all",
    implemented_search: str | None = None,
    implemented_sort: str = "implemented_at_desc",
    rules: ContentRecommendationRules | None = None,
) -> list[dict[str, Any]]:
    payload = build_site_content_recommendations(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        baseline_crawl_id=baseline_crawl_id,
        gsc_date_range=gsc_date_range,
        page=1,
        page_size=100_000,
        sort_by=sort_by,
        sort_order=sort_order,
        recommendation_type=recommendation_type,
        segment=segment,
        page_type=page_type,
        cluster=cluster,
        confidence_min=confidence_min,
        priority_score_min=priority_score_min,
        implemented_outcome_window=implemented_outcome_window,
        implemented_status_filter=implemented_status_filter,
        implemented_mode_filter=implemented_mode_filter,
        implemented_search=implemented_search,
        implemented_sort=implemented_sort,
        rules=rules,
    )
    return list(payload["items"])


def mark_site_content_recommendation_done(
    session: Session,
    site_id: int,
    *,
    recommendation_key: str,
    active_crawl_id: int | None = None,
    baseline_crawl_id: int | None = None,
    gsc_date_range: str = "last_28_days",
    rules: ContentRecommendationRules | None = None,
) -> dict[str, Any]:
    payload = _build_site_content_recommendation_payload(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        baseline_crawl_id=baseline_crawl_id,
        gsc_date_range=gsc_date_range,
        implemented_outcome_window="30d",
        rules=rules,
    )
    active_crawl_id = payload["context"]["active_crawl_id"]
    if active_crawl_id is None:
        raise ContentRecommendationServiceError("Cannot mark a recommendation as done without an active crawl.")

    recommendation = next(
        (item for item in payload["items"] if str(item.get("recommendation_key")) == recommendation_key),
        None,
    )
    if recommendation is None:
        raise ContentRecommendationServiceError(
            "Recommendation was not found in the current active payload for this site and crawl."
        )

    state = session.scalar(
        select(SiteContentRecommendationState).where(
            SiteContentRecommendationState.site_id == site_id,
            SiteContentRecommendationState.recommendation_key == recommendation_key,
        )
    )
    now = utcnow()
    snapshot = _build_recommendation_state_snapshot(recommendation)
    primary_outcome_kind = _infer_primary_outcome_kind(recommendation)

    if state is None:
        state = SiteContentRecommendationState(
            site_id=site_id,
            recommendation_key=recommendation_key,
            recommendation_type=str(recommendation["recommendation_type"]),
            segment=recommendation.get("segment"),
            target_url=recommendation.get("target_url"),
            normalized_target_url=recommendation.get("normalized_target_url"),
            target_title_snapshot=_extract_recommendation_target_title(recommendation),
            suggested_page_type=recommendation.get("suggested_page_type"),
            cluster_label=recommendation.get("cluster_label"),
            cluster_key=recommendation.get("cluster_key"),
            recommendation_text=str(recommendation.get("rationale") or ""),
            signals_snapshot_json=snapshot,
            helper_snapshot_json=recommendation.get("url_improvement_helper"),
            primary_outcome_kind=primary_outcome_kind,
            implemented_at=now,
            implemented_crawl_job_id=active_crawl_id,
            implemented_baseline_crawl_job_id=payload["context"]["baseline_crawl_id"],
            times_marked_done=1,
        )
        session.add(state)
    else:
        state.recommendation_type = str(recommendation["recommendation_type"])
        state.segment = recommendation.get("segment")
        state.target_url = recommendation.get("target_url")
        state.normalized_target_url = recommendation.get("normalized_target_url")
        state.target_title_snapshot = _extract_recommendation_target_title(recommendation)
        state.suggested_page_type = recommendation.get("suggested_page_type")
        state.cluster_label = recommendation.get("cluster_label")
        state.cluster_key = recommendation.get("cluster_key")
        state.recommendation_text = str(recommendation.get("rationale") or "")
        state.signals_snapshot_json = snapshot
        state.helper_snapshot_json = recommendation.get("url_improvement_helper")
        state.primary_outcome_kind = primary_outcome_kind
        state.implemented_at = now
        state.implemented_crawl_job_id = active_crawl_id
        state.implemented_baseline_crawl_job_id = payload["context"]["baseline_crawl_id"]
        state.times_marked_done = int(state.times_marked_done or 0) + 1
        state.updated_at = now

    session.commit()
    session.refresh(state)

    return {
        "recommendation_key": state.recommendation_key,
        "implemented_at": _ensure_utc_datetime(state.implemented_at),
        "implemented_crawl_job_id": state.implemented_crawl_job_id,
        "implemented_baseline_crawl_job_id": state.implemented_baseline_crawl_job_id,
        "primary_outcome_kind": state.primary_outcome_kind,
        "times_marked_done": int(state.times_marked_done or 0),
    }


def _build_site_content_recommendation_payload(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None,
    baseline_crawl_id: int | None,
    gsc_date_range: str,
    implemented_outcome_window: str,
    rules: ContentRecommendationRules | None,
) -> dict[str, Any]:
    resolved_rules = rules or get_content_recommendation_rules()
    context = site_service.resolve_site_workspace_context(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        baseline_crawl_id=baseline_crawl_id,
    )
    site = context["site"]
    active_crawl = context["active_crawl"]
    baseline_crawl = context["baseline_crawl"]

    response_context = {
        "site_id": site.id,
        "site_domain": site.domain,
        "active_crawl_id": active_crawl.id if active_crawl else None,
        "baseline_crawl_id": baseline_crawl.id if baseline_crawl else None,
        "gsc_date_range": gsc_date_range,
        "active_crawl": _serialize_site_crawl_context(active_crawl, site.root_url),
        "baseline_crawl": _serialize_site_crawl_context(baseline_crawl, site.root_url),
    }
    if active_crawl is None:
        return {
            "context": response_context,
            "summary": _empty_summary(),
            "items": [],
            "implemented_items": _build_implemented_recommendations(
                _load_recommendation_states(session, site.id),
                active_crawl_id=None,
                active_analysis=None,
                active_reference_at=None,
                outcome_window=implemented_outcome_window,
            ),
            "implemented_total": len(_load_recommendation_states(session, site.id)),
        }

    suffix = _resolve_gsc_suffix(gsc_date_range)
    active_analysis = _load_recommendation_analysis_context(
        session,
        active_crawl.id,
        gsc_date_range=gsc_date_range,
    )
    page_records = active_analysis.page_records
    internal_rows = active_analysis.internal_rows
    internal_row_by_page_id = active_analysis.internal_by_page_id
    query_tokens_by_page = _load_query_tokens_by_page(session, active_crawl.id, gsc_date_range, resolved_rules)
    anchor_tokens_by_page = _load_anchor_tokens_by_page(internal_rows, resolved_rules)

    profiles = _build_page_profiles(
        page_records,
        internal_row_by_page_id=internal_row_by_page_id,
        query_tokens_by_page=query_tokens_by_page,
        anchor_tokens_by_page=anchor_tokens_by_page,
        rules=resolved_rules,
        gsc_suffix=suffix,
    )
    if not profiles:
        implemented_states = _load_recommendation_states(session, site.id)
        return {
            "context": response_context,
            "summary": _empty_summary(implemented_count=len(implemented_states)),
            "items": [],
            "implemented_items": _build_implemented_recommendations(
                implemented_states,
                active_crawl_id=active_crawl.id,
                active_analysis=active_analysis,
                active_reference_at=_resolve_implemented_reference_at(active_crawl),
                outcome_window=implemented_outcome_window,
            ),
            "implemented_total": len(implemented_states),
        }

    clusters = _build_clusters(session, active_crawl.id, profiles, resolved_rules)
    recommendations = _build_recommendations(clusters, resolved_rules)
    baseline_analysis: RecommendationAnalysisContext | None = None
    if baseline_crawl is not None:
        baseline_analysis = _load_recommendation_analysis_context(
            session,
            baseline_crawl.id,
            gsc_date_range=gsc_date_range,
        )
    _attach_url_improvement_helpers(
        recommendations,
        page_records=active_analysis.page_records,
        internal_rows=active_analysis.internal_rows,
        gsc_suffix=suffix,
        rules=resolved_rules,
        baseline_crawl_id=baseline_crawl.id if baseline_crawl is not None else None,
        baseline_page_records=baseline_analysis.page_records if baseline_analysis is not None else None,
        baseline_internal_rows=baseline_analysis.internal_rows if baseline_analysis is not None else None,
    )
    implemented_states = _load_recommendation_states(session, site.id)
    implemented_state_by_key = {state.recommendation_key: state for state in implemented_states}
    active_recommendations: list[dict[str, Any]] = []
    for recommendation in recommendations:
        state = implemented_state_by_key.get(str(recommendation["recommendation_key"]))
        if state is not None:
            recommendation["was_implemented_before"] = True
            recommendation["previously_implemented_at"] = _ensure_utc_datetime(state.implemented_at)
            if state.implemented_crawl_job_id == active_crawl.id:
                continue
        else:
            recommendation["was_implemented_before"] = False
            recommendation["previously_implemented_at"] = None
        active_recommendations.append(recommendation)

    implemented_items = _build_implemented_recommendations(
        implemented_states,
        active_crawl_id=active_crawl.id,
        active_analysis=active_analysis,
        active_reference_at=_resolve_implemented_reference_at(active_crawl),
        outcome_window=implemented_outcome_window,
    )

    return {
        "context": response_context,
        "summary": _build_summary(active_recommendations, implemented_count=len(implemented_states)),
        "items": active_recommendations,
        "implemented_items": implemented_items,
        "implemented_total": len(implemented_items),
    }


def _load_recommendation_analysis_context(
    session: Session,
    crawl_job_id: int,
    *,
    gsc_date_range: str,
) -> RecommendationAnalysisContext:
    page_records = build_page_records(session, crawl_job_id)
    apply_priority_metadata(page_records, gsc_date_range=gsc_date_range)
    cannibalization_service.apply_cannibalization_page_metadata(
        session,
        crawl_job_id,
        page_records,
        gsc_date_range=gsc_date_range,
    )
    internal_rows = internal_linking_service.get_all_internal_linking_rows(
        session,
        crawl_job_id,
        gsc_date_range=gsc_date_range,
    )
    page_by_id = {int(record["id"]): record for record in page_records}
    page_by_normalized_url = {
        str(record["normalized_url"]): record
        for record in page_records
        if not text_value_missing(record.get("normalized_url"))
    }
    internal_by_page_id = {int(row["page_id"]): row for row in internal_rows}
    internal_by_normalized_url = {
        str(row["normalized_url"]): row
        for row in internal_rows
        if not text_value_missing(row.get("normalized_url"))
    }
    return RecommendationAnalysisContext(
        gsc_suffix=_resolve_gsc_suffix(gsc_date_range),
        page_records=page_records,
        page_by_id=page_by_id,
        page_by_normalized_url=page_by_normalized_url,
        internal_rows=internal_rows,
        internal_by_page_id=internal_by_page_id,
        internal_by_normalized_url=internal_by_normalized_url,
    )


def _load_recommendation_states(session: Session, site_id: int) -> list[SiteContentRecommendationState]:
    return list(
        session.scalars(
            select(SiteContentRecommendationState)
            .where(SiteContentRecommendationState.site_id == site_id)
            .order_by(SiteContentRecommendationState.implemented_at.desc(), SiteContentRecommendationState.id.desc())
        )
    )


def _build_page_profiles(
    page_records: list[dict[str, Any]],
    *,
    internal_row_by_page_id: dict[int, dict[str, Any]],
    query_tokens_by_page: dict[int, dict[str, float]],
    anchor_tokens_by_page: dict[int, dict[str, float]],
    rules: ContentRecommendationRules,
    gsc_suffix: str,
) -> list[PageTopicProfile]:
    profiles: list[PageTopicProfile] = []
    path_primary_counts: Counter[str] = Counter()

    for record in page_records:
        if not _page_is_cluster_eligible(record, rules):
            continue

        page_id = int(record["id"])
        path_token, path_weights = _extract_path_topic_weights(record.get("normalized_url"), rules)
        text_weights = _extract_text_topic_weights(record, rules)
        topic_weights = _merge_weight_maps(
            path_weights,
            text_weights,
            query_tokens_by_page.get(page_id, {}),
            anchor_tokens_by_page.get(page_id, {}),
        )
        primary_token = _primary_token(topic_weights)
        if path_token:
            path_primary_counts[path_token] += 1

        internal_row = internal_row_by_page_id.get(page_id)
        impressions = int(record.get(f"impressions_{gsc_suffix}") or 0)
        clicks = int(record.get(f"clicks_{gsc_suffix}") or 0)
        top_queries_count = int(record.get(f"top_queries_count_{gsc_suffix}") or 0)
        position = float(record.get(f"position_{gsc_suffix}")) if record.get(f"position_{gsc_suffix}") is not None else None

        profiles.append(
            PageTopicProfile(
                page_id=page_id,
                url=str(record["url"]),
                normalized_url=str(record["normalized_url"]),
                page_type=str(record.get("page_type") or "other"),
                page_bucket=str(record.get("page_bucket") or "other"),
                page_type_confidence=float(record.get("page_type_confidence") or 0.0),
                priority_score=int(record.get("priority_score") or 0),
                priority_level=str(record.get("priority_level") or "low"),
                priority_rationale=str(record.get("priority_rationale") or ""),
                primary_opportunity_type=record.get("primary_opportunity_type"),
                opportunity_types=list(record.get("opportunity_types") or []),
                word_count=int(record.get("word_count") or 0),
                technical_issue_count=int(record.get("technical_issue_count") or 0),
                incoming_internal_links=int(record.get("incoming_internal_links") or 0),
                incoming_internal_linking_pages=int(record.get("incoming_internal_linking_pages") or 0),
                impressions=impressions,
                clicks=clicks,
                ctr=float(record.get(f"ctr_{gsc_suffix}") or 0.0),
                position=position,
                top_queries_count=top_queries_count,
                has_cannibalization=bool(record.get("has_cannibalization")),
                cannibalization_severity=record.get("cannibalization_severity"),
                internal_issue_types=list(internal_row.get("issue_types") or []) if internal_row else [],
                internal_linking_score=int(internal_row.get("internal_linking_score") or 0) if internal_row else 0,
                link_equity_score=float(internal_row.get("link_equity_score") or 0.0) if internal_row else 0.0,
                anchor_diversity_score=float(internal_row.get("anchor_diversity_score") or 0.0) if internal_row else 0.0,
                topic_weights=topic_weights,
                path_primary_token=path_token,
                primary_token=primary_token,
                label_hint=_build_label_hint(record, topic_weights),
                cluster_key="",
            )
        )

    for profile in profiles:
        if (
            profile.path_primary_token
            and path_primary_counts.get(profile.path_primary_token, 0) >= rules.stable_path_token_min_pages
        ):
            profile.cluster_key = profile.path_primary_token
            profile.topic_weights[profile.cluster_key] = profile.topic_weights.get(profile.cluster_key, 0.0) + rules.stable_path_token_bonus
        elif profile.primary_token:
            profile.cluster_key = profile.primary_token
        else:
            profile.cluster_key = f"{profile.page_type}-{profile.page_id}"

    return profiles


def _build_clusters(
    session: Session,
    crawl_job_id: int,
    profiles: list[PageTopicProfile],
    rules: ContentRecommendationRules,
) -> list[ClusterAnalysis]:
    page_by_id = {profile.page_id: profile for profile in profiles}
    cluster_pages: dict[str, list[PageTopicProfile]] = defaultdict(list)
    for profile in profiles:
        cluster_pages[profile.cluster_key].append(profile)

    cluster_link_metrics = _load_cluster_link_metrics(session, crawl_job_id, page_by_id)
    clusters: list[ClusterAnalysis] = []
    for cluster_key, pages in sorted(cluster_pages.items(), key=lambda item: item[0]):
        sorted_pages = sorted(
            pages,
            key=lambda page: (-page.priority_score, -page.impressions, page.url.lower()),
        )
        cluster_metrics = cluster_link_metrics.get(
            cluster_key,
            {
                "cluster_internal_links": 0,
                "cluster_linking_pages": 0,
                "links_to_page": defaultdict(int),
                "linking_pages_to_page": defaultdict(set),
            },
        )
        hub_page = _choose_hub_page(sorted_pages, cluster_metrics, rules)
        total_pages = len(sorted_pages)
        commercial_pages = sum(1 for page in sorted_pages if page.page_type in rules.commercial_page_types)
        supporting_pages = sum(1 for page in sorted_pages if page.page_type in rules.supporting_page_types)
        blog_articles = sum(1 for page in sorted_pages if page.page_type == "blog_article")
        blog_indexes = sum(1 for page in sorted_pages if page.page_type == "blog_index")
        faq_pages = sum(1 for page in sorted_pages if page.page_type == "faq")
        category_pages = sum(1 for page in sorted_pages if page.page_type == "category")
        product_pages = sum(1 for page in sorted_pages if page.page_type == "product")
        service_pages = sum(1 for page in sorted_pages if page.page_type == "service")
        location_pages = sum(1 for page in sorted_pages if page.page_type == "location")
        total_impressions = sum(page.impressions for page in sorted_pages)
        total_clicks = sum(page.clicks for page in sorted_pages)
        max_priority_score = max((page.priority_score for page in sorted_pages), default=0)
        avg_taxonomy_confidence = round(sum(page.page_type_confidence for page in sorted_pages) / total_pages, 2)
        hub_links_from_cluster = int(cluster_metrics["links_to_page"].get(hub_page.page_id, 0))
        hub_linking_pages_from_cluster = len(cluster_metrics["linking_pages_to_page"].get(hub_page.page_id, set()))
        cluster_internal_links = int(cluster_metrics["cluster_internal_links"])
        cluster_linking_pages = int(cluster_metrics["cluster_linking_pages"])
        cluster_strength = _compute_cluster_strength(
            total_pages=total_pages,
            page_types={page.page_type for page in sorted_pages},
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            cluster_internal_links=cluster_internal_links,
            cluster_linking_pages=cluster_linking_pages,
        )
        internal_support_score = _compute_internal_support_score(
            total_pages=total_pages,
            cluster_internal_links=cluster_internal_links,
            cluster_linking_pages=cluster_linking_pages,
            hub_linking_pages_from_cluster=hub_linking_pages_from_cluster,
            pages=sorted_pages,
        )
        coverage_gap_score = _compute_coverage_gap_score(
            total_pages=total_pages,
            commercial_pages=commercial_pages,
            supporting_pages=supporting_pages,
            blog_articles=blog_articles,
            blog_indexes=blog_indexes,
            faq_pages=faq_pages,
            category_pages=category_pages,
            product_pages=product_pages,
            service_pages=service_pages,
            location_pages=location_pages,
            internal_support_score=internal_support_score,
        )
        high_cannibalization_pages = sum(
            1
            for page in sorted_pages
            if page.has_cannibalization and page.cannibalization_severity in {"high", "critical"}
        )
        clusters.append(
            ClusterAnalysis(
                key=cluster_key,
                label=_build_cluster_label(cluster_key, sorted_pages, rules),
                pages=sorted_pages,
                stable=any(page.path_primary_token == cluster_key for page in sorted_pages) or len(sorted_pages) > 1,
                hub_page=hub_page,
                total_pages=total_pages,
                commercial_pages=commercial_pages,
                supporting_pages=supporting_pages,
                blog_articles=blog_articles,
                blog_indexes=blog_indexes,
                faq_pages=faq_pages,
                category_pages=category_pages,
                product_pages=product_pages,
                service_pages=service_pages,
                location_pages=location_pages,
                total_impressions=total_impressions,
                total_clicks=total_clicks,
                max_priority_score=max_priority_score,
                average_taxonomy_confidence=avg_taxonomy_confidence,
                cluster_internal_links=cluster_internal_links,
                cluster_linking_pages=cluster_linking_pages,
                hub_links_from_cluster=hub_links_from_cluster,
                hub_linking_pages_from_cluster=hub_linking_pages_from_cluster,
                cluster_strength=cluster_strength,
                coverage_gap_score=coverage_gap_score,
                internal_support_score=internal_support_score,
                high_cannibalization_pages=high_cannibalization_pages,
            )
        )
    return clusters


def _build_recommendations(
    clusters: list[ClusterAnalysis],
    rules: ContentRecommendationRules,
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for cluster in clusters:
        for builder in (
            _build_missing_supporting_content_recommendation,
            _build_thin_cluster_recommendation,
            _build_expand_existing_page_recommendation,
            _build_missing_structural_page_type_recommendation,
            _build_internal_linking_support_recommendation,
        ):
            recommendation = builder(cluster, rules)
            if recommendation is not None:
                recommendations.append(recommendation)

    deduped: dict[str, dict[str, Any]] = {}
    for recommendation in recommendations:
        deduped[recommendation["id"]] = recommendation
    return list(deduped.values())


def _attach_url_improvement_helpers(
    recommendations: list[dict[str, Any]],
    *,
    page_records: list[dict[str, Any]],
    internal_rows: list[dict[str, Any]],
    gsc_suffix: str,
    rules: ContentRecommendationRules,
    baseline_crawl_id: int | None,
    baseline_page_records: list[dict[str, Any]] | None,
    baseline_internal_rows: list[dict[str, Any]] | None,
) -> None:
    active_page_by_id = {int(record["id"]): record for record in page_records}
    active_page_lookup: dict[str, dict[str, Any]] = {}
    for record in page_records:
        for key in ("url", "normalized_url"):
            value = record.get(key)
            if text_value_missing(value):
                continue
            active_page_lookup[str(value)] = record

    internal_row_by_page_id = {int(row["page_id"]): row for row in internal_rows}
    baseline_page_by_normalized_url = {
        str(record["normalized_url"]): record
        for record in (baseline_page_records or [])
        if not text_value_missing(record.get("normalized_url"))
    }
    baseline_internal_by_normalized_url = {
        str(row["normalized_url"]): row
        for row in (baseline_internal_rows or [])
        if not text_value_missing(row.get("normalized_url"))
    }

    for recommendation in recommendations:
        target_page = None
        target_page_id = recommendation.get("target_page_id")
        target_url = recommendation.get("target_url")
        if target_page_id is not None:
            target_page = active_page_by_id.get(int(target_page_id))
        if target_page is None and not text_value_missing(target_url):
            target_page = active_page_lookup.get(str(target_url))
        internal_row = (
            internal_row_by_page_id.get(int(target_page["id"]))
            if target_page is not None and target_page.get("id") is not None
            else None
        )
        recommendation["url_improvement_helper"] = _build_url_improvement_helper(
            recommendation,
            active_page_by_id=active_page_by_id,
            active_page_lookup=active_page_lookup,
            internal_row_by_page_id=internal_row_by_page_id,
            gsc_suffix=gsc_suffix,
            rules=rules,
            baseline_crawl_id=baseline_crawl_id,
            baseline_page_by_normalized_url=baseline_page_by_normalized_url,
            baseline_internal_by_normalized_url=baseline_internal_by_normalized_url,
        )
        recommendation["_outcome_snapshot"] = _build_recommendation_outcome_snapshot(
            recommendation,
            active_page=target_page,
            internal_row=internal_row,
            gsc_suffix=gsc_suffix,
        )


def _build_url_improvement_helper(
    recommendation: dict[str, Any],
    *,
    active_page_by_id: dict[int, dict[str, Any]],
    active_page_lookup: dict[str, dict[str, Any]],
    internal_row_by_page_id: dict[int, dict[str, Any]],
    gsc_suffix: str,
    rules: ContentRecommendationRules,
    baseline_crawl_id: int | None,
    baseline_page_by_normalized_url: dict[str, dict[str, Any]],
    baseline_internal_by_normalized_url: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    target_url = recommendation.get("target_url")
    if text_value_missing(target_url):
        return None

    target_page_id = recommendation.get("target_page_id")
    active_page = None
    if target_page_id is not None:
        active_page = active_page_by_id.get(int(target_page_id))
    if active_page is None:
        active_page = active_page_lookup.get(str(target_url))
    if active_page is None:
        return None

    page_id = int(active_page["id"])
    normalized_url = str(active_page.get("normalized_url") or active_page.get("url") or target_url)
    internal_row = internal_row_by_page_id.get(page_id) or _default_internal_helper_row(active_page)
    baseline_page = baseline_page_by_normalized_url.get(normalized_url)
    baseline_internal_row = baseline_internal_by_normalized_url.get(normalized_url)

    return {
        "target_url": str(target_url),
        "title": active_page.get("title") or active_page.get("h1"),
        "page_type": str(active_page.get("page_type") or recommendation.get("target_page_type") or "other"),
        "page_bucket": active_page.get("page_bucket"),
        "open_issues": _build_url_improvement_open_issues(
            active_page,
            internal_row=internal_row,
            recommendation=recommendation,
            gsc_suffix=gsc_suffix,
            rules=rules,
        ),
        "improvement_actions": _build_url_improvement_actions(
            active_page,
            internal_row=internal_row,
            recommendation=recommendation,
            gsc_suffix=gsc_suffix,
            rules=rules,
        ),
        "supporting_signals": _build_url_improvement_supporting_signals(
            active_page,
            internal_row=internal_row,
            recommendation=recommendation,
            gsc_suffix=gsc_suffix,
        ),
        "gsc_context": _build_url_improvement_gsc_context(active_page, gsc_suffix=gsc_suffix, rules=rules),
        "internal_linking_context": _build_url_improvement_internal_linking_context(internal_row, active_page=active_page),
        "cannibalization_context": _build_url_improvement_cannibalization_context(active_page),
        "compare_context": _build_url_improvement_compare_context(
            active_page,
            internal_row=internal_row,
            baseline_page=baseline_page,
            baseline_internal_row=baseline_internal_row,
            baseline_crawl_id=baseline_crawl_id,
            gsc_suffix=gsc_suffix,
        ),
    }


def _default_internal_helper_row(active_page: dict[str, Any]) -> dict[str, Any]:
    return {
        "internal_linking_score": 0,
        "issue_count": 0,
        "issue_types": [],
        "incoming_internal_links": int(active_page.get("incoming_internal_links") or 0),
        "incoming_internal_linking_pages": int(active_page.get("incoming_internal_linking_pages") or 0),
        "link_equity_score": 0.0,
        "anchor_diversity_score": 0.0,
    }


def _build_url_improvement_open_issues(
    active_page: dict[str, Any],
    *,
    internal_row: dict[str, Any],
    recommendation: dict[str, Any],
    gsc_suffix: str,
    rules: ContentRecommendationRules,
) -> list[str]:
    issues: list[str] = []
    if bool(active_page.get("noindex_like")) or bool(active_page.get("non_indexable_like")):
        issues.append("Indexability is still at risk on this URL.")

    canonical_issues: list[str] = []
    if bool(active_page.get("canonical_missing")):
        canonical_issues.append("missing canonical")
    if bool(active_page.get("canonical_to_other_url")):
        canonical_issues.append("canonical points to another URL")
    if bool(active_page.get("canonical_to_non_200")):
        canonical_issues.append("canonical target is non-200")
    if bool(active_page.get("canonical_to_redirect")):
        canonical_issues.append("canonical target redirects")
    if canonical_issues:
        issues.append(f"Canonical setup still needs cleanup: {', '.join(canonical_issues[:3])}.")

    snippet_issues = [
        label for key, label in HELPER_SNIPPET_ISSUE_LABELS.items() if bool(active_page.get(key))
    ]
    if snippet_issues:
        issues.append(f"Snippet inputs are still weak: {', '.join(snippet_issues[:3])}.")

    heading_issues = [
        label for key, label in HELPER_HEADING_ISSUE_LABELS.items() if bool(active_page.get(key))
    ]
    if heading_issues:
        issues.append(f"Heading coverage is still weak: {', '.join(heading_issues[:3])}.")

    if bool(active_page.get("thin_content")):
        issues.append("Thin content signal is still active for this URL.")
    if bool(active_page.get("duplicate_content")):
        issues.append("Duplicate content signal is still active for this URL.")
    if bool(active_page.get("missing_alt_images")):
        issues.append("Images on this page still miss alt text.")
    if bool(active_page.get("oversized")):
        issues.append("HTML size still looks oversized for this page.")

    for issue_type in list(internal_row.get("issue_types") or []):
        label = HELPER_INTERNAL_ISSUE_LABELS.get(str(issue_type))
        if label:
            issues.append(label)

    if int(recommendation.get("internal_support_score") or 0) < rules.helper_low_internal_support_score:
        issues.append("The surrounding cluster still has weak internal support.")
    if int(recommendation.get("cluster_strength") or 0) < rules.helper_low_cluster_strength_score:
        issues.append("The topic cluster around this URL still looks thin.")
    if int(recommendation.get("coverage_gap_score") or 0) >= rules.helper_high_coverage_gap_score:
        issues.append("The topic still shows a meaningful coverage gap around this URL.")

    issues.extend(_build_helper_gsc_issue_messages(active_page, gsc_suffix=gsc_suffix, rules=rules))

    if bool(active_page.get("has_cannibalization")):
        severity = str(active_page.get("cannibalization_severity") or "low")
        issues.append(f"Cannibalization signals are still active for this URL ({severity} severity).")

    if (
        int(active_page.get("priority_score") or 0) >= rules.helper_high_priority_attention_score
        and (
            int(active_page.get("technical_issue_count") or 0) > 0
            or int(internal_row.get("issue_count") or 0) > 0
            or int(recommendation.get("internal_support_score") or 0) < rules.helper_low_internal_support_score
        )
    ):
        issues.append("This URL is still high priority while important blockers remain open.")

    return _dedupe_strings(issues)[:6]


def _build_url_improvement_actions(
    active_page: dict[str, Any],
    *,
    internal_row: dict[str, Any],
    recommendation: dict[str, Any],
    gsc_suffix: str,
    rules: ContentRecommendationRules,
) -> list[str]:
    actions: list[str] = []
    if bool(active_page.get("noindex_like")) or bool(active_page.get("non_indexable_like")) or any(
        bool(active_page.get(key))
        for key in ("canonical_missing", "canonical_to_other_url", "canonical_to_non_200", "canonical_to_redirect")
    ):
        actions.append("Fix indexability and canonical blockers before expanding this URL further.")

    if any(bool(active_page.get(key)) for key in HELPER_SNIPPET_ISSUE_LABELS):
        actions.append("Tighten the title and meta description so the page can compete better in search snippets.")

    if any(bool(active_page.get(key)) for key in HELPER_HEADING_ISSUE_LABELS) or bool(active_page.get("thin_content")):
        actions.append("Expand content depth and strengthen heading coverage on the existing URL.")

    if bool(active_page.get("duplicate_content")):
        actions.append("Differentiate or consolidate duplicate sections so this URL has a clearer value proposition.")

    if bool(active_page.get("missing_alt_images")):
        actions.append("Fill missing alt text on the page's key images.")

    if int(internal_row.get("issue_count") or 0) > 0 or int(recommendation.get("internal_support_score") or 0) < rules.helper_low_internal_support_score:
        actions.append("Add more contextual internal links from relevant supporting URLs into this page.")

    if {"LOW_ANCHOR_DIVERSITY", "EXACT_MATCH_ANCHOR_CONCENTRATION"} & set(internal_row.get("issue_types") or []):
        actions.append("Diversify anchor text so internal support is less repetitive and more descriptive.")

    if bool(active_page.get("has_cannibalization")):
        actions.append("Review overlapping URLs and reinforce one clear primary page for shared queries.")

    if _has_low_query_coverage_issue(active_page, gsc_suffix=gsc_suffix, rules=rules):
        actions.append("Cover the page's current top queries more completely in the content and supporting cluster.")

    if int(active_page.get("priority_score") or 0) >= rules.helper_high_priority_attention_score:
        actions.append("Keep this URL in the active priority set until the blocking signals improve.")

    for opportunity_type in list(active_page.get("opportunity_types") or []):
        action = _opportunity_follow_up_action(str(opportunity_type))
        if action:
            actions.append(action)

    return _dedupe_strings(actions)[:5]


def _build_url_improvement_supporting_signals(
    active_page: dict[str, Any],
    *,
    internal_row: dict[str, Any],
    recommendation: dict[str, Any],
    gsc_suffix: str,
) -> list[str]:
    signals = [
        f"Priority score: {int(active_page.get('priority_score') or 0)} ({str(active_page.get('priority_level') or 'low')})",
        f"Technical issues still active: {int(active_page.get('technical_issue_count') or 0)}",
        (
            "Cluster scores: "
            f"strength {int(recommendation.get('cluster_strength') or 0)}, "
            f"coverage gap {int(recommendation.get('coverage_gap_score') or 0)}, "
            f"internal support {int(recommendation.get('internal_support_score') or 0)}"
        ),
        (
            "Internal linking snapshot: "
            f"{int(internal_row.get('incoming_internal_links') or 0)} links "
            f"from {int(internal_row.get('incoming_internal_linking_pages') or 0)} pages"
        ),
    ]
    if bool(active_page.get(f"has_gsc_{gsc_suffix}")):
        signals.append(
            "GSC snapshot: "
            f"{int(active_page.get(f'impressions_{gsc_suffix}') or 0)} impressions, "
            f"{int(active_page.get(f'clicks_{gsc_suffix}') or 0)} clicks, "
            f"avg position {_format_position(active_page.get(f'position_{gsc_suffix}'))}, "
            f"top queries {int(active_page.get(f'top_queries_count_{gsc_suffix}') or 0)}"
        )
    else:
        signals.append("No GSC URL metrics are available for this snapshot.")

    opportunity_types = [
        HELPER_OPPORTUNITY_LABELS.get(str(item), str(item).replace("_", " ").lower())
        for item in list(active_page.get("opportunity_types") or [])
    ]
    if opportunity_types:
        signals.append(f"Opportunity signals: {', '.join(opportunity_types[:3])}")

    if bool(active_page.get("has_cannibalization")):
        signals.append(
            "Cannibalization snapshot: "
            f"{str(active_page.get('cannibalization_severity') or 'low')} severity, "
            f"{int(active_page.get('cannibalization_competing_urls_count') or 0)} competing URLs"
        )

    return _dedupe_strings(signals)[:6]


def _build_url_improvement_gsc_context(
    active_page: dict[str, Any],
    *,
    gsc_suffix: str,
    rules: ContentRecommendationRules,
) -> dict[str, Any]:
    available = bool(active_page.get(f"has_gsc_{gsc_suffix}"))
    notes = (
        _build_helper_gsc_issue_messages(active_page, gsc_suffix=gsc_suffix, rules=rules)
        if available
        else ["No GSC URL metrics are available for this snapshot."]
    )
    return {
        "available": available,
        "impressions": int(active_page.get(f"impressions_{gsc_suffix}") or 0),
        "clicks": int(active_page.get(f"clicks_{gsc_suffix}") or 0),
        "ctr": float(active_page.get(f"ctr_{gsc_suffix}") or 0.0),
        "position": float(active_page.get(f"position_{gsc_suffix}")) if active_page.get(f"position_{gsc_suffix}") is not None else None,
        "top_queries_count": int(active_page.get(f"top_queries_count_{gsc_suffix}") or 0),
        "notes": notes[:3],
    }


def _build_url_improvement_internal_linking_context(
    internal_row: dict[str, Any],
    *,
    active_page: dict[str, Any],
) -> dict[str, Any]:
    return {
        "internal_linking_score": int(internal_row.get("internal_linking_score") or 0),
        "issue_count": int(internal_row.get("issue_count") or 0),
        "issue_types": list(internal_row.get("issue_types") or []),
        "incoming_internal_links": int(internal_row.get("incoming_internal_links") or active_page.get("incoming_internal_links") or 0),
        "incoming_internal_linking_pages": int(
            internal_row.get("incoming_internal_linking_pages") or active_page.get("incoming_internal_linking_pages") or 0
        ),
        "link_equity_score": round(float(internal_row.get("link_equity_score") or 0.0), 2),
        "anchor_diversity_score": round(float(internal_row.get("anchor_diversity_score") or 0.0), 2),
    }


def _build_url_improvement_cannibalization_context(active_page: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_active_signals": bool(active_page.get("has_cannibalization")),
        "severity": active_page.get("cannibalization_severity"),
        "competing_urls_count": int(active_page.get("cannibalization_competing_urls_count") or 0),
        "common_queries_count": int(active_page.get("cannibalization_common_queries_count") or 0),
        "strongest_competing_url": active_page.get("cannibalization_strongest_competing_url"),
        "shared_top_queries": list(active_page.get("cannibalization_shared_top_queries") or []),
    }


def _build_url_improvement_compare_context(
    active_page: dict[str, Any],
    *,
    internal_row: dict[str, Any],
    baseline_page: dict[str, Any] | None,
    baseline_internal_row: dict[str, Any] | None,
    baseline_crawl_id: int | None,
    gsc_suffix: str,
) -> dict[str, Any] | None:
    if baseline_crawl_id is None:
        return None

    if baseline_page is None:
        return {
            "baseline_crawl_id": baseline_crawl_id,
            "signals": [
                {
                    "key": "url_presence",
                    "label": "URL presence",
                    "status": "new",
                    "detail": "This URL is new in the active crawl versus the baseline crawl.",
                }
            ],
        }

    baseline_internal = baseline_internal_row or _default_internal_helper_row(baseline_page)
    signals = [
        _compare_numeric_signal(
            "technical_issues",
            "Technical issues",
            current=int(active_page.get("technical_issue_count") or 0),
            baseline=int(baseline_page.get("technical_issue_count") or 0),
            higher_is_better=False,
            formatter=lambda value: f"{int(value)} issue(s)",
        ),
        _compare_numeric_signal(
            "internal_linking_issues",
            "Internal linking issues",
            current=int(internal_row.get("issue_count") or 0),
            baseline=int(baseline_internal.get("issue_count") or 0),
            higher_is_better=False,
            formatter=lambda value: f"{int(value)} issue(s)",
        ),
        _compare_numeric_signal(
            "linking_pages",
            "Linking pages",
            current=int(internal_row.get("incoming_internal_linking_pages") or active_page.get("incoming_internal_linking_pages") or 0),
            baseline=int(
                baseline_internal.get("incoming_internal_linking_pages")
                or baseline_page.get("incoming_internal_linking_pages")
                or 0
            ),
            higher_is_better=True,
            formatter=lambda value: f"{int(value)} page(s)",
        ),
        _compare_numeric_signal(
            "gsc_clicks",
            "GSC clicks",
            current=_optional_metric_value(active_page.get(f"clicks_{gsc_suffix}")),
            baseline=_optional_metric_value(baseline_page.get(f"clicks_{gsc_suffix}")),
            higher_is_better=True,
            formatter=lambda value: f"{int(value)} click(s)",
        ),
        _compare_numeric_signal(
            "gsc_position",
            "Average position",
            current=_optional_metric_value(active_page.get(f"position_{gsc_suffix}")),
            baseline=_optional_metric_value(baseline_page.get(f"position_{gsc_suffix}")),
            higher_is_better=False,
            formatter=lambda value: _format_position(value),
        ),
        _compare_numeric_signal(
            "top_queries",
            "Top queries",
            current=int(active_page.get(f"top_queries_count_{gsc_suffix}") or 0),
            baseline=int(baseline_page.get(f"top_queries_count_{gsc_suffix}") or 0),
            higher_is_better=True,
            formatter=lambda value: f"{int(value)} query(s)",
        ),
        _compare_cannibalization_signal(active_page, baseline_page),
    ]
    return {
        "baseline_crawl_id": baseline_crawl_id,
        "signals": [signal for signal in signals if signal is not None],
    }


def _build_helper_gsc_issue_messages(
    active_page: dict[str, Any],
    *,
    gsc_suffix: str,
    rules: ContentRecommendationRules,
) -> list[str]:
    if not bool(active_page.get(f"has_gsc_{gsc_suffix}")):
        return []

    impressions = int(active_page.get(f"impressions_{gsc_suffix}") or 0)
    clicks = int(active_page.get(f"clicks_{gsc_suffix}") or 0)
    ctr = float(active_page.get(f"ctr_{gsc_suffix}") or 0.0)
    position = float(active_page.get(f"position_{gsc_suffix}")) if active_page.get(f"position_{gsc_suffix}") is not None else None
    top_queries_count = int(active_page.get(f"top_queries_count_{gsc_suffix}") or 0)

    issues: list[str] = []
    if impressions >= rules.helper_visibility_watch_min_impressions and clicks == 0:
        issues.append("The URL has search visibility but still no clicks.")
    if (
        impressions >= rules.helper_visibility_watch_min_impressions
        and position is not None
        and position > rules.helper_low_position_threshold
    ):
        issues.append(f"Average position is still weak at {position:.1f}.")
    if _has_low_query_coverage_issue(active_page, gsc_suffix=gsc_suffix, rules=rules):
        issues.append("Top-query coverage still looks shallow for this URL.")
    if impressions >= rules.helper_low_ctr_watch_min_impressions and ctr < rules.helper_low_ctr_threshold:
        issues.append(f"CTR is still weak at {ctr:.1%} for the current visibility.")
    return issues


def _has_low_query_coverage_issue(
    active_page: dict[str, Any],
    *,
    gsc_suffix: str,
    rules: ContentRecommendationRules,
) -> bool:
    impressions = int(active_page.get(f"impressions_{gsc_suffix}") or 0)
    top_queries_count = int(active_page.get(f"top_queries_count_{gsc_suffix}") or 0)
    return (
        impressions >= rules.helper_visibility_watch_min_impressions
        and top_queries_count <= rules.helper_low_query_coverage_max_queries
    )


def _opportunity_follow_up_action(opportunity_type: str) -> str | None:
    if opportunity_type == "HIGH_IMPRESSIONS_LOW_CTR":
        return "Improve snippet inputs because this URL already has meaningful impression demand."
    if opportunity_type == "TRAFFIC_WITH_TECHNICAL_ISSUES":
        return "Resolve active technical issues before pushing more visibility to this page."
    if opportunity_type == "IMPORTANT_BUT_WEAK":
        return "Prioritize this URL in the next quality pass because it already matters in search."
    if opportunity_type == "LOW_HANGING_FRUIT":
        return "Start with the low-effort fixes already flagged on this URL."
    if opportunity_type == "HIGH_RISK_PAGES":
        return "Reduce the high-risk SEO blockers before scaling content work on this page."
    if opportunity_type == "UNDERLINKED_OPPORTUNITIES":
        return "Increase internal linking support from relevant pages that already cover this topic."
    if opportunity_type == "QUICK_WINS":
        return "Start with the quickest on-page fixes because the page already sits within reach."
    return None


def _compare_numeric_signal(
    key: str,
    label: str,
    *,
    current: int | float | None,
    baseline: int | float | None,
    higher_is_better: bool,
    formatter,
) -> dict[str, Any] | None:
    if current is None and baseline is None:
        return None
    if baseline is None:
        return {
            "key": key,
            "label": label,
            "status": "new",
            "detail": f"{formatter(current)} now; no baseline value was available.",
        }
    if current is None:
        return {
            "key": key,
            "label": label,
            "status": "missing",
            "detail": f"Missing now; baseline was {formatter(baseline)}.",
        }

    status = "unchanged"
    if current != baseline:
        improved = current > baseline if higher_is_better else current < baseline
        status = "improved" if improved else "worsened"
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": f"{formatter(current)} now vs {formatter(baseline)} in baseline.",
    }


def _compare_cannibalization_signal(
    active_page: dict[str, Any],
    baseline_page: dict[str, Any],
) -> dict[str, Any]:
    active_severity = active_page.get("cannibalization_severity") if bool(active_page.get("has_cannibalization")) else None
    baseline_severity = (
        baseline_page.get("cannibalization_severity") if bool(baseline_page.get("has_cannibalization")) else None
    )
    active_rank = CANNIBALIZATION_SEVERITY_ORDER.get(active_severity, 0)
    baseline_rank = CANNIBALIZATION_SEVERITY_ORDER.get(baseline_severity, 0)

    status = "unchanged"
    if active_rank != baseline_rank:
        status = "improved" if active_rank < baseline_rank else "worsened"

    return {
        "key": "cannibalization",
        "label": "Cannibalization",
        "status": status,
        "detail": f"{_format_cannibalization_state(active_page)} now vs {_format_cannibalization_state(baseline_page)} in baseline.",
    }


def _format_cannibalization_state(page: dict[str, Any]) -> str:
    if not bool(page.get("has_cannibalization")):
        return "no active signals"
    severity = str(page.get("cannibalization_severity") or "low")
    competing_urls_count = int(page.get("cannibalization_competing_urls_count") or 0)
    return f"{severity} severity across {competing_urls_count} competing URL(s)"


def _optional_metric_value(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _format_position(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}"


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _extract_recommendation_target_title(recommendation: dict[str, Any]) -> str | None:
    helper = recommendation.get("url_improvement_helper")
    if isinstance(helper, dict):
        title = helper.get("title")
        if not text_value_missing(title):
            return str(title)
    return None


def _ensure_utc_datetime(value: Any) -> Any:
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_implemented_reference_at(crawl_job: Any) -> datetime | None:
    if crawl_job is None:
        return None
    for field in ("finished_at", "started_at", "created_at"):
        value = _ensure_utc_datetime(getattr(crawl_job, field, None))
        if isinstance(value, datetime):
            return value
    return None


def _days_since_implemented(
    implemented_at: datetime | None,
    reference_at: datetime | None,
) -> int | None:
    if not isinstance(implemented_at, datetime) or not isinstance(reference_at, datetime):
        return None
    delta = reference_at - implemented_at
    return max(int(delta.total_seconds() // 86_400), 0)


def _eligible_for_outcome_window(
    implemented_at: datetime | None,
    reference_at: datetime | None,
    *,
    outcome_window: str,
) -> bool:
    if outcome_window == "all":
        return isinstance(implemented_at, datetime) and isinstance(reference_at, datetime)
    minimum_days = OUTCOME_WINDOW_DAYS.get(outcome_window)
    if minimum_days is None:
        return False
    days_since_implemented = _days_since_implemented(implemented_at, reference_at)
    if days_since_implemented is None:
        return False
    return days_since_implemented >= minimum_days


def _build_recommendation_outcome_snapshot(
    recommendation: dict[str, Any],
    *,
    active_page: dict[str, Any] | None,
    internal_row: dict[str, Any] | None,
    gsc_suffix: str,
) -> dict[str, Any]:
    issue_flags = [flag for flag in OUTCOME_ISSUE_FLAG_KEYS if active_page is not None and bool(active_page.get(flag))]
    if active_page is None:
        gsc_context = None
        internal_context = None
        cannibalization_context = None
        issue_context = {
            "technical_issue_count": 0,
            "active_flags": [],
        }
    else:
        helper = recommendation.get("url_improvement_helper")
        gsc_context = helper.get("gsc_context") if isinstance(helper, dict) else {
            "available": bool(active_page.get(f"has_gsc_{gsc_suffix}")),
            "impressions": int(active_page.get(f"impressions_{gsc_suffix}") or 0),
            "clicks": int(active_page.get(f"clicks_{gsc_suffix}") or 0),
            "ctr": float(active_page.get(f"ctr_{gsc_suffix}") or 0.0),
            "position": _optional_metric_value(active_page.get(f"position_{gsc_suffix}")),
            "top_queries_count": int(active_page.get(f"top_queries_count_{gsc_suffix}") or 0),
            "notes": [],
        }
        internal_context = helper.get("internal_linking_context") if isinstance(helper, dict) else {
            "internal_linking_score": int((internal_row or {}).get("internal_linking_score") or 0),
            "issue_count": int((internal_row or {}).get("issue_count") or 0),
            "issue_types": list((internal_row or {}).get("issue_types") or []),
            "incoming_internal_links": int((internal_row or {}).get("incoming_internal_links") or 0),
            "incoming_internal_linking_pages": int((internal_row or {}).get("incoming_internal_linking_pages") or 0),
            "link_equity_score": float((internal_row or {}).get("link_equity_score") or 0.0),
            "anchor_diversity_score": float((internal_row or {}).get("anchor_diversity_score") or 0.0),
        }
        cannibalization_context = helper.get("cannibalization_context") if isinstance(helper, dict) else {
            "has_active_signals": bool(active_page.get("has_cannibalization")),
            "severity": active_page.get("cannibalization_severity"),
            "competing_urls_count": int(active_page.get("cannibalization_competing_urls_count") or 0),
            "common_queries_count": int(active_page.get("cannibalization_common_queries_count") or 0),
            "strongest_competing_url": active_page.get("cannibalization_strongest_competing_url"),
            "shared_top_queries": list(active_page.get("cannibalization_shared_top_queries") or []),
        }
        issue_context = {
            "technical_issue_count": int(active_page.get("technical_issue_count") or 0),
            "active_flags": issue_flags,
        }

    return {
        "signals": list(recommendation.get("signals") or []),
        "reasons": list(recommendation.get("reasons") or []),
        "recommendation": {
            "priority_score": int(recommendation.get("priority_score") or 0),
            "cluster_strength": int(recommendation.get("cluster_strength") or 0),
            "coverage_gap_score": int(recommendation.get("coverage_gap_score") or 0),
            "internal_support_score": int(recommendation.get("internal_support_score") or 0),
        },
        "gsc": gsc_context,
        "internal_linking": internal_context,
        "cannibalization": cannibalization_context,
        "issue_flags": issue_context,
    }


def _build_recommendation_state_snapshot(recommendation: dict[str, Any]) -> dict[str, Any]:
    snapshot = recommendation.get("_outcome_snapshot")
    if isinstance(snapshot, dict):
        return snapshot
    return {
        "signals": list(recommendation.get("signals") or []),
        "reasons": list(recommendation.get("reasons") or []),
        "recommendation": {
            "priority_score": int(recommendation.get("priority_score") or 0),
            "cluster_strength": int(recommendation.get("cluster_strength") or 0),
            "coverage_gap_score": int(recommendation.get("coverage_gap_score") or 0),
            "internal_support_score": int(recommendation.get("internal_support_score") or 0),
        },
        "gsc": None,
        "internal_linking": None,
        "cannibalization": None,
        "issue_flags": {"technical_issue_count": 0, "active_flags": []},
    }


def _infer_primary_outcome_kind(recommendation: dict[str, Any]) -> str:
    recommendation_type = str(recommendation.get("recommendation_type") or "")
    snapshot = _build_recommendation_state_snapshot(recommendation)
    gsc_context = snapshot.get("gsc") or {}
    internal_context = snapshot.get("internal_linking") or {}
    cannibalization_context = snapshot.get("cannibalization") or {}
    issue_context = snapshot.get("issue_flags") or {}

    internal_issue_count = int(internal_context.get("issue_count") or 0)
    technical_issue_count = int(issue_context.get("technical_issue_count") or 0)
    active_flags = list(issue_context.get("active_flags") or [])
    cannibalization_severity = cannibalization_context.get("severity")
    has_target_url = not text_value_missing(recommendation.get("target_url"))

    if recommendation_type == "INTERNAL_LINKING_SUPPORT":
        return "internal_linking"
    if bool(cannibalization_context.get("has_active_signals")) and (
        CANNIBALIZATION_SEVERITY_ORDER.get(cannibalization_severity, 0) >= CANNIBALIZATION_SEVERITY_ORDER["high"]
        or int(cannibalization_context.get("common_queries_count") or 0) >= 2
    ):
        return "cannibalization"
    if technical_issue_count >= 2 or {"noindex_like", "non_indexable_like", "thin_content", "duplicate_content"} & set(active_flags):
        return "issue_flags"
    if has_target_url and bool(gsc_context.get("available")):
        return "gsc"
    if internal_issue_count > 0:
        return "internal_linking"
    if technical_issue_count > 0:
        return "issue_flags"
    return "mixed" if has_target_url else "unknown"


def _build_implemented_recommendations(
    states: list[SiteContentRecommendationState],
    *,
    active_crawl_id: int | None,
    active_analysis: RecommendationAnalysisContext | None,
    active_reference_at: datetime | None,
    outcome_window: str,
) -> list[dict[str, Any]]:
    items = [
        _build_implemented_recommendation_row(
            state,
            active_crawl_id=active_crawl_id,
            active_analysis=active_analysis,
            active_reference_at=active_reference_at,
            outcome_window=outcome_window,
        )
        for state in states
    ]
    _sort_implemented_recommendations(items, sort_by="implemented_at_desc")
    return items


def _build_implemented_recommendation_row(
    state: SiteContentRecommendationState,
    *,
    active_crawl_id: int | None,
    active_analysis: RecommendationAnalysisContext | None,
    active_reference_at: datetime | None,
    outcome_window: str,
) -> dict[str, Any]:
    helper_snapshot = state.helper_snapshot_json if isinstance(state.helper_snapshot_json, dict) else None
    signals_snapshot = state.signals_snapshot_json if isinstance(state.signals_snapshot_json, dict) else {}
    outcome = _build_implemented_recommendation_outcome(
        state,
        active_crawl_id=active_crawl_id,
        active_analysis=active_analysis,
        active_reference_at=active_reference_at,
        outcome_window=outcome_window,
        signals_snapshot=signals_snapshot,
    )
    return {
        "recommendation_key": state.recommendation_key,
        "recommendation_type": state.recommendation_type,
        "segment": state.segment,
        "target_url": state.target_url,
        "normalized_target_url": state.normalized_target_url,
        "target_title_snapshot": state.target_title_snapshot,
        "suggested_page_type": state.suggested_page_type,
        "cluster_label": state.cluster_label,
        "cluster_key": state.cluster_key,
        "recommendation_text": state.recommendation_text,
        "signals_snapshot": list(signals_snapshot.get("signals") or []),
        "reasons_snapshot": list(signals_snapshot.get("reasons") or []),
        "helper_snapshot": helper_snapshot,
        "primary_outcome_kind": state.primary_outcome_kind if state.primary_outcome_kind in OUTCOME_KIND_VALUES else "unknown",
        "outcome_status": outcome["status"],
        "outcome_summary": outcome["summary"],
        "outcome_details": outcome["details"],
        "outcome_window": outcome["outcome_window"],
        "is_too_early": outcome["is_too_early"],
        "days_since_implemented": outcome["days_since_implemented"],
        "eligible_for_window": outcome["eligible_for_window"],
        "implemented_at": _ensure_utc_datetime(state.implemented_at),
        "implemented_crawl_job_id": state.implemented_crawl_job_id,
        "implemented_baseline_crawl_job_id": state.implemented_baseline_crawl_job_id,
        "times_marked_done": int(state.times_marked_done or 0),
    }


def _build_implemented_recommendation_outcome(
    state: SiteContentRecommendationState,
    *,
    active_crawl_id: int | None,
    active_analysis: RecommendationAnalysisContext | None,
    active_reference_at: datetime | None,
    outcome_window: str,
    signals_snapshot: dict[str, Any],
) -> dict[str, Any]:
    implemented_at = _ensure_utc_datetime(state.implemented_at)
    reference_at = _ensure_utc_datetime(active_reference_at)
    days_since_implemented = _days_since_implemented(implemented_at, reference_at)
    eligible_for_window = _eligible_for_outcome_window(
        implemented_at,
        reference_at,
        outcome_window=outcome_window,
    )

    def with_window_metadata(
        status: str,
        summary: str,
        details: list[dict[str, Any]] | None = None,
        *,
        is_too_early: bool = False,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "summary": summary,
            "details": details or [],
            "outcome_window": outcome_window,
            "is_too_early": is_too_early,
            "days_since_implemented": days_since_implemented,
            "eligible_for_window": bool(eligible_for_window),
        }

    if active_crawl_id is None or active_analysis is None:
        return with_window_metadata("unavailable", "Outcome tracking needs an active crawl snapshot.")
    if state.implemented_crawl_job_id is None:
        return with_window_metadata("unavailable", "The implementation crawl snapshot is no longer available.")
    if active_crawl_id == state.implemented_crawl_job_id:
        return with_window_metadata("pending", "Waiting for a newer active crawl or GSC import.")
    if isinstance(reference_at, datetime) and isinstance(implemented_at, datetime) and reference_at <= implemented_at:
        return with_window_metadata("pending", "Waiting for post-implementation data in the selected active snapshot.")
    if outcome_window != "all" and not eligible_for_window:
        return with_window_metadata(
            "too_early",
            f"Too early to evaluate ({outcome_window} window).",
            is_too_early=True,
        )

    current_page = None
    current_internal = None
    if not text_value_missing(state.normalized_target_url):
        current_page = active_analysis.page_by_normalized_url.get(str(state.normalized_target_url))
        current_internal = active_analysis.internal_by_normalized_url.get(str(state.normalized_target_url))

    outcome_kind = state.primary_outcome_kind if state.primary_outcome_kind in OUTCOME_KIND_VALUES else "unknown"
    if outcome_kind == "gsc":
        base_outcome = _build_gsc_outcome(signals_snapshot, current_page=current_page, gsc_suffix=active_analysis.gsc_suffix)
        return with_window_metadata(base_outcome["status"], base_outcome["summary"], base_outcome["details"])
    if outcome_kind == "internal_linking":
        base_outcome = _build_internal_linking_outcome(
            signals_snapshot,
            current_page=current_page,
            current_internal=current_internal,
        )
        return with_window_metadata(base_outcome["status"], base_outcome["summary"], base_outcome["details"])
    if outcome_kind == "cannibalization":
        base_outcome = _build_cannibalization_outcome(signals_snapshot, current_page=current_page)
        return with_window_metadata(base_outcome["status"], base_outcome["summary"], base_outcome["details"])
    if outcome_kind == "issue_flags":
        base_outcome = _build_issue_flags_outcome(signals_snapshot, current_page=current_page)
        return with_window_metadata(base_outcome["status"], base_outcome["summary"], base_outcome["details"])
    if current_page is not None and bool((signals_snapshot.get("gsc") or {}).get("available")):
        base_outcome = _build_gsc_outcome(signals_snapshot, current_page=current_page, gsc_suffix=active_analysis.gsc_suffix)
        return with_window_metadata(base_outcome["status"], base_outcome["summary"], base_outcome["details"])
    if current_page is not None:
        base_outcome = _build_issue_flags_outcome(signals_snapshot, current_page=current_page)
        return with_window_metadata(base_outcome["status"], base_outcome["summary"], base_outcome["details"])
    return with_window_metadata("limited", "Outcome tracking is limited for this structural recommendation.")


def _build_gsc_outcome(
    signals_snapshot: dict[str, Any],
    *,
    current_page: dict[str, Any] | None,
    gsc_suffix: str,
) -> dict[str, Any]:
    before = signals_snapshot.get("gsc") or {}
    if not bool(before.get("available")):
        return {
            "status": "limited",
            "summary": "No before-state GSC snapshot was saved for this recommendation.",
            "details": [],
        }
    if current_page is None:
        return {
            "status": "limited",
            "summary": "Current URL metrics are unavailable in the active crawl.",
            "details": [],
        }

    before_impressions = int(before.get("impressions") or 0)
    before_clicks = int(before.get("clicks") or 0)
    before_ctr = float(before.get("ctr") or 0.0)
    before_position = _optional_metric_value(before.get("position"))

    after_impressions = int(current_page.get(f"impressions_{gsc_suffix}") or 0)
    after_clicks = int(current_page.get(f"clicks_{gsc_suffix}") or 0)
    after_ctr = float(current_page.get(f"ctr_{gsc_suffix}") or 0.0)
    after_position = _optional_metric_value(current_page.get(f"position_{gsc_suffix}"))

    delta_impressions = after_impressions - before_impressions
    delta_clicks = after_clicks - before_clicks
    delta_position = None if before_position is None or after_position is None else before_position - after_position

    score = 0
    score += 1 if delta_impressions > 0 else -1 if delta_impressions < 0 else 0
    score += 2 if delta_clicks > 0 else -2 if delta_clicks < 0 else 0
    score += 1 if delta_position is not None and delta_position > 0.25 else -1 if delta_position is not None and delta_position < -0.25 else 0
    status = "improved" if score > 0 else "worsened" if score < 0 else "unchanged"

    if delta_clicks != 0:
        summary = f"{_format_signed_int(delta_clicks)} clicks"
    elif delta_impressions != 0:
        summary = f"{_format_signed_int(delta_impressions)} impressions"
    elif before_position is not None and after_position is not None and abs(before_position - after_position) > 0.05:
        summary = f"Position {before_position:.1f} -> {after_position:.1f}"
    else:
        summary = "No meaningful GSC movement yet."

    return {
        "status": status,
        "summary": summary,
        "details": [
            _outcome_detail("Impressions", str(before_impressions), str(after_impressions), _format_signed_int(delta_impressions)),
            _outcome_detail("Clicks", str(before_clicks), str(after_clicks), _format_signed_int(delta_clicks)),
            _outcome_detail("CTR", f"{before_ctr:.2%}", f"{after_ctr:.2%}", _format_signed_float(after_ctr - before_ctr, precision=2, suffix="pp")),
            _outcome_detail(
                "Avg position",
                "-" if before_position is None else f"{before_position:.1f}",
                "-" if after_position is None else f"{after_position:.1f}",
                None if delta_position is None else _format_signed_float(delta_position, precision=1),
            ),
        ],
    }


def _build_internal_linking_outcome(
    signals_snapshot: dict[str, Any],
    *,
    current_page: dict[str, Any] | None,
    current_internal: dict[str, Any] | None,
) -> dict[str, Any]:
    before = signals_snapshot.get("internal_linking") or {}
    if not before:
        return {
            "status": "limited",
            "summary": "No before-state internal linking snapshot was saved for this recommendation.",
            "details": [],
        }
    if current_page is None and current_internal is None:
        return {
            "status": "limited",
            "summary": "Current internal linking data is unavailable for this URL.",
            "details": [],
        }

    after_issue_count = int((current_internal or {}).get("issue_count") or 0)
    after_score = int((current_internal or {}).get("internal_linking_score") or 0)
    after_linking_pages = int(
        (current_internal or {}).get("incoming_internal_linking_pages")
        or (current_page or {}).get("incoming_internal_linking_pages")
        or 0
    )

    before_issue_count = int(before.get("issue_count") or 0)
    before_score = int(before.get("internal_linking_score") or 0)
    before_linking_pages = int(before.get("incoming_internal_linking_pages") or 0)

    score = 0
    score += 2 if after_issue_count < before_issue_count else -2 if after_issue_count > before_issue_count else 0
    score += 1 if after_score > before_score else -1 if after_score < before_score else 0
    score += 1 if after_linking_pages > before_linking_pages else -1 if after_linking_pages < before_linking_pages else 0
    status = "improved" if score > 0 else "worsened" if score < 0 else "unchanged"

    if before_issue_count != after_issue_count:
        summary = f"Internal issues {before_issue_count} -> {after_issue_count}"
    elif before_linking_pages != after_linking_pages:
        summary = f"Linking pages {before_linking_pages} -> {after_linking_pages}"
    elif before_score != after_score:
        summary = f"Internal score {before_score} -> {after_score}"
    else:
        summary = "Internal linking support is unchanged."

    return {
        "status": status,
        "summary": summary,
        "details": [
            _outcome_detail(
                "Internal linking score",
                str(before_score),
                str(after_score),
                _format_signed_int(after_score - before_score),
            ),
            _outcome_detail(
                "Issue count",
                str(before_issue_count),
                str(after_issue_count),
                _format_signed_int(after_issue_count - before_issue_count),
            ),
            _outcome_detail(
                "Linking pages",
                str(before_linking_pages),
                str(after_linking_pages),
                _format_signed_int(after_linking_pages - before_linking_pages),
            ),
        ],
    }


def _build_cannibalization_outcome(
    signals_snapshot: dict[str, Any],
    *,
    current_page: dict[str, Any] | None,
) -> dict[str, Any]:
    before = signals_snapshot.get("cannibalization") or {}
    if not before:
        return {
            "status": "limited",
            "summary": "No before-state cannibalization snapshot was saved for this recommendation.",
            "details": [],
        }
    if current_page is None:
        return {
            "status": "limited",
            "summary": "Current cannibalization data is unavailable for this URL.",
            "details": [],
        }

    before_active = bool(before.get("has_active_signals"))
    after_active = bool(current_page.get("has_cannibalization"))
    before_severity = before.get("severity")
    after_severity = current_page.get("cannibalization_severity")
    before_competing_urls = int(before.get("competing_urls_count") or 0)
    after_competing_urls = int(current_page.get("cannibalization_competing_urls_count") or 0)
    before_shared_queries = int(before.get("common_queries_count") or 0)
    after_shared_queries = int(current_page.get("cannibalization_common_queries_count") or 0)

    before_score = (10 if before_active else 0) + CANNIBALIZATION_SEVERITY_ORDER.get(before_severity, 0) * 5 + before_competing_urls + before_shared_queries
    after_score = (10 if after_active else 0) + CANNIBALIZATION_SEVERITY_ORDER.get(after_severity, 0) * 5 + after_competing_urls + after_shared_queries
    status = "improved" if after_score < before_score else "worsened" if after_score > before_score else "unchanged"

    if before_active and not after_active:
        summary = "Cannibalization signal cleared."
    elif before_severity != after_severity and before_active and after_active:
        summary = f"Severity {before_severity or 'none'} -> {after_severity or 'none'}"
    elif before_competing_urls != after_competing_urls:
        summary = f"Competing URLs {before_competing_urls} -> {after_competing_urls}"
    else:
        summary = "Cannibalization signal is unchanged."

    return {
        "status": status,
        "summary": summary,
        "details": [
            _outcome_detail("Active signal", "Yes" if before_active else "No", "Yes" if after_active else "No", None),
            _outcome_detail("Severity", str(before_severity or "none"), str(after_severity or "none"), None),
            _outcome_detail(
                "Competing URLs",
                str(before_competing_urls),
                str(after_competing_urls),
                _format_signed_int(after_competing_urls - before_competing_urls),
            ),
            _outcome_detail(
                "Shared queries",
                str(before_shared_queries),
                str(after_shared_queries),
                _format_signed_int(after_shared_queries - before_shared_queries),
            ),
        ],
    }


def _build_issue_flags_outcome(
    signals_snapshot: dict[str, Any],
    *,
    current_page: dict[str, Any] | None,
) -> dict[str, Any]:
    before = signals_snapshot.get("issue_flags") or {}
    if current_page is None:
        return {
            "status": "limited",
            "summary": "Current issue data is unavailable for this URL.",
            "details": [],
        }

    before_count = int(before.get("technical_issue_count") or 0)
    after_count = int(current_page.get("technical_issue_count") or 0)
    before_flags = set(str(flag) for flag in before.get("active_flags") or [])
    after_flags = {flag for flag in OUTCOME_ISSUE_FLAG_KEYS if bool(current_page.get(flag))}
    resolved_flags = sorted(before_flags - after_flags)
    new_flags = sorted(after_flags - before_flags)

    score = 0
    score += 2 if after_count < before_count else -2 if after_count > before_count else 0
    score += 1 if len(resolved_flags) > len(new_flags) else -1 if len(new_flags) > len(resolved_flags) else 0
    status = "improved" if score > 0 else "worsened" if score < 0 else "unchanged"

    if before_flags and not after_flags:
        summary = "Tracked SEO issue flags no longer appear."
    elif before_count != after_count:
        summary = f"Technical issues {before_count} -> {after_count}"
    elif resolved_flags:
        summary = f"Resolved {len(resolved_flags)} tracked issue flag(s)."
    elif new_flags:
        summary = f"{len(new_flags)} tracked issue flag(s) worsened or appeared."
    else:
        summary = "Issue flags are unchanged."

    return {
        "status": status,
        "summary": summary,
        "details": [
            _outcome_detail(
                "Technical issue count",
                str(before_count),
                str(after_count),
                _format_signed_int(after_count - before_count),
            ),
            _outcome_detail(
                "Active issue flags",
                ", ".join(OUTCOME_ISSUE_FLAG_LABELS.get(flag, flag) for flag in sorted(before_flags)) or "None",
                ", ".join(OUTCOME_ISSUE_FLAG_LABELS.get(flag, flag) for flag in sorted(after_flags)) or "None",
                None,
            ),
        ],
    }


def _outcome_detail(label: str, before: str | None, after: str | None, change: str | None) -> dict[str, Any]:
    return {
        "label": label,
        "before": before,
        "after": after,
        "change": change,
    }


def _format_signed_int(value: int) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def _format_signed_float(value: float, *, precision: int, suffix: str = "") -> str:
    if value > 0:
        return f"+{value:.{precision}f}{suffix}"
    return f"{value:.{precision}f}{suffix}"


def _build_summary(recommendations: list[dict[str, Any]], *, implemented_count: int = 0) -> dict[str, Any]:
    counts_by_type = {recommendation_type: 0 for recommendation_type in CONTENT_RECOMMENDATION_TYPES}
    counts_by_page_type = {page_type: 0 for page_type in PAGE_TYPES}
    for recommendation in recommendations:
        recommendation_type = str(recommendation["recommendation_type"])
        counts_by_type[recommendation_type] = counts_by_type.get(recommendation_type, 0) + 1
        page_type = str(recommendation.get("page_type") or "other")
        counts_by_page_type[page_type] = counts_by_page_type.get(page_type, 0) + 1

    segments = Counter(str(recommendation["segment"]) for recommendation in recommendations)
    covered_clusters = {str(recommendation["cluster_key"]) for recommendation in recommendations}
    return {
        "total_recommendations": len(recommendations),
        "implemented_recommendations": int(implemented_count),
        "high_priority_recommendations": sum(1 for recommendation in recommendations if int(recommendation["priority_score"]) >= 70),
        "clusters_covered": len(covered_clusters),
        "create_new_page_recommendations": int(segments.get("create_new_page", 0)),
        "expand_existing_page_recommendations": int(segments.get("expand_existing_page", 0)),
        "strengthen_cluster_recommendations": int(segments.get("strengthen_cluster", 0)),
        "improve_internal_support_recommendations": int(segments.get("improve_internal_support", 0)),
        "counts_by_type": counts_by_type,
        "counts_by_page_type": counts_by_page_type,
    }


def _empty_summary(*, implemented_count: int = 0) -> dict[str, Any]:
    return {
        "total_recommendations": 0,
        "implemented_recommendations": int(implemented_count),
        "high_priority_recommendations": 0,
        "clusters_covered": 0,
        "create_new_page_recommendations": 0,
        "expand_existing_page_recommendations": 0,
        "strengthen_cluster_recommendations": 0,
        "improve_internal_support_recommendations": 0,
        "counts_by_type": {recommendation_type: 0 for recommendation_type in CONTENT_RECOMMENDATION_TYPES},
        "counts_by_page_type": {page_type: 0 for page_type in PAGE_TYPES},
    }


def _build_implemented_summary(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {status: 0 for status in IMPLEMENTED_OUTCOME_STATUS_ORDER}
    mode_counts = {mode: 0 for mode in OUTCOME_KIND_ORDER}
    for recommendation in recommendations:
        status = str(recommendation.get("outcome_status") or "")
        if status in status_counts:
            status_counts[status] += 1
        mode = str(recommendation.get("primary_outcome_kind") or "")
        if mode not in mode_counts:
            mode = "unknown"
        mode_counts[mode] += 1
    return {
        "total_count": len(recommendations),
        "status_counts": status_counts,
        "mode_counts": mode_counts,
    }


def _filter_recommendations(
    recommendations: list[dict[str, Any]],
    *,
    recommendation_type: str | None,
    segment: str | None,
    page_type: str | None,
    cluster: str | None,
    confidence_min: float | None,
    priority_score_min: int | None,
) -> list[dict[str, Any]]:
    filtered = list(recommendations)
    if recommendation_type:
        filtered = [recommendation for recommendation in filtered if str(recommendation.get("recommendation_type")) == recommendation_type]
    if segment:
        filtered = [recommendation for recommendation in filtered if str(recommendation.get("segment")) == segment]
    if page_type:
        filtered = [recommendation for recommendation in filtered if str(recommendation.get("page_type") or "") == page_type]
    if cluster:
        token = cluster.strip().lower()
        filtered = [
            recommendation
            for recommendation in filtered
            if token in str(recommendation.get("cluster_label") or "").lower()
            or token in str(recommendation.get("cluster_key") or "").lower()
        ]
    if confidence_min is not None:
        filtered = [recommendation for recommendation in filtered if float(recommendation.get("confidence") or 0.0) >= float(confidence_min)]
    if priority_score_min is not None:
        filtered = [recommendation for recommendation in filtered if int(recommendation.get("priority_score") or 0) >= int(priority_score_min)]
    return filtered


def _filter_implemented_recommendations(
    recommendations: list[dict[str, Any]],
    *,
    status_filter: str | None,
    mode_filter: str | None,
    search: str | None,
) -> list[dict[str, Any]]:
    filtered = list(recommendations)
    if status_filter and status_filter in IMPLEMENTED_STATUS_FILTER_VALUES and status_filter != "all":
        filtered = [recommendation for recommendation in filtered if str(recommendation.get("outcome_status") or "") == status_filter]
    if mode_filter and mode_filter in IMPLEMENTED_MODE_FILTER_VALUES and mode_filter != "all":
        filtered = [recommendation for recommendation in filtered if str(recommendation.get("primary_outcome_kind") or "") == mode_filter]
    search_tokens = [token for token in _tokenize_cluster_search(search) if token]
    if search_tokens:
        filtered = [
            recommendation
            for recommendation in filtered
            if all(token in _implemented_search_text(recommendation) for token in search_tokens)
        ]
    return filtered


def _tokenize_cluster_search(value: str | None) -> list[str]:
    if text_value_missing(value):
        return []
    normalized = _normalize_text(str(value))
    return [token.strip("-") for token in WORD_RE.findall(normalized) if token.strip("-")]


def _implemented_search_text(recommendation: dict[str, Any]) -> str:
    parts = [
        recommendation.get("recommendation_text"),
        recommendation.get("target_url"),
        recommendation.get("normalized_target_url"),
        recommendation.get("target_title_snapshot"),
        recommendation.get("cluster_label"),
        recommendation.get("cluster_key"),
    ]
    searchable_text = " ".join(str(part or "") for part in parts if not text_value_missing(part))
    return _normalize_text(searchable_text)


def _implemented_title_sort_value(recommendation: dict[str, Any]) -> str:
    candidates = (
        recommendation.get("target_title_snapshot"),
        recommendation.get("target_url"),
        recommendation.get("cluster_label"),
        recommendation.get("cluster_key"),
        recommendation.get("recommendation_text"),
    )
    for candidate in candidates:
        if not text_value_missing(candidate):
            return str(candidate).lower()
    return ""


def _datetime_sort_stamp(value: Any) -> float:
    normalized = _ensure_utc_datetime(value)
    if isinstance(normalized, datetime):
        return normalized.timestamp()
    return 0.0


def _sort_implemented_recommendations(
    recommendations: list[dict[str, Any]],
    *,
    sort_by: str,
) -> None:
    resolved_sort = sort_by if sort_by in IMPLEMENTED_SORT_VALUES else "implemented_at_desc"
    if resolved_sort == "implemented_at_desc":
        recommendations.sort(
            key=lambda recommendation: (
                -_datetime_sort_stamp(recommendation.get("implemented_at")),
                str(recommendation.get("recommendation_key") or "").lower(),
            )
        )
        return
    if resolved_sort == "implemented_at_asc":
        recommendations.sort(
            key=lambda recommendation: (
                _datetime_sort_stamp(recommendation.get("implemented_at")),
                str(recommendation.get("recommendation_key") or "").lower(),
            )
        )
        return
    if resolved_sort == "outcome":
        recommendations.sort(
            key=lambda recommendation: (
                IMPLEMENTED_OUTCOME_STATUS_RANK.get(
                    str(recommendation.get("outcome_status") or ""),
                    len(IMPLEMENTED_OUTCOME_STATUS_RANK),
                ),
                -_datetime_sort_stamp(recommendation.get("implemented_at")),
                _implemented_title_sort_value(recommendation),
                str(recommendation.get("recommendation_key") or "").lower(),
            )
        )
        return
    if resolved_sort == "recommendation_type":
        recommendations.sort(
            key=lambda recommendation: (
                str(recommendation.get("recommendation_type") or "").lower(),
                _implemented_title_sort_value(recommendation),
                -_datetime_sort_stamp(recommendation.get("implemented_at")),
                str(recommendation.get("recommendation_key") or "").lower(),
            )
        )
        return
    recommendations.sort(
        key=lambda recommendation: (
            _implemented_title_sort_value(recommendation),
            -_datetime_sort_stamp(recommendation.get("implemented_at")),
            str(recommendation.get("recommendation_key") or "").lower(),
        )
    )


def _sort_recommendations(
    recommendations: list[dict[str, Any]],
    *,
    sort_by: str,
    sort_order: str,
) -> None:
    def normalize_sort_value(recommendation: dict[str, Any]) -> tuple[Any, ...]:
        if sort_by == "priority_score":
            return (int(recommendation.get("priority_score") or 0), str(recommendation.get("cluster_label") or "").lower())
        if sort_by == "confidence":
            return (float(recommendation.get("confidence") or 0.0), str(recommendation.get("cluster_label") or "").lower())
        if sort_by == "impact":
            return (IMPACT_ORDER.get(str(recommendation.get("impact") or "low"), 0), str(recommendation.get("cluster_label") or "").lower())
        if sort_by == "effort":
            return (EFFORT_ORDER.get(str(recommendation.get("effort") or "low"), 0), str(recommendation.get("cluster_label") or "").lower())
        if sort_by == "recommendation_type":
            return (str(recommendation.get("recommendation_type") or "").lower(), str(recommendation.get("cluster_label") or "").lower())
        if sort_by == "page_type":
            return (str(recommendation.get("page_type") or "").lower(), str(recommendation.get("cluster_label") or "").lower())
        return (str(recommendation.get("cluster_label") or "").lower(), str(recommendation.get("recommendation_type") or "").lower())

    recommendations.sort(key=normalize_sort_value, reverse=sort_order == "desc")


def _serialize_site_crawl_context(crawl_job: Any, default_root_url: str) -> dict[str, Any] | None:
    if crawl_job is None:
        return None
    settings = crawl_job.settings_json if isinstance(crawl_job.settings_json, dict) else {}
    root_url = settings.get("start_url") or default_root_url
    status_value = crawl_job.status.value if hasattr(crawl_job.status, "value") else str(crawl_job.status)
    return {
        "id": crawl_job.id,
        "status": status_value,
        "created_at": crawl_job.created_at,
        "started_at": crawl_job.started_at,
        "finished_at": crawl_job.finished_at,
        "root_url": root_url,
    }


def _build_missing_supporting_content_recommendation(
    cluster: ClusterAnalysis,
    rules: ContentRecommendationRules,
) -> dict[str, Any] | None:
    if cluster.total_pages < rules.missing_support_min_pages:
        return None
    if cluster.supporting_pages > rules.missing_support_max_supporting_pages:
        return None
    if cluster.commercial_pages == 0:
        return None
    if (
        cluster.max_priority_score < rules.missing_support_min_priority_score
        and cluster.total_impressions < rules.missing_support_min_impressions
    ):
        return None

    suggested_page_type = "blog_article" if cluster.blog_articles == 0 else "faq"
    target_page = cluster.hub_page
    reasons = [
        f'Cluster "{cluster.label}" has {cluster.total_pages} indexed pages but no real supporting content layer.',
        f'The strongest page is {target_page.page_type} and already carries priority score {target_page.priority_score}.',
    ]
    signals = [
        f"Cluster pages: {cluster.total_pages}",
        f"Supporting pages: {cluster.supporting_pages}",
        f"Commercial pages: {cluster.commercial_pages}",
        f"Cluster impressions: {cluster.total_impressions}",
        f"Hub linking pages: {cluster.hub_linking_pages_from_cluster}",
    ]
    rationale = (
        f'Add a {suggested_page_type.replace("_", " ")} page to support "{cluster.label}" around '
        f"{target_page.url}, because the topic already exists but the cluster has no informational support."
    )
    return _compose_recommendation(
        recommendation_type="MISSING_SUPPORTING_CONTENT",
        cluster=cluster,
        target_page=target_page,
        page_type=suggested_page_type,
        suggested_page_type=suggested_page_type,
        impact=_resolve_impact(cluster.max_priority_score, cluster.total_impressions, cluster.total_clicks, rules),
        effort="medium",
        need_score=max(cluster.coverage_gap_score, 62),
        rationale=rationale,
        reasons=reasons,
        signals=signals,
        prerequisites=_build_prerequisites(cluster, target_page, "MISSING_SUPPORTING_CONTENT"),
        rules=rules,
    )


def _build_thin_cluster_recommendation(
    cluster: ClusterAnalysis,
    rules: ContentRecommendationRules,
) -> dict[str, Any] | None:
    if cluster.total_pages > rules.thin_cluster_max_pages:
        return None
    if (
        cluster.max_priority_score < rules.thin_cluster_min_priority_score
        and cluster.total_impressions < rules.thin_cluster_min_impressions
    ):
        return None

    target_page = cluster.hub_page
    suggested_page_type = "blog_article" if target_page.page_type in rules.commercial_page_types else "category"
    reasons = [
        f'Cluster "{cluster.label}" is represented by only {cluster.total_pages} page.',
        f"The topic already has {cluster.total_impressions} impressions and {cluster.cluster_internal_links} cluster links, so coverage is too shallow.",
    ]
    signals = [
        f"Cluster pages: {cluster.total_pages}",
        f"Cluster strength: {cluster.cluster_strength}",
        f"Coverage gap score: {cluster.coverage_gap_score}",
        f"Internal support score: {cluster.internal_support_score}",
        f"Target page type: {target_page.page_type}",
    ]
    rationale = (
        f'Strengthen "{cluster.label}" beyond {target_page.url}: right now the topic is only a single-page cluster, '
        "which limits support, intent coverage and internal reinforcement."
    )
    effort: EffortLevel = "high" if target_page.page_type in {"category", "service", "product"} else "medium"
    return _compose_recommendation(
        recommendation_type="THIN_CLUSTER",
        cluster=cluster,
        target_page=target_page,
        page_type=suggested_page_type,
        suggested_page_type=suggested_page_type,
        impact=_resolve_impact(cluster.max_priority_score, cluster.total_impressions, cluster.total_clicks, rules),
        effort=effort,
        need_score=max(cluster.coverage_gap_score, 68),
        rationale=rationale,
        reasons=reasons,
        signals=signals,
        prerequisites=_build_prerequisites(cluster, target_page, "THIN_CLUSTER"),
        rules=rules,
    )


def _build_expand_existing_page_recommendation(
    cluster: ClusterAnalysis,
    rules: ContentRecommendationRules,
) -> dict[str, Any] | None:
    candidates: list[tuple[float, PageTopicProfile]] = []
    for page in cluster.pages:
        if page.page_type not in rules.expansion_candidate_page_types:
            continue
        has_search_signal = (
            page.priority_score >= rules.expand_existing_min_priority_score
            or page.impressions >= rules.expand_existing_min_impressions
            or page.top_queries_count >= rules.expand_existing_min_top_queries
        )
        needs_depth = (
            page.word_count <= rules.expand_existing_max_word_count
            or page.technical_issue_count >= rules.expand_existing_min_issue_count
            or page.incoming_internal_linking_pages <= rules.expand_existing_low_linking_pages
        )
        if not has_search_signal or not needs_depth:
            continue
        candidate_score = (
            page.priority_score
            + min(page.impressions, 250) * 0.08
            + min(page.top_queries_count, 8) * 4
            + max(0, rules.expand_existing_max_word_count - page.word_count) * 0.02
            + max(0, rules.expand_existing_low_linking_pages - page.incoming_internal_linking_pages + 1) * 6
        )
        candidates.append((candidate_score, page))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1].url.lower()), reverse=True)
    target_page = candidates[0][1]
    signals = [
        f"Priority score: {target_page.priority_score}",
        f"Impressions: {target_page.impressions}",
        f"Top queries: {target_page.top_queries_count}",
        f"Word count: {target_page.word_count}",
        f"Linking pages: {target_page.incoming_internal_linking_pages}",
        f"Technical issues: {target_page.technical_issue_count}",
    ]
    reasons = [
        f"{target_page.url} already has demand signals, but the page is still too shallow or weakly supported.",
        f'The cluster around "{cluster.label}" already exists, so expanding this URL is more efficient than creating a parallel page first.',
    ]
    if target_page.primary_opportunity_type:
        reasons.append(f"Existing opportunity context already flags {target_page.primary_opportunity_type}.")
    rationale = (
        f"Expand {target_page.url}: the page already attracts demand, but content depth, on-page quality or internal support "
        "still leave clear upside on the table."
    )
    effort: EffortLevel = "high" if target_page.word_count <= 250 and target_page.technical_issue_count >= 3 else "medium"
    need_score = min(
        100,
        45
        + max(0, rules.expand_existing_max_word_count - target_page.word_count) // 5
        + min(target_page.technical_issue_count * 8, 24)
        + max(0, rules.expand_existing_low_linking_pages - target_page.incoming_internal_linking_pages + 1) * 10,
    )
    return _compose_recommendation(
        recommendation_type="EXPAND_EXISTING_PAGE",
        cluster=cluster,
        target_page=target_page,
        page_type=target_page.page_type,
        suggested_page_type=None,
        impact=_resolve_impact(target_page.priority_score, target_page.impressions, target_page.clicks, rules),
        effort=effort,
        need_score=need_score,
        rationale=rationale,
        reasons=reasons,
        signals=signals,
        prerequisites=_build_prerequisites(cluster, target_page, "EXPAND_EXISTING_PAGE"),
        rules=rules,
    )


def _build_missing_structural_page_type_recommendation(
    cluster: ClusterAnalysis,
    rules: ContentRecommendationRules,
) -> dict[str, Any] | None:
    suggested_page_type = None
    structural_reason = None
    if cluster.product_pages >= rules.missing_structural_min_detail_pages and cluster.category_pages == 0:
        suggested_page_type = "category"
        structural_reason = "The topic already has product-level detail pages, but no category or collection hub."
    elif cluster.blog_articles >= rules.missing_structural_min_blog_articles and cluster.blog_indexes == 0:
        suggested_page_type = "blog_index"
        structural_reason = "The topic already has multiple supporting articles, but no blog hub or archive page."

    if suggested_page_type is None or structural_reason is None:
        return None

    target_page = cluster.hub_page
    reasons = [
        structural_reason,
        f'Cluster "{cluster.label}" already spans {cluster.total_pages} pages, so the missing structural layer is now a bottleneck.',
    ]
    signals = [
        f"Product pages: {cluster.product_pages}",
        f"Blog articles: {cluster.blog_articles}",
        f"Category pages: {cluster.category_pages}",
        f"Blog indexes: {cluster.blog_indexes}",
        f"Cluster strength: {cluster.cluster_strength}",
    ]
    rationale = (
        f'Create a {suggested_page_type.replace("_", " ")} page for "{cluster.label}" so the existing URLs have a clearer '
        "hub and the cluster stops relying only on detail pages."
    )
    return _compose_recommendation(
        recommendation_type="MISSING_STRUCTURAL_PAGE_TYPE",
        cluster=cluster,
        target_page=target_page,
        page_type=suggested_page_type,
        suggested_page_type=suggested_page_type,
        impact=_resolve_impact(cluster.max_priority_score, cluster.total_impressions, cluster.total_clicks, rules),
        effort="high",
        need_score=max(cluster.coverage_gap_score, 74),
        rationale=rationale,
        reasons=reasons,
        signals=signals,
        prerequisites=_build_prerequisites(cluster, target_page, "MISSING_STRUCTURAL_PAGE_TYPE"),
        rules=rules,
    )


def _build_internal_linking_support_recommendation(
    cluster: ClusterAnalysis,
    rules: ContentRecommendationRules,
) -> dict[str, Any] | None:
    if cluster.total_pages < rules.internal_support_min_cluster_pages:
        return None

    target_page = cluster.hub_page
    direct_issue_weight = sum(rules.internal_issue_priority_weights.get(issue_type, 0) for issue_type in target_page.internal_issue_types)
    cluster_links_per_page = cluster.cluster_internal_links / max(cluster.total_pages, 1)
    weak_cluster_support = (
        cluster.hub_linking_pages_from_cluster <= rules.internal_support_max_cluster_linking_pages
        or cluster_links_per_page <= rules.internal_support_low_cluster_links_per_page
    )
    if not weak_cluster_support and direct_issue_weight <= 0:
        return None
    if (
        target_page.priority_score < rules.internal_support_min_priority_score
        and cluster.total_impressions < rules.medium_impact_impressions
    ):
        return None

    suggested_sources = sorted(
        {
            page.page_type.replace("_", " ")
            for page in cluster.pages
            if page.page_id != target_page.page_id and page.page_type not in {"other"}
        }
    )
    reasons = [
        f'{target_page.url} is the strongest page in the cluster, but internal support inside "{cluster.label}" is still weak.',
        f"The topic already exists across {cluster.total_pages} pages, so better internal linking is a faster lever than creating more URLs immediately.",
    ]
    signals = [
        f"Cluster internal links: {cluster.cluster_internal_links}",
        f"Cluster linking pages: {cluster.cluster_linking_pages}",
        f"Links to hub: {cluster.hub_links_from_cluster}",
        f"Hub linking pages: {cluster.hub_linking_pages_from_cluster}",
        f"Target internal issues: {', '.join(target_page.internal_issue_types) or 'none'}",
    ]
    if suggested_sources:
        signals.append(f"Suggested supporting page types: {', '.join(suggested_sources[:3])}")
    rationale = (
        f"Improve internal linking for {target_page.url}: the cluster has enough content to support the topic, "
        "but cross-linking and hub reinforcement are still too light."
    )
    effort: EffortLevel = "medium" if target_page.internal_issue_types else "low"
    need_score = min(
        100,
        45
        + direct_issue_weight
        + max(0, 5 - cluster.hub_linking_pages_from_cluster) * 8
        + max(0, int(round((1.5 - cluster_links_per_page) * 10))),
    )
    return _compose_recommendation(
        recommendation_type="INTERNAL_LINKING_SUPPORT",
        cluster=cluster,
        target_page=target_page,
        page_type=target_page.page_type,
        suggested_page_type=None,
        impact=_resolve_impact(target_page.priority_score, cluster.total_impressions, cluster.total_clicks, rules),
        effort=effort,
        need_score=need_score,
        rationale=rationale,
        reasons=reasons,
        signals=signals,
        prerequisites=_build_prerequisites(cluster, target_page, "INTERNAL_LINKING_SUPPORT"),
        rules=rules,
    )


def _compose_recommendation(
    *,
    recommendation_type: ContentRecommendationType,
    cluster: ClusterAnalysis,
    target_page: PageTopicProfile,
    page_type: str,
    suggested_page_type: str | None,
    impact: ImpactLevel,
    effort: EffortLevel,
    need_score: int,
    rationale: str,
    reasons: list[str],
    signals: list[str],
    prerequisites: list[str],
    rules: ContentRecommendationRules,
) -> dict[str, Any]:
    confidence = _compute_confidence(
        recommendation_type=recommendation_type,
        cluster=cluster,
        target_page=target_page,
        prerequisites=prerequisites,
        rules=rules,
    )
    priority_score = _compute_priority_score(
        recommendation_type=recommendation_type,
        impact=impact,
        effort=effort,
        confidence=confidence,
        business_value=max(target_page.priority_score, cluster.max_priority_score),
        demand_impressions=max(target_page.impressions, cluster.total_impressions),
        demand_clicks=max(target_page.clicks, cluster.total_clicks),
        need_score=need_score,
        internal_support_score=cluster.internal_support_score,
        rules=rules,
    )
    supporting_urls = [page.url for page in cluster.pages if page.page_id != target_page.page_id][:3]
    recommendation_id = f"{recommendation_type}:{cluster.key}:{target_page.page_id}:{suggested_page_type or target_page.page_type}"
    recommendation = {
        "id": recommendation_id,
        "recommendation_type": recommendation_type,
        "segment": rules.recommendation_segment_by_type[recommendation_type],
        "cluster_key": cluster.key,
        "cluster_label": cluster.label,
        "target_page_id": target_page.page_id,
        "target_url": target_page.url,
        "normalized_target_url": target_page.normalized_url,
        "page_type": page_type,
        "target_page_type": target_page.page_type,
        "suggested_page_type": suggested_page_type,
        "priority_score": priority_score,
        "confidence": confidence,
        "impact": impact,
        "effort": effort,
        "cluster_strength": cluster.cluster_strength,
        "coverage_gap_score": cluster.coverage_gap_score,
        "internal_support_score": cluster.internal_support_score,
        "rationale": rationale,
        "signals": signals[:6],
        "reasons": reasons[:4],
        "prerequisites": prerequisites[:3],
        "supporting_urls": supporting_urls,
        "was_implemented_before": False,
        "previously_implemented_at": None,
    }
    recommendation["recommendation_key"] = build_content_recommendation_key(recommendation)
    return recommendation


def _page_is_cluster_eligible(record: dict[str, Any], rules: ContentRecommendationRules) -> bool:
    if not bool(record.get("is_internal")):
        return False
    if str(record.get("page_type") or "other") not in rules.cluster_eligible_page_types:
        return False
    if bool(record.get("non_indexable_like")):
        return False
    status_code = record.get("status_code")
    if status_code is not None and int(status_code) >= 400:
        return False
    return True


def _extract_path_topic_weights(url: Any, rules: ContentRecommendationRules) -> tuple[str | None, dict[str, float]]:
    if text_value_missing(url):
        return None, {}
    parsed = urlsplit(str(url))
    path = unquote(parsed.path or "/")
    segments = [segment for segment in path.split("/") if segment]
    weights: dict[str, float] = {}
    primary_token = None
    non_generic_rank = 0
    for segment in segments:
        tokens = _tokenize(segment, rules)
        for token in tokens:
            non_generic_rank += 1
            if primary_token is None:
                primary_token = token
                weights[token] = weights.get(token, 0.0) + rules.path_primary_token_weight
            else:
                bonus = rules.path_secondary_token_weight / min(non_generic_rank, 3)
                weights[token] = weights.get(token, 0.0) + bonus
    return primary_token, weights


def _extract_text_topic_weights(record: dict[str, Any], rules: ContentRecommendationRules) -> dict[str, float]:
    weights: dict[str, float] = {}
    for value, weight in ((record.get("title"), rules.title_token_weight), (record.get("h1"), rules.h1_token_weight)):
        if text_value_missing(value):
            continue
        for token in _tokenize(str(value), rules):
            weights[token] = weights.get(token, 0.0) + weight
    return weights


def _build_label_hint(record: dict[str, Any], topic_weights: dict[str, float]) -> str:
    if not text_value_missing(record.get("h1")):
        return str(record["h1"]).strip()
    if not text_value_missing(record.get("title")):
        return str(record["title"]).strip()
    top_tokens = [token for token, _ in sorted(topic_weights.items(), key=lambda item: (-item[1], item[0]))[:2]]
    return " ".join(_prettify_token(token) for token in top_tokens) or str(record.get("url") or "")


def _merge_weight_maps(*maps: dict[str, float]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for item in maps:
        for token, weight in item.items():
            merged[token] = merged.get(token, 0.0) + float(weight)
    return merged


def _primary_token(topic_weights: dict[str, float]) -> str | None:
    if not topic_weights:
        return None
    ranked = sorted(topic_weights.items(), key=lambda item: (-item[1], item[0]))
    return ranked[0][0]


def _build_cluster_label(cluster_key: str, pages: list[PageTopicProfile], rules: ContentRecommendationRules) -> str:
    aggregate: dict[str, float] = {}
    for page in pages:
        for token, weight in page.topic_weights.items():
            aggregate[token] = aggregate.get(token, 0.0) + weight
    ranked = sorted(aggregate.items(), key=lambda item: (-item[1], item[0]))
    if not ranked:
        return _prettify_token(cluster_key)

    label_tokens = [ranked[0][0]]
    if (
        len(ranked) > 1
        and ranked[1][1] >= ranked[0][1] * rules.label_secondary_token_min_share
        and len(label_tokens) < rules.label_max_tokens
    ):
        label_tokens.append(ranked[1][0])
    if len(pages) == 1 and pages[0].label_hint:
        best_hint = pages[0].label_hint.strip()
        if len(best_hint.split()) <= 7:
            return best_hint
    return " ".join(_prettify_token(token) for token in label_tokens)


def _load_query_tokens_by_page(
    session: Session,
    crawl_job_id: int,
    gsc_date_range: str,
    rules: ContentRecommendationRules,
) -> dict[int, dict[str, float]]:
    rows = session.scalars(
        select(GscTopQuery)
        .where(
            GscTopQuery.crawl_job_id == crawl_job_id,
            GscTopQuery.date_range_label == gsc_date_range,
            GscTopQuery.page_id.is_not(None),
        )
        .order_by(GscTopQuery.impressions.desc(), GscTopQuery.clicks.desc(), GscTopQuery.id.asc())
    ).all()
    counts_by_page: Counter[int] = Counter()
    weights_by_page: dict[int, dict[str, float]] = defaultdict(dict)
    for row in rows:
        if row.page_id is None:
            continue
        page_id = int(row.page_id)
        if counts_by_page[page_id] >= rules.max_query_rows_per_page:
            continue
        counts_by_page[page_id] += 1
        bonus = min(
            rules.query_token_max_bonus,
            (float(row.impressions or 0) / rules.query_impression_bonus_divisor)
            + (float(row.clicks or 0) / rules.query_click_bonus_divisor),
        )
        for token in _tokenize(str(row.query or ""), rules):
            weights_by_page[page_id][token] = weights_by_page[page_id].get(token, 0.0) + rules.query_token_weight + bonus
    return {page_id: dict(weights) for page_id, weights in weights_by_page.items()}


def _load_anchor_tokens_by_page(
    internal_rows: list[dict[str, Any]],
    rules: ContentRecommendationRules,
) -> dict[int, dict[str, float]]:
    weights_by_page: dict[int, dict[str, float]] = defaultdict(dict)
    for row in internal_rows:
        page_id = int(row["page_id"])
        samples = row.get("top_anchor_samples") or []
        used = 0
        for sample in samples:
            if used >= rules.max_anchor_samples_per_page:
                break
            if bool(sample.get("boilerplate_likely")):
                continue
            used += 1
            for token in _tokenize(str(sample.get("anchor_text") or ""), rules):
                weights_by_page[page_id][token] = weights_by_page[page_id].get(token, 0.0) + rules.anchor_token_weight
    return {page_id: dict(weights) for page_id, weights in weights_by_page.items()}


def _choose_hub_page(
    pages: list[PageTopicProfile],
    cluster_metrics: dict[str, Any],
    rules: ContentRecommendationRules,
) -> PageTopicProfile:
    links_to_page = cluster_metrics["links_to_page"]
    linking_pages_to_page = cluster_metrics["linking_pages_to_page"]

    def hub_score(page: PageTopicProfile) -> tuple[float, int]:
        base = rules.hub_page_type_weights.get(page.page_type, 1.0)
        cluster_links = int(links_to_page.get(page.page_id, 0))
        cluster_linking_pages = len(linking_pages_to_page.get(page.page_id, set()))
        score = base + (page.priority_score / 18.0) + min(page.impressions, 250) / 120.0 + cluster_linking_pages * 0.8 + cluster_links * 0.2
        return (score, -page.page_id)

    return max(pages, key=hub_score)


def _load_cluster_link_metrics(
    session: Session,
    crawl_job_id: int,
    page_by_id: dict[int, PageTopicProfile],
) -> dict[str, dict[str, Any]]:
    page_id_by_normalized_url = {page.normalized_url: page.page_id for page in page_by_id.values()}
    metrics: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "cluster_internal_links": 0,
            "cluster_linking_pages": set(),
            "links_to_page": defaultdict(int),
            "linking_pages_to_page": defaultdict(set),
        }
    )
    rows = session.scalars(
        select(Link)
        .where(Link.crawl_job_id == crawl_job_id, Link.is_internal.is_(True), Link.target_normalized_url.is_not(None))
        .order_by(Link.id.asc())
    ).all()
    for link in rows:
        source_page = page_by_id.get(int(link.source_page_id))
        if source_page is None:
            continue
        target_page_id = page_id_by_normalized_url.get(str(link.target_normalized_url))
        if target_page_id is None:
            continue
        target_page = page_by_id.get(target_page_id)
        if target_page is None or source_page.cluster_key != target_page.cluster_key:
            continue
        cluster_metrics = metrics[source_page.cluster_key]
        cluster_metrics["cluster_internal_links"] += 1
        cluster_metrics["cluster_linking_pages"].add(source_page.page_id)
        cluster_metrics["links_to_page"][target_page.page_id] += 1
        cluster_metrics["linking_pages_to_page"][target_page.page_id].add(source_page.page_id)

    for cluster_metrics in metrics.values():
        cluster_metrics["cluster_linking_pages"] = len(cluster_metrics["cluster_linking_pages"])
    return metrics


def _compute_cluster_strength(
    *,
    total_pages: int,
    page_types: set[str],
    total_impressions: int,
    total_clicks: int,
    cluster_internal_links: int,
    cluster_linking_pages: int,
) -> int:
    pages_component = min(38, total_pages * 10)
    diversity_component = min(20, len(page_types) * 5)
    demand_component = min(24, (total_impressions // 40) + (total_clicks * 2))
    support_component = min(18, (cluster_internal_links * 3) + (cluster_linking_pages * 4))
    return max(0, min(100, pages_component + diversity_component + demand_component + support_component))


def _compute_internal_support_score(
    *,
    total_pages: int,
    cluster_internal_links: int,
    cluster_linking_pages: int,
    hub_linking_pages_from_cluster: int,
    pages: list[PageTopicProfile],
) -> int:
    if total_pages <= 1:
        return 18
    weak_pages = sum(1 for page in pages if {"WEAKLY_LINKED_IMPORTANT", "LOW_LINK_EQUITY", "ORPHAN_LIKE"} & set(page.internal_issue_types))
    score = 18 + min(30, cluster_internal_links * 5) + min(20, cluster_linking_pages * 6) + min(24, hub_linking_pages_from_cluster * 8) - min(18, weak_pages * 6)
    return max(0, min(100, score))


def _compute_coverage_gap_score(
    *,
    total_pages: int,
    commercial_pages: int,
    supporting_pages: int,
    blog_articles: int,
    blog_indexes: int,
    faq_pages: int,
    category_pages: int,
    product_pages: int,
    service_pages: int,
    location_pages: int,
    internal_support_score: int,
) -> int:
    score = 0
    if total_pages <= 1:
        score += 52
    if commercial_pages > 0 and supporting_pages == 0 and total_pages >= 2:
        score += 28
    if product_pages >= 2 and category_pages == 0:
        score += 32
    if blog_articles >= 2 and blog_indexes == 0:
        score += 28
    if commercial_pages >= 2 and faq_pages == 0:
        score += 10
    if service_pages + location_pages >= 2 and supporting_pages == 0:
        score += 12
    if internal_support_score < 40:
        score += 12
    return max(0, min(100, score))


def _resolve_impact(priority_score: int, impressions: int, clicks: int, rules: ContentRecommendationRules) -> ImpactLevel:
    if priority_score >= rules.high_impact_priority_score or impressions >= rules.high_impact_impressions or clicks >= rules.high_impact_clicks:
        return "high"
    if priority_score >= rules.medium_impact_priority_score or impressions >= rules.medium_impact_impressions or clicks >= rules.medium_impact_clicks:
        return "medium"
    return "low"


def _compute_confidence(
    *,
    recommendation_type: ContentRecommendationType,
    cluster: ClusterAnalysis,
    target_page: PageTopicProfile,
    prerequisites: list[str],
    rules: ContentRecommendationRules,
) -> float:
    confidence = rules.confidence_base_by_type[recommendation_type]
    if cluster.stable:
        confidence += 0.06
    if cluster.total_pages >= 2:
        confidence += 0.04
    if cluster.average_taxonomy_confidence >= 0.7:
        confidence += 0.05
    if target_page.page_type_confidence >= 0.75:
        confidence += 0.05
    if target_page.impressions > 0 or target_page.clicks > 0 or target_page.top_queries_count > 0:
        confidence += 0.08
    if target_page.internal_issue_types:
        confidence += 0.05
    if cluster.high_cannibalization_pages > 0:
        confidence -= 0.03
    if prerequisites:
        confidence -= 0.04
    return round(max(0.35, min(0.95, confidence)), 2)


def _compute_priority_score(
    *,
    recommendation_type: ContentRecommendationType,
    impact: ImpactLevel,
    effort: EffortLevel,
    confidence: float,
    business_value: int,
    demand_impressions: int,
    demand_clicks: int,
    need_score: int,
    internal_support_score: int,
    rules: ContentRecommendationRules,
) -> int:
    score = rules.impact_base_score[impact]
    score += min(18, business_value // 4)
    score += min(14, demand_impressions // 70)
    score += min(8, demand_clicks // 4)
    score += min(18, int(need_score) // 5)
    score += min(10, max(0, 55 - internal_support_score) // 4)
    score += int(round(confidence * 12))
    score += rules.type_priority_bonus[recommendation_type]
    score -= rules.effort_penalty[effort]
    return max(0, min(100, int(score)))


def _build_prerequisites(
    cluster: ClusterAnalysis,
    target_page: PageTopicProfile,
    recommendation_type: ContentRecommendationType,
) -> list[str]:
    prerequisites: list[str] = []
    if target_page.has_cannibalization and target_page.cannibalization_severity in {"high", "critical"}:
        prerequisites.append("Resolve overlapping cannibalization on the target URL before expanding this topic further.")
    if recommendation_type != "INTERNAL_LINKING_SUPPORT" and {"WEAKLY_LINKED_IMPORTANT", "LOW_LINK_EQUITY", "ORPHAN_LIKE"} & set(target_page.internal_issue_types):
        prerequisites.append("Improve internal linking support around the target URL before scaling the cluster.")
    if cluster.high_cannibalization_pages >= 2:
        prerequisites.append("Review overlapping URLs inside the cluster before adding more pages to the same topic.")
    return prerequisites


def _resolve_gsc_suffix(gsc_date_range: str) -> str:
    if gsc_date_range == "last_90_days":
        return "90d"
    if gsc_date_range == "last_28_days":
        return "28d"
    raise ContentRecommendationServiceError(f"Unsupported gsc_date_range '{gsc_date_range}'.")


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    return ascii_only.lower()


def _tokenize(value: str, rules: ContentRecommendationRules) -> list[str]:
    if text_value_missing(value):
        return []
    normalized = _normalize_text(value)
    tokens: list[str] = []
    for token in WORD_RE.findall(normalized):
        cleaned = token.strip("-")
        if not cleaned or len(cleaned) < rules.min_token_length:
            continue
        if cleaned in rules.stopwords or cleaned in rules.generic_topic_tokens:
            continue
        if cleaned.isdigit():
            continue
        tokens.append(cleaned)
    return tokens


def _prettify_token(token: str) -> str:
    if not token:
        return token
    return token.replace("-", " ").strip().title()
