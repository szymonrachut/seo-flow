from __future__ import annotations

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from datetime import timedelta, timezone
import hashlib
import json
import logging
import math
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    CrawlJob,
    GscTopQuery,
    Page,
    SiteContentGapCandidate,
    SiteContentGapReviewRun,
    utcnow,
)
from app.db.session import SessionLocal
from app.services import site_service
from app.services.content_gap_candidate_service import DEFAULT_GSC_DATE_RANGE


logger = logging.getLogger(__name__)

CONTENT_GAP_REVIEW_RUN_ACTIVE_STATUSES = {"queued", "running"}
CONTENT_GAP_REVIEW_RUN_RETRYABLE_STATUSES = {"failed", "stale", "cancelled"}
DEFAULT_CONTENT_GAP_REVIEW_RUNNING_LEASE_SECONDS = 300
DEFAULT_CONTENT_GAP_REVIEW_QUEUED_LEASE_SECONDS = 7_200
DEFAULT_CONTENT_GAP_REVIEW_BATCH_SIZE = 5
CONTENT_GAP_REVIEW_PROMPT_VERSION = "content-gap-review-v1"
CONTENT_GAP_REVIEW_SCHEMA_VERSION = "content_gap_review_v1"
CONTENT_GAP_REVIEW_STALE_ERROR_CODE = "stale_content_gap_review_run"
CONTENT_GAP_REVIEW_STALE_ERROR_MESSAGE = (
    "Content Gap review run was abandoned after a backend restart or missed heartbeat and has been marked as stale."
)
CONTENT_GAP_REVIEW_CANCELLED_ERROR_CODE = "content_gap_review_cancelled"
CONTENT_GAP_REVIEW_CANCELLED_ERROR_MESSAGE = "Content Gap review run was cancelled before completion."


class ContentGapReviewRunServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "content_gap_review_run_error") -> None:
        super().__init__(message)
        self.code = code


