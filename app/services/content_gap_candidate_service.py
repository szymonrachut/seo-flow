from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.text_processing import collapse_whitespace
from app.db.models import SiteContentGapCandidate, SiteCompetitorSemanticCandidate, utcnow
from app.services import competitive_gap_service, site_service


CONTENT_GAP_CANDIDATE_GENERATION_VERSION = "content-gap-candidates-v1"
CONTENT_GAP_CANDIDATE_RULES_VERSION = "competitive-gap-legacy-read-model-v1"
DEFAULT_GSC_DATE_RANGE = "last_28_days"
ACTIVE_CANDIDATE_STATUS = "active"
SUPERSEDED_CANDIDATE_STATUS = "superseded"
INVALIDATED_CANDIDATE_STATUS = "invalidated"


class ContentGapCandidateServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class ContentGapCandidateRefreshSummary:
    basis_crawl_job_id: int | None
    generated_count: int = 0
    reused_count: int = 0
    superseded_count: int = 0
    invalidated_count: int = 0
    skipped_reason: str | None = None


def refresh_site_content_gap_candidates(
    session: Session,
    site_id: int,
    *,
    basis_crawl_job_id: int | None = None,
    generated_at: datetime | None = None,
) -> ContentGapCandidateRefreshSummary:
    if basis_crawl_job_id is None:
        workspace_context = site_service.resolve_site_workspace_context(
            session,
            site_id,
            active_crawl_id=None,
        )
        active_crawl = workspace_context["active_crawl"]
        if active_crawl is None:
            return ContentGapCandidateRefreshSummary(
                basis_crawl_job_id=None,
                skipped_reason="no_active_crawl",
            )
        basis_crawl_job_id = int(active_crawl.id)

    generated_at = generated_at or utcnow()
    rows = _build_raw_candidate_rows(
        session,
        site_id,
        basis_crawl_job_id=basis_crawl_job_id,
    )
    existing_current_candidates = session.scalars(
        select(SiteContentGapCandidate)
        .where(
            SiteContentGapCandidate.site_id == site_id,
            SiteContentGapCandidate.basis_crawl_job_id == basis_crawl_job_id,
            SiteContentGapCandidate.current.is_(True),
        )
        .order_by(SiteContentGapCandidate.id.asc())
    ).all()
    existing_by_key = {row.candidate_key: row for row in existing_current_candidates}
    seen_candidate_keys: set[str] = set()
    summary = ContentGapCandidateRefreshSummary(basis_crawl_job_id=basis_crawl_job_id)

    for row in rows:
        candidate_key = str(row["candidate_key"])
        seen_candidate_keys.add(candidate_key)
        existing = existing_by_key.get(candidate_key)
        if existing is not None and existing.candidate_input_hash == row["candidate_input_hash"]:
            existing.last_generated_at = generated_at
            existing.updated_at = generated_at
            summary.reused_count += 1
            continue

        if existing is not None:
            existing.status = SUPERSEDED_CANDIDATE_STATUS
            existing.current = False
            existing.updated_at = generated_at
            summary.superseded_count += 1

        session.add(
            SiteContentGapCandidate(
                site_id=site_id,
                basis_crawl_job_id=basis_crawl_job_id,
                candidate_key=candidate_key,
                candidate_input_hash=str(row["candidate_input_hash"]),
                status=ACTIVE_CANDIDATE_STATUS,
                current=True,
                generation_version=CONTENT_GAP_CANDIDATE_GENERATION_VERSION,
                rules_version=CONTENT_GAP_CANDIDATE_RULES_VERSION,
                normalized_topic_key=str(row["normalized_topic_key"]),
                original_topic_label=str(row["original_topic_label"]),
                original_phrase=str(row["original_phrase"]),
                gap_type=str(row["gap_type"]),
                source_cluster_key=str(row["source_cluster_key"]),
                source_cluster_hash=str(row["source_cluster_hash"]),
                source_competitor_ids_json=list(row["source_competitor_ids_json"]),
                source_competitor_page_ids_json=list(row["source_competitor_page_ids_json"]),
                competitor_count=int(row["competitor_count"]),
                own_coverage_hint=str(row["own_coverage_hint"]),
                deterministic_priority_score=int(row["deterministic_priority_score"]),
                rationale_summary=str(row["rationale_summary"]),
                signals_json=dict(row["signals_json"]),
                review_needed=True,
                review_visibility="visible",
                first_generated_at=generated_at,
                last_generated_at=generated_at,
                created_at=generated_at,
                updated_at=generated_at,
            )
        )
        summary.generated_count += 1

    for existing in existing_current_candidates:
        if existing.candidate_key in seen_candidate_keys:
            continue
        existing.status = INVALIDATED_CANDIDATE_STATUS
        existing.current = False
        existing.updated_at = generated_at
        summary.invalidated_count += 1

    session.flush()
    return summary


def _build_raw_candidate_rows(
    session: Session,
    site_id: int,
    *,
    basis_crawl_job_id: int,
) -> list[dict[str, Any]]:
    payload = competitive_gap_service._build_legacy_competitive_gap_read_model(
        session,
        site_id,
        active_crawl_id=basis_crawl_job_id,
        gsc_date_range=DEFAULT_GSC_DATE_RANGE,
    )
    source_candidate_ids = sorted(
        {
            int(candidate_id)
            for row in payload.get("items", [])
            for candidate_id in (row.get("signals", {}).get("semantic", {}).get("source_candidate_ids") or [])
            if candidate_id is not None
        }
    )
    semantic_candidates_by_id = _load_semantic_candidates_by_id(session, source_candidate_ids)
    return [
        _build_candidate_row(
            row,
            semantic_candidates_by_id=semantic_candidates_by_id,
        )
        for row in payload.get("items", [])
    ]


