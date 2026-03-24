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
from app.services import cannibalization_service, priority_service
from app.services.seo_analysis import build_link_records, build_page_records, text_value_missing

RENDER_MODES = {"never", "auto", "always"}
GSC_DATE_RANGE_SUFFIX = {
    "last_28_days": "28d",
    "last_90_days": "90d",
}


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


def _normalize_python_sort_value(value: Any) -> tuple[int, Any]:
    if value is None:
        return (1, "")
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, str):
        return (0, value.lower())
    return (0, value)


def _sort_python_records(records: list[dict[str, Any]], *, sort_by: str, sort_order: str) -> None:
    present_records = [record for record in records if not text_value_missing(record.get(sort_by))]
    missing_records = [record for record in records if text_value_missing(record.get(sort_by))]

    present_records.sort(
        key=lambda item: (
            _normalize_python_sort_value(item.get(sort_by)),
            _normalize_python_sort_value(item.get("id")),
        ),
        reverse=sort_order == "desc",
    )
    missing_records.sort(key=lambda item: _normalize_python_sort_value(item.get("id")))
    records[:] = present_records + missing_records


def _resolve_gsc_suffix(gsc_date_range: str) -> str:
    suffix = GSC_DATE_RANGE_SUFFIX.get(gsc_date_range)
    if suffix is None:
        raise ValueError(f"Unsupported gsc_date_range '{gsc_date_range}'.")
    return suffix


def _resolve_page_sort_key(sort_by: str, gsc_date_range: str) -> str:
    if sort_by == "priority_score":
        return "priority_score"
    if not sort_by.startswith("gsc_"):
        return sort_by

    suffix = _resolve_gsc_suffix(gsc_date_range)
    mapping = {
        "gsc_clicks": f"clicks_{suffix}",
        "gsc_impressions": f"impressions_{suffix}",
        "gsc_ctr": f"ctr_{suffix}",
        "gsc_position": f"position_{suffix}",
        "gsc_top_queries_count": f"top_queries_count_{suffix}",
    }
    return mapping.get(sort_by, sort_by)


def validate_crawl_limits(max_urls: int, max_depth: int, delay: float) -> None:
    if max_urls < 1:
        raise ValueError("max_urls must be >= 1")
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    if delay < 0:
        raise ValueError("delay must be >= 0")


def validate_render_settings(render_mode: str, render_timeout_ms: int, max_rendered_pages_per_job: int) -> None:
    normalized_render_mode = str(render_mode).strip().lower()
    if normalized_render_mode not in RENDER_MODES:
        raise ValueError(f"render_mode must be one of: {', '.join(sorted(RENDER_MODES))}")
    if render_timeout_ms < 1:
        raise ValueError("render_timeout_ms must be >= 1")
    if max_rendered_pages_per_job < 1:
        raise ValueError("max_rendered_pages_per_job must be >= 1")


def build_crawl_settings(
    *,
    start_url: str,
    max_urls: int,
    max_depth: int,
    delay: float,
    render_mode: str,
    render_timeout_ms: int,
    max_rendered_pages_per_job: int,
) -> dict[str, Any]:
    return {
        "start_url": start_url,
        "max_urls": max_urls,
        "max_depth": max_depth,
        "delay": delay,
        "request_delay": delay,
        "render_mode": render_mode,
        "render_timeout_ms": render_timeout_ms,
        "max_rendered_pages_per_job": max_rendered_pages_per_job,
    }


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


def get_site(session: Session, site_id: int) -> Site | None:
    return session.get(Site, site_id)


def _create_pending_crawl_job(
    session: Session,
    *,
    site_id: int,
    normalized_start_url: str,
    max_urls: int,
    max_depth: int,
    delay: float,
    render_mode: str,
    render_timeout_ms: int,
    max_rendered_pages_per_job: int,
) -> CrawlJob:
    crawl_job = CrawlJob(
        site_id=site_id,
        status=CrawlJobStatus.PENDING,
        settings_json=build_crawl_settings(
            start_url=normalized_start_url,
            max_urls=max_urls,
            max_depth=max_depth,
            delay=delay,
            render_mode=render_mode,
            render_timeout_ms=render_timeout_ms,
            max_rendered_pages_per_job=max_rendered_pages_per_job,
        ),
        stats_json={},
    )
    session.add(crawl_job)
    session.flush()
    return crawl_job


def _resolve_site_for_new_crawl(
    session: Session,
    *,
    site_id: int | None,
    normalized_start_url: str,
    registered_domain: str,
) -> Site:
    if site_id is None:
        return get_or_create_site(session, normalized_start_url, registered_domain)

    site = session.get(Site, site_id)
    if site is None:
        raise ValueError(f"Site {site_id} not found.")
    if site.domain != registered_domain:
        raise ValueError(
            f"Site {site_id} belongs to domain '{site.domain}', but got URL for domain '{registered_domain}'."
        )
    return site


