from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Any
from urllib.parse import unquote, urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.text_processing import collapse_whitespace, dedupe_preserve_order, normalize_text_for_hash, tokenize_topic_text
from app.db.models import CrawlJob, SiteCompetitorPage, SiteCompetitorPageExtraction, SiteCompetitorSemanticCandidate, utcnow
from app.services import competitive_gap_own_semantic_service, competitive_gap_service, priority_service
from app.services.competitive_gap_page_diagnostics import (
    get_page_robots_meta,
    get_page_schema_present,
    get_page_schema_types,
    get_page_word_count,
    get_page_x_robots_tag,
)
from app.services.competitive_gap_semantic_card_service import (
    build_primary_topic_key,
    build_semantic_match_terms,
    normalize_semantic_card,
)
from app.services.competitive_gap_semantic_rules import resolve_semantic_eligibility
from app.services.competitive_gap_topic_quality_service import TopicQualitySignals, analyze_topic_quality, update_page_topic_quality_debug
from app.services.seo_analysis import build_page_records


PATH_TOKEN_WEIGHTS: tuple[float, ...] = (4.0, 2.0, 1.5, 1.0)
TITLE_TOKEN_WEIGHT = 3.0
H1_TOKEN_WEIGHT = 4.0
PRIMARY_TOKEN_LIMIT = 4
SECONDARY_TOKEN_LIMIT = 6
DEFAULT_CANDIDATE_LIMIT = 10
MIN_COMPETITOR_MERGE_SCORE = 18
MIN_OWN_MATCH_SCORE = 16
COMMERCIAL_PAGE_TYPES = {"home", "category", "product", "service", "location"}
INFORMATIONAL_PAGE_TYPES = {"blog_article", "blog_index", "faq"}
TRUST_PAGE_TYPES = {"about", "contact", "legal"}
GENERIC_TOPIC_TOKENS = set(competitive_gap_service.IGNORED_TOPIC_TOKENS) | {
    "account",
    "archive",
    "cart",
    "checkout",
    "contact",
    "home",
    "index",
    "legal",
    "login",
    "page",
    "pages",
    "policy",
    "privacy",
    "register",
    "search",
    "terms",
    "utility",
}


class CompetitiveGapSemanticServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class MaterializedSemanticTopic:
    semantic_input_hash: str
    raw_topic_key: str | None
    raw_topic_label: str | None
    primary_tokens: list[str]
    secondary_tokens: list[str]
    match_terms: list[str]
    quality_score: int
    path_tokens: list[str]


@dataclass(slots=True)
class SemanticFoundationRefreshResult:
    processed_pages: int = 0
    unchanged_pages: int = 0
    eligible_pages: int = 0
    excluded_pages: int = 0
    inserted_candidates: int = 0
    updated_candidates: int = 0
    retired_candidates: int = 0
    changed_candidate_ids: list[int] | None = None


@dataclass(slots=True)
class CompetitorMergeCandidateSuggestion:
    candidate_id: int
    competitor_id: int
    competitor_page_id: int
    raw_topic_key: str
    raw_topic_label: str
    score: int
    shared_primary_tokens: int
    shared_nonprimary_terms: int
    shared_terms: int
    exact_topic_key_match: bool
    same_page_type: bool
    same_page_bucket: bool
    quality_bonus: int


@dataclass(slots=True)
class CompetitorMergeCandidateGroup:
    source_candidate_id: int
    source_competitor_id: int
    source_competitor_page_id: int
    source_raw_topic_key: str
    source_raw_topic_label: str
    candidates: list[CompetitorMergeCandidateSuggestion]


@dataclass(slots=True)
class OwnSiteMatchCandidateSuggestion:
    page_id: int
    normalized_url: str
    page_type: str
    score: int
    priority_score: int
    impressions: int
    shared_primary_tokens: int
    shared_nonprimary_terms: int
    shared_terms: int
    shared_anchor_terms: int
    exact_topic_key_match: bool
    same_page_family: bool
    same_intent: bool
    same_page_role: bool
    semantic_alignment_score: float
    priority_bonus: int
    impressions_bonus: int


@dataclass(slots=True)
class OwnSiteMatchCandidateGroup:
    source_candidate_id: int
    source_competitor_id: int
    source_competitor_page_id: int
    source_raw_topic_key: str
    source_raw_topic_label: str
    candidates: list[OwnSiteMatchCandidateSuggestion]


@dataclass(slots=True)
class OwnSiteMatchIndex:
    own_pages: list[Any]
    own_pages_by_id: dict[int, Any]
    own_term_index: dict[str, set[int]]


