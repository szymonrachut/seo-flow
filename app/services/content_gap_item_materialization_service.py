from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SiteContentGapCandidate, SiteContentGapItem, SiteContentGapReviewRun, utcnow


logger = logging.getLogger(__name__)

ACTIVE_ITEM_STATUS = "active"
SUPERSEDED_ITEM_STATUS = "superseded"
VALID_DECISION_ACTIONS = {"keep", "remove", "merge", "rewrite"}
VISIBLE_DISPLAY_STATE = "visible"
HIDDEN_REMOVED_DISPLAY_STATE = "hidden_removed"
HIDDEN_MERGED_CHILD_DISPLAY_STATE = "hidden_merged_child"


class ContentGapItemMaterializationServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "content_gap_item_materialization_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class SanitizedContentGapDecision:
    source_candidate_id: int
    decision_action: str
    decision_reason_text: str
    fit_score: float
    confidence: float
    reviewed_phrase: str | None = None
    reviewed_topic_label: str | None = None
    reviewed_normalized_topic_key: str | None = None
    reviewed_gap_type: str | None = None
    decision_reason_code: str | None = None
    merge_target_candidate_key: str | None = None
    merge_target_phrase: str | None = None
    remove_reason_code: str | None = None
    remove_reason_text: str | None = None
    rewrite_reason_text: str | None = None
    review_group_key: str | None = None
    group_primary: bool | None = None
    own_site_alignment_json: dict[str, Any] | None = None
    gsc_support_json: dict[str, Any] | None = None
    competitor_evidence_json: dict[str, Any] | None = None
    raw_decision_json: dict[str, Any] | None = None
    response_hash: str | None = None
    sort_score: float | None = None


@dataclass(slots=True)
class ContentGapItemMaterializationSummary:
    review_run_id: int
    created_count: int = 0
    superseded_count: int = 0
    visible_count: int = 0
    hidden_removed_count: int = 0
    hidden_merged_child_count: int = 0


def materialize_review_items(
    session: Session,
    *,
    site_id: int,
    review_run_id: int,
    decisions: list[SanitizedContentGapDecision],
) -> ContentGapItemMaterializationSummary:
    review_run = _load_review_run_or_raise(session, site_id=site_id, review_run_id=review_run_id)
    candidates_by_id = _load_scope_candidates_for_run(session, review_run=review_run)
    _validate_decisions(decisions, review_run=review_run, candidates_by_id=candidates_by_id)

    now = utcnow()
    source_candidate_ids = sorted(candidates_by_id)
    existing_active_items = session.scalars(
        select(SiteContentGapItem)
        .where(
            SiteContentGapItem.site_id == site_id,
            SiteContentGapItem.basis_crawl_job_id == review_run.basis_crawl_job_id,
            SiteContentGapItem.source_candidate_id.in_(source_candidate_ids),
            SiteContentGapItem.item_status == ACTIVE_ITEM_STATUS,
        )
        .order_by(SiteContentGapItem.id.asc())
    ).all()
    summary = ContentGapItemMaterializationSummary(review_run_id=review_run_id)
    for item in existing_active_items:
        item.item_status = SUPERSEDED_ITEM_STATUS
        item.updated_at = now
        summary.superseded_count += 1

    for decision in decisions:
        candidate = candidates_by_id[int(decision.source_candidate_id)]
        display_state = _resolve_display_state(decision)
        item = SiteContentGapItem(
            site_id=site_id,
            basis_crawl_job_id=review_run.basis_crawl_job_id,
            review_run_id=review_run.id,
            source_candidate_id=candidate.id,
            source_candidate_key=candidate.candidate_key,
            source_candidate_input_hash=candidate.candidate_input_hash,
            item_status=ACTIVE_ITEM_STATUS,
            decision_action=decision.decision_action,
            display_state=display_state,
            review_group_key=_resolve_review_group_key(decision, candidate),
            group_primary=_resolve_group_primary(decision),
            original_phrase=candidate.original_phrase,
            original_topic_label=candidate.original_topic_label,
            reviewed_phrase=_trim_or_none(decision.reviewed_phrase, max_length=255),
            reviewed_topic_label=_trim_or_none(decision.reviewed_topic_label, max_length=255),
            reviewed_normalized_topic_key=_trim_or_none(decision.reviewed_normalized_topic_key, max_length=255),
            reviewed_gap_type=_trim_or_none(decision.reviewed_gap_type, max_length=64),
            fit_score=float(decision.fit_score),
            confidence=float(decision.confidence),
            decision_reason_code=_trim_or_none(decision.decision_reason_code, max_length=64),
            decision_reason_text=_trim_text(decision.decision_reason_text),
            merge_target_candidate_key=_trim_or_none(decision.merge_target_candidate_key, max_length=96),
            merge_target_phrase=_trim_or_none(decision.merge_target_phrase, max_length=255),
            remove_reason_code=_trim_or_none(decision.remove_reason_code, max_length=64),
            remove_reason_text=_trim_text_or_none(decision.remove_reason_text),
            rewrite_reason_text=_trim_text_or_none(decision.rewrite_reason_text),
            own_site_alignment_json=_sanitize_optional_json(decision.own_site_alignment_json),
            gsc_support_json=_sanitize_optional_json(decision.gsc_support_json),
            competitor_evidence_json=_sanitize_optional_json(decision.competitor_evidence_json),
            llm_provider=review_run.llm_provider,
            llm_model=review_run.llm_model,
            prompt_version=review_run.prompt_version,
            schema_version=review_run.schema_version,
            output_language=review_run.output_language,
            response_hash=_resolve_response_hash(decision),
            raw_decision_json=_build_sanitized_raw_decision_json(decision),
            visible_in_results=display_state == VISIBLE_DISPLAY_STATE,
            sort_score=float(decision.sort_score) if decision.sort_score is not None else None,
            created_at=now,
            updated_at=now,
        )
        session.add(item)
        summary.created_count += 1
        if display_state == VISIBLE_DISPLAY_STATE:
            summary.visible_count += 1
        elif display_state == HIDDEN_REMOVED_DISPLAY_STATE:
            summary.hidden_removed_count += 1
        else:
            summary.hidden_merged_child_count += 1

    session.flush()
    logger.info(
        "content_gap_items.materialized site_id=%s review_run_id=%s created=%s superseded=%s visible=%s hidden_removed=%s hidden_merged_child=%s",
        site_id,
        review_run_id,
        summary.created_count,
        summary.superseded_count,
        summary.visible_count,
        summary.hidden_removed_count,
        summary.hidden_merged_child_count,
    )
    return summary