def queue_review_run(
    session: Session,
    *,
    site_id: int,
    basis_crawl_job_id: int | None = None,
    trigger_source: str = "manual",
    scope_type: str = "all_current",
    selected_candidate_ids: Sequence[int] | None = None,
    output_language: str = "en",
    llm_provider: str | None = "openai",
    llm_model: str | None = None,
    prompt_version: str | None = CONTENT_GAP_REVIEW_PROMPT_VERSION,
    schema_version: str | None = CONTENT_GAP_REVIEW_SCHEMA_VERSION,
    batch_size: int = DEFAULT_CONTENT_GAP_REVIEW_BATCH_SIZE,
) -> dict[str, Any]:
    reconcile_stale_review_runs(session, site_id=site_id)
    if _get_active_run(session, site_id=site_id) is not None:
        raise ContentGapReviewRunServiceError(
            "Content Gap review is already queued or running for this site.",
            code="already_running",
        )

    basis_crawl = _resolve_basis_crawl(session, site_id=site_id, basis_crawl_job_id=basis_crawl_job_id)
    normalized_scope_type = _normalize_scope_type(scope_type, selected_candidate_ids=selected_candidate_ids)
    candidates = _load_scope_candidates(
        session,
        site_id=site_id,
        basis_crawl_job_id=basis_crawl.id,
        scope_type=normalized_scope_type,
        selected_candidate_ids=selected_candidate_ids,
    )
    if not candidates:
        raise ContentGapReviewRunServiceError(
            "No current raw Content Gap candidates are available for this crawl snapshot.",
            code="no_candidates",
        )

    settings = get_settings()
    resolved_model = llm_model or settings.openai_model_competitor_merge
    normalized_candidate_ids = [int(candidate.id) for candidate in candidates]
    candidate_generation_version = _resolve_candidate_generation_version(candidates)
    candidate_set_hash = _build_candidate_set_hash(candidates)
    own_context_hash, own_pages_count = _build_own_context_hash(session, basis_crawl_job_id=basis_crawl.id)
    gsc_context_hash, gsc_query_count = _build_gsc_context_hash(session, basis_crawl_job_id=basis_crawl.id)
    normalized_batch_size = max(1, int(batch_size))
    batch_count = int(math.ceil(len(candidates) / normalized_batch_size))

    next_run_id = (
        session.scalar(
            select(func.coalesce(func.max(SiteContentGapReviewRun.run_id), 0) + 1)
            .where(SiteContentGapReviewRun.site_id == site_id)
        )
        or 1
    )
    context_summary = {
        "basis_crawl_job_id": int(basis_crawl.id),
        "scope_type": normalized_scope_type,
        "candidate_count": len(candidates),
        "selected_candidate_ids_count": len(normalized_candidate_ids),
        "own_pages_count": own_pages_count,
        "has_gsc_context": gsc_context_hash is not None,
        "gsc_query_count": gsc_query_count,
        "gsc_date_range_label": DEFAULT_GSC_DATE_RANGE,
        "candidate_generation_version": candidate_generation_version,
    }
    run = SiteContentGapReviewRun(
        site_id=site_id,
        basis_crawl_job_id=int(basis_crawl.id),
        run_id=int(next_run_id),
        status="queued",
        stage="queued",
        trigger_source=trigger_source[:32],
        scope_type=normalized_scope_type[:32],
        selected_candidate_ids_json=list(normalized_candidate_ids),
        candidate_count=len(candidates),
        candidate_set_hash=candidate_set_hash,
        candidate_generation_version=candidate_generation_version,
        own_context_hash=own_context_hash,
        gsc_context_hash=gsc_context_hash,
        context_summary_json=context_summary,
        output_language=(output_language or "en")[:16],
        llm_provider=llm_provider[:64] if isinstance(llm_provider, str) and llm_provider else None,
        llm_model=resolved_model[:128] if isinstance(resolved_model, str) and resolved_model else None,
        prompt_version=prompt_version[:64] if isinstance(prompt_version, str) and prompt_version else None,
        schema_version=schema_version[:64] if isinstance(schema_version, str) and schema_version else None,
        batch_size=normalized_batch_size,
        batch_count=batch_count,
        completed_batch_count=0,
        last_heartbeat_at=utcnow(),
        lease_expires_at=_lease_expires_at(status="queued"),
    )
    session.add(run)
    session.flush()
    logger.info(
        "content_gap_review_run.queued site_id=%s basis_crawl_job_id=%s run_id=%s candidates=%s scope_type=%s",
        site_id,
        basis_crawl.id,
        run.run_id,
        run.candidate_count,
        run.scope_type,
    )
    return serialize_review_run(run)


def claim_review_run(
    session: Session,
    *,
    site_id: int,
    run_id: int,
    lease_owner: str | None = None,
) -> bool:
    reconcile_stale_review_runs(session, site_id=site_id)
    run = _get_run_or_none(session, site_id=site_id, run_id=run_id)
    if run is None or run.status != "queued":
        return False

    now = utcnow()
    run.status = "running"
    run.stage = "prepare_context"
    run.started_at = now
    run.finished_at = None
    run.last_heartbeat_at = now
    run.lease_expires_at = _lease_expires_at(now, status="running")
    run.lease_owner = lease_owner[:64] if isinstance(lease_owner, str) and lease_owner else None
    run.error_code = None
    run.error_message_safe = None
    session.commit()
    logger.info(
        "content_gap_review_run.claimed site_id=%s run_id=%s basis_crawl_job_id=%s",
        site_id,
        run_id,
        run.basis_crawl_job_id,
    )
    return True


def touch_review_run(
    session: Session,
    *,
    site_id: int,
    run_id: int,
    stage: str,
    completed_batch_count: int | None = None,
    lease_owner: str | None = None,
) -> None:
    run = _get_run_or_raise(session, site_id=site_id, run_id=run_id)
    if run.status not in CONTENT_GAP_REVIEW_RUN_ACTIVE_STATUSES:
        raise ContentGapReviewRunServiceError(
            f"Content Gap review run {run_id} is no longer active.",
            code="review_run_inactive",
        )

    now = utcnow()
    run.status = "running"
    run.stage = (stage or "prepare_context")[:32]
    run.last_heartbeat_at = now
    run.lease_expires_at = _lease_expires_at(now, status="running")
    if completed_batch_count is not None:
        run.completed_batch_count = max(0, min(run.batch_count, int(completed_batch_count)))
    if isinstance(lease_owner, str) and lease_owner:
        run.lease_owner = lease_owner[:64]
    run.error_code = None
    run.error_message_safe = None
    session.commit()