def refresh_competitor_semantic_foundation(
    session: Session,
    site_id: int,
    competitor_id: int,
    *,
    page_ids: Sequence[int] | None = None,
) -> SemanticFoundationRefreshResult:
    query = (
        select(SiteCompetitorPage)
        .where(
            SiteCompetitorPage.site_id == site_id,
            SiteCompetitorPage.competitor_id == competitor_id,
        )
        .order_by(SiteCompetitorPage.id.asc())
    )
    if page_ids is not None:
        normalized_ids = sorted({int(page_id) for page_id in page_ids})
        if not normalized_ids:
            return SemanticFoundationRefreshResult()
        query = query.where(SiteCompetitorPage.id.in_(normalized_ids))

    pages = session.scalars(query).all()
    if not pages:
        return SemanticFoundationRefreshResult()
    latest_extractions_by_page_id = _load_latest_valid_extractions_by_page_id(
        session,
        competitor_id=competitor_id,
        page_ids=[page.id for page in pages],
    )

    candidate_rows = session.scalars(
        select(SiteCompetitorSemanticCandidate)
        .where(
            SiteCompetitorSemanticCandidate.competitor_page_id.in_([page.id for page in pages]),
        )
        .order_by(
            SiteCompetitorSemanticCandidate.competitor_page_id.asc(),
            SiteCompetitorSemanticCandidate.created_at.asc(),
            SiteCompetitorSemanticCandidate.id.asc(),
        )
    ).all()
    candidates_by_page_id: dict[int, list[SiteCompetitorSemanticCandidate]] = defaultdict(list)
    for row in candidate_rows:
        candidates_by_page_id[row.competitor_page_id].append(row)

    result = SemanticFoundationRefreshResult()
    changed_candidate_refs: list[SiteCompetitorSemanticCandidate] = []
    evaluated_at = utcnow()
    for page in pages:
        result.processed_pages += 1
        quality_signals = update_page_topic_quality_debug(page)
        semantic_card = _resolve_page_semantic_card(page, latest_extractions_by_page_id.get(page.id))
        materialized = materialize_page_semantic_topic(page, semantic_card=semantic_card, quality_signals=quality_signals)
        eligibility = resolve_semantic_eligibility(page, match_terms=materialized.match_terms)
        if (
            page.semantic_last_evaluated_at is not None
            and page.semantic_input_hash == materialized.semantic_input_hash
            and bool(page.semantic_eligible) == bool(eligibility.eligible)
            and str(page.semantic_exclusion_reason or "") == str(eligibility.exclusion_reason or "")
        ):
            result.unchanged_pages += 1
            continue

        page_candidates = candidates_by_page_id.get(page.id, [])
        retired_count = _retire_current_candidates(
            page_candidates,
            keep_hash=materialized.semantic_input_hash if eligibility.eligible else None,
            touched_at=evaluated_at,
        )
        result.retired_candidates += retired_count

        page.semantic_input_hash = materialized.semantic_input_hash
        page.semantic_last_evaluated_at = evaluated_at
        page.semantic_eligible = eligibility.eligible
        page.semantic_exclusion_reason = eligibility.exclusion_reason

        if not eligibility.eligible:
            result.excluded_pages += 1
            continue

        candidate = _find_candidate_for_hash(page_candidates, materialized.semantic_input_hash)
        if candidate is None:
            candidate = SiteCompetitorSemanticCandidate(
                site_id=page.site_id,
                competitor_id=page.competitor_id,
                competitor_page_id=page.id,
                semantic_input_hash=materialized.semantic_input_hash,
                raw_topic_key=materialized.raw_topic_key or "",
                raw_topic_label=materialized.raw_topic_label or "",
                normalized_terms_json=list(materialized.match_terms),
                page_type=str(page.page_type or "other"),
                page_bucket=str(page.page_bucket or "other"),
                quality_score=int(materialized.quality_score),
                current=True,
            )
            session.add(candidate)
            page_candidates.append(candidate)
            result.inserted_candidates += 1
            changed_candidate_refs.append(candidate)
        else:
            candidate.raw_topic_key = materialized.raw_topic_key or ""
            candidate.raw_topic_label = materialized.raw_topic_label or ""
            candidate.normalized_terms_json = list(materialized.match_terms)
            candidate.page_type = str(page.page_type or "other")
            candidate.page_bucket = str(page.page_bucket or "other")
            candidate.quality_score = int(materialized.quality_score)
            candidate.current = True
            result.updated_candidates += 1
            changed_candidate_refs.append(candidate)

        result.eligible_pages += 1

    session.flush()
    result.changed_candidate_ids = [candidate.id for candidate in changed_candidate_refs if candidate.id is not None]
    return result


