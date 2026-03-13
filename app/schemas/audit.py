from __future__ import annotations

from pydantic import BaseModel


class PageIssue(BaseModel):
    page_id: int
    url: str
    normalized_url: str
    status_code: int | None
    title: str | None = None
    meta_description: str | None = None
    h1: str | None = None


class DuplicateValueGroup(BaseModel):
    value: str
    count: int
    pages: list[PageIssue]


class LinkIssue(BaseModel):
    link_id: int
    source_url: str
    target_url: str
    target_normalized_url: str | None
    target_status_code: int | None = None
    final_url: str | None = None


class NonIndexableLikeSignal(BaseModel):
    page_id: int
    url: str
    normalized_url: str
    status_code: int | None
    robots_meta: str | None
    signals: list[str]


class AuditSummary(BaseModel):
    total_pages: int
    pages_missing_title: int
    pages_missing_meta_description: int
    pages_missing_h1: int
    pages_duplicate_title_groups: int
    pages_duplicate_meta_description_groups: int
    broken_internal_links: int
    unresolved_internal_targets: int
    redirecting_internal_links: int
    non_indexable_like_signals: int


class AuditReportResponse(BaseModel):
    crawl_job_id: int
    summary: AuditSummary
    pages_missing_title: list[PageIssue]
    pages_missing_meta_description: list[PageIssue]
    pages_missing_h1: list[PageIssue]
    pages_duplicate_title: list[DuplicateValueGroup]
    pages_duplicate_meta_description: list[DuplicateValueGroup]
    broken_internal_links: list[LinkIssue]
    unresolved_internal_targets: list[LinkIssue]
    redirecting_internal_links: list[LinkIssue]
    non_indexable_like_signals: list[NonIndexableLikeSignal]