def complete_review_run(
    site_id: int,
    run_id: int,
    *,
    completed_batch_count: int | None = None,
) -> None:
    with _session_scope() as session:
        _complete_review_run_in_session(
            session,
            site_id=site_id,
            run_id=run_id,
            completed_batch_count=completed_batch_count,
        )


def fail_review_run(
    site_id: int,
    run_id: int,
    *,
    error_code: str,
    error_message_safe: str,
) -> None:
    with _session_scope() as session:
        _fail_review_run_in_session(
            session,
            site_id=site_id,
            run_id=run_id,
            error_code=error_code,
            error_message_safe=error_message_safe,
        )


def cancel_review_run(
    site_id: int,
    run_id: int,
    *,
    error_message_safe: str = CONTENT_GAP_REVIEW_CANCELLED_ERROR_MESSAGE,
) -> None:
    with _session_scope() as session:
        run = _get_run_or_none(session, site_id=site_id, run_id=run_id)
        if run is None or run.status not in CONTENT_GAP_REVIEW_RUN_ACTIVE_STATUSES:
            return

        now = utcnow()
        run.status = "cancelled"
        run.stage = "finalize"
        run.finished_at = now
        run.last_heartbeat_at = now
        run.lease_expires_at = now
        run.error_code = CONTENT_GAP_REVIEW_CANCELLED_ERROR_CODE
        run.error_message_safe = error_message_safe[:1000]
        session.flush()
        logger.info(
            "content_gap_review_run.cancelled site_id=%s run_id=%s",
            site_id,
            run_id,
        )


def retry_review_run(
    session: Session,
    *,
    site_id: int,
    run_id: int,
    trigger_source: str = "retry",
) -> dict[str, Any]:
    reconcile_stale_review_runs(session, site_id=site_id)
    if _get_active_run(session, site_id=site_id) is not None:
        raise ContentGapReviewRunServiceError(
            "Content Gap review is already queued or running for this site.",
            code="already_running",
        )

    source_run = _get_run_or_raise(session, site_id=site_id, run_id=run_id)
    if source_run.status not in CONTENT_GAP_REVIEW_RUN_RETRYABLE_STATUSES:
        raise ContentGapReviewRunServiceError(
            "Only failed, stale, or cancelled review runs can be retried.",
            code="not_retryable",
        )

    next_run_id = (
        session.scalar(
            select(func.coalesce(func.max(SiteContentGapReviewRun.run_id), 0) + 1)
            .where(SiteContentGapReviewRun.site_id == site_id)
        )
        or 1
    )
    now = utcnow()
    retry_run = SiteContentGapReviewRun(
        site_id=site_id,
        basis_crawl_job_id=source_run.basis_crawl_job_id,
        run_id=int(next_run_id),
        status="queued",
        stage="queued",
        trigger_source=trigger_source[:32],
        scope_type=source_run.scope_type,
        selected_candidate_ids_json=list(source_run.selected_candidate_ids_json or []),
        candidate_count=source_run.candidate_count,
        candidate_set_hash=source_run.candidate_set_hash,
        candidate_generation_version=source_run.candidate_generation_version,
        own_context_hash=source_run.own_context_hash,
        gsc_context_hash=source_run.gsc_context_hash,
        context_summary_json=dict(source_run.context_summary_json or {}),
        output_language=source_run.output_language,
        llm_provider=source_run.llm_provider,
        llm_model=source_run.llm_model,
        prompt_version=source_run.prompt_version,
        schema_version=source_run.schema_version,
        batch_size=source_run.batch_size,
        batch_count=source_run.batch_count,
        completed_batch_count=0,
        lease_owner=None,
        lease_expires_at=_lease_expires_at(now, status="queued"),
        last_heartbeat_at=now,
        retry_of_run_id=source_run.id,
        created_at=now,
        updated_at=now,
    )
    session.add(retry_run)
    session.flush()
    logger.info(
        "content_gap_review_run.retry_queued site_id=%s source_run_id=%s retry_run_id=%s",
        site_id,
        source_run.run_id,
        retry_run.run_id,
    )
    return serialize_review_run(retry_run)