def materialize_page_semantic_topic(
    page: SiteCompetitorPage,
    *,
    semantic_card: dict[str, Any] | None = None,
    quality_signals: TopicQualitySignals | None = None,
) -> MaterializedSemanticTopic:
    semantic_input_hash = build_semantic_input_hash(page)
    path_tokens = _extract_path_tokens(page.final_url or page.normalized_url or page.url or "")
    if semantic_card:
        normalized_card = normalize_semantic_card(semantic_card)
        semantic_input_hash = str(normalized_card.get("semantic_input_hash") or semantic_input_hash)
        primary_tokens = tokenize_topic_text(str(normalized_card.get("primary_topic") or ""))[:PRIMARY_TOKEN_LIMIT]
        secondary_source = [
            *(normalized_card.get("topic_labels") or []),
            *(normalized_card.get("supporting_subtopics") or []),
            *(normalized_card.get("entities") or []),
        ]
        secondary_tokens = dedupe_preserve_order(
            token
            for value in secondary_source
            for token in tokenize_topic_text(value)
            if token and token not in primary_tokens
        )[:SECONDARY_TOKEN_LIMIT]
        match_terms = build_semantic_match_terms(normalized_card)
        raw_topic_key = build_primary_topic_key(normalized_card)
        raw_topic_label = str(
            normalized_card.get("primary_topic")
            or (normalized_card.get("topic_labels") or [None])[0]
            or _build_raw_topic_label(page, primary_tokens + secondary_tokens)
            or ""
        ).strip() or None
        quality_score = max(
            _build_quality_score(page, has_path_topic=bool(path_tokens)),
            int(round(float(normalized_card.get("confidence") or 0.0) * 100)),
        )
        return MaterializedSemanticTopic(
            semantic_input_hash=semantic_input_hash,
            raw_topic_key=raw_topic_key or None,
            raw_topic_label=raw_topic_label,
            primary_tokens=list(primary_tokens),
            secondary_tokens=list(secondary_tokens),
            match_terms=list(match_terms),
            quality_score=quality_score,
            path_tokens=list(path_tokens),
        )
    resolved_quality_signals = quality_signals or analyze_topic_quality(page)
    primary_tokens = list(resolved_quality_signals.primary_tokens[:PRIMARY_TOKEN_LIMIT])
    if not primary_tokens and path_tokens:
        primary_tokens = list(path_tokens[:PRIMARY_TOKEN_LIMIT])
    secondary_tokens = dedupe_preserve_order(
        [
            *resolved_quality_signals.secondary_tokens,
            *path_tokens,
        ]
    )
    secondary_tokens = [
        token for token in secondary_tokens if token not in primary_tokens
    ][:SECONDARY_TOKEN_LIMIT]
    match_terms = dedupe_preserve_order(
        [
            *resolved_quality_signals.normalized_terms,
            *primary_tokens,
            *secondary_tokens,
            *path_tokens,
        ]
    )
    raw_topic_key = resolved_quality_signals.dominant_topic_key or ("-".join(primary_tokens) if primary_tokens else None)
    raw_topic_label = resolved_quality_signals.dominant_topic_label or _build_raw_topic_label(page, primary_tokens + secondary_tokens)
    quality_score = _build_quality_score(
        page,
        has_path_topic=bool(path_tokens),
        quality_signals=resolved_quality_signals,
    )
    return MaterializedSemanticTopic(
        semantic_input_hash=semantic_input_hash,
        raw_topic_key=raw_topic_key,
        raw_topic_label=raw_topic_label,
        primary_tokens=list(primary_tokens),
        secondary_tokens=list(secondary_tokens),
        match_terms=list(match_terms),
        quality_score=quality_score,
        path_tokens=list(path_tokens),
    )


