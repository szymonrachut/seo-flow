from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.crawler.normalization.urls import extract_registered_domain, normalize_url
from app.db.models import CrawlJob, CrawlJobStatus, Link, Page, Site
from app.db.session import SessionLocal

PAGE_SORT_COLUMNS = {
    "url": Page.url,
    "status_code": Page.status_code,
    "depth": Page.depth,
    "title": Page.title,
    "fetched_at": Page.fetched_at,
    "response_time_ms": Page.response_time_ms,
}

LINK_SORT_COLUMNS = {
    "source_url": Link.source_url,
    "target_url": Link.target_url,
    "target_domain": Link.target_domain,
    "is_internal": Link.is_internal,
    "is_nofollow": Link.is_nofollow,
}


def _text_missing_condition(field):
    return or_(field.is_(None), func.trim(field) == "")


def _non_indexable_like_condition():
    status_signal = and_(Page.status_code.is_not(None), or_(Page.status_code < 200, Page.status_code >= 300))
    robots_signal = func.lower(func.coalesce(Page.robots_meta, "")).like("%noindex%")
    return or_(status_signal, robots_signal)


def _resolve_presence_filter(
    *,
    has_value: bool | None,
    missing_value: bool | None,
    field_name: str,
) -> bool | None:
    if has_value is not None and missing_value is not None and has_value == missing_value:
        raise ValueError(f"Conflicting filters for {field_name}: has_* and missing_* do not match.")
    if has_value is not None:
        return has_value
    if missing_value is not None:
        return not missing_value
    return None


def _apply_sort(stmt, *, sort_column, sort_order: str, tie_breaker_column):
    if sort_order == "desc":
        return stmt.order_by(sort_column.desc(), tie_breaker_column.desc())
    return stmt.order_by(sort_column.asc(), tie_breaker_column.asc())


def validate_crawl_limits(max_urls: int, max_depth: int, delay: float) -> None:
    if max_urls < 1:
        raise ValueError("max_urls must be >= 1")
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    if delay < 0:
        raise ValueError("delay must be >= 0")


def normalize_start_url_or_raise(start_url: str) -> tuple[str, str]:
    normalized_start_url = normalize_url(start_url)
    if normalized_start_url is None:
        raise ValueError("Start URL must be a valid HTTP or HTTPS URL.")

    registered_domain = extract_registered_domain(normalized_start_url)
    if not registered_domain:
        raise ValueError("Could not determine domain from start URL.")

    return normalized_start_url, registered_domain


def get_or_create_site(session: Session, start_url: str, domain: str) -> Site:
    site = session.scalar(select(Site).where(Site.domain == domain))
    if site:
        return site

    site = Site(root_url=start_url, domain=domain)
    session.add(site)
    session.flush()
    return site


def create_crawl_job(
    session: Session,
    root_url: str,
    max_urls: int,
    max_depth: int,
    delay: float,
) -> CrawlJob:
    validate_crawl_limits(max_urls=max_urls, max_depth=max_depth, delay=delay)
    normalized_start_url, registered_domain = normalize_start_url_or_raise(root_url)

    site = get_or_create_site(session, normalized_start_url, registered_domain)
    crawl_job = CrawlJob(
        site_id=site.id,
        status=CrawlJobStatus.PENDING,
        settings_json={
            "start_url": normalized_start_url,
            "max_urls": max_urls,
            "max_depth": max_depth,
            "request_delay": delay,
        },
        stats_json={},
    )
    session.add(crawl_job)
    session.flush()
    return crawl_job


def prepare_existing_crawl_job(
    session: Session,
    crawl_job_id: int,
    root_url: str,
    max_urls: int,
    max_depth: int,
    delay: float,
) -> tuple[CrawlJob, str, str]:
    validate_crawl_limits(max_urls=max_urls, max_depth=max_depth, delay=delay)
    normalized_start_url, registered_domain = normalize_start_url_or_raise(root_url)

    crawl_job = session.get(CrawlJob, crawl_job_id)
    if crawl_job is None:
        raise RuntimeError(f"Crawl job {crawl_job_id} not found.")
    if crawl_job.status == CrawlJobStatus.STOPPED:
        raise RuntimeError(f"Crawl job {crawl_job_id} is stopped and cannot be resumed.")

    site = session.get(Site, crawl_job.site_id)
    if site is None:
        raise RuntimeError(f"Site for crawl job {crawl_job_id} not found.")

    if site.domain != registered_domain:
        raise ValueError(
            f"Crawl job {crawl_job_id} belongs to domain '{site.domain}', "
            f"but got URL for domain '{registered_domain}'."
        )

    crawl_job.status = CrawlJobStatus.PENDING
    crawl_job.started_at = None
    crawl_job.finished_at = None
    crawl_job.stats_json = {}
    crawl_job.settings_json = {
        "start_url": normalized_start_url,
        "max_urls": max_urls,
        "max_depth": max_depth,
        "request_delay": delay,
    }
    session.flush()
    return crawl_job, normalized_start_url, registered_domain


