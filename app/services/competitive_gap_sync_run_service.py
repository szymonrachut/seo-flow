from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import logging
from datetime import timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import SiteCompetitor, SiteCompetitorSyncRun, utcnow
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)

SYNC_RUN_ACTIVE_STATUSES = {"queued", "running"}
SYNC_RUN_RETRYABLE_STATUSES = {"failed", "stale", "cancelled"}
DEFAULT_SYNC_LEASE_SECONDS = 90
STALE_RUN_ERROR_CODE = "stale_run"
STALE_RUN_ERROR_MESSAGE = (
    "Competitor sync was abandoned after a backend restart or missed heartbeat and has been marked as stale."
)
CANCELLED_RUN_ERROR_CODE = "sync_cancelled"
CANCELLED_RUN_ERROR_MESSAGE = "Competitor sync was reset before completion."


class CompetitiveGapSyncRunServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "sync_run_error") -> None:
        super().__init__(message)
        self.code = code


def queue_sync_run(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    trigger_source: str,
    url_limit: int,
    retry_of_run_id: int | None = None,
) -> dict[str, Any]:
    reconcile_stale_sync_runs(session, site_id=site_id, competitor_id=competitor_id)

    update_result = session.execute(
        update(SiteCompetitor)
        .where(
            SiteCompetitor.id == competitor_id,
            SiteCompetitor.site_id == site_id,
            SiteCompetitor.last_sync_status.not_in(tuple(SYNC_RUN_ACTIVE_STATUSES)),
        )
        .values(
            last_sync_run_id=SiteCompetitor.last_sync_run_id + 1,
            last_sync_status="queued",
            last_sync_stage="queued",
            last_sync_started_at=None,
            last_sync_finished_at=None,
            last_sync_error_code=None,
            last_sync_error=None,
            last_sync_processed_urls=0,
            last_sync_url_limit=url_limit,
            last_sync_processed_extraction_pages=0,
            last_sync_total_extractable_pages=0,
            last_sync_summary_json=_build_empty_summary_payload(),
        )
    )
    if not update_result.rowcount:
        raise CompetitiveGapSyncRunServiceError(
            "Competitor sync is already queued or running.",
            code="already_running",
        )

    session.expire_all()
    competitor = _get_competitor_or_raise(session, site_id, competitor_id)
    run = SiteCompetitorSyncRun(
        site_id=site_id,
        competitor_id=competitor_id,
        run_id=competitor.last_sync_run_id,
        status="queued",
        stage="queued",
        trigger_source=trigger_source[:32],
        last_heartbeat_at=utcnow(),
        lease_expires_at=_lease_expires_at(),
        summary_json=_build_empty_summary_payload(),
        retry_of_run_id=retry_of_run_id,
        processed_urls=0,
        url_limit=url_limit,
        processed_extraction_pages=0,
        total_extractable_pages=0,
    )
    session.add(run)
    session.flush()
    logger.info(
        "competitor_sync.run_queued site_id=%s competitor_id=%s run_id=%s trigger_source=%s",
        site_id,
        competitor_id,
        run.run_id,
        run.trigger_source,
    )
    return serialize_sync_run(run)