def list_review_runs(
    session: Session,
    *,
    site_id: int,
    limit: int = 5,
) -> list[dict[str, Any]]:
    reconcile_stale_review_runs(session, site_id=site_id)
    rows = session.scalars(
        select(SiteContentGapReviewRun)
        .where(SiteContentGapReviewRun.site_id == site_id)
        .order_by(SiteContentGapReviewRun.id.desc())
        .limit(max(1, min(int(limit), 25)))
    ).all()
    return [serialize_review_run(run) for run in rows]


def reconcile_stale_review_runs(session: Session, *, site_id: int) -> int:
    now = utcnow()
    runs = session.scalars(
        select(SiteContentGapReviewRun)
        .where(
            SiteContentGapReviewRun.site_id == site_id,
            SiteContentGapReviewRun.status.in_(tuple(CONTENT_GAP_REVIEW_RUN_ACTIVE_STATUSES)),
            SiteContentGapReviewRun.lease_expires_at.is_not(None),
            SiteContentGapReviewRun.lease_expires_at < now,
        )
        .order_by(SiteContentGapReviewRun.id.asc())
    ).all()
    stale_count = 0
    for run in runs:
        run.status = "stale"
        run.stage = "finalize"
        run.finished_at = now
        run.last_heartbeat_at = now
        run.lease_expires_at = now
        run.error_code = CONTENT_GAP_REVIEW_STALE_ERROR_CODE
        run.error_message_safe = CONTENT_GAP_REVIEW_STALE_ERROR_MESSAGE
        stale_count += 1
        logger.info(
            "content_gap_review_run.stale site_id=%s run_id=%s basis_crawl_job_id=%s",
            run.site_id,
            run.run_id,
            run.basis_crawl_job_id,
        )
    if stale_count:
        session.flush()
    return stale_count