def create_crawl_job(
    session: Session,
    root_url: str,
    max_urls: int,
    max_depth: int,
    delay: float,
    *,
    render_mode: str,
    render_timeout_ms: int,
    max_rendered_pages_per_job: int,
) -> CrawlJob:
    validate_crawl_limits(max_urls=max_urls, max_depth=max_depth, delay=delay)
    validate_render_settings(
        render_mode=render_mode,
        render_timeout_ms=render_timeout_ms,
        max_rendered_pages_per_job=max_rendered_pages_per_job,
    )
    normalized_start_url, registered_domain = normalize_start_url_or_raise(root_url)
    site = _resolve_site_for_new_crawl(
        session,
        site_id=None,
        normalized_start_url=normalized_start_url,
        registered_domain=registered_domain,
    )
    return _create_pending_crawl_job(
        session,
        site_id=site.id,
        normalized_start_url=normalized_start_url,
        max_urls=max_urls,
        max_depth=max_depth,
        delay=delay,
        render_mode=render_mode,
        render_timeout_ms=render_timeout_ms,
        max_rendered_pages_per_job=max_rendered_pages_per_job,
    )


def create_crawl_job_for_site(
    session: Session,
    site_id: int,
    root_url: str,
    max_urls: int,
    max_depth: int,
    delay: float,
    *,
    render_mode: str,
    render_timeout_ms: int,
    max_rendered_pages_per_job: int,
) -> CrawlJob:
    validate_crawl_limits(max_urls=max_urls, max_depth=max_depth, delay=delay)
    validate_render_settings(
        render_mode=render_mode,
        render_timeout_ms=render_timeout_ms,
        max_rendered_pages_per_job=max_rendered_pages_per_job,
    )
    normalized_start_url, registered_domain = normalize_start_url_or_raise(root_url)
    site = _resolve_site_for_new_crawl(
        session,
        site_id=site_id,
        normalized_start_url=normalized_start_url,
        registered_domain=registered_domain,
    )
    return _create_pending_crawl_job(
        session,
        site_id=site.id,
        normalized_start_url=normalized_start_url,
        max_urls=max_urls,
        max_depth=max_depth,
        delay=delay,
        render_mode=render_mode,
        render_timeout_ms=render_timeout_ms,
        max_rendered_pages_per_job=max_rendered_pages_per_job,
    )


def prepare_existing_crawl_job(
    session: Session,
    crawl_job_id: int,
    root_url: str,
    max_urls: int,
    max_depth: int,
    delay: float,
    *,
    render_mode: str,
    render_timeout_ms: int,
    max_rendered_pages_per_job: int,
) -> tuple[CrawlJob, str, str]:
    validate_crawl_limits(max_urls=max_urls, max_depth=max_depth, delay=delay)
    validate_render_settings(
        render_mode=render_mode,
        render_timeout_ms=render_timeout_ms,
        max_rendered_pages_per_job=max_rendered_pages_per_job,
    )
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
    crawl_job.settings_json = build_crawl_settings(
        start_url=normalized_start_url,
        max_urls=max_urls,
        max_depth=max_depth,
        delay=delay,
        render_mode=render_mode,
        render_timeout_ms=render_timeout_ms,
        max_rendered_pages_per_job=max_rendered_pages_per_job,
    )
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
    status_filter: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    stmt = select(CrawlJob, Site).join(Site, Site.id == CrawlJob.site_id)

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

    if status_filter:
        jobs = [job for job in jobs if job["status"] == status_filter]

    if search:
        token = search.strip().lower()
        if token:
            jobs = [
                job
                for job in jobs
                if token in str(job["id"]).lower() or token in str(job.get("root_url") or "").lower()
            ]

    jobs.sort(
        key=lambda item: (_normalize_python_sort_value(item.get(sort_by)), _normalize_python_sort_value(item.get("id"))),
        reverse=sort_order == "desc",
    )
    return jobs[:limit]


def _apply_boolean_filter(
    records: list[dict[str, Any]],
    *,
    key: str,
    value: bool | None,
) -> list[dict[str, Any]]:
    if value is None:
        return records
    return [record for record in records if bool(record.get(key)) is value]


def _filter_schema_type(records: list[dict[str, Any]], schema_type: str | None) -> list[dict[str, Any]]:
    if not schema_type:
        return records

    token = schema_type.strip().lower()
    if not token:
        return records

    return [
        record
        for record in records
        if any(str(candidate).strip().lower() == token for candidate in record.get("schema_types_json") or [])
    ]