def build_semantic_input_hash(page: SiteCompetitorPage) -> str:
    payload = {
        "canonical_url": normalize_text_for_hash(page.canonical_url),
        "content_text_hash": normalize_text_for_hash(page.content_text_hash),
        "content_type": normalize_text_for_hash(page.content_type),
        "final_url": normalize_text_for_hash(page.final_url),
        "h1": normalize_text_for_hash(page.h1),
        "meta_description": normalize_text_for_hash(page.meta_description),
        "normalized_url": normalize_text_for_hash(page.normalized_url),
        "page_bucket": normalize_text_for_hash(page.page_bucket),
        "page_type": normalize_text_for_hash(page.page_type),
        "robots_meta": normalize_text_for_hash(get_page_robots_meta(page)),
        "schema_types_json": sorted(
            normalize_text_for_hash(value)
            for value in get_page_schema_types(page)
            if normalize_text_for_hash(value)
        ),
        "status_code": int(page.status_code) if page.status_code is not None else None,
        "title": normalize_text_for_hash(page.title),
        "x_robots_tag": normalize_text_for_hash(get_page_x_robots_tag(page)),
    }
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def list_competitor_merge_candidates(
    session: Session,
    site_id: int,
    *,
    source_candidate_ids: Sequence[int] | None = None,
    limit: int = DEFAULT_CANDIDATE_LIMIT,
) -> list[CompetitorMergeCandidateGroup]:
    current_candidates = _load_current_semantic_candidates(session, site_id)
    if not current_candidates:
        return []
    limit = _normalize_limit(limit)
    source_id_filter = {int(candidate_id) for candidate_id in source_candidate_ids or []}
    source_candidates = [
        candidate
        for candidate in current_candidates
        if not source_id_filter or candidate.id in source_id_filter
    ]
    candidates_by_id = {candidate.id: candidate for candidate in current_candidates}
    term_index = _build_term_index(current_candidates)
    groups: list[CompetitorMergeCandidateGroup] = []

    for source in sorted(source_candidates, key=lambda item: item.id):
        suggestion_rows: list[CompetitorMergeCandidateSuggestion] = []
        target_ids = _candidate_ids_from_index(term_index, _candidate_normalized_terms(source), exclude_id=source.id)
        for target_id in target_ids:
            target = candidates_by_id.get(target_id)
            if target is None:
                continue
            if target.competitor_id == source.competitor_id:
                continue
            suggestion = _score_competitor_merge_pair(source, target)
            if suggestion is not None:
                suggestion_rows.append(suggestion)

        suggestion_rows.sort(
            key=lambda item: (
                -item.score,
                -item.shared_primary_tokens,
                -item.shared_terms,
                item.competitor_id,
                item.competitor_page_id,
                item.candidate_id,
            )
        )
        groups.append(
            CompetitorMergeCandidateGroup(
                source_candidate_id=source.id,
                source_competitor_id=source.competitor_id,
                source_competitor_page_id=source.competitor_page_id,
                source_raw_topic_key=source.raw_topic_key,
                source_raw_topic_label=source.raw_topic_label,
                candidates=suggestion_rows[:limit],
            )
        )
    return groups


def list_own_site_match_candidates(
    session: Session,
    site_id: int,
    active_crawl_id: int,
    *,
    source_candidate_ids: Sequence[int] | None = None,
    limit: int = DEFAULT_CANDIDATE_LIMIT,
    own_site_index: OwnSiteMatchIndex | None = None,
) -> list[OwnSiteMatchCandidateGroup]:
    own_site_index = own_site_index or build_own_site_match_index(
        session,
        site_id,
        active_crawl_id,
    )

    current_candidates = _load_current_semantic_candidates(session, site_id)
    if not current_candidates:
        return []

    limit = _normalize_limit(limit)
    source_id_filter = {int(candidate_id) for candidate_id in source_candidate_ids or []}
    source_candidates = [
        candidate
        for candidate in current_candidates
        if not source_id_filter or candidate.id in source_id_filter
    ]

    own_pages = own_site_index.own_pages
    if not own_pages:
        return [
            OwnSiteMatchCandidateGroup(
                source_candidate_id=source.id,
                source_competitor_id=source.competitor_id,
                source_competitor_page_id=source.competitor_page_id,
                source_raw_topic_key=source.raw_topic_key,
                source_raw_topic_label=source.raw_topic_label,
                candidates=[],
            )
            for source in sorted(source_candidates, key=lambda item: item.id)
        ]

    own_pages_by_id = own_site_index.own_pages_by_id
    own_term_index = own_site_index.own_term_index
    groups: list[OwnSiteMatchCandidateGroup] = []
    for source in sorted(source_candidates, key=lambda item: item.id):
        candidate_rows: list[OwnSiteMatchCandidateSuggestion] = []
        page_ids = _candidate_ids_from_index(own_term_index, _candidate_normalized_terms(source))
        for page_id in page_ids:
            own_page = own_pages_by_id.get(page_id)
            if own_page is None:
                continue
            suggestion = _score_own_match_pair(source, own_page)
            if suggestion is not None:
                candidate_rows.append(suggestion)

        candidate_rows.sort(
            key=lambda item: (-item.score, -item.priority_score, -item.impressions, item.page_id)
        )
        groups.append(
            OwnSiteMatchCandidateGroup(
                source_candidate_id=source.id,
                source_competitor_id=source.competitor_id,
                source_competitor_page_id=source.competitor_page_id,
                source_raw_topic_key=source.raw_topic_key,
                source_raw_topic_label=source.raw_topic_label,
                candidates=candidate_rows[:limit],
            )
        )
    return groups