def _load_review_run_or_raise(session: Session, *, site_id: int, review_run_id: int) -> SiteContentGapReviewRun:
    review_run = session.scalar(
        select(SiteContentGapReviewRun)
        .where(
            SiteContentGapReviewRun.id == review_run_id,
            SiteContentGapReviewRun.site_id == site_id,
        )
        .limit(1)
    )
    if review_run is None:
        raise ContentGapItemMaterializationServiceError(
            f"Content Gap review run {review_run_id} not found for site {site_id}.",
            code="review_run_not_found",
        )
    return review_run


def _load_scope_candidates_for_run(
    session: Session,
    *,
    review_run: SiteContentGapReviewRun,
) -> dict[int, SiteContentGapCandidate]:
    selected_candidate_ids = sorted({int(candidate_id) for candidate_id in (review_run.selected_candidate_ids_json or [])})
    if not selected_candidate_ids:
        raise ContentGapItemMaterializationServiceError(
            "Review run has no candidate scope to materialize.",
            code="empty_review_scope",
        )
    rows = session.scalars(
        select(SiteContentGapCandidate)
        .where(
            SiteContentGapCandidate.id.in_(selected_candidate_ids),
            SiteContentGapCandidate.site_id == review_run.site_id,
            SiteContentGapCandidate.basis_crawl_job_id == review_run.basis_crawl_job_id,
        )
        .order_by(SiteContentGapCandidate.id.asc())
    ).all()
    candidates_by_id = {int(row.id): row for row in rows}
    if len(candidates_by_id) != len(selected_candidate_ids):
        raise ContentGapItemMaterializationServiceError(
            "Review run references candidates outside its snapshot scope.",
            code="candidate_scope_mismatch",
        )
    return candidates_by_id