def _filter_page_records(
    records: list[dict[str, Any]],
    *,
    gsc_date_range: str = "last_28_days",
    url_contains: str | None = None,
    title_contains: str | None = None,
    page_type: str | None = None,
    page_bucket: str | None = None,
    page_type_confidence_min: float | None = None,
    page_type_confidence_max: float | None = None,
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
    noindex_like: bool | None = None,
    non_indexable_like: bool | None = None,
    title_exact: str | None = None,
    meta_description_exact: str | None = None,
    content_text_hash_exact: str | None = None,
    title_too_short: bool | None = None,
    title_too_long: bool | None = None,
    meta_too_short: bool | None = None,
    meta_too_long: bool | None = None,
    multiple_h1: bool | None = None,
    missing_h2: bool | None = None,
    self_canonical: bool | None = None,
    canonical_to_other_url: bool | None = None,
    canonical_to_non_200: bool | None = None,
    canonical_to_redirect: bool | None = None,
    thin_content: bool | None = None,
    duplicate_content: bool | None = None,
    missing_alt_images: bool | None = None,
    no_images: bool | None = None,
    oversized: bool | None = None,
    was_rendered: bool | None = None,
    js_heavy_like: bool | None = None,
    schema_present: bool | None = None,
    schema_type: str | None = None,
    has_render_error: bool | None = None,
    has_x_robots_tag: bool | None = None,
    has_technical_issue: bool | None = None,
    has_gsc_data: bool | None = None,
    has_cannibalization: bool | None = None,
    priority_level: str | None = None,
    opportunity_type: str | None = None,
    priority_score_min: int | None = None,
    priority_score_max: int | None = None,
    gsc_clicks_min: int | None = None,
    gsc_clicks_max: int | None = None,
    gsc_impressions_min: int | None = None,
    gsc_impressions_max: int | None = None,
    gsc_ctr_min: float | None = None,
    gsc_ctr_max: float | None = None,
    gsc_position_min: float | None = None,
    gsc_position_max: float | None = None,
    gsc_top_queries_min: int | None = None,
) -> list[dict[str, Any]]:
    gsc_suffix = _resolve_gsc_suffix(gsc_date_range)
    gsc_clicks_key = f"clicks_{gsc_suffix}"
    gsc_impressions_key = f"impressions_{gsc_suffix}"
    gsc_ctr_key = f"ctr_{gsc_suffix}"
    gsc_position_key = f"position_{gsc_suffix}"
    gsc_top_queries_key = f"top_queries_count_{gsc_suffix}"
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

    filtered = records

    if url_contains:
        url_token = url_contains.strip().lower()
        if url_token:
            filtered = [
                record
                for record in filtered
                if url_token in str(record.get("url") or "").lower()
                or url_token in str(record.get("normalized_url") or "").lower()
            ]

    if title_contains:
        title_token = title_contains.strip().lower()
        if title_token:
            filtered = [
                record
                for record in filtered
                if title_token in str(record.get("title") or "").lower()
            ]

    if page_type:
        page_type_token = page_type.strip().lower()
        if page_type_token:
            filtered = [
                record
                for record in filtered
                if str(record.get("page_type") or "").lower() == page_type_token
            ]

    if page_bucket:
        page_bucket_token = page_bucket.strip().lower()
        if page_bucket_token:
            filtered = [
                record
                for record in filtered
                if str(record.get("page_bucket") or "").lower() == page_bucket_token
            ]

    if page_type_confidence_min is not None:
        filtered = [
            record
            for record in filtered
            if record.get("page_type_confidence") is not None
            and float(record["page_type_confidence"]) >= page_type_confidence_min
        ]

    if page_type_confidence_max is not None:
        filtered = [
            record
            for record in filtered
            if record.get("page_type_confidence") is not None
            and float(record["page_type_confidence"]) <= page_type_confidence_max
        ]

    if resolved_has_title is not None:
        filtered = [record for record in filtered if (not bool(record.get("title_missing"))) is resolved_has_title]

    if resolved_has_meta is not None:
        filtered = [
            record
            for record in filtered
            if (not bool(record.get("meta_description_missing"))) is resolved_has_meta
        ]

    if resolved_has_h1 is not None:
        filtered = [record for record in filtered if (not bool(record.get("h1_missing"))) is resolved_has_h1]

    if status_code is not None:
        filtered = [record for record in filtered if record.get("status_code") == status_code]
    if status_code_min is not None:
        filtered = [
            record
            for record in filtered
            if record.get("status_code") is not None and int(record["status_code"]) >= status_code_min
        ]
    if status_code_max is not None:
        filtered = [
            record
            for record in filtered
            if record.get("status_code") is not None and int(record["status_code"]) <= status_code_max
        ]

    filtered = _apply_boolean_filter(filtered, key="canonical_missing", value=canonical_missing)
    filtered = _apply_boolean_filter(filtered, key="noindex_like", value=noindex_like)
    filtered = _apply_boolean_filter(filtered, key="non_indexable_like", value=non_indexable_like)
    filtered = _apply_boolean_filter(filtered, key="title_too_short", value=title_too_short)
    filtered = _apply_boolean_filter(filtered, key="title_too_long", value=title_too_long)
    filtered = _apply_boolean_filter(filtered, key="meta_description_too_short", value=meta_too_short)
    filtered = _apply_boolean_filter(filtered, key="meta_description_too_long", value=meta_too_long)
    filtered = _apply_boolean_filter(filtered, key="multiple_h1", value=multiple_h1)
    filtered = _apply_boolean_filter(filtered, key="missing_h2", value=missing_h2)
    filtered = _apply_boolean_filter(filtered, key="self_canonical", value=self_canonical)
    filtered = _apply_boolean_filter(filtered, key="canonical_to_other_url", value=canonical_to_other_url)
    filtered = _apply_boolean_filter(filtered, key="canonical_to_non_200", value=canonical_to_non_200)
    filtered = _apply_boolean_filter(filtered, key="canonical_to_redirect", value=canonical_to_redirect)
    filtered = _apply_boolean_filter(filtered, key="thin_content", value=thin_content)
    filtered = _apply_boolean_filter(filtered, key="duplicate_content", value=duplicate_content)
    filtered = _apply_boolean_filter(filtered, key="missing_alt_images", value=missing_alt_images)
    filtered = _apply_boolean_filter(filtered, key="no_images", value=no_images)
    filtered = _apply_boolean_filter(filtered, key="oversized", value=oversized)
    filtered = _apply_boolean_filter(filtered, key="was_rendered", value=was_rendered)
    filtered = _apply_boolean_filter(filtered, key="js_heavy_like", value=js_heavy_like)
    filtered = _apply_boolean_filter(filtered, key="schema_present", value=schema_present)
    filtered = _apply_boolean_filter(filtered, key="has_render_error", value=has_render_error)
    filtered = _apply_boolean_filter(filtered, key="has_x_robots_tag", value=has_x_robots_tag)
    filtered = _apply_boolean_filter(filtered, key="has_technical_issue", value=has_technical_issue)
    filtered = _apply_boolean_filter(filtered, key="has_cannibalization", value=has_cannibalization)

    if priority_level:
        priority_level_token = priority_level.strip().lower()
        filtered = [
            record
            for record in filtered
            if str(record.get("priority_level") or "").lower() == priority_level_token
        ]

    if opportunity_type:
        opportunity_type_token = opportunity_type.strip().upper()
        filtered = [
            record
            for record in filtered
            if opportunity_type_token in {str(item).upper() for item in record.get("opportunity_types") or []}
        ]

    if priority_score_min is not None:
        filtered = [
            record
            for record in filtered
            if record.get("priority_score") is not None and int(record["priority_score"]) >= priority_score_min
        ]

    if priority_score_max is not None:
        filtered = [
            record
            for record in filtered
            if record.get("priority_score") is not None and int(record["priority_score"]) <= priority_score_max
        ]

    if robots_meta_contains:
        token = robots_meta_contains.strip().lower()
        if token:
            filtered = [
                record
                for record in filtered
                if token in str(record.get("robots_meta") or "").lower()
            ]

    if title_exact:
        filtered = [record for record in filtered if record.get("title") == title_exact]

    if meta_description_exact:
        filtered = [
            record
            for record in filtered
            if record.get("meta_description") == meta_description_exact
        ]

    if content_text_hash_exact:
        filtered = [
            record
            for record in filtered
            if record.get("content_text_hash") == content_text_hash_exact
        ]

    filtered = _filter_schema_type(filtered, schema_type)

    if has_gsc_data is not None:
        filtered = [
            record
            for record in filtered
            if any(record.get(key) is not None for key in [gsc_clicks_key, gsc_impressions_key, gsc_ctr_key, gsc_position_key]) is has_gsc_data
        ]

    if gsc_clicks_min is not None:
        filtered = [
            record for record in filtered if record.get(gsc_clicks_key) is not None and int(record[gsc_clicks_key]) >= gsc_clicks_min
        ]
    if gsc_clicks_max is not None:
        filtered = [
            record for record in filtered if record.get(gsc_clicks_key) is not None and int(record[gsc_clicks_key]) <= gsc_clicks_max
        ]
    if gsc_impressions_min is not None:
        filtered = [
            record
            for record in filtered
            if record.get(gsc_impressions_key) is not None and int(record[gsc_impressions_key]) >= gsc_impressions_min
        ]
    if gsc_impressions_max is not None:
        filtered = [
            record
            for record in filtered
            if record.get(gsc_impressions_key) is not None and int(record[gsc_impressions_key]) <= gsc_impressions_max
        ]
    if gsc_ctr_min is not None:
        filtered = [
            record for record in filtered if record.get(gsc_ctr_key) is not None and float(record[gsc_ctr_key]) >= gsc_ctr_min
        ]
    if gsc_ctr_max is not None:
        filtered = [
            record for record in filtered if record.get(gsc_ctr_key) is not None and float(record[gsc_ctr_key]) <= gsc_ctr_max
        ]
    if gsc_position_min is not None:
        filtered = [
            record
            for record in filtered
            if record.get(gsc_position_key) is not None and float(record[gsc_position_key]) >= gsc_position_min
        ]
    if gsc_position_max is not None:
        filtered = [
            record
            for record in filtered
            if record.get(gsc_position_key) is not None and float(record[gsc_position_key]) <= gsc_position_max
        ]
    if gsc_top_queries_min is not None:
        filtered = [
            record
            for record in filtered
            if int(record.get(gsc_top_queries_key) or 0) >= gsc_top_queries_min
        ]

    return filtered


