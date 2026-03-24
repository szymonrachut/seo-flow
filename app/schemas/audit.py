from __future__ import annotations

from pydantic import BaseModel, Field


class PageIssue(BaseModel):
    page_id: int
    url: str
    normalized_url: str
    final_url: str | None = None
    status_code: int | None
    title: str | None = None
    title_length: int | None = None
    meta_description: str | None = None
    meta_description_length: int | None = None
    h1: str | None = None
    h1_count: int | None = None
    h2_count: int | None = None
    canonical_url: str | None = None
    canonical_target_url: str | None = None
    canonical_target_status_code: int | None = None
    canonical_target_final_url: str | None = None
    robots_meta: str | None = None
    x_robots_tag: str | None = None
    word_count: int | None = None
    content_text_hash: str | None = None
    images_count: int | None = None
    images_missing_alt_count: int | None = None
    html_size_bytes: int | None = None
    was_rendered: bool = False
    js_heavy_like: bool = False
    render_reason: str | None = None
    render_error_message: str | None = None
    schema_present: bool = False
    schema_count: int | None = None
    schema_types_json: list[str] = Field(default_factory=list)


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
    redirect_hops: int | None = None
    target_canonical_url: str | None = None
    target_noindex_like: bool = False
    target_non_indexable_like: bool = False
    signals: list[str]


class AuditSummary(BaseModel):
    total_pages: int
    pages_missing_title: int
    pages_title_too_short: int
    pages_title_too_long: int
    pages_missing_meta_description: int
    pages_meta_description_too_short: int
    pages_meta_description_too_long: int
    pages_missing_h1: int
    pages_multiple_h1: int
    pages_missing_h2: int
    pages_missing_canonical: int
    pages_self_canonical: int
    pages_canonical_to_other_url: int
    pages_canonical_to_non_200: int
    pages_canonical_to_redirect: int
    pages_noindex_like: int
    pages_non_indexable_like: int
    pages_duplicate_title_groups: int
    pages_duplicate_meta_description_groups: int
    pages_thin_content: int
    pages_duplicate_content_groups: int
    pages_with_missing_alt_images: int
    pages_with_no_images: int
    oversized_pages: int
    js_heavy_like_pages: int
    rendered_pages: int
    pages_with_render_errors: int
    pages_with_schema: int
    pages_missing_schema: int
    pages_with_x_robots_tag: int
    pages_with_schema_types_summary: int
    broken_internal_links: int
    unresolved_internal_targets: int
    redirecting_internal_links: int
    internal_links_to_noindex_like_pages: int
    internal_links_to_canonicalized_pages: int
    redirect_chains_internal: int


class AuditReportResponse(BaseModel):
    crawl_job_id: int
    summary: AuditSummary
    pages_missing_title: list[PageIssue]
    pages_title_too_short: list[PageIssue]
    pages_title_too_long: list[PageIssue]
    pages_missing_meta_description: list[PageIssue]
    pages_meta_description_too_short: list[PageIssue]
    pages_meta_description_too_long: list[PageIssue]
    pages_missing_h1: list[PageIssue]
    pages_multiple_h1: list[PageIssue]
    pages_missing_h2: list[PageIssue]
    pages_missing_canonical: list[PageIssue]
    pages_self_canonical: list[PageIssue]
    pages_canonical_to_other_url: list[PageIssue]
    pages_canonical_to_non_200: list[PageIssue]
    pages_canonical_to_redirect: list[PageIssue]
    pages_noindex_like: list[PageIssue]
    pages_non_indexable_like: list[PageIssue]
    pages_duplicate_title: list[DuplicateValueGroup]
    pages_duplicate_meta_description: list[DuplicateValueGroup]
    pages_thin_content: list[PageIssue]
    pages_duplicate_content: list[DuplicateValueGroup]
    pages_with_missing_alt_images: list[PageIssue]
    pages_with_no_images: list[PageIssue]
    oversized_pages: list[PageIssue]
    js_heavy_like_pages: list[PageIssue]
    rendered_pages: list[PageIssue]
    pages_with_render_errors: list[PageIssue]
    pages_with_schema: list[PageIssue]
    pages_missing_schema: list[PageIssue]
    pages_with_x_robots_tag: list[PageIssue]
    pages_with_schema_types_summary: list[DuplicateValueGroup]
    broken_internal_links: list[LinkIssue]
    unresolved_internal_targets: list[LinkIssue]
    redirecting_internal_links: list[LinkIssue]
    internal_links_to_noindex_like_pages: list[LinkIssue]
    internal_links_to_canonicalized_pages: list[LinkIssue]
    redirect_chains_internal: list[LinkIssue]
