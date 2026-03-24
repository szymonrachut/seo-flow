from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.text_processing import normalize_text_for_hash
from app.db.models import SiteCompetitiveGapClusterState


def _cluster_state_scope_predicates(*, site_id: int, active_crawl_id: int | None) -> list[Any]:
    predicates: list[Any] = [SiteCompetitiveGapClusterState.site_id == site_id]
    if active_crawl_id is None:
        predicates.append(SiteCompetitiveGapClusterState.active_crawl_id.is_(None))
    else:
        predicates.append(SiteCompetitiveGapClusterState.active_crawl_id == active_crawl_id)
    return predicates


def load_cluster_state_map(
    session: Session,
    *,
    site_id: int,
    active_crawl_id: int | None,
    semantic_cluster_keys: Sequence[str],
) -> dict[str, SiteCompetitiveGapClusterState]:
    if not semantic_cluster_keys:
        return {}
    rows = session.scalars(
        select(SiteCompetitiveGapClusterState)
        .where(
            *_cluster_state_scope_predicates(site_id=site_id, active_crawl_id=active_crawl_id),
            SiteCompetitiveGapClusterState.semantic_cluster_key.in_(list(semantic_cluster_keys)),
        )
        .order_by(SiteCompetitiveGapClusterState.id.asc())
    ).all()
    state_by_key: dict[str, SiteCompetitiveGapClusterState] = {}
    for row in rows:
        state_by_key.setdefault(str(row.semantic_cluster_key), row)
    return state_by_key


def build_cluster_state_hash(*, cluster_summary: dict[str, Any]) -> str:
    return _hash_payload(cluster_summary)


def build_coverage_state_hash(
    *,
    active_crawl_id: int | None,
    related_own_pages: Sequence[Any],
) -> str:
    payload = {
        "active_crawl_id": active_crawl_id,
        "related_own_pages": [
            {
                "page_id": int(getattr(page, "page_id", 0) or 0),
                "semantic_input_hash": normalize_text_for_hash(getattr(page, "semantic_input_hash", None)),
                "topic_key": normalize_text_for_hash(getattr(page, "topic_key", None)),
                "page_type": normalize_text_for_hash(getattr(page, "page_type", None)),
                "page_bucket": normalize_text_for_hash(getattr(page, "page_bucket", None)),
            }
            for page in sorted(related_own_pages, key=lambda item: int(getattr(item, "page_id", 0) or 0))
        ],
    }
    return _hash_payload(payload)


def upsert_cluster_state(
    session: Session,
    *,
    site_id: int,
    active_crawl_id: int | None,
    semantic_cluster_key: str,
    topic_key: str | None,
    canonical_topic_label: str | None,
    source_candidate_ids: Sequence[int],
    competitor_ids: Sequence[int],
    cluster_state_hash: str,
    coverage_state_hash: str | None,
    cluster_summary_json: dict[str, Any],
    coverage_state_json: dict[str, Any],
    existing_row: SiteCompetitiveGapClusterState | None = None,
) -> SiteCompetitiveGapClusterState:
    row = existing_row
    if row is None:
        row = session.scalars(
            select(SiteCompetitiveGapClusterState)
            .where(
                *_cluster_state_scope_predicates(site_id=site_id, active_crawl_id=active_crawl_id),
                SiteCompetitiveGapClusterState.semantic_cluster_key == semantic_cluster_key,
            )
            .limit(1)
        ).first()
    if row is None:
        row = SiteCompetitiveGapClusterState(
            site_id=site_id,
            active_crawl_id=active_crawl_id,
            semantic_cluster_key=semantic_cluster_key,
            cluster_state_hash=cluster_state_hash,
            coverage_state_hash=coverage_state_hash,
        )
        session.add(row)
    row.topic_key = topic_key
    row.canonical_topic_label = canonical_topic_label
    row.source_candidate_ids_json = [int(value) for value in source_candidate_ids]
    row.competitor_ids_json = [int(value) for value in competitor_ids]
    row.cluster_state_hash = cluster_state_hash
    row.coverage_state_hash = coverage_state_hash
    row.cluster_summary_json = dict(cluster_summary_json or {})
    row.coverage_state_json = dict(coverage_state_json or {})
    return row


def normalize_cached_coverage_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(payload or {})
    normalized["coverage_best_own_urls"] = [
        str(value)
        for value in (normalized.get("coverage_best_own_urls") or [])
        if value
    ]
    normalized["mismatch_notes"] = [
        str(value)
        for value in (normalized.get("mismatch_notes") or [])
        if value
    ]
    normalized["matched_own_page_ids"] = [
        int(value)
        for value in (normalized.get("matched_own_page_ids") or [])
        if value is not None
    ]
    normalized["coverage_debug"] = dict(normalized.get("coverage_debug") or {})
    return normalized


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