def _collect_available_status_codes(records: list[dict[str, Any]]) -> list[int]:
    return sorted(
        {
            int(status_code)
            for record in records
            if (status_code := record.get("status_code")) is not None
        }
    )


def _records_have_gsc_integration(records: list[dict[str, Any]]) -> bool:
    return any(
        bool(record.get("has_gsc_28d"))
        or bool(record.get("has_gsc_90d"))
        or int(record.get("top_queries_count_28d") or 0) > 0
        or int(record.get("top_queries_count_90d") or 0) > 0
        for record in records
    )


def get_pages_for_job(
    session: Session,
    crawl_job_id: int,
    *,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "url",
    sort_order: str = "asc",
    gsc_date_range: str = "last_28_days",
    url_contains: str | None = None,
    title_contains: str | None = None,
    page_type: str | None = None,
    page_bucket: str | None = None,
    page_type_confidence_min: float | None = None,
    page_type_confidence_max: float | None = None,
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
    noindex_like: bool | None = None,
    non_indexable_like: bool | None = None,
    title_exact: str | None = None,
    meta_description_exact: str | None = None,
    content_text_hash_exact: str | None = None,
    title_too_short: bool | None = None,
    title_too_long: bool | None = None,
    meta_too_short: bool | None = None,
    meta_too_long: bool | None = None,
    multiple_h1: bool | None = None,
    missing_h2: bool | None = None,
    self_canonical: bool | None = None,
    canonical_to_other_url: bool | None = None,
    canonical_to_non_200: bool | None = None,
    canonical_to_redirect: bool | None = None,
    thin_content: bool | None = None,
    duplicate_content: bool | None = None,
    missing_alt_images: bool | None = None,
    no_images: bool | None = None,
    oversized: bool | None = None,
    was_rendered: bool | None = None,
    js_heavy_like: bool | None = None,
    schema_present: bool | None = None,
    schema_type: str | None = None,
    has_render_error: bool | None = None,
    has_x_robots_tag: bool | None = None,
    has_technical_issue: bool | None = None,
    has_gsc_data: bool | None = None,
    has_cannibalization: bool | None = None,
    priority_level: str | None = None,
    opportunity_type: str | None = None,
    priority_score_min: int | None = None,
    priority_score_max: int | None = None,
    gsc_clicks_min: int | None = None,
    gsc_clicks_max: int | None = None,
    gsc_impressions_min: int | None = None,
    gsc_impressions_max: int | None = None,
    gsc_ctr_min: float | None = None,
    gsc_ctr_max: float | None = None,
    gsc_position_min: float | None = None,
    gsc_position_max: float | None = None,
    gsc_top_queries_min: int | None = None,
) -> tuple[list[dict[str, Any]], int, list[int], bool]:
    records = build_page_records(session, crawl_job_id)
    priority_service.apply_priority_metadata(records, gsc_date_range=gsc_date_range)
    cannibalization_service.apply_cannibalization_page_metadata(
        session,
        crawl_job_id,
        records,
        gsc_date_range=gsc_date_range,
    )
    available_status_codes = _collect_available_status_codes(records)
    has_gsc_integration = _records_have_gsc_integration(records)
    filtered = _filter_page_records(
        records,
        gsc_date_range=gsc_date_range,
        url_contains=url_contains,
        title_contains=title_contains,
        page_type=page_type,
        page_bucket=page_bucket,
        page_type_confidence_min=page_type_confidence_min,
        page_type_confidence_max=page_type_confidence_max,
        missing_title=missing_title,
        missing_meta_description=missing_meta_description,
        missing_h1=missing_h1,
        has_title=has_title,
        has_meta_description=has_meta_description,
        has_h1=has_h1,
        status_code=status_code,
        status_code_min=status_code_min,
        status_code_max=status_code_max,
        canonical_missing=canonical_missing,
        robots_meta_contains=robots_meta_contains,
        noindex_like=noindex_like,
        non_indexable_like=non_indexable_like,
        title_exact=title_exact,
        meta_description_exact=meta_description_exact,
        content_text_hash_exact=content_text_hash_exact,
        title_too_short=title_too_short,
        title_too_long=title_too_long,
        meta_too_short=meta_too_short,
        meta_too_long=meta_too_long,
        multiple_h1=multiple_h1,
        missing_h2=missing_h2,
        self_canonical=self_canonical,
        canonical_to_other_url=canonical_to_other_url,
        canonical_to_non_200=canonical_to_non_200,
        canonical_to_redirect=canonical_to_redirect,
        thin_content=thin_content,
        duplicate_content=duplicate_content,
        missing_alt_images=missing_alt_images,
        no_images=no_images,
        oversized=oversized,
        was_rendered=was_rendered,
        js_heavy_like=js_heavy_like,
        schema_present=schema_present,
        schema_type=schema_type,
        has_render_error=has_render_error,
        has_x_robots_tag=has_x_robots_tag,
        has_technical_issue=has_technical_issue,
        has_gsc_data=has_gsc_data,
        has_cannibalization=has_cannibalization,
        priority_level=priority_level,
        opportunity_type=opportunity_type,
        priority_score_min=priority_score_min,
        priority_score_max=priority_score_max,
        gsc_clicks_min=gsc_clicks_min,
        gsc_clicks_max=gsc_clicks_max,
        gsc_impressions_min=gsc_impressions_min,
        gsc_impressions_max=gsc_impressions_max,
        gsc_ctr_min=gsc_ctr_min,
        gsc_ctr_max=gsc_ctr_max,
        gsc_position_min=gsc_position_min,
        gsc_position_max=gsc_position_max,
        gsc_top_queries_min=gsc_top_queries_min,
    )

    _sort_python_records(
        filtered,
        sort_by=_resolve_page_sort_key(sort_by, gsc_date_range),
        sort_order=sort_order,
    )
    total_items = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    return filtered[start:end], total_items, available_status_codes, has_gsc_integration


