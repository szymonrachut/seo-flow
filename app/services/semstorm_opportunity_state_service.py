from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.text_processing import normalize_text_for_hash
from app.db.models import SiteSemstormOpportunityState, SiteSemstormPromotedItem, utcnow


SemstormOpportunityStateStatus = Literal["new", "accepted", "dismissed", "promoted"]
SemstormPromotionStatus = Literal["active", "archived"]


def normalize_semstorm_keyword(value: str | None) -> str:
    return normalize_text_for_hash(value)


def build_semstorm_opportunity_key(site_id: int, normalized_keyword: str) -> str:
    payload = json.dumps(
        {
            "site_id": int(site_id),
            "normalized_keyword": str(normalized_keyword or ""),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:24]
    return f"semstorm:{digest}"


def load_opportunity_states(
    session: Session,
    site_id: int,
    normalized_keywords: Sequence[str],
) -> dict[str, SiteSemstormOpportunityState]:
    normalized = _dedupe_normalized_keywords(normalized_keywords)
    if not normalized:
        return {}
    rows = session.scalars(
        select(SiteSemstormOpportunityState).where(
            SiteSemstormOpportunityState.site_id == site_id,
            SiteSemstormOpportunityState.normalized_keyword.in_(normalized),
        )
    ).all()
    return {str(row.normalized_keyword): row for row in rows}


def load_promoted_items(
    session: Session,
    site_id: int,
    normalized_keywords: Sequence[str],
) -> dict[str, SiteSemstormPromotedItem]:
    normalized = _dedupe_normalized_keywords(normalized_keywords)
    if not normalized:
        return {}
    rows = session.scalars(
        select(SiteSemstormPromotedItem).where(
            SiteSemstormPromotedItem.site_id == site_id,
            SiteSemstormPromotedItem.normalized_keyword.in_(normalized),
        )
    ).all()
    return {str(row.normalized_keyword): row for row in rows}


def upsert_opportunity_state(
    session: Session,
    *,
    site_id: int,
    normalized_keyword: str,
    state_status: SemstormOpportunityStateStatus,
    source_run_id: int | None,
    note: str | None = None,
) -> SiteSemstormOpportunityState:
    normalized = normalize_semstorm_keyword(normalized_keyword)
    if not normalized:
        raise ValueError("normalized_keyword is required.")

    state = session.scalar(
        select(SiteSemstormOpportunityState).where(
            SiteSemstormOpportunityState.site_id == site_id,
            SiteSemstormOpportunityState.normalized_keyword == normalized,
        )
    )
    now = utcnow()
    clean_note = _normalize_note(note)
    if state is None:
        state = SiteSemstormOpportunityState(
            site_id=site_id,
            opportunity_key=build_semstorm_opportunity_key(site_id, normalized),
            source_run_id=source_run_id,
            normalized_keyword=normalized[:512],
            state_status=state_status,
            note=clean_note,
            created_at=now,
            updated_at=now,
        )
        session.add(state)
    else:
        state.opportunity_key = build_semstorm_opportunity_key(site_id, normalized)
        state.source_run_id = source_run_id
        state.state_status = state_status
        state.note = clean_note
        state.updated_at = now

    if state_status == "accepted":
        state.accepted_at = now
    elif state_status == "dismissed":
        state.dismissed_at = now
    elif state_status == "promoted":
        state.promoted_at = now

    return state


def create_promoted_item(
    session: Session,
    *,
    site_id: int,
    source_run_id: int,
    keyword: str,
    normalized_keyword: str,
    bucket: str,
    decision_type: str,
    opportunity_score_v2: int,
    coverage_status: str,
    best_match_page_url: str | None,
    gsc_signal_status: str,
    source_payload_json: dict[str, Any] | None,
) -> tuple[SiteSemstormPromotedItem, bool]:
    normalized = normalize_semstorm_keyword(normalized_keyword)
    if not normalized:
        raise ValueError("normalized_keyword is required.")

    existing = session.scalar(
        select(SiteSemstormPromotedItem).where(
            SiteSemstormPromotedItem.site_id == site_id,
            SiteSemstormPromotedItem.normalized_keyword == normalized,
        )
    )
    if existing is not None:
        return existing, False

    now = utcnow()
    promoted_item = SiteSemstormPromotedItem(
        site_id=site_id,
        opportunity_key=build_semstorm_opportunity_key(site_id, normalized),
        source_run_id=source_run_id,
        keyword=str(keyword or "")[:512],
        normalized_keyword=normalized[:512],
        bucket=str(bucket or "watchlist")[:32],
        decision_type=str(decision_type or "monitor_only")[:32],
        opportunity_score_v2=int(opportunity_score_v2 or 0),
        coverage_status=str(coverage_status or "missing")[:32],
        best_match_page_url=_string_or_none(best_match_page_url),
        gsc_signal_status=str(gsc_signal_status or "none")[:32],
        source_payload_json=dict(source_payload_json or {}),
        promotion_status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(promoted_item)
    return promoted_item, True


def serialize_opportunity_state(
    state: SiteSemstormOpportunityState | None,
) -> dict[str, Any]:
    if state is None:
        return {
            "state_status": "new",
            "state_note": None,
        }
    return {
        "state_status": state.state_status or "new",
        "state_note": state.note,
    }


def serialize_promoted_item(
    item: SiteSemstormPromotedItem,
) -> dict[str, Any]:
    return {
        "id": item.id,
        "site_id": item.site_id,
        "opportunity_key": item.opportunity_key,
        "source_run_id": item.source_run_id,
        "keyword": item.keyword,
        "normalized_keyword": item.normalized_keyword,
        "bucket": item.bucket,
        "decision_type": item.decision_type,
        "opportunity_score_v2": int(item.opportunity_score_v2 or 0),
        "coverage_status": item.coverage_status,
        "best_match_page_url": item.best_match_page_url,
        "gsc_signal_status": item.gsc_signal_status,
        "promotion_status": item.promotion_status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _dedupe_normalized_keywords(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_semstorm_keyword(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _normalize_note(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
