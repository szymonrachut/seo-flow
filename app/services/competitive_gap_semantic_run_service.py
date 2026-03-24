from __future__ import annotations

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from datetime import timedelta, timezone
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import SiteCompetitor, SiteCompetitorSemanticRun, utcnow
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)

SEMANTIC_RUN_ACTIVE_STATUSES = {"queued", "running"}
DEFAULT_SEMANTIC_RUNNING_LEASE_SECONDS = 300
DEFAULT_SEMANTIC_QUEUED_LEASE_SECONDS = 7_200
DEFAULT_SEMANTIC_LEASE_SECONDS = DEFAULT_SEMANTIC_RUNNING_LEASE_SECONDS
STALE_RUN_ERROR_CODE = "stale_semantic_run"
STALE_RUN_ERROR_MESSAGE = (
    "Semantic matching was abandoned after a backend restart or missed heartbeat and has been marked as stale."
)

SEMANTIC_SUMMARY_INT_FIELDS = {
    "semantic_candidates_count",
    "semantic_llm_jobs_count",
    "semantic_resolved_count",
    "semantic_cache_hits",
    "semantic_fallback_count",
    "merge_pairs_count",
    "own_match_pairs_count",
    "batch_size",
    "cluster_count",
    "low_confidence_count",
    "semantic_cards_count",
    "own_page_profiles_count",
    "canonical_pages_count",
    "duplicate_pages_count",
    "near_duplicate_pages_count",
}


class CompetitiveGapSemanticRunServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "semantic_run_error") -> None:
        super().__init__(message)
        self.code = code


def build_empty_semantic_summary_payload() -> dict[str, Any]:
    return {
        "semantic_candidates_count": 0,
        "semantic_llm_jobs_count": 0,
        "semantic_resolved_count": 0,
        "semantic_cache_hits": 0,
        "semantic_fallback_count": 0,
        "merge_pairs_count": 0,
        "own_match_pairs_count": 0,
        "batch_size": 0,
        "cluster_count": 0,
        "low_confidence_count": 0,
        "semantic_cards_count": 0,
        "own_page_profiles_count": 0,
        "canonical_pages_count": 0,
        "duplicate_pages_count": 0,
        "near_duplicate_pages_count": 0,
        "semantic_version": None,
        "cluster_version": None,
        "coverage_version": None,
    }


def normalize_semantic_summary_payload(payload: Any) -> dict[str, Any]:
    normalized = build_empty_semantic_summary_payload()
    if not isinstance(payload, dict):
        return normalized

    for field_name in SEMANTIC_SUMMARY_INT_FIELDS:
        try:
            normalized[field_name] = max(0, int(payload.get(field_name, 0) or 0))
        except (TypeError, ValueError):
            normalized[field_name] = 0

    for field_name in ("semantic_version", "cluster_version", "coverage_version"):
        value = payload.get(field_name)
        normalized[field_name] = str(value).strip()[:64] if isinstance(value, str) and value.strip() else None
    return normalized