def get_all_pages_for_job(
    session: Session,
    crawl_job_id: int,
    *,
    sort_by: str = "url",
    sort_order: str = "asc",
    gsc_date_range: str = "last_28_days",
    url_contains: str | None = None,
    title_contains: str | None = None,
    page_type: str | None = None,
    page_bucket: str | None = None,
    page_type_confidence_min: float | None = None,
    page_type_confidence_max: float | None = None,
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
    noindex_like: bool | None = None,
    non_indexable_like: bool | None = None,
    title_exact: str | None = None,
    meta_description_exact: str | None = None,
    content_text_hash_exact: str | None = None,
    title_too_short: bool | None = None,
    title_too_long: bool | None = None,
    meta_too_short: bool | None = None,
    meta_too_long: bool | None = None,
    multiple_h1: bool | None = None,
    missing_h2: bool | None = None,
    self_canonical: bool | None = None,
    canonical_to_other_url: bool | None = None,
    canonical_to_non_200: bool | None = None,
    canonical_to_redirect: bool | None = None,
    thin_content: bool | None = None,
    duplicate_content: bool | None = None,
    missing_alt_images: bool | None = None,
    no_images: bool | None = None,
    oversized: bool | None = None,
    was_rendered: bool | None = None,
    js_heavy_like: bool | None = None,
    schema_present: bool | None = None,
    schema_type: str | None = None,
    has_render_error: bool | None = None,
    has_x_robots_tag: bool | None = None,
    has_technical_issue: bool | None = None,
    has_gsc_data: bool | None = None,
    has_cannibalization: bool | None = None,
    priority_level: str | None = None,
    opportunity_type: str | None = None,
    priority_score_min: int | None = None,
    priority_score_max: int | None = None,
    gsc_clicks_min: int | None = None,
    gsc_clicks_max: int | None = None,
    gsc_impressions_min: int | None = None,
    gsc_impressions_max: int | None = None,
    gsc_ctr_min: float | None = None,
    gsc_ctr_max: float | None = None,
    gsc_position_min: float | None = None,
    gsc_position_max: float | None = None,
    gsc_top_queries_min: int | None = None,
) -> list[dict[str, Any]]:
    records = build_page_records(session, crawl_job_id)
    priority_service.apply_priority_metadata(records, gsc_date_range=gsc_date_range)
    cannibalization_service.apply_cannibalization_page_metadata(
        session,
        crawl_job_id,
        records,
        gsc_date_range=gsc_date_range,
    )
    filtered = _filter_page_records(
        records,
        gsc_date_range=gsc_date_range,
        url_contains=url_contains,
        title_contains=title_contains,
        page_type=page_type,
        page_bucket=page_bucket,
        page_type_confidence_min=page_type_confidence_min,
        page_type_confidence_max=page_type_confidence_max,
        missing_title=missing_title,
        missing_meta_description=missing_meta_description,
        missing_h1=missing_h1,
        has_title=has_title,
        has_meta_description=has_meta_description,
        has_h1=has_h1,
        status_code=status_code,
        status_code_min=status_code_min,
        status_code_max=status_code_max,
        canonical_missing=canonical_missing,
        robots_meta_contains=robots_meta_contains,
        noindex_like=noindex_like,
        non_indexable_like=non_indexable_like,
        title_exact=title_exact,
        meta_description_exact=meta_description_exact,
        content_text_hash_exact=content_text_hash_exact,
        title_too_short=title_too_short,
        title_too_long=title_too_long,
        meta_too_short=meta_too_short,
        meta_too_long=meta_too_long,
        multiple_h1=multiple_h1,
        missing_h2=missing_h2,
        self_canonical=self_canonical,
        canonical_to_other_url=canonical_to_other_url,
        canonical_to_non_200=canonical_to_non_200,
        canonical_to_redirect=canonical_to_redirect,
        thin_content=thin_content,
        duplicate_content=duplicate_content,
        missing_alt_images=missing_alt_images,
        no_images=no_images,
        oversized=oversized,
        was_rendered=was_rendered,
        js_heavy_like=js_heavy_like,
        schema_present=schema_present,
        schema_type=schema_type,
        has_render_error=has_render_error,
        has_x_robots_tag=has_x_robots_tag,
        has_technical_issue=has_technical_issue,
        has_gsc_data=has_gsc_data,
        has_cannibalization=has_cannibalization,
        priority_level=priority_level,
        opportunity_type=opportunity_type,
        priority_score_min=priority_score_min,
        priority_score_max=priority_score_max,
        gsc_clicks_min=gsc_clicks_min,
        gsc_clicks_max=gsc_clicks_max,
        gsc_impressions_min=gsc_impressions_min,
        gsc_impressions_max=gsc_impressions_max,
        gsc_ctr_min=gsc_ctr_min,
        gsc_ctr_max=gsc_ctr_max,
        gsc_position_min=gsc_position_min,
        gsc_position_max=gsc_position_max,
        gsc_top_queries_min=gsc_top_queries_min,
    )
    _sort_python_records(
        filtered,
        sort_by=_resolve_page_sort_key(sort_by, gsc_date_range),
        sort_order=sort_order,
    )
    return filtered


