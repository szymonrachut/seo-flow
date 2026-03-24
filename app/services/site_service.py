from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CrawlJob, CrawlJobStatus, Site
from app.services import crawl_job_service


class SiteServiceError(RuntimeError):
    pass


def list_sites(session: Session) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    sites = session.scalars(select(Site).order_by(Site.created_at.desc(), Site.id.desc())).all()
    for site in sites:
        crawl_jobs = _load_site_crawl_jobs(session, site.id)
        items.append(
            {
                "id": site.id,
                "domain": site.domain,
                "root_url": site.root_url,
                "created_at": site.created_at,
                "selected_gsc_property_uri": site.gsc_property.property_uri if site.gsc_property else None,
                "summary": _build_site_summary(crawl_jobs),
                "latest_crawl": _serialize_site_crawl(session, crawl_jobs[0], site) if crawl_jobs else None,
            }
        )

    items.sort(
        key=lambda item: (
            item["summary"]["last_crawl_at"] or item["created_at"],
            item["id"],
        ),
        reverse=True,
    )
    return items


def build_site_detail(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
    baseline_crawl_id: int | None = None,
) -> dict[str, Any]:
    context = resolve_site_workspace_context(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        baseline_crawl_id=baseline_crawl_id,
    )
    site = context["site"]
    crawl_jobs = context["crawl_jobs"]
    active_crawl = context["active_crawl"]
    baseline_crawl = context["baseline_crawl"]

    return {
        "id": site.id,
        "domain": site.domain,
        "root_url": site.root_url,
        "created_at": site.created_at,
        "selected_gsc_property_uri": site.gsc_property.property_uri if site.gsc_property else None,
        "selected_gsc_property_permission_level": site.gsc_property.permission_level if site.gsc_property else None,
        "summary": _build_site_summary(crawl_jobs),
        "active_crawl_id": active_crawl.id if active_crawl else None,
        "baseline_crawl_id": baseline_crawl.id if baseline_crawl else None,
        "active_crawl": (
            crawl_job_service.build_crawl_job_detail(session, active_crawl)
            if active_crawl is not None
            else None
        ),
        "baseline_crawl": (
            crawl_job_service.build_crawl_job_detail(session, baseline_crawl)
            if baseline_crawl is not None
            else None
        ),
        "crawl_history": [_serialize_site_crawl(session, crawl_job, site) for crawl_job in crawl_jobs],
    }


def resolve_site_workspace_context(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
    baseline_crawl_id: int | None = None,
) -> dict[str, Any]:
    site = _get_site_or_raise(session, site_id)
    crawl_jobs = _load_site_crawl_jobs(session, site.id)
    active_crawl = _resolve_active_crawl(crawl_jobs, active_crawl_id=active_crawl_id)
    baseline_crawl = _resolve_baseline_crawl(
        crawl_jobs,
        active_crawl=active_crawl,
        baseline_crawl_id=baseline_crawl_id,
    )
    return {
        "site": site,
        "crawl_jobs": crawl_jobs,
        "active_crawl": active_crawl,
        "baseline_crawl": baseline_crawl,
    }


def list_site_crawls(session: Session, site_id: int) -> list[dict[str, Any]]:
    site = _get_site_or_raise(session, site_id)
    crawl_jobs = _load_site_crawl_jobs(session, site.id)
    return [_serialize_site_crawl(session, crawl_job, site) for crawl_job in crawl_jobs]


def _load_site_crawl_jobs(session: Session, site_id: int) -> list[CrawlJob]:
    return session.scalars(
        select(CrawlJob)
        .where(CrawlJob.site_id == site_id)
        .order_by(CrawlJob.created_at.desc(), CrawlJob.id.desc())
    ).all()


def _serialize_site_crawl(session: Session, crawl_job: CrawlJob, site: Site) -> dict[str, Any]:
    stats = crawl_job_service.get_crawl_job_stats(session, crawl_job.id)
    settings = crawl_job.settings_json if isinstance(crawl_job.settings_json, dict) else {}
    root_url = settings.get("start_url") or site.root_url
    status_value = crawl_job.status.value if isinstance(crawl_job.status, CrawlJobStatus) else str(crawl_job.status)
    return {
        "id": crawl_job.id,
        "site_id": crawl_job.site_id,
        "status": status_value,
        "root_url": root_url,
        "created_at": crawl_job.created_at,
        "started_at": crawl_job.started_at,
        "finished_at": crawl_job.finished_at,
        "total_pages": stats["total_pages"],
        "total_internal_links": stats["total_internal_links"],
        "total_external_links": stats["total_external_links"],
        "total_errors": stats["total_errors"],
    }


def _build_site_summary(crawl_jobs: Sequence[CrawlJob]) -> dict[str, Any]:
    statuses = [
        crawl_job.status.value if isinstance(crawl_job.status, CrawlJobStatus) else str(crawl_job.status)
        for crawl_job in crawl_jobs
    ]
    return {
        "total_crawls": len(crawl_jobs),
        "pending_crawls": sum(1 for status in statuses if status == CrawlJobStatus.PENDING.value),
        "running_crawls": sum(1 for status in statuses if status == CrawlJobStatus.RUNNING.value),
        "finished_crawls": sum(1 for status in statuses if status == CrawlJobStatus.FINISHED.value),
        "failed_crawls": sum(1 for status in statuses if status == CrawlJobStatus.FAILED.value),
        "stopped_crawls": sum(1 for status in statuses if status == CrawlJobStatus.STOPPED.value),
        "first_crawl_at": crawl_jobs[-1].created_at if crawl_jobs else None,
        "last_crawl_at": crawl_jobs[0].created_at if crawl_jobs else None,
    }


def _resolve_active_crawl(crawl_jobs: Sequence[CrawlJob], *, active_crawl_id: int | None) -> CrawlJob | None:
    if not crawl_jobs:
        return None
    if active_crawl_id is None:
        return crawl_jobs[0]

    for crawl_job in crawl_jobs:
        if crawl_job.id == active_crawl_id:
            return crawl_job
    raise SiteServiceError(f"Active crawl {active_crawl_id} does not belong to the requested site.")


def _resolve_baseline_crawl(
    crawl_jobs: Sequence[CrawlJob],
    *,
    active_crawl: CrawlJob | None,
    baseline_crawl_id: int | None,
) -> CrawlJob | None:
    if active_crawl is None:
        return None

    candidates = [crawl_job for crawl_job in crawl_jobs if crawl_job.id != active_crawl.id]
    if baseline_crawl_id is None:
        older_candidates = [
            crawl_job
            for crawl_job in candidates
            if crawl_job.created_at <= active_crawl.created_at
        ]
        if older_candidates:
            return older_candidates[0]
        return candidates[0] if candidates else None

    if baseline_crawl_id == active_crawl.id:
        raise SiteServiceError("Baseline crawl must be different from the active crawl.")

    for crawl_job in candidates:
        if crawl_job.id == baseline_crawl_id:
            return crawl_job
    raise SiteServiceError(f"Baseline crawl {baseline_crawl_id} does not belong to the requested site.")


def _get_site_or_raise(session: Session, site_id: int) -> Site:
    site = crawl_job_service.get_site(session, site_id)
    if site is None:
        raise SiteServiceError(f"Site {site_id} not found.")
    return site