def serialize_review_run(run: SiteContentGapReviewRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "site_id": run.site_id,
        "basis_crawl_job_id": run.basis_crawl_job_id,
        "run_id": run.run_id,
        "status": run.status,
        "stage": run.stage,
        "trigger_source": run.trigger_source,
        "scope_type": run.scope_type,
        "selected_candidate_ids_json": list(run.selected_candidate_ids_json or []),
        "candidate_count": run.candidate_count,
        "candidate_set_hash": run.candidate_set_hash,
        "candidate_generation_version": run.candidate_generation_version,
        "own_context_hash": run.own_context_hash,
        "gsc_context_hash": run.gsc_context_hash,
        "context_summary_json": dict(run.context_summary_json or {}),
        "output_language": run.output_language,
        "llm_provider": run.llm_provider,
        "llm_model": run.llm_model,
        "prompt_version": run.prompt_version,
        "schema_version": run.schema_version,
        "batch_size": run.batch_size,
        "batch_count": run.batch_count,
        "completed_batch_count": run.completed_batch_count,
        "lease_owner": run.lease_owner,
        "lease_expires_at": run.lease_expires_at,
        "last_heartbeat_at": run.last_heartbeat_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error_code": run.error_code,
        "error_message_safe": run.error_message_safe,
        "retry_of_run_id": run.retry_of_run_id,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _resolve_basis_crawl(session: Session, *, site_id: int, basis_crawl_job_id: int | None) -> CrawlJob:
    workspace_context = site_service.resolve_site_workspace_context(
        session,
        site_id,
        active_crawl_id=basis_crawl_job_id,
    )
    active_crawl = workspace_context["active_crawl"]
    if active_crawl is None:
        raise ContentGapReviewRunServiceError(
            "Content Gap review requires an active crawl snapshot.",
            code="no_active_crawl",
        )
    return active_crawl


def _normalize_scope_type(scope_type: str, *, selected_candidate_ids: Sequence[int] | None) -> str:
    if selected_candidate_ids:
        return "selected_ids"
    normalized = (scope_type or "all_current").strip().lower()
    if normalized not in {"all_current", "selected_ids"}:
        raise ContentGapReviewRunServiceError(
            f"Unsupported review scope '{scope_type}'.",
            code="invalid_scope_type",
        )
    return normalized


def _load_scope_candidates(
    session: Session,
    *,
    site_id: int,
    basis_crawl_job_id: int,
    scope_type: str,
    selected_candidate_ids: Sequence[int] | None,
) -> list[SiteContentGapCandidate]:
    query = (
        select(SiteContentGapCandidate)
        .where(
            SiteContentGapCandidate.site_id == site_id,
            SiteContentGapCandidate.basis_crawl_job_id == basis_crawl_job_id,
            SiteContentGapCandidate.current.is_(True),
            SiteContentGapCandidate.status == "active",
        )
        .order_by(SiteContentGapCandidate.id.asc())
    )
    candidates = session.scalars(query).all()
    if scope_type == "all_current":
        return candidates

    selected_ids = sorted({int(candidate_id) for candidate_id in (selected_candidate_ids or [])})
    if not selected_ids:
        raise ContentGapReviewRunServiceError(
            "Selected review scope requires at least one candidate id.",
            code="invalid_scope_type",
        )
    candidates_by_id = {int(candidate.id): candidate for candidate in candidates}
    selected_candidates = [candidates_by_id[candidate_id] for candidate_id in selected_ids if candidate_id in candidates_by_id]
    if len(selected_candidates) != len(selected_ids):
        raise ContentGapReviewRunServiceError(
            "Selected candidates must exist as current candidates for the requested crawl snapshot.",
            code="candidate_scope_mismatch",
        )
    return selected_candidates


def _resolve_candidate_generation_version(candidates: Sequence[SiteContentGapCandidate]) -> str:
    versions = sorted({str(candidate.generation_version) for candidate in candidates if candidate.generation_version})
    if not versions:
        return "unknown"
    if len(versions) == 1:
        return versions[0][:32]
    return "mixed"


def _build_candidate_set_hash(candidates: Sequence[SiteContentGapCandidate]) -> str:
    payload = [
        {
            "id": int(candidate.id),
            "candidate_key": str(candidate.candidate_key),
            "candidate_input_hash": str(candidate.candidate_input_hash),
            "generation_version": str(candidate.generation_version),
        }
        for candidate in sorted(candidates, key=lambda candidate: (candidate.id, candidate.candidate_key))
    ]
    return _hash_payload(payload)


def _build_own_context_hash(session: Session, *, basis_crawl_job_id: int) -> tuple[str, int]:
    rows = session.execute(
        select(
            Page.id,
            Page.normalized_url,
            Page.title,
            Page.h1,
            Page.meta_description,
            Page.page_type,
            Page.page_bucket,
        )
        .where(Page.crawl_job_id == basis_crawl_job_id)
        .order_by(Page.id.asc())
    ).all()
    payload = [
        {
            "id": int(row.id),
            "normalized_url": row.normalized_url,
            "title": row.title,
            "h1": row.h1,
            "meta_description": row.meta_description,
            "page_type": row.page_type,
            "page_bucket": row.page_bucket,
        }
        for row in rows
    ]
    return _hash_payload(payload), len(payload)


def _build_gsc_context_hash(session: Session, *, basis_crawl_job_id: int) -> tuple[str | None, int]:
    rows = session.execute(
        select(
            GscTopQuery.page_id,
            GscTopQuery.normalized_url,
            GscTopQuery.query,
            GscTopQuery.clicks,
            GscTopQuery.impressions,
            GscTopQuery.position,
        )
        .where(
            GscTopQuery.crawl_job_id == basis_crawl_job_id,
            GscTopQuery.date_range_label == DEFAULT_GSC_DATE_RANGE,
        )
        .order_by(GscTopQuery.id.asc())
    ).all()
    if not rows:
        return None, 0
    payload = [
        {
            "page_id": int(row.page_id) if row.page_id is not None else None,
            "normalized_url": row.normalized_url,
            "query": row.query,
            "clicks": int(row.clicks or 0),
            "impressions": int(row.impressions or 0),
            "position": float(row.position) if row.position is not None else None,
        }
        for row in rows
    ]
    return _hash_payload(payload), len(payload)


def _get_active_run(session: Session, *, site_id: int) -> SiteContentGapReviewRun | None:
    return session.scalar(
        select(SiteContentGapReviewRun)
        .where(
            SiteContentGapReviewRun.site_id == site_id,
            SiteContentGapReviewRun.status.in_(tuple(CONTENT_GAP_REVIEW_RUN_ACTIVE_STATUSES)),
        )
        .order_by(SiteContentGapReviewRun.id.desc())
        .limit(1)
    )


def _get_run_or_none(session: Session, *, site_id: int, run_id: int) -> SiteContentGapReviewRun | None:
    return session.scalar(
        select(SiteContentGapReviewRun)
        .where(
            SiteContentGapReviewRun.site_id == site_id,
            SiteContentGapReviewRun.run_id == run_id,
        )
        .limit(1)
    )


def _get_run_or_raise(session: Session, *, site_id: int, run_id: int) -> SiteContentGapReviewRun:
    run = _get_run_or_none(session, site_id=site_id, run_id=run_id)
    if run is None:
        raise ContentGapReviewRunServiceError(
            f"Content Gap review run {run_id} not found for site {site_id}.",
            code="not_found",
        )
    return run


def _complete_review_run_in_session(
    session: Session,
    *,
    site_id: int,
    run_id: int,
    completed_batch_count: int | None = None,
) -> bool:
    run = _get_run_or_none(session, site_id=site_id, run_id=run_id)
    if run is None or run.status not in CONTENT_GAP_REVIEW_RUN_ACTIVE_STATUSES:
        return False

    now = utcnow()
    run.status = "completed"
    run.stage = "finalize"
    run.finished_at = now
    run.last_heartbeat_at = now
    run.lease_expires_at = now
    run.completed_batch_count = (
        max(0, min(run.batch_count, int(completed_batch_count)))
        if completed_batch_count is not None
        else run.batch_count
    )
    run.error_code = None
    run.error_message_safe = None
    session.flush()
    logger.info(
        "content_gap_review_run.completed site_id=%s run_id=%s basis_crawl_job_id=%s candidates=%s",
        site_id,
        run_id,
        run.basis_crawl_job_id,
        run.candidate_count,
    )
    return True


def _fail_review_run_in_session(
    session: Session,
    *,
    site_id: int,
    run_id: int,
    error_code: str,
    error_message_safe: str,
) -> bool:
    run = _get_run_or_none(session, site_id=site_id, run_id=run_id)
    if run is None or run.status not in CONTENT_GAP_REVIEW_RUN_ACTIVE_STATUSES:
        return False

    now = utcnow()
    run.status = "failed"
    run.stage = "finalize"
    run.finished_at = now
    run.last_heartbeat_at = now
    run.lease_expires_at = now
    run.error_code = (error_code or "content_gap_review_run_failed")[:64]
    run.error_message_safe = (error_message_safe or "Content Gap review run failed.")[:1000]
    session.flush()
    logger.info(
        "content_gap_review_run.failed site_id=%s run_id=%s error_code=%s",
        site_id,
        run_id,
        run.error_code,
    )
    return True


def _lease_expires_at(
    reference: Any | None = None,
    *,
    status: str,
) -> Any:
    base = reference or utcnow()
    base = base.astimezone(timezone.utc) if getattr(base, "tzinfo", None) is not None else base
    seconds = (
        DEFAULT_CONTENT_GAP_REVIEW_QUEUED_LEASE_SECONDS
        if status == "queued"
        else DEFAULT_CONTENT_GAP_REVIEW_RUNNING_LEASE_SECONDS
    )
    return base + timedelta(seconds=seconds)


def _hash_payload(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@contextmanager
def _session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