def _filter_link_records(
    records: list[dict[str, Any]],
    *,
    is_internal: bool | None = None,
    is_nofollow: bool | None = None,
    target_domain: str | None = None,
    has_anchor: bool | None = None,
    broken_internal: bool | None = None,
    redirecting_internal: bool | None = None,
    unresolved_internal: bool | None = None,
    to_noindex_like: bool | None = None,
    to_canonicalized: bool | None = None,
    redirect_chain: bool | None = None,
) -> list[dict[str, Any]]:
    filtered = records

    if is_internal is not None:
        filtered = [record for record in filtered if record["is_internal"] is is_internal]

    if is_nofollow is not None:
        filtered = [record for record in filtered if record["is_nofollow"] is is_nofollow]

    if target_domain:
        target_token = target_domain.strip().lower()
        filtered = [
            record
            for record in filtered
            if str(record.get("target_domain") or "").lower() == target_token
        ]

    if has_anchor is not None:
        filtered = [
            record
            for record in filtered
            if (not text_value_missing(record.get("anchor_text"))) is has_anchor
        ]

    filtered = _apply_boolean_filter(filtered, key="broken_internal", value=broken_internal)
    filtered = _apply_boolean_filter(filtered, key="redirecting_internal", value=redirecting_internal)
    filtered = _apply_boolean_filter(filtered, key="unresolved_internal", value=unresolved_internal)
    filtered = _apply_boolean_filter(filtered, key="to_noindex_like", value=to_noindex_like)
    filtered = _apply_boolean_filter(filtered, key="to_canonicalized", value=to_canonicalized)
    filtered = _apply_boolean_filter(filtered, key="redirect_chain", value=redirect_chain)

    return filtered


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
    broken_internal: bool | None = None,
    redirecting_internal: bool | None = None,
    unresolved_internal: bool | None = None,
    to_noindex_like: bool | None = None,
    to_canonicalized: bool | None = None,
    redirect_chain: bool | None = None,
) -> tuple[list[dict[str, Any]], int]:
    records = build_link_records(session, crawl_job_id)
    filtered = _filter_link_records(
        records,
        is_internal=is_internal,
        is_nofollow=is_nofollow,
        target_domain=target_domain,
        has_anchor=has_anchor,
        broken_internal=broken_internal,
        redirecting_internal=redirecting_internal,
        unresolved_internal=unresolved_internal,
        to_noindex_like=to_noindex_like,
        to_canonicalized=to_canonicalized,
        redirect_chain=redirect_chain,
    )

    _sort_python_records(filtered, sort_by=sort_by, sort_order=sort_order)
    total_items = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    return filtered[start:end], total_items