def claim_sync_run(session: Session, *, site_id: int, competitor_id: int, run_id: int, url_limit: int) -> bool:
    reconcile_stale_sync_runs(session, site_id=site_id, competitor_id=competitor_id)
    run = _get_run_or_none(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
    if run is None or run.status != "queued":
        return False

    now = utcnow()
    run.status = "running"
    run.stage = "crawling"
    run.started_at = now
    run.finished_at = None
    run.last_heartbeat_at = now
    run.lease_expires_at = _lease_expires_at(now)
    run.error_code = None
    run.error_message_safe = None
    run.summary_json = _build_empty_summary_payload()
    run.processed_urls = 0
    run.url_limit = url_limit
    run.processed_extraction_pages = 0
    run.total_extractable_pages = 0

    competitor = _get_competitor_or_raise(session, site_id, competitor_id)
    competitor.last_sync_run_id = run_id
    competitor.last_sync_status = "running"
    competitor.last_sync_stage = "crawling"
    competitor.last_sync_started_at = now
    competitor.last_sync_finished_at = None
    competitor.last_sync_error_code = None
    competitor.last_sync_error = None
    competitor.last_sync_processed_urls = 0
    competitor.last_sync_url_limit = url_limit
    competitor.last_sync_processed_extraction_pages = 0
    competitor.last_sync_total_extractable_pages = 0
    competitor.last_sync_summary_json = _build_empty_summary_payload()
    session.commit()
    logger.info(
        "competitor_sync.run_claimed site_id=%s competitor_id=%s run_id=%s",
        site_id,
        competitor_id,
        run_id,
    )
    return True


def touch_sync_run(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    run_id: int,
    stage: str,
    processed_urls: int,
    url_limit: int,
    processed_extraction_pages: int,
    total_extractable_pages: int,
    summary_payload: dict[str, Any],
) -> None:
    run = _get_run_or_raise(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
    if run.status not in SYNC_RUN_ACTIVE_STATUSES:
        raise CompetitiveGapSyncRunServiceError(
            f"Sync run {run_id} is no longer active.",
            code="sync_reset",
        )

    now = utcnow()
    run.status = "running"
    run.stage = stage[:32]
    run.last_heartbeat_at = now
    run.lease_expires_at = _lease_expires_at(now)
    run.processed_urls = max(0, int(processed_urls))
    run.url_limit = max(0, int(url_limit))
    run.processed_extraction_pages = max(0, int(processed_extraction_pages))
    run.total_extractable_pages = max(0, int(total_extractable_pages))
    run.summary_json = _normalize_summary_payload(summary_payload)
    run.error_code = None
    run.error_message_safe = None

    competitor = _get_competitor_or_raise(session, site_id, competitor_id)
    competitor.last_sync_status = "running"
    competitor.last_sync_stage = stage[:32]
    competitor.last_sync_error_code = None
    competitor.last_sync_error = None
    competitor.last_sync_processed_urls = run.processed_urls
    competitor.last_sync_url_limit = run.url_limit
    competitor.last_sync_processed_extraction_pages = run.processed_extraction_pages
    competitor.last_sync_total_extractable_pages = run.total_extractable_pages
    competitor.last_sync_summary_json = run.summary_json
    session.commit()


def complete_sync_run(
    site_id: int,
    competitor_id: int,
    run_id: int,
    *,
    processed_urls: int,
    url_limit: int,
    processed_extraction_pages: int,
    total_extractable_pages: int,
    summary_payload: dict[str, Any],
) -> None:
    with _session_scope() as session:
        run = _get_run_or_none(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
        if run is None or run.status not in SYNC_RUN_ACTIVE_STATUSES:
            return

        now = utcnow()
        run.status = "done"
        run.stage = "done"
        run.finished_at = now
        run.last_heartbeat_at = now
        run.lease_expires_at = now
        run.error_code = None
        run.error_message_safe = None
        run.processed_urls = max(0, int(processed_urls))
        run.url_limit = max(0, int(url_limit))
        run.processed_extraction_pages = max(0, int(processed_extraction_pages))
        run.total_extractable_pages = max(0, int(total_extractable_pages))
        run.summary_json = _normalize_summary_payload(summary_payload)

        competitor = _get_competitor_or_raise(session, site_id, competitor_id)
        competitor.last_sync_run_id = run_id
        competitor.last_sync_status = "done"
        competitor.last_sync_stage = "done"
        competitor.last_sync_finished_at = now
        competitor.last_sync_error_code = None
        competitor.last_sync_error = None
        competitor.last_sync_processed_urls = run.processed_urls
        competitor.last_sync_url_limit = run.url_limit
        competitor.last_sync_processed_extraction_pages = run.processed_extraction_pages
        competitor.last_sync_total_extractable_pages = run.total_extractable_pages
        competitor.last_sync_summary_json = run.summary_json
        session.flush()
        logger.info(
            "competitor_sync.run_done site_id=%s competitor_id=%s run_id=%s processed_urls=%s extraction_pages=%s",
            site_id,
            competitor_id,
            run_id,
            run.processed_urls,
            run.processed_extraction_pages,
        )


def fail_sync_run(
    site_id: int,
    competitor_id: int,
    run_id: int,
    *,
    error_code: str,
    error_message_safe: str,
    summary_payload: dict[str, Any] | None = None,
    processed_urls: int | None = None,
    url_limit: int | None = None,
    processed_extraction_pages: int | None = None,
    total_extractable_pages: int | None = None,
) -> None:
    with _session_scope() as session:
        run = _get_run_or_none(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
        if run is None or run.status not in SYNC_RUN_ACTIVE_STATUSES:
            return

        now = utcnow()
        run.status = "failed"
        run.stage = "failed"
        run.finished_at = now
        run.last_heartbeat_at = now
        run.lease_expires_at = now
        run.error_code = (error_code or "sync_failed")[:64]
        run.error_message_safe = _trim_safe_message(error_message_safe)
        if processed_urls is not None:
            run.processed_urls = max(0, int(processed_urls))
        if url_limit is not None:
            run.url_limit = max(0, int(url_limit))
        if processed_extraction_pages is not None:
            run.processed_extraction_pages = max(0, int(processed_extraction_pages))
        if total_extractable_pages is not None:
            run.total_extractable_pages = max(0, int(total_extractable_pages))
        if summary_payload is not None:
            run.summary_json = _normalize_summary_payload(summary_payload)

        competitor = _get_competitor_or_raise(session, site_id, competitor_id)
        competitor.last_sync_run_id = run_id
        competitor.last_sync_status = "failed"
        competitor.last_sync_stage = "failed"
        competitor.last_sync_finished_at = now
        competitor.last_sync_error_code = run.error_code
        competitor.last_sync_error = run.error_message_safe
        competitor.last_sync_processed_urls = run.processed_urls
        competitor.last_sync_url_limit = run.url_limit
        competitor.last_sync_processed_extraction_pages = run.processed_extraction_pages
        competitor.last_sync_total_extractable_pages = run.total_extractable_pages
        competitor.last_sync_summary_json = _normalize_summary_payload(run.summary_json)
        session.flush()
        logger.warning(
            "competitor_sync.run_failed site_id=%s competitor_id=%s run_id=%s error_code=%s",
            site_id,
            competitor_id,
            run_id,
            run.error_code,
        )
def reset_sync_runtime(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    url_limit: int,
) -> dict[str, Any]:
    reconcile_stale_sync_runs(session, site_id=site_id, competitor_id=competitor_id)
    competitor = _get_competitor_or_raise(session, site_id, competitor_id)
    active_run = _get_active_run(session, site_id=site_id, competitor_id=competitor_id)
    now = utcnow()

    if active_run is not None:
        active_run.status = "cancelled"
        active_run.stage = "cancelled"
        active_run.finished_at = now
        active_run.last_heartbeat_at = now
        active_run.lease_expires_at = now
        active_run.error_code = CANCELLED_RUN_ERROR_CODE
        active_run.error_message_safe = CANCELLED_RUN_ERROR_MESSAGE
        logger.warning(
            "competitor_sync.run_cancelled site_id=%s competitor_id=%s run_id=%s",
            site_id,
            competitor_id,
            active_run.run_id,
        )

    competitor.last_sync_status = "idle"
    competitor.last_sync_stage = "idle"
    competitor.last_sync_started_at = None
    competitor.last_sync_finished_at = None
    competitor.last_sync_error_code = None
    competitor.last_sync_error = None
    competitor.last_sync_processed_urls = 0
    competitor.last_sync_url_limit = max(0, int(url_limit))
    competitor.last_sync_processed_extraction_pages = 0
    competitor.last_sync_total_extractable_pages = 0
    competitor.last_sync_summary_json = _build_empty_summary_payload()
    session.flush()
    return serialize_sync_run(active_run) if active_run is not None else {}


def retry_last_sync_run(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    trigger_source: str,
    url_limit: int,
) -> dict[str, Any]:
    reconcile_stale_sync_runs(session, site_id=site_id, competitor_id=competitor_id)
    latest_retryable = session.scalars(
        select(SiteCompetitorSyncRun)
        .where(
            SiteCompetitorSyncRun.site_id == site_id,
            SiteCompetitorSyncRun.competitor_id == competitor_id,
            SiteCompetitorSyncRun.status.in_(tuple(SYNC_RUN_RETRYABLE_STATUSES)),
        )
        .order_by(SiteCompetitorSyncRun.id.desc())
        .limit(1)
    ).first()
    if latest_retryable is None:
        raise CompetitiveGapSyncRunServiceError(
            "No failed or stale competitor sync run is available for retry.",
            code="not_retryable",
        )
    return queue_sync_run(
        session,
        site_id=site_id,
        competitor_id=competitor_id,
        trigger_source=trigger_source,
        url_limit=url_limit,
        retry_of_run_id=latest_retryable.run_id,
    )


def list_sync_runs(
    session: Session,
    *,
    site_id: int,
    competitor_id: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if reconcile_stale_sync_runs(session, site_id=site_id, competitor_id=competitor_id):
        session.commit()
    _get_competitor_or_raise(session, site_id, competitor_id)
    runs = session.scalars(
        select(SiteCompetitorSyncRun)
        .where(
            SiteCompetitorSyncRun.site_id == site_id,
            SiteCompetitorSyncRun.competitor_id == competitor_id,
        )
        .order_by(SiteCompetitorSyncRun.id.desc())
        .limit(max(1, min(int(limit), 25)))
    ).all()
    return [serialize_sync_run(run) for run in runs]


def is_sync_run_active(session: Session, *, site_id: int, competitor_id: int, run_id: int) -> bool:
    run = _get_run_or_none(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
    return run is not None and run.status in SYNC_RUN_ACTIVE_STATUSES


def reconcile_stale_sync_runs(
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
        select(SiteCompetitorSyncRun)
        .where(
            SiteCompetitorSyncRun.site_id == site_id,
            SiteCompetitorSyncRun.competitor_id.in_(competitor_ids),
            SiteCompetitorSyncRun.status.in_(tuple(SYNC_RUN_ACTIVE_STATUSES)),
        )
        .order_by(SiteCompetitorSyncRun.id.asc())
    ).all()

    active_run_by_competitor_and_run_id = {
        (run.competitor_id, run.run_id): run
        for run in active_runs
    }
    touched = 0

    for run in active_runs:
        lease_expired = False
        if run.lease_expires_at is not None:
            lease_expired = _coerce_utc_datetime(run.lease_expires_at) <= now
        if not lease_expired:
            continue
        _mark_run_stale(session, run, now=now)
        competitor = next((item for item in competitors if item.id == run.competitor_id), None)
        if competitor is not None and competitor.last_sync_status in SYNC_RUN_ACTIVE_STATUSES and competitor.last_sync_run_id == run.run_id:
            _mark_competitor_runtime_stale(competitor, run=run, now=now)
        touched += 1

    for competitor in competitors:
        if competitor.last_sync_status not in SYNC_RUN_ACTIVE_STATUSES:
            continue
        expected_run = active_run_by_competitor_and_run_id.get((competitor.id, competitor.last_sync_run_id))
        if expected_run is not None:
            continue
        competitor.last_sync_status = "failed"
        competitor.last_sync_stage = "failed"
        competitor.last_sync_finished_at = now
        competitor.last_sync_error_code = STALE_RUN_ERROR_CODE
        competitor.last_sync_error = STALE_RUN_ERROR_MESSAGE
        touched += 1

    if touched:
        session.flush()
    return touched


def serialize_sync_run(run: SiteCompetitorSyncRun) -> dict[str, Any]:
    summary_payload = _normalize_summary_payload(run.summary_json)
    return {
        "id": run.id,
        "site_id": run.site_id,
        "competitor_id": run.competitor_id,
        "run_id": run.run_id,
        "status": run.status,
        "stage": run.stage,
        "trigger_source": run.trigger_source,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "last_heartbeat_at": run.last_heartbeat_at,
        "lease_expires_at": run.lease_expires_at,
        "error_code": run.error_code,
        "error_message_safe": run.error_message_safe,
        "summary_json": summary_payload,
        "retry_of_run_id": run.retry_of_run_id,
        "processed_urls": run.processed_urls,
        "url_limit": run.url_limit,
        "processed_extraction_pages": run.processed_extraction_pages,
        "total_extractable_pages": run.total_extractable_pages,
        "progress_percent": _compute_progress_percent(run),
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _mark_run_stale(session: Session, run: SiteCompetitorSyncRun, *, now) -> None:
    run.status = "stale"
    run.stage = "stale"
    run.finished_at = now
    run.last_heartbeat_at = now
    run.lease_expires_at = now
    run.error_code = STALE_RUN_ERROR_CODE
    run.error_message_safe = STALE_RUN_ERROR_MESSAGE
    logger.warning(
        "competitor_sync.run_stale site_id=%s competitor_id=%s run_id=%s",
        run.site_id,
        run.competitor_id,
        run.run_id,
    )


def _mark_competitor_runtime_stale(competitor: SiteCompetitor, *, run: SiteCompetitorSyncRun, now) -> None:
    competitor.last_sync_status = "failed"
    competitor.last_sync_stage = "failed"
    competitor.last_sync_finished_at = now
    competitor.last_sync_error_code = run.error_code
    competitor.last_sync_error = run.error_message_safe
    competitor.last_sync_processed_urls = run.processed_urls
    competitor.last_sync_url_limit = run.url_limit
    competitor.last_sync_processed_extraction_pages = run.processed_extraction_pages
    competitor.last_sync_total_extractable_pages = run.total_extractable_pages
    competitor.last_sync_summary_json = _normalize_summary_payload(run.summary_json)


def _compute_progress_percent(run: SiteCompetitorSyncRun) -> int:
    if run.status == "done":
        return 100
    if run.stage == "extracting" and run.total_extractable_pages > 0:
        return int(round(min(100, (run.processed_extraction_pages / run.total_extractable_pages) * 100)))
    if run.url_limit > 0:
        return int(round(min(100, (run.processed_urls / run.url_limit) * 100)))
    return 0


def _lease_expires_at(reference=None):
    current = reference or utcnow()
    return current + timedelta(seconds=DEFAULT_SYNC_LEASE_SECONDS)


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
        raise CompetitiveGapSyncRunServiceError(
            f"Competitor {competitor_id} not found for site {site_id}.",
            code="not_found",
        )
    return competitor


def _get_run_or_none(session: Session, *, site_id: int, competitor_id: int, run_id: int) -> SiteCompetitorSyncRun | None:
    return session.scalars(
        select(SiteCompetitorSyncRun)
        .where(
            SiteCompetitorSyncRun.site_id == site_id,
            SiteCompetitorSyncRun.competitor_id == competitor_id,
            SiteCompetitorSyncRun.run_id == run_id,
        )
        .limit(1)
    ).first()


def _get_run_or_raise(session: Session, *, site_id: int, competitor_id: int, run_id: int) -> SiteCompetitorSyncRun:
    run = _get_run_or_none(session, site_id=site_id, competitor_id=competitor_id, run_id=run_id)
    if run is None:
        raise CompetitiveGapSyncRunServiceError(
            f"Competitor sync run {run_id} not found for competitor {competitor_id}.",
            code="not_found",
        )
    return run


def _get_active_run(session: Session, *, site_id: int, competitor_id: int) -> SiteCompetitorSyncRun | None:
    return session.scalars(
        select(SiteCompetitorSyncRun)
        .where(
            SiteCompetitorSyncRun.site_id == site_id,
            SiteCompetitorSyncRun.competitor_id == competitor_id,
            SiteCompetitorSyncRun.status.in_(tuple(SYNC_RUN_ACTIVE_STATUSES)),
        )
        .order_by(SiteCompetitorSyncRun.id.desc())
        .limit(1)
    ).first()


def _build_empty_summary_payload() -> dict[str, Any]:
    from app.services import site_competitor_service

    return site_competitor_service.build_empty_sync_summary_payload()


def _normalize_summary_payload(payload: Any) -> dict[str, Any]:
    from app.services import site_competitor_service

    return site_competitor_service.normalize_sync_summary_payload(payload)


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