def build_own_site_match_index(
    session: Session,
    site_id: int,
    active_crawl_id: int,
) -> OwnSiteMatchIndex:
    crawl_job = session.get(CrawlJob, active_crawl_id)
    if crawl_job is None or crawl_job.site_id != site_id:
        raise CompetitiveGapSemanticServiceError(
            f"Active crawl {active_crawl_id} not found for site {site_id}."
        )

    page_records = build_page_records(session, active_crawl_id)
    priority_service.apply_priority_metadata(page_records, gsc_date_range="last_28_days")
    own_profiles = competitive_gap_own_semantic_service.load_current_own_page_semantic_profiles(
        session,
        site_id,
        active_crawl_id,
        gsc_date_range="last_28_days",
        page_records=page_records,
    )
    own_profile_map = {int(row.page_id): dict(row.semantic_card_json or {}) for row in own_profiles}
    own_pages = competitive_gap_service._build_own_page_profiles(
        page_records,
        suffix=competitive_gap_service._resolve_gsc_suffix("last_28_days"),
        semantic_profile_map=own_profile_map,
    )
    own_pages_by_id = {page.page_id: page for page in own_pages}
    own_term_index = _build_own_page_term_index(own_pages)
    return OwnSiteMatchIndex(
        own_pages=own_pages,
        own_pages_by_id=own_pages_by_id,
        own_term_index=own_term_index,
    )


def _load_current_semantic_candidates(session: Session, site_id: int) -> list[SiteCompetitorSemanticCandidate]:
    return session.scalars(
        select(SiteCompetitorSemanticCandidate)
        .options(selectinload(SiteCompetitorSemanticCandidate.competitor_page))
        .where(
            SiteCompetitorSemanticCandidate.site_id == site_id,
            SiteCompetitorSemanticCandidate.current.is_(True),
        )
        .order_by(
            SiteCompetitorSemanticCandidate.id.asc(),
        )
    ).all()


def _build_term_index(
    candidates: Sequence[SiteCompetitorSemanticCandidate],
) -> dict[str, set[int]]:
    index: dict[str, set[int]] = defaultdict(set)
    for candidate in candidates:
        for term in _candidate_normalized_terms(candidate):
            normalized_term = normalize_text_for_hash(term).replace(" ", "-")
            if normalized_term:
                index[normalized_term].add(candidate.id)
    return index


def _build_own_page_term_index(own_pages: Sequence[Any]) -> dict[str, set[int]]:
    index: dict[str, set[int]] = defaultdict(set)
    for page in own_pages:
        for term in _expand_terms(page.topic_tokens):
            normalized_term = normalize_text_for_hash(term).replace(" ", "-")
            if normalized_term:
                index[normalized_term].add(page.page_id)
    return index


def _candidate_ids_from_index(
    index: dict[str, set[int]],
    terms: Sequence[str],
    *,
    exclude_id: int | None = None,
) -> list[int]:
    candidate_ids: set[int] = set()
    for term in terms:
        normalized_term = normalize_text_for_hash(term).replace(" ", "-")
        if not normalized_term:
            continue
        candidate_ids.update(index.get(normalized_term, set()))
    if exclude_id is not None:
        candidate_ids.discard(exclude_id)
    return sorted(candidate_ids)


def _score_competitor_merge_pair(
    source: SiteCompetitorSemanticCandidate,
    target: SiteCompetitorSemanticCandidate,
) -> CompetitorMergeCandidateSuggestion | None:
    source_primary = set(_candidate_primary_terms(source))
    target_primary = set(_candidate_primary_terms(target))
    shared_primary = len(source_primary & target_primary)

    source_terms = set(_candidate_normalized_terms(source))
    target_terms = set(_candidate_normalized_terms(target))
    source_nonprimary = source_terms - source_primary
    target_nonprimary = target_terms - target_primary
    shared_nonprimary = len(source_nonprimary & target_nonprimary)
    shared_terms = len(source_terms & target_terms)
    exact_topic_key_match = source.raw_topic_key == target.raw_topic_key
    same_page_type = source.page_type == target.page_type
    same_page_bucket = source.page_bucket == target.page_bucket
    quality_bonus = min(12, int(round((((source.quality_score or 0) + (target.quality_score or 0)) / 2) / 8)))
    score = (
        (40 if exact_topic_key_match else 0)
        + (18 * shared_primary)
        + (8 * shared_nonprimary)
        + (6 if same_page_type else 0)
        + (4 if same_page_bucket else 0)
        + quality_bonus
    )
    if score < MIN_COMPETITOR_MERGE_SCORE:
        return None
    return CompetitorMergeCandidateSuggestion(
        candidate_id=target.id,
        competitor_id=target.competitor_id,
        competitor_page_id=target.competitor_page_id,
        raw_topic_key=target.raw_topic_key,
        raw_topic_label=target.raw_topic_label,
        score=score,
        shared_primary_tokens=shared_primary,
        shared_nonprimary_terms=shared_nonprimary,
        shared_terms=shared_terms,
        exact_topic_key_match=exact_topic_key_match,
        same_page_type=same_page_type,
        same_page_bucket=same_page_bucket,
        quality_bonus=quality_bonus,
    )