def get_crawl_job(session: Session, crawl_job_id: int) -> CrawlJob | None:
    return session.get(CrawlJob, crawl_job_id)


def list_crawl_jobs(
    session: Session,
    *,
    sort_by: str = "id",
    sort_order: str = "desc",
    limit: int = 100,
) -> list[dict[str, Any]]:
    sort_column = CrawlJob.id if sort_by == "id" else CrawlJob.created_at
    stmt = select(CrawlJob, Site).join(Site, Site.id == CrawlJob.site_id)
    stmt = _apply_sort(stmt, sort_column=sort_column, sort_order=sort_order, tie_breaker_column=CrawlJob.id)
    stmt = stmt.limit(limit)

    jobs: list[dict[str, Any]] = []
    for crawl_job, site in session.execute(stmt).all():
        stats = get_crawl_job_stats(session, crawl_job.id)
        root_url = None
        if isinstance(crawl_job.settings_json, dict):
            root_url = crawl_job.settings_json.get("start_url")
        if not root_url:
            root_url = site.root_url

        jobs.append(
            {
                "id": crawl_job.id,
                "status": crawl_job.status.value if isinstance(crawl_job.status, CrawlJobStatus) else str(crawl_job.status),
                "root_url": root_url,
                "created_at": crawl_job.created_at,
                "started_at": crawl_job.started_at,
                "finished_at": crawl_job.finished_at,
                "total_pages": stats["total_pages"],
                "total_internal_links": stats["total_internal_links"],
                "total_external_links": stats["total_external_links"],
                "total_errors": stats["total_errors"],
            }
        )

    return jobs


def get_pages_for_job(
    session: Session,
    crawl_job_id: int,
    *,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "url",
    sort_order: str = "asc",
    missing_title: bool | None = None,
    missing_meta_description: bool | None = None,
    missing_h1: bool | None = None,
    has_title: bool | None = None,
    has_meta_description: bool | None = None,
    has_h1: bool | None = None,
    status_code: int | None = None,
    status_code_min: int | None = None,
    status_code_max: int | None = None,
    canonical_missing: bool | None = None,
    robots_meta_contains: str | None = None,
    non_indexable_like: bool | None = None,
) -> tuple[list[Page], int]:
    resolved_has_title = _resolve_presence_filter(
        has_value=has_title,
        missing_value=missing_title,
        field_name="title",
    )
    resolved_has_meta = _resolve_presence_filter(
        has_value=has_meta_description,
        missing_value=missing_meta_description,
        field_name="meta_description",
    )
    resolved_has_h1 = _resolve_presence_filter(
        has_value=has_h1,
        missing_value=missing_h1,
        field_name="h1",
    )

    conditions = [Page.crawl_job_id == crawl_job_id]

    if resolved_has_title is not None:
        condition = _text_missing_condition(Page.title)
        conditions.append(~condition if resolved_has_title else condition)

    if resolved_has_meta is not None:
        condition = _text_missing_condition(Page.meta_description)
        conditions.append(~condition if resolved_has_meta else condition)

    if resolved_has_h1 is not None:
        condition = _text_missing_condition(Page.h1)
        conditions.append(~condition if resolved_has_h1 else condition)

    if status_code is not None:
        conditions.append(Page.status_code == status_code)
    if status_code_min is not None:
        conditions.append(Page.status_code.is_not(None))
        conditions.append(Page.status_code >= status_code_min)
    if status_code_max is not None:
        conditions.append(Page.status_code.is_not(None))
        conditions.append(Page.status_code <= status_code_max)

    if canonical_missing is not None:
        condition = _text_missing_condition(Page.canonical_url)
        conditions.append(condition if canonical_missing else ~condition)

    if robots_meta_contains:
        token = robots_meta_contains.strip().lower()
        if token:
            conditions.append(func.lower(func.coalesce(Page.robots_meta, "")).like(f"%{token}%"))

    if non_indexable_like is not None:
        condition = _non_indexable_like_condition()
        conditions.append(condition if non_indexable_like else ~condition)

    total_items = session.scalar(select(func.count(Page.id)).where(*conditions)) or 0

    sort_column = PAGE_SORT_COLUMNS.get(sort_by, Page.url)
    stmt = select(Page).where(*conditions)
    stmt = _apply_sort(stmt, sort_column=sort_column, sort_order=sort_order, tie_breaker_column=Page.id)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    return list(session.scalars(stmt).all()), int(total_items)


