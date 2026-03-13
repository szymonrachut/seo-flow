from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.crawler.normalization.urls import normalize_url
from app.db.models import Link, Page


def build_audit_report(session: Session, crawl_job_id: int) -> dict[str, Any]:
    missing_title_pages = _get_missing_pages(session, crawl_job_id, Page.title)
    missing_meta_pages = _get_missing_pages(session, crawl_job_id, Page.meta_description)
    missing_h1_pages = _get_missing_pages(session, crawl_job_id, Page.h1)
    duplicate_title_groups = _get_duplicate_value_groups(session, crawl_job_id, Page.title)
    duplicate_meta_groups = _get_duplicate_value_groups(session, crawl_job_id, Page.meta_description)
    broken_links, unresolved_links, redirecting_links = _get_internal_link_findings(session, crawl_job_id)
    non_indexable_signals = _get_non_indexable_like_signals(session, crawl_job_id)

    total_pages = session.scalar(select(func.count(Page.id)).where(Page.crawl_job_id == crawl_job_id)) or 0
    summary = {
        "total_pages": int(total_pages),
        "pages_missing_title": len(missing_title_pages),
        "pages_missing_meta_description": len(missing_meta_pages),
        "pages_missing_h1": len(missing_h1_pages),
        "pages_duplicate_title_groups": len(duplicate_title_groups),
        "pages_duplicate_meta_description_groups": len(duplicate_meta_groups),
        "broken_internal_links": len(broken_links),
        "unresolved_internal_targets": len(unresolved_links),
        "redirecting_internal_links": len(redirecting_links),
        "non_indexable_like_signals": len(non_indexable_signals),
    }

    return {
        "crawl_job_id": crawl_job_id,
        "summary": summary,
        "pages_missing_title": missing_title_pages,
        "pages_missing_meta_description": missing_meta_pages,
        "pages_missing_h1": missing_h1_pages,
        "pages_duplicate_title": duplicate_title_groups,
        "pages_duplicate_meta_description": duplicate_meta_groups,
        "broken_internal_links": broken_links,
        "unresolved_internal_targets": unresolved_links,
        "redirecting_internal_links": redirecting_links,
        "non_indexable_like_signals": non_indexable_signals,
    }


def _get_missing_pages(session: Session, crawl_job_id: int, field) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Page)
        .where(
            Page.crawl_job_id == crawl_job_id,
            or_(field.is_(None), func.trim(field) == ""),
        )
        .order_by(Page.id.asc())
    ).all()
    return [_page_ref(page) for page in rows]


def _get_duplicate_value_groups(session: Session, crawl_job_id: int, field) -> list[dict[str, Any]]:
    duplicate_values = session.execute(
        select(field, func.count(Page.id).label("count"))
        .where(
            Page.crawl_job_id == crawl_job_id,
            field.is_not(None),
            func.trim(field) != "",
        )
        .group_by(field)
        .having(func.count(Page.id) > 1)
        .order_by(func.count(Page.id).desc(), field.asc())
    ).all()

    if not duplicate_values:
        return []

    values = [row[0] for row in duplicate_values]
    pages = session.scalars(
        select(Page).where(Page.crawl_job_id == crawl_job_id, field.in_(values)).order_by(field.asc(), Page.id.asc())
    ).all()

    pages_by_value: dict[str, list[dict[str, Any]]] = {}
    for page in pages:
        value = getattr(page, field.key)
        if value is None:
            continue
        pages_by_value.setdefault(value, []).append(_page_ref(page))

    return [
        {
            "value": value,
            "count": int(count),
            "pages": pages_by_value.get(value, []),
        }
        for value, count in duplicate_values
    ]


def _get_internal_link_findings(
    session: Session,
    crawl_job_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    target_page = aliased(Page)
    rows = session.execute(
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
    ).all()

    broken_links: list[dict[str, Any]] = []
    unresolved_links: list[dict[str, Any]] = []
    redirecting_links: list[dict[str, Any]] = []

    for link, target in rows:
        if target is None:
            unresolved_links.append(
                {
                    "link_id": link.id,
                    "source_url": link.source_url,
                    "target_url": link.target_url,
                    "target_normalized_url": link.target_normalized_url,
                }
            )
            continue

        if target.status_code is not None and target.status_code >= 400:
            broken_links.append(
                {
                    "link_id": link.id,
                    "source_url": link.source_url,
                    "target_url": link.target_url,
                    "target_normalized_url": link.target_normalized_url,
                    "target_status_code": target.status_code,
                }
            )

        normalized_final = normalize_url(target.final_url) if target.final_url else None
        if normalized_final and normalized_final != target.normalized_url:
            redirecting_links.append(
                {
                    "link_id": link.id,
                    "source_url": link.source_url,
                    "target_url": link.target_url,
                    "target_normalized_url": link.target_normalized_url,
                    "final_url": target.final_url,
                    "target_status_code": target.status_code,
                }
            )

    return broken_links, unresolved_links, redirecting_links


def _get_non_indexable_like_signals(session: Session, crawl_job_id: int) -> list[dict[str, Any]]:
    status_signal = and_(Page.status_code.is_not(None), or_(Page.status_code < 200, Page.status_code >= 300))
    robots_signal = func.lower(func.coalesce(Page.robots_meta, "")).like("%noindex%")

    pages = session.scalars(
        select(Page)
        .where(Page.crawl_job_id == crawl_job_id, or_(status_signal, robots_signal))
        .order_by(Page.id.asc())
    ).all()

    findings: list[dict[str, Any]] = []
    for page in pages:
        signals: list[str] = []
        if page.robots_meta and "noindex" in page.robots_meta.lower():
            signals.append("robots_noindex")
        if page.status_code is not None and not (200 <= page.status_code <= 299):
            signals.append("status_not_2xx")
        findings.append(
            {
                "page_id": page.id,
                "url": page.url,
                "normalized_url": page.normalized_url,
                "status_code": page.status_code,
                "robots_meta": page.robots_meta,
                "signals": signals,
            }
        )

    return findings


def _page_ref(page: Page) -> dict[str, Any]:
    return {
        "page_id": page.id,
        "url": page.url,
        "normalized_url": page.normalized_url,
        "status_code": page.status_code,
        "title": page.title,
        "meta_description": page.meta_description,
        "h1": page.h1,
    }