def get_all_links_for_job(
    session: Session,
    crawl_job_id: int,
    *,
    sort_by: str = "source_url",
    sort_order: str = "asc",
    is_internal: bool | None = None,
    is_nofollow: bool | None = None,
    target_domain: str | None = None,
    has_anchor: bool | None = None,
    broken_internal: bool | None = None,
    redirecting_internal: bool | None = None,
    unresolved_internal: bool | None = None,
    to_noindex_like: bool | None = None,
    to_canonicalized: bool | None = None,
    redirect_chain: bool | None = None,
) -> list[dict[str, Any]]:
    records = build_link_records(session, crawl_job_id)
    filtered = _filter_link_records(
        records,
        is_internal=is_internal,
        is_nofollow=is_nofollow,
        target_domain=target_domain,
        has_anchor=has_anchor,
        broken_internal=broken_internal,
        redirecting_internal=redirecting_internal,
        unresolved_internal=unresolved_internal,
        to_noindex_like=to_noindex_like,
        to_canonicalized=to_canonicalized,
        redirect_chain=redirect_chain,
    )
    _sort_python_records(filtered, sort_by=sort_by, sort_order=sort_order)
    return filtered


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
    page_records = build_page_records(session, crawl_job_id)
    link_records = build_link_records(session, crawl_job_id, page_records=page_records)

    return {
        "total_pages": len(page_records),
        "total_links": len(link_records),
        "total_internal_links": sum(1 for record in link_records if record["is_internal"]),
        "total_external_links": sum(1 for record in link_records if not record["is_internal"]),
        "pages_missing_title": sum(1 for record in page_records if record["title_missing"]),
        "pages_missing_meta_description": sum(1 for record in page_records if record["meta_description_missing"]),
        "pages_missing_h1": sum(1 for record in page_records if record["h1_missing"]),
        "pages_non_indexable_like": sum(1 for record in page_records if record["non_indexable_like"]),
        "rendered_pages": sum(1 for record in page_records if record["was_rendered"]),
        "js_heavy_like_pages": sum(1 for record in page_records if record["js_heavy_like"]),
        "pages_with_render_errors": sum(1 for record in page_records if record["has_render_error"]),
        "pages_with_schema": sum(1 for record in page_records if record["schema_present"]),
        "pages_with_x_robots_tag": sum(1 for record in page_records if record["has_x_robots_tag"]),
        "pages_with_gsc_28d": sum(1 for record in page_records if record.get("clicks_28d") is not None),
        "pages_with_gsc_90d": sum(1 for record in page_records if record.get("clicks_90d") is not None),
        "gsc_opportunities_28d": sum(
            1 for record in page_records if record.get("has_technical_issue") and (record.get("impressions_28d") or 0) > 0
        ),
        "gsc_opportunities_90d": sum(
            1 for record in page_records if record.get("has_technical_issue") and (record.get("impressions_90d") or 0) > 0
        ),
        "broken_internal_links": sum(1 for record in link_records if record["broken_internal"]),
        "redirecting_internal_links": sum(1 for record in link_records if record["redirecting_internal"]),
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
    render_mode: str,
    render_timeout_ms: int,
    max_rendered_pages_per_job: int,
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
        "--render-mode",
        str(render_mode),
        "--render-timeout-ms",
        str(render_timeout_ms),
        "--max-rendered-pages",
        str(max_rendered_pages_per_job),
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