def get_links_for_job(
    session: Session,
    crawl_job_id: int,
    *,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "source_url",
    sort_order: str = "asc",
    is_internal: bool | None = None,
    is_nofollow: bool | None = None,
    target_domain: str | None = None,
    has_anchor: bool | None = None,
) -> tuple[list[Link], int]:
    conditions = [Link.crawl_job_id == crawl_job_id]

    if is_internal is not None:
        conditions.append(Link.is_internal.is_(is_internal))

    if is_nofollow is not None:
        conditions.append(Link.is_nofollow.is_(is_nofollow))

    if target_domain:
        conditions.append(func.lower(func.coalesce(Link.target_domain, "")) == target_domain.strip().lower())

    if has_anchor is not None:
        condition = _text_missing_condition(Link.anchor_text)
        conditions.append(~condition if has_anchor else condition)

    total_items = session.scalar(select(func.count(Link.id)).where(*conditions)) or 0

    sort_column = LINK_SORT_COLUMNS.get(sort_by, Link.source_url)
    stmt = select(Link).where(*conditions)
    stmt = _apply_sort(stmt, sort_column=sort_column, sort_order=sort_order, tie_breaker_column=Link.id)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    return list(session.scalars(stmt).all()), int(total_items)


def get_crawl_job_stats(session: Session, crawl_job_id: int) -> dict[str, int]:
    total_pages = session.scalar(select(func.count(Page.id)).where(Page.crawl_job_id == crawl_job_id)) or 0
    total_internal_links = (
        session.scalar(select(func.count(Link.id)).where(Link.crawl_job_id == crawl_job_id, Link.is_internal.is_(True)))
        or 0
    )
    total_external_links = (
        session.scalar(select(func.count(Link.id)).where(Link.crawl_job_id == crawl_job_id, Link.is_internal.is_(False)))
        or 0
    )
    total_errors = (
        session.scalar(
            select(func.count(Page.id)).where(
                Page.crawl_job_id == crawl_job_id,
                or_(Page.error_message.is_not(None), Page.status_code >= 400),
            )
        )
        or 0
    )
    return {
        "total_pages": int(total_pages),
        "total_internal_links": int(total_internal_links),
        "total_external_links": int(total_external_links),
        "total_errors": int(total_errors),
    }


def get_crawl_job_progress(
    session: Session,
    crawl_job_id: int,
    *,
    status: CrawlJobStatus | str | None,
) -> dict[str, int]:
    visited_pages = session.scalar(select(func.count(Page.id)).where(Page.crawl_job_id == crawl_job_id)) or 0
    discovered_links = session.scalar(select(func.count(Link.id)).where(Link.crawl_job_id == crawl_job_id)) or 0
    internal_links = (
        session.scalar(select(func.count(Link.id)).where(Link.crawl_job_id == crawl_job_id, Link.is_internal.is_(True)))
        or 0
    )
    external_links = (
        session.scalar(select(func.count(Link.id)).where(Link.crawl_job_id == crawl_job_id, Link.is_internal.is_(False)))
        or 0
    )
    errors_count = (
        session.scalar(
            select(func.count(Page.id)).where(
                Page.crawl_job_id == crawl_job_id,
                or_(Page.error_message.is_not(None), Page.status_code >= 400),
            )
        )
        or 0
    )

    status_value = status.value if isinstance(status, CrawlJobStatus) else (str(status) if status is not None else "")
    terminal_statuses = {CrawlJobStatus.FINISHED.value, CrawlJobStatus.FAILED.value, CrawlJobStatus.STOPPED.value}
    if status_value in terminal_statuses:
        queued_urls = 0
    else:
        target_page = aliased(Page)
        queued_urls = (
            session.scalar(
                select(func.count(func.distinct(Link.target_normalized_url)))
                .select_from(Link)
                .outerjoin(
                    target_page,
                    and_(
                        target_page.crawl_job_id == Link.crawl_job_id,
                        target_page.normalized_url == Link.target_normalized_url,
                    ),
                )
                .where(
                    Link.crawl_job_id == crawl_job_id,
                    Link.is_internal.is_(True),
                    Link.target_normalized_url.is_not(None),
                    target_page.id.is_(None),
                )
            )
            or 0
        )

    return {
        "visited_pages": int(visited_pages),
        "queued_urls": int(queued_urls),
        "discovered_links": int(discovered_links),
        "internal_links": int(internal_links),
        "external_links": int(external_links),
        "errors_count": int(errors_count),
    }