def _load_semantic_candidates_by_id(
    session: Session,
    candidate_ids: list[int],
) -> dict[int, SiteCompetitorSemanticCandidate]:
    if not candidate_ids:
        return {}
    rows = session.scalars(
        select(SiteCompetitorSemanticCandidate)
        .where(SiteCompetitorSemanticCandidate.id.in_(candidate_ids))
        .order_by(SiteCompetitorSemanticCandidate.id.asc())
    ).all()
    return {int(row.id): row for row in rows}


def _build_candidate_row(
    row: dict[str, Any],
    *,
    semantic_candidates_by_id: dict[int, SiteCompetitorSemanticCandidate],
) -> dict[str, Any]:
    semantic_signals = dict((row.get("signals") or {}).get("semantic") or {})
    source_candidate_ids = [
        int(candidate_id)
        for candidate_id in (semantic_signals.get("source_candidate_ids") or [])
        if candidate_id is not None
    ]
    source_competitor_page_ids = sorted(
        {
            int(candidate.competitor_page_id)
            for candidate_id in source_candidate_ids
            for candidate in [semantic_candidates_by_id.get(candidate_id)]
            if candidate is not None and candidate.competitor_page_id is not None
        }
    )
    source_competitor_ids = sorted(
        {
            int(value)
            for value in (row.get("competitor_ids") or semantic_signals.get("source_competitor_ids") or [])
            if value is not None
        }
    )
    normalized_topic_key = str(
        row.get("topic_key")
        or semantic_signals.get("canonical_topic_label")
        or row.get("topic_label")
        or "topic"
    )
    original_topic_label = collapse_whitespace(
        row.get("topic_label")
        or row.get("canonical_topic_label")
        or normalized_topic_key
    ) or normalized_topic_key
    original_phrase = original_topic_label
    source_cluster_key = str(row.get("semantic_cluster_key") or row.get("gap_key") or normalized_topic_key)
    source_cluster_hash = _hash_payload(
        {
            "source_cluster_key": source_cluster_key,
            "normalized_topic_key": normalized_topic_key,
            "gap_type": str(row.get("gap_type") or "NEW_TOPIC"),
            "source_competitor_ids": source_competitor_ids,
            "source_competitor_page_ids": source_competitor_page_ids,
        }
    )
    signals_json = _build_candidate_signals_payload(
        row,
        source_candidate_ids=source_candidate_ids,
        source_competitor_page_ids=source_competitor_page_ids,
    )
    candidate_input_hash = _hash_payload(
        {
            "candidate_key": str(row.get("gap_key") or source_cluster_key),
            "normalized_topic_key": normalized_topic_key,
            "original_topic_label": original_topic_label,
            "original_phrase": original_phrase,
            "gap_type": str(row.get("gap_type") or "NEW_TOPIC"),
            "source_cluster_key": source_cluster_key,
            "source_cluster_hash": source_cluster_hash,
            "source_competitor_ids": source_competitor_ids,
            "source_competitor_page_ids": source_competitor_page_ids,
            "competitor_count": int(row.get("competitor_count") or 0),
            "own_coverage_hint": _own_coverage_hint_from_row(row),
            "deterministic_priority_score": int(row.get("priority_score") or 0),
            "rationale_summary": str(row.get("rationale") or ""),
            "signals_json": signals_json,
        }
    )
    return {
        "candidate_key": str(row.get("gap_key") or source_cluster_key),
        "candidate_input_hash": candidate_input_hash,
        "normalized_topic_key": normalized_topic_key,
        "original_topic_label": original_topic_label,
        "original_phrase": original_phrase,
        "gap_type": str(row.get("gap_type") or "NEW_TOPIC"),
        "source_cluster_key": source_cluster_key,
        "source_cluster_hash": source_cluster_hash,
        "source_competitor_ids_json": source_competitor_ids,
        "source_competitor_page_ids_json": source_competitor_page_ids,
        "competitor_count": int(row.get("competitor_count") or 0),
        "own_coverage_hint": _own_coverage_hint_from_row(row),
        "deterministic_priority_score": int(row.get("priority_score") or 0),
        "rationale_summary": str(row.get("rationale") or ""),
        "signals_json": signals_json,
    }


def _build_candidate_signals_payload(
    row: dict[str, Any],
    *,
    source_candidate_ids: list[int],
    source_competitor_page_ids: list[int],
) -> dict[str, Any]:
    signals = dict(row.get("signals") or {})
    semantic_signals = dict(signals.get("semantic") or {})
    semantic_signals["source_candidate_ids"] = source_candidate_ids
    semantic_signals["source_competitor_page_ids"] = source_competitor_page_ids
    semantic_signals["candidate_source_mode"] = "legacy"
    signals["semantic"] = semantic_signals
    return signals


def _own_coverage_hint_from_row(row: dict[str, Any]) -> str:
    status = str(row.get("own_match_status") or "")
    if status in {"exact_match", "semantic_match"}:
        return "existing_strong"
    if status == "partial_coverage":
        return "partial"
    return "none"


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
