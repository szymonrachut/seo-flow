from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Link, Page
from app.services.audit_service import build_audit_report

UTF8_BOM = "\ufeff"


def build_pages_csv(session: Session, crawl_job_id: int) -> str:
    pages = session.scalars(select(Page).where(Page.crawl_job_id == crawl_job_id).order_by(Page.id.asc())).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "crawl_job_id",
            "url",
            "normalized_url",
            "final_url",
            "status_code",
            "title",
            "meta_description",
            "h1",
            "canonical_url",
            "robots_meta",
            "content_type",
            "response_time_ms",
            "is_internal",
            "depth",
            "fetched_at",
            "error_message",
            "created_at",
        ]
    )
    for page in pages:
        writer.writerow(
            [
                page.id,
                page.crawl_job_id,
                page.url,
                page.normalized_url,
                page.final_url,
                page.status_code,
                page.title,
                page.meta_description,
                page.h1,
                page.canonical_url,
                page.robots_meta,
                page.content_type,
                page.response_time_ms,
                page.is_internal,
                page.depth,
                page.fetched_at.isoformat() if page.fetched_at else "",
                page.error_message,
                page.created_at.isoformat() if page.created_at else "",
            ]
        )
    return UTF8_BOM + buffer.getvalue()


def build_links_csv(session: Session, crawl_job_id: int) -> str:
    links = session.scalars(select(Link).where(Link.crawl_job_id == crawl_job_id).order_by(Link.id.asc())).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "crawl_job_id",
            "source_page_id",
            "source_url",
            "target_url",
            "target_normalized_url",
            "target_domain",
            "anchor_text",
            "rel_attr",
            "is_nofollow",
            "is_internal",
            "created_at",
        ]
    )
    for link in links:
        writer.writerow(
            [
                link.id,
                link.crawl_job_id,
                link.source_page_id,
                link.source_url,
                link.target_url,
                link.target_normalized_url,
                link.target_domain,
                link.anchor_text,
                link.rel_attr,
                link.is_nofollow,
                link.is_internal,
                link.created_at.isoformat() if link.created_at else "",
            ]
        )
    return UTF8_BOM + buffer.getvalue()


def build_audit_csv(session: Session, crawl_job_id: int) -> str:
    report = build_audit_report(session, crawl_job_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["issue_type", "key", "value", "url", "details"])

    for key, value in report["summary"].items():
        writer.writerow(["summary", key, value, "", ""])

    _write_page_issue_rows(writer, "pages_missing_title", report["pages_missing_title"])
    _write_page_issue_rows(writer, "pages_missing_meta_description", report["pages_missing_meta_description"])
    _write_page_issue_rows(writer, "pages_missing_h1", report["pages_missing_h1"])
    _write_duplicate_rows(writer, "pages_duplicate_title", report["pages_duplicate_title"])
    _write_duplicate_rows(writer, "pages_duplicate_meta_description", report["pages_duplicate_meta_description"])
    _write_link_issue_rows(writer, "broken_internal_links", report["broken_internal_links"])
    _write_link_issue_rows(writer, "unresolved_internal_targets", report["unresolved_internal_targets"])
    _write_link_issue_rows(writer, "redirecting_internal_links", report["redirecting_internal_links"])
    _write_non_indexable_rows(writer, report["non_indexable_like_signals"])

    return UTF8_BOM + buffer.getvalue()


def _write_page_issue_rows(writer: csv.writer, section: str, issues: list[dict[str, Any]]) -> None:
    for issue in issues:
        writer.writerow([section, "page_id", issue.get("page_id"), issue.get("url", ""), issue.get("normalized_url", "")])


def _write_duplicate_rows(writer: csv.writer, section: str, groups: list[dict[str, Any]]) -> None:
    for group in groups:
        urls = [page.get("url", "") for page in group.get("pages", [])]
        writer.writerow([section, group.get("value", ""), group.get("count", 0), "", " | ".join(urls)])


def _write_link_issue_rows(writer: csv.writer, section: str, issues: list[dict[str, Any]]) -> None:
    for issue in issues:
        details_parts = []
        if issue.get("target_status_code") is not None:
            details_parts.append(f"target_status_code={issue.get('target_status_code')}")
        if issue.get("final_url"):
            details_parts.append(f"final_url={issue.get('final_url')}")
        details = "; ".join(details_parts)
        writer.writerow([section, "target_url", issue.get("target_url", ""), issue.get("source_url", ""), details])


def _write_non_indexable_rows(writer: csv.writer, issues: list[dict[str, Any]]) -> None:
    for issue in issues:
        details = ", ".join(issue.get("signals", []))
        writer.writerow(["non_indexable_like_signals", "status_code", issue.get("status_code"), issue.get("url", ""), details])