def _score_own_match_pair(
    source: SiteCompetitorSemanticCandidate,
    own_page: Any,
) -> OwnSiteMatchCandidateSuggestion | None:
    competitor_page = source.competitor_page
    source_primary = set(_candidate_primary_terms(source))
    source_terms = set(_candidate_normalized_terms(source))
    source_anchor_tokens = _anchor_tokens(
        source.raw_topic_label,
        source.raw_topic_key,
        competitor_page.title if competitor_page is not None else None,
        competitor_page.h1 if competitor_page is not None else None,
        competitor_page.meta_description if competitor_page is not None else None,
    )
    own_tokens = set(_expand_terms(own_page.topic_tokens))
    own_anchor_tokens = _anchor_tokens(
        getattr(own_page, "title", None),
        getattr(own_page, "h1", None),
        getattr(own_page, "meta_description", None),
        getattr(own_page, "topic_key", None),
        str(getattr(own_page, "semantic_card", {}).get("primary_topic") or ""),
    )
    shared_primary = len(source_primary & own_tokens)
    source_nonprimary = source_terms - source_primary
    shared_nonprimary = len(source_nonprimary & own_tokens)
    shared_terms = len(source_terms & own_tokens)
    shared_anchor_terms = len(source_anchor_tokens & own_anchor_tokens)
    exact_topic_key_match = source.raw_topic_key == own_page.topic_key
    same_page_family = _page_family(source.page_type) == _page_family(own_page.page_type)
    same_intent = _candidate_dominant_intent(source) == str(getattr(own_page, "dominant_intent", "other") or "other")
    same_page_role = _candidate_page_role(source) == str(getattr(own_page, "page_role", "other") or "other")
    semantic_alignment_score = _semantic_alignment_ratio(source_terms | source_anchor_tokens, own_page)
    priority_bonus = min(15, max(0, int(own_page.priority_score or 0) // 5))
    impressions_bonus = min(10, max(0, int(own_page.impressions or 0) // 50))
    score = (
        (35 if exact_topic_key_match else 0)
        + (16 * shared_primary)
        + (10 * shared_anchor_terms)
        + (6 * shared_nonprimary)
        + (6 if same_page_family else 0)
        + (8 if same_intent else 0)
        + (6 if same_page_role else 0)
        + int(round(semantic_alignment_score * 18))
        + priority_bonus
        + impressions_bonus
    )
    if score < MIN_OWN_MATCH_SCORE:
        return None
    return OwnSiteMatchCandidateSuggestion(
        page_id=own_page.page_id,
        normalized_url=own_page.normalized_url,
        page_type=own_page.page_type,
        score=score,
        priority_score=int(own_page.priority_score or 0),
        impressions=int(own_page.impressions or 0),
        shared_primary_tokens=shared_primary,
        shared_nonprimary_terms=shared_nonprimary,
        shared_terms=shared_terms,
        shared_anchor_terms=shared_anchor_terms,
        exact_topic_key_match=exact_topic_key_match,
        same_page_family=same_page_family,
        same_intent=same_intent,
        same_page_role=same_page_role,
        semantic_alignment_score=round(semantic_alignment_score, 2),
        priority_bonus=priority_bonus,
        impressions_bonus=impressions_bonus,
    )


def _page_family(page_type: str | None) -> str:
    normalized = str(page_type or "other")
    if normalized in COMMERCIAL_PAGE_TYPES:
        return "commercial"
    if normalized in INFORMATIONAL_PAGE_TYPES:
        return "informational"
    if normalized in TRUST_PAGE_TYPES:
        return "trust"
    if normalized == "utility":
        return "utility"
    return "other"


def _anchor_tokens(*values: Any) -> set[str]:
    tokens: list[str] = []
    for value in values:
        for token in tokenize_topic_text(str(value or "")):
            normalized = normalize_text_for_hash(token).replace(" ", "-").strip("-")
            if not normalized or normalized in GENERIC_TOPIC_TOKENS:
                continue
            tokens.extend(_expand_hyphenated_token(normalized))
    return set(dedupe_preserve_order(tokens))


def _candidate_dominant_intent(candidate: SiteCompetitorSemanticCandidate) -> str:
    page_bucket = str(candidate.page_bucket or "other")
    page_family = _page_family(candidate.page_type)
    if page_bucket == "commercial" or page_family == "commercial":
        return "commercial"
    if page_family == "informational":
        return "informational"
    return "other"


def _candidate_page_role(candidate: SiteCompetitorSemanticCandidate) -> str:
    page_family = _page_family(candidate.page_type)
    if page_family == "commercial":
        return "money_page"
    if page_family == "informational":
        return "supporting_page"
    if page_family == "trust":
        return "trust_page"
    if page_family == "utility":
        return "utility_page"
    return "other"


def _semantic_alignment_ratio(source_terms: set[str], own_page: Any) -> float:
    own_terms = set(_expand_terms(getattr(own_page, "topic_tokens", set())))
    own_terms.update(
        _anchor_tokens(
            getattr(own_page, "title", None),
            getattr(own_page, "h1", None),
            getattr(own_page, "meta_description", None),
            getattr(own_page, "topic_key", None),
            str(getattr(own_page, "semantic_card", {}).get("primary_topic") or ""),
        )
    )
    if not source_terms or not own_terms:
        return 0.0
    return len(source_terms & own_terms) / max(1, len(source_terms | own_terms))


def _find_candidate_for_hash(
    candidates: Sequence[SiteCompetitorSemanticCandidate],
    semantic_input_hash: str,
) -> SiteCompetitorSemanticCandidate | None:
    for candidate in candidates:
        if candidate.semantic_input_hash == semantic_input_hash:
            return candidate
    return None


def _load_latest_valid_extractions_by_page_id(
    session: Session,
    *,
    competitor_id: int,
    page_ids: Sequence[int],
) -> dict[int, SiteCompetitorPageExtraction]:
    if not page_ids:
        return {}
    rows = session.scalars(
        select(SiteCompetitorPageExtraction)
        .where(
            SiteCompetitorPageExtraction.competitor_id == competitor_id,
            SiteCompetitorPageExtraction.competitor_page_id.in_(list(page_ids)),
        )
        .order_by(
            SiteCompetitorPageExtraction.competitor_page_id.asc(),
            SiteCompetitorPageExtraction.extracted_at.desc(),
            SiteCompetitorPageExtraction.id.desc(),
        )
    ).all()
    latest_by_page_id: dict[int, SiteCompetitorPageExtraction] = {}
    for row in rows:
        page_id = int(row.competitor_page_id)
        if page_id in latest_by_page_id:
            continue
        latest_by_page_id[page_id] = row
    return latest_by_page_id


def _resolve_page_semantic_card(
    page: SiteCompetitorPage,
    extraction: SiteCompetitorPageExtraction | None,
) -> dict[str, Any] | None:
    if extraction is None:
        return None
    if page.content_text_hash != extraction.content_hash_at_extraction:
        return None
    if not extraction.semantic_card_json:
        return None
    return dict(extraction.semantic_card_json)


def _retire_current_candidates(
    candidates: Sequence[SiteCompetitorSemanticCandidate],
    *,
    keep_hash: str | None,
    touched_at: Any,
) -> int:
    retired_count = 0
    for candidate in candidates:
        if not candidate.current:
            continue
        if keep_hash is not None and candidate.semantic_input_hash == keep_hash:
            continue
        candidate.current = False
        candidate.updated_at = touched_at
        retired_count += 1
    return retired_count


def _build_weighted_tokens(
    page: SiteCompetitorPage,
    *,
    path_tokens: Sequence[str],
) -> tuple[dict[str, float], dict[str, int]]:
    weights: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    order = 0

    for index, token in enumerate(path_tokens[: len(PATH_TOKEN_WEIGHTS)]):
        weights[token] = weights.get(token, 0.0) + PATH_TOKEN_WEIGHTS[index]
        if token not in first_seen:
            first_seen[token] = order
            order += 1

    for field_value, weight in ((page.title, TITLE_TOKEN_WEIGHT), (page.h1, H1_TOKEN_WEIGHT)):
        for token in dedupe_preserve_order(_tokenize_topic_value(field_value)):
            weights[token] = weights.get(token, 0.0) + weight
            if token not in first_seen:
                first_seen[token] = order
                order += 1

    return weights, first_seen


def _extract_path_tokens(url: str) -> list[str]:
    parsed = urlsplit(str(url or ""))
    path = unquote(parsed.path or "/")
    path_tokens: list[str] = []
    for raw_token in tokenize_topic_text(path.replace("/", " ")):
        for token in _expand_hyphenated_token(raw_token):
            if token in GENERIC_TOPIC_TOKENS:
                continue
            path_tokens.append(token)
    path_tokens = dedupe_preserve_order(path_tokens)
    return path_tokens[:PRIMARY_TOKEN_LIMIT]


def _tokenize_topic_value(value: Any) -> list[str]:
    return [
        token
        for token in dedupe_preserve_order(tokenize_topic_text(str(value or "")))
        if token not in GENERIC_TOPIC_TOKENS
    ]


def _build_raw_topic_label(page: SiteCompetitorPage, ranked_tokens: Sequence[str]) -> str | None:
    h1 = collapse_whitespace(page.h1)
    if h1 and len(h1.split()) <= 7:
        return h1

    title = collapse_whitespace(page.title)
    if title and len(title.split()) <= 9:
        return title

    label_tokens = list(ranked_tokens[:2])
    if not label_tokens:
        return None
    return " ".join(token.replace("-", " ").title() for token in label_tokens)


def _build_quality_score(
    page: SiteCompetitorPage,
    *,
    has_path_topic: bool,
    quality_signals: TopicQualitySignals | None = None,
) -> int:
    score = 12
    if collapse_whitespace(page.title):
        score += 16
    if collapse_whitespace(page.h1):
        score += 18
    if collapse_whitespace(page.meta_description):
        score += 8
    if has_path_topic:
        score += 8
    word_count = get_page_word_count(page)
    if word_count >= 200:
        score += 10
    elif word_count >= 80:
        score += 5
    if get_page_schema_present(page):
        score += 6
    if quality_signals is not None:
        score += int(round(quality_signals.title_h1_alignment_score * 18))
        score += int(round(quality_signals.meta_support_score * 12))
        score += int(round((1.0 - quality_signals.body_conflict_score) * 8))
        score += int(round((1.0 - quality_signals.boilerplate_contamination_score) * 8))
        score += int(round(quality_signals.dominant_topic_strength * 20))
        if quality_signals.weak_evidence_flag:
            score -= 20
    return min(100, score)


def _normalize_limit(limit: int) -> int:
    try:
        normalized = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_CANDIDATE_LIMIT
    return max(1, min(DEFAULT_CANDIDATE_LIMIT, normalized))


def _expand_terms(values: Iterable[str]) -> list[str]:
    expanded: list[str] = []
    for value in values:
        expanded.extend(_expand_hyphenated_token(value))
    return dedupe_preserve_order(expanded)


def _expand_hyphenated_token(token: str) -> list[str]:
    cleaned = normalize_text_for_hash(token).replace(" ", "-").strip("-")
    if not cleaned:
        return []
    if "-" not in cleaned:
        return [cleaned]
    parts = [part for part in cleaned.split("-") if len(part) >= 3]
    return parts or [cleaned]


def _candidate_normalized_terms(candidate: SiteCompetitorSemanticCandidate) -> list[str]:
    normalized_terms = dedupe_preserve_order(
        normalize_text_for_hash(term).replace(" ", "-")
        for term in (candidate.normalized_terms_json or [])
        if normalize_text_for_hash(term)
    )
    if normalized_terms:
        return normalized_terms
    return _candidate_primary_terms(candidate)


def _candidate_primary_terms(candidate: SiteCompetitorSemanticCandidate) -> list[str]:
    values = [
        str(candidate.raw_topic_key or "").replace("-", " "),
        str(candidate.raw_topic_label or ""),
    ]
    tokens = dedupe_preserve_order(
        token
        for value in values
        for token in _tokenize_topic_value(value)
    )
    primary_terms = _expand_terms(tokens)[:PRIMARY_TOKEN_LIMIT]
    if primary_terms:
        return primary_terms
    return [
        normalize_text_for_hash(term).replace(" ", "-")
        for term in (candidate.normalized_terms_json or [])[:PRIMARY_TOKEN_LIMIT]
        if normalize_text_for_hash(term)
    ]


def _candidate_secondary_terms(candidate: SiteCompetitorSemanticCandidate) -> list[str]:
    primary_terms = set(_candidate_primary_terms(candidate))
    return [
        term
        for term in _candidate_normalized_terms(candidate)
        if term not in primary_terms
    ]