def queue_semantic_run(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    trigger_source: str,
    mode: str,
    active_crawl_id: int | None,
    source_candidate_ids: Sequence[int],
    llm_provider: str | None = None,
    llm_model: str | None = None,
    prompt_version: str | None = None,
) -> dict[str, Any]:
    reconcile_stale_semantic_runs(session, site_id=site_id, competitor_id=competitor_id)
    _get_competitor_or_raise(session, site_id, competitor_id)
    active_run = _get_active_run(session, site_id=site_id, competitor_id=competitor_id)
    if active_run is not None:
        raise CompetitiveGapSemanticRunServiceError(
            "Semantic matching is already queued or running for this competitor.",
            code="already_running",
        )

    next_run_id = (
        session.scalar(
            select(func.coalesce(func.max(SiteCompetitorSemanticRun.run_id), 0) + 1)
            .where(SiteCompetitorSemanticRun.competitor_id == competitor_id)
        )
        or 1
    )
    summary_payload = build_empty_semantic_summary_payload()
    normalized_candidate_ids = sorted({int(candidate_id) for candidate_id in source_candidate_ids})
    summary_payload["semantic_candidates_count"] = len(normalized_candidate_ids)

    run = SiteCompetitorSemanticRun(
        site_id=site_id,
        competitor_id=competitor_id,
        run_id=int(next_run_id),
        status="queued",
        stage="queued",
        trigger_source=trigger_source[:32],
        mode=mode[:16],
        active_crawl_id=active_crawl_id,
        last_heartbeat_at=utcnow(),
        lease_expires_at=_lease_expires_at(status="queued"),
        llm_provider=llm_provider,
        llm_model=llm_model,
        prompt_version=prompt_version,
        source_candidate_ids_json=list(normalized_candidate_ids),
        summary_json=summary_payload,
    )
    session.add(run)
    session.flush()
    logger.info(
        "semantic_run.queued site_id=%s competitor_id=%s run_id=%s mode=%s trigger_source=%s candidates=%s",
        site_id,
        competitor_id,
        run.run_id,
        run.mode,
        run.trigger_source,
        len(normalized_candidate_ids),
    )
    return serialize_semantic_run(run)