def _validate_decisions(
    decisions: list[SanitizedContentGapDecision],
    *,
    review_run: SiteContentGapReviewRun,
    candidates_by_id: dict[int, SiteContentGapCandidate],
) -> None:
    if not decisions:
        raise ContentGapItemMaterializationServiceError(
            "At least one sanitized decision is required for item materialization.",
            code="empty_decisions",
        )
    if len(decisions) != len(candidates_by_id):
        raise ContentGapItemMaterializationServiceError(
            "Sanitized decisions must cover the entire review run candidate scope.",
            code="decision_scope_mismatch",
        )

    seen_candidate_ids: set[int] = set()
    primary_count_by_group: dict[str, int] = {}
    for decision in decisions:
        candidate_id = int(decision.source_candidate_id)
        if candidate_id in seen_candidate_ids:
            raise ContentGapItemMaterializationServiceError(
                "Only one sanitized decision per source candidate is allowed.",
                code="duplicate_source_candidate",
            )
        seen_candidate_ids.add(candidate_id)
        candidate = candidates_by_id.get(candidate_id)
        if candidate is None:
            raise ContentGapItemMaterializationServiceError(
                "Decision references a candidate outside the review run scope.",
                code="decision_scope_mismatch",
            )
        if candidate.basis_crawl_job_id != review_run.basis_crawl_job_id:
            raise ContentGapItemMaterializationServiceError(
                "Decision candidate snapshot does not match the review run snapshot.",
                code="snapshot_mismatch",
            )
        if decision.decision_action not in VALID_DECISION_ACTIONS:
            raise ContentGapItemMaterializationServiceError(
                f"Unsupported decision action '{decision.decision_action}'.",
                code="invalid_decision_action",
            )
        if not _trim_text(decision.decision_reason_text):
            raise ContentGapItemMaterializationServiceError(
                "Decision reason text is required for every materialized item.",
                code="missing_decision_reason",
            )
        if decision.decision_action == "merge":
            if not _resolve_review_group_key(decision, candidate):
                raise ContentGapItemMaterializationServiceError(
                    "Merge decisions require a review group key or merge target candidate key.",
                    code="missing_merge_group_key",
                )
        if decision.decision_action == "remove" and not _trim_text_or_none(decision.remove_reason_text):
            raise ContentGapItemMaterializationServiceError(
                "Remove decisions require remove_reason_text.",
                code="missing_remove_reason",
            )
        if decision.decision_action == "rewrite" and not _trim_text_or_none(decision.reviewed_phrase):
            raise ContentGapItemMaterializationServiceError(
                "Rewrite decisions require reviewed_phrase.",
                code="missing_reviewed_phrase",
            )

        group_key = _resolve_review_group_key(decision, candidate)
        if _resolve_group_primary(decision):
            primary_count_by_group[group_key] = primary_count_by_group.get(group_key, 0) + 1

    if set(seen_candidate_ids) != set(candidates_by_id):
        raise ContentGapItemMaterializationServiceError(
            "Sanitized decisions must exactly match the review run candidate scope.",
            code="decision_scope_mismatch",
        )
    conflicting_groups = [group_key for group_key, count in primary_count_by_group.items() if count > 1]
    if conflicting_groups:
        raise ContentGapItemMaterializationServiceError(
            "A merge group may contain at most one primary item.",
            code="multiple_group_primaries",
        )


def _resolve_display_state(decision: SanitizedContentGapDecision) -> str:
    if decision.decision_action == "remove":
        return HIDDEN_REMOVED_DISPLAY_STATE
    if decision.decision_action == "merge" and not _resolve_group_primary(decision):
        return HIDDEN_MERGED_CHILD_DISPLAY_STATE
    return VISIBLE_DISPLAY_STATE


def _resolve_review_group_key(
    decision: SanitizedContentGapDecision,
    candidate: SiteContentGapCandidate,
) -> str:
    if isinstance(decision.review_group_key, str) and decision.review_group_key.strip():
        return decision.review_group_key.strip()[:96]
    if isinstance(decision.merge_target_candidate_key, str) and decision.merge_target_candidate_key.strip():
        return decision.merge_target_candidate_key.strip()[:96]
    return candidate.candidate_key[:96]


def _resolve_group_primary(decision: SanitizedContentGapDecision) -> bool:
    if decision.decision_action != "merge":
        return True
    return bool(decision.group_primary)


def _resolve_response_hash(decision: SanitizedContentGapDecision) -> str:
    if isinstance(decision.response_hash, str) and decision.response_hash.strip():
        return decision.response_hash.strip()[:64]
    payload = _build_sanitized_raw_decision_json(decision)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _build_sanitized_raw_decision_json(decision: SanitizedContentGapDecision) -> dict[str, Any]:
    payload = asdict(decision)
    payload.pop("response_hash", None)
    return {
        key: value
        for key, value in payload.items()
        if value is not None
    }


def _sanitize_optional_json(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return dict(value)


def _trim_or_none(value: str | None, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed[:max_length]


def _trim_text(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:1000]


def _trim_text_or_none(value: str | None) -> str | None:
    trimmed = _trim_text(value or "")
    return trimmed or None