def get_crawl_job_summary_counts(session: Session, crawl_job_id: int) -> dict[str, int]:
    from app.services.audit_service import build_audit_report

    total_pages = session.scalar(select(func.count(Page.id)).where(Page.crawl_job_id == crawl_job_id)) or 0
    total_links = session.scalar(select(func.count(Link.id)).where(Link.crawl_job_id == crawl_job_id)) or 0
    total_internal_links = (
        session.scalar(select(func.count(Link.id)).where(Link.crawl_job_id == crawl_job_id, Link.is_internal.is_(True)))
        or 0
    )
    total_external_links = (
        session.scalar(select(func.count(Link.id)).where(Link.crawl_job_id == crawl_job_id, Link.is_internal.is_(False)))
        or 0
    )

    missing_title = session.scalar(
        select(func.count(Page.id)).where(Page.crawl_job_id == crawl_job_id, _text_missing_condition(Page.title))
    ) or 0
    missing_meta_description = session.scalar(
        select(func.count(Page.id)).where(Page.crawl_job_id == crawl_job_id, _text_missing_condition(Page.meta_description))
    ) or 0
    missing_h1 = (
        session.scalar(select(func.count(Page.id)).where(Page.crawl_job_id == crawl_job_id, _text_missing_condition(Page.h1)))
        or 0
    )
    non_indexable_like = session.scalar(
        select(func.count(Page.id)).where(Page.crawl_job_id == crawl_job_id, _non_indexable_like_condition())
    ) or 0

    audit_summary = build_audit_report(session, crawl_job_id)["summary"]

    return {
        "total_pages": int(total_pages),
        "total_links": int(total_links),
        "total_internal_links": int(total_internal_links),
        "total_external_links": int(total_external_links),
        "pages_missing_title": int(missing_title),
        "pages_missing_meta_description": int(missing_meta_description),
        "pages_missing_h1": int(missing_h1),
        "pages_non_indexable_like": int(non_indexable_like),
        "broken_internal_links": int(audit_summary["broken_internal_links"]),
        "redirecting_internal_links": int(audit_summary["redirecting_internal_links"]),
    }


def build_crawl_job_detail(session: Session, crawl_job: CrawlJob) -> dict[str, Any]:
    status_value = crawl_job.status.value if isinstance(crawl_job.status, CrawlJobStatus) else str(crawl_job.status)
    return {
        "id": crawl_job.id,
        "site_id": crawl_job.site_id,
        "status": status_value,
        "created_at": crawl_job.created_at,
        "started_at": crawl_job.started_at,
        "finished_at": crawl_job.finished_at,
        "settings_json": crawl_job.settings_json or {},
        "stats_json": crawl_job.stats_json or {},
        "summary_counts": get_crawl_job_summary_counts(session, crawl_job.id),
        "progress": get_crawl_job_progress(session, crawl_job.id, status=status_value),
    }


def stop_crawl_job(session: Session, crawl_job_id: int) -> CrawlJob | None:
    crawl_job = session.get(CrawlJob, crawl_job_id)
    if crawl_job is None:
        return None
    if crawl_job.status in {CrawlJobStatus.FINISHED, CrawlJobStatus.FAILED, CrawlJobStatus.STOPPED}:
        return crawl_job

    crawl_job.status = CrawlJobStatus.STOPPED
    crawl_job.finished_at = datetime.now(timezone.utc)
    stats = crawl_job.stats_json if isinstance(crawl_job.stats_json, dict) else {}
    stats["stop_requested"] = True
    crawl_job.stats_json = stats
    session.flush()
    return crawl_job


def mark_crawl_job_failed(crawl_job_id: int, error: str) -> None:
    with SessionLocal() as session:
        crawl_job = session.get(CrawlJob, crawl_job_id)
        if crawl_job is None:
            return
        if crawl_job.status == CrawlJobStatus.STOPPED:
            return
        crawl_job.status = CrawlJobStatus.FAILED
        crawl_job.finished_at = datetime.now(timezone.utc)
        stats = crawl_job.stats_json if isinstance(crawl_job.stats_json, dict) else {}
        stats["error"] = error
        crawl_job.stats_json = stats
        session.commit()


def run_crawl_job_subprocess(
    crawl_job_id: int,
    *,
    root_url: str,
    max_urls: int,
    max_depth: int,
    delay: float,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        "-m",
        "app.cli.run_crawl",
        root_url,
        "--max-urls",
        str(max_urls),
        "--max-depth",
        str(max_depth),
        "--delay",
        str(delay),
        "--job-id",
        str(crawl_job_id),
    ]

    try:
        subprocess.Popen(  # noqa: S603
            command,
            cwd=str(project_root),
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        mark_crawl_job_failed(crawl_job_id, f"subprocess_error: {exc}")


def resolve_link_targets_for_job(session: Session, crawl_job_id: int):
    target_page = aliased(Page)
    stmt = (
        select(Link, target_page)
        .outerjoin(
            target_page,
            and_(
                target_page.crawl_job_id == Link.crawl_job_id,
                target_page.normalized_url == Link.target_normalized_url,
            ),
        )
        .where(Link.crawl_job_id == crawl_job_id, Link.is_internal.is_(True))
        .order_by(Link.id.asc())
    )
    return session.execute(stmt).all()