def claim_semantic_run(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    run_id: int,
) -> bool:
    reconcile_stale_semantic_runs(session, site_id=site_id, competitor_id=competitor_id)
    run = _get_run_or_none(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
    if run is None or run.status != "queued":
        return False

    now = utcnow()
    run.status = "running"
    run.stage = "prepare_candidates"
    run.started_at = now
    run.finished_at = None
    run.last_heartbeat_at = now
    run.lease_expires_at = _lease_expires_at(now, status="running")
    run.error_code = None
    run.error_message_safe = None
    session.commit()
    logger.info(
        "semantic_run.claimed site_id=%s competitor_id=%s run_id=%s",
        site_id,
        competitor_id,
        run_id,
    )
    return True


def touch_semantic_run(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    run_id: int,
    stage: str,
    summary_payload: dict[str, Any],
    llm_provider: str | None = None,
    llm_model: str | None = None,
    prompt_version: str | None = None,
) -> None:
    run = _get_run_or_raise(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
    if run.status not in SEMANTIC_RUN_ACTIVE_STATUSES:
        raise CompetitiveGapSemanticRunServiceError(
            f"Semantic run {run_id} is no longer active.",
            code="semantic_run_inactive",
        )

    now = utcnow()
    run.status = "running"
    run.stage = stage[:32]
    run.last_heartbeat_at = now
    run.lease_expires_at = _lease_expires_at(now, status="running")
    run.summary_json = normalize_semantic_summary_payload(summary_payload)
    if llm_provider is not None:
        run.llm_provider = llm_provider
    if llm_model is not None:
        run.llm_model = llm_model
    if prompt_version is not None:
        run.prompt_version = prompt_version
    run.error_code = None
    run.error_message_safe = None
    session.commit()


def complete_semantic_run(
    site_id: int,
    competitor_id: int,
    run_id: int,
    *,
    summary_payload: dict[str, Any],
    llm_provider: str | None = None,
    llm_model: str | None = None,
    prompt_version: str | None = None,
) -> None:
    with _session_scope() as session:
        run = _get_run_or_none(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
        if run is None or run.status not in SEMANTIC_RUN_ACTIVE_STATUSES:
            return

        now = utcnow()
        run.status = "completed"
        run.stage = "completed"
        run.finished_at = now
        run.last_heartbeat_at = now
        run.lease_expires_at = now
        run.summary_json = normalize_semantic_summary_payload(summary_payload)
        if llm_provider is not None:
            run.llm_provider = llm_provider
        if llm_model is not None:
            run.llm_model = llm_model
        if prompt_version is not None:
            run.prompt_version = prompt_version
        run.error_code = None
        run.error_message_safe = None
        session.flush()
        logger.info(
            "semantic_run.completed site_id=%s competitor_id=%s run_id=%s resolved=%s llm_jobs=%s cache_hits=%s",
            site_id,
            competitor_id,
            run_id,
            run.summary_json.get("semantic_resolved_count", 0),
            run.summary_json.get("semantic_llm_jobs_count", 0),
            run.summary_json.get("semantic_cache_hits", 0),
        )


def fail_semantic_run(
    site_id: int,
    competitor_id: int,
    run_id: int,
    *,
    error_code: str,
    error_message_safe: str,
    summary_payload: dict[str, Any] | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    prompt_version: str | None = None,
) -> None:
    with _session_scope() as session:
        run = _get_run_or_none(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
        if run is None or run.status not in SEMANTIC_RUN_ACTIVE_STATUSES:
            return

        now = utcnow()
        run.status = "failed"
        run.stage = "failed"
        run.finished_at = now
        run.last_heartbeat_at = now
        run.lease_expires_at = now
        run.error_code = (error_code or "semantic_run_failed")[:64]
        run.error_message_safe = _trim_safe_message(error_message_safe)
        if summary_payload is not None:
            run.summary_json = normalize_semantic_summary_payload(summary_payload)
        if llm_provider is not None:
            run.llm_provider = llm_provider
        if llm_model is not None:
            run.llm_model = llm_model
        if prompt_version is not None:
            run.prompt_version = prompt_version
        session.flush()
        logger.warning(
            "semantic_run.failed site_id=%s competitor_id=%s run_id=%s error_code=%s",
            site_id,
            competitor_id,
            run_id,
            run.error_code,
        )


def is_semantic_run_active(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    run_id: int,
) -> bool:
    run = _get_run_or_none(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
    return run is not None and run.status in SEMANTIC_RUN_ACTIVE_STATUSES


def list_semantic_runs(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if reconcile_stale_semantic_runs(session, site_id=site_id, competitor_id=competitor_id):
        session.commit()
    _get_competitor_or_raise(session, site_id, competitor_id)
    runs = session.scalars(
        select(SiteCompetitorSemanticRun)
        .where(
            SiteCompetitorSemanticRun.site_id == site_id,
            SiteCompetitorSemanticRun.competitor_id == competitor_id,
        )
        .order_by(SiteCompetitorSemanticRun.id.desc())
        .limit(max(1, min(int(limit), 25)))
    ).all()
    return [serialize_semantic_run(run) for run in runs]


def reconcile_stale_semantic_runs(
    session: Session,
    *,
    site_id: int,
    competitor_id: int | None = None,
) -> int:
    now = utcnow()
    competitor_query = select(SiteCompetitor).where(SiteCompetitor.site_id == site_id)
    if competitor_id is not None:
        competitor_query = competitor_query.where(SiteCompetitor.id == competitor_id)
    competitors = session.scalars(competitor_query.order_by(SiteCompetitor.id.asc())).all()
    if not competitors:
        return 0

    competitor_ids = [competitor.id for competitor in competitors]
    active_runs = session.scalars(
        select(SiteCompetitorSemanticRun)
        .where(
            SiteCompetitorSemanticRun.site_id == site_id,
            SiteCompetitorSemanticRun.competitor_id.in_(competitor_ids),
            SiteCompetitorSemanticRun.status.in_(tuple(SEMANTIC_RUN_ACTIVE_STATUSES)),
        )
        .order_by(SiteCompetitorSemanticRun.id.asc())
    ).all()

    touched = 0
    for run in active_runs:
        lease_expired = False
        if run.lease_expires_at is not None:
            lease_expired = _coerce_utc_datetime(run.lease_expires_at) <= now
        if not lease_expired:
            continue
        run.status = "stale"
        run.stage = "stale"
        run.finished_at = now
        run.last_heartbeat_at = now
        run.lease_expires_at = now
        run.error_code = STALE_RUN_ERROR_CODE
        run.error_message_safe = STALE_RUN_ERROR_MESSAGE
        touched += 1
        logger.warning(
            "semantic_run.stale site_id=%s competitor_id=%s run_id=%s",
            run.site_id,
            run.competitor_id,
            run.run_id,
        )

    if touched:
        session.flush()
    return touched


def serialize_semantic_run(run: SiteCompetitorSemanticRun) -> dict[str, Any]:
    summary_payload = normalize_semantic_summary_payload(run.summary_json)
    return {
        "id": run.id,
        "site_id": run.site_id,
        "competitor_id": run.competitor_id,
        "run_id": run.run_id,
        "status": run.status,
        "stage": run.stage,
        "trigger_source": run.trigger_source,
        "mode": run.mode,
        "active_crawl_id": run.active_crawl_id,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "last_heartbeat_at": run.last_heartbeat_at,
        "lease_expires_at": run.lease_expires_at,
        "error_code": run.error_code,
        "error_message_safe": run.error_message_safe,
        "llm_provider": run.llm_provider,
        "llm_model": run.llm_model,
        "prompt_version": run.prompt_version,
        "source_candidate_ids": list(run.source_candidate_ids_json or []),
        "summary_json": summary_payload,
        "progress_percent": _compute_progress_percent(run, summary_payload),
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _compute_progress_percent(run: SiteCompetitorSemanticRun, summary_payload: dict[str, Any]) -> int:
    if run.status == "completed":
        return 100
    total = max(0, int(summary_payload.get("semantic_candidates_count", 0) or 0))
    resolved = max(0, int(summary_payload.get("semantic_resolved_count", 0) or 0))
    if total > 0:
        return int(round(min(100, (resolved / total) * 100)))
    return 0


def _lease_expires_at(reference=None, *, status: str = "running"):
    current = reference or utcnow()
    lease_seconds = (
        DEFAULT_SEMANTIC_QUEUED_LEASE_SECONDS
        if status == "queued"
        else DEFAULT_SEMANTIC_RUNNING_LEASE_SECONDS
    )
    return current + timedelta(seconds=lease_seconds)


def _trim_safe_message(message: str | None) -> str | None:
    if message is None:
        return None
    stripped = message.strip()
    if not stripped:
        return None
    return stripped[:4000]


def _coerce_utc_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get_competitor_or_raise(session: Session, site_id: int, competitor_id: int) -> SiteCompetitor:
    competitor = session.get(SiteCompetitor, competitor_id)
    if competitor is None or competitor.site_id != site_id:
        raise CompetitiveGapSemanticRunServiceError(
            f"Competitor {competitor_id} not found for site {site_id}.",
            code="not_found",
        )
    return competitor


def _get_run_or_none(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    run_id: int,
) -> SiteCompetitorSemanticRun | None:
    return session.scalars(
        select(SiteCompetitorSemanticRun)
        .where(
            SiteCompetitorSemanticRun.site_id == site_id,
            SiteCompetitorSemanticRun.competitor_id == competitor_id,
            SiteCompetitorSemanticRun.run_id == run_id,
        )
        .limit(1)
    ).first()


def _get_run_or_raise(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    run_id: int,
) -> SiteCompetitorSemanticRun:
    run = _get_run_or_none(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
    if run is None:
        raise CompetitiveGapSemanticRunServiceError(
            f"Semantic run {run_id} not found for competitor {competitor_id}.",
            code="not_found",
        )
    return run


def _get_active_run(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
) -> SiteCompetitorSemanticRun | None:
    return session.scalars(
        select(SiteCompetitorSemanticRun)
        .where(
            SiteCompetitorSemanticRun.site_id == site_id,
            SiteCompetitorSemanticRun.competitor_id == competitor_id,
            SiteCompetitorSemanticRun.status.in_(tuple(SEMANTIC_RUN_ACTIVE_STATUSES)),
        )
        .order_by(SiteCompetitorSemanticRun.id.desc())
        .limit(1)
    ).first()


def _session_scope():
    @contextmanager
    def _managed_session() -> Generator[Session, None, None]:
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _managed_session()
