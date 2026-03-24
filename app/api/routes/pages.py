from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.gsc import GscDateRangeLabel
from app.schemas.opportunities import OpportunityType, PriorityLevel
from app.schemas.page import PageResponse, PageTaxonomySummaryResponse, PaginatedPageResponse
from app.services import crawl_job_service, page_taxonomy_service

router = APIRouter(prefix="/crawl-jobs", tags=["pages"])


@router.get("/{job_id}/pages", response_model=PaginatedPageResponse)
def get_crawl_job_pages(
    job_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: Literal[
        "url",
        "status_code",
        "depth",
        "page_type",
        "page_bucket",
        "page_type_confidence",
        "title",
        "title_length",
        "meta_description",
        "meta_description_length",
        "h1",
        "h1_length",
        "h1_count",
        "h2_count",
        "canonical_url",
        "robots_meta",
        "x_robots_tag",
        "word_count",
        "was_rendered",
        "js_heavy_like",
        "schema_count",
        "images_count",
        "images_missing_alt_count",
        "html_size_bytes",
        "gsc_clicks",
        "gsc_impressions",
        "gsc_ctr",
        "gsc_position",
        "gsc_top_queries_count",
        "priority_score",
        "fetched_at",
        "response_time_ms",
    ] = Query(default="url"),
    sort_order: Literal["asc", "desc"] = Query(default="asc"),
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    url_contains: str | None = Query(default=None),
    title_contains: str | None = Query(default=None),
    page_type: Literal[
        "home",
        "category",
        "product",
        "service",
        "blog_article",
        "blog_index",
        "contact",
        "about",
        "faq",
        "location",
        "legal",
        "utility",
        "other",
    ] | None = Query(default=None),
    page_bucket: Literal["commercial", "informational", "utility", "trust", "other"] | None = Query(default=None),
    page_type_confidence_min: float | None = Query(default=None, ge=0, le=1),
    page_type_confidence_max: float | None = Query(default=None, ge=0, le=1),
    missing_title: bool | None = Query(default=None),
    missing_meta_description: bool | None = Query(default=None),
    missing_h1: bool | None = Query(default=None),
    has_title: bool | None = Query(default=None),
    has_meta_description: bool | None = Query(default=None),
    has_h1: bool | None = Query(default=None),
    status_code: int | None = Query(default=None),
    status_code_min: int | None = Query(default=None),
    status_code_max: int | None = Query(default=None),
    canonical_missing: bool | None = Query(default=None),
    robots_meta_contains: str | None = Query(default=None),
    noindex_like: bool | None = Query(default=None),
    non_indexable_like: bool | None = Query(default=None),
    title_exact: str | None = Query(default=None),
    meta_description_exact: str | None = Query(default=None),
    content_text_hash_exact: str | None = Query(default=None),
    title_too_short: bool | None = Query(default=None),
    title_too_long: bool | None = Query(default=None),
    meta_too_short: bool | None = Query(default=None),
    meta_too_long: bool | None = Query(default=None),
    multiple_h1: bool | None = Query(default=None),
    missing_h2: bool | None = Query(default=None),
    self_canonical: bool | None = Query(default=None),
    canonical_to_other_url: bool | None = Query(default=None),
    canonical_to_non_200: bool | None = Query(default=None),
    canonical_to_redirect: bool | None = Query(default=None),
    thin_content: bool | None = Query(default=None),
    duplicate_content: bool | None = Query(default=None),
    missing_alt_images: bool | None = Query(default=None),
    no_images: bool | None = Query(default=None),
    oversized: bool | None = Query(default=None),
    was_rendered: bool | None = Query(default=None),
    js_heavy_like: bool | None = Query(default=None),
    schema_present: bool | None = Query(default=None),
    schema_type: str | None = Query(default=None),
    has_render_error: bool | None = Query(default=None),
    has_x_robots_tag: bool | None = Query(default=None),
    has_technical_issue: bool | None = Query(default=None),
    has_gsc_data: bool | None = Query(default=None),
    has_cannibalization: bool | None = Query(default=None),
    priority_level: PriorityLevel | None = Query(default=None),
    opportunity_type: OpportunityType | None = Query(default=None),
    priority_score_min: int | None = Query(default=None),
    priority_score_max: int | None = Query(default=None),
    gsc_clicks_min: int | None = Query(default=None),
    gsc_clicks_max: int | None = Query(default=None),
    gsc_impressions_min: int | None = Query(default=None),
    gsc_impressions_max: int | None = Query(default=None),
    gsc_ctr_min: float | None = Query(default=None),
    gsc_ctr_max: float | None = Query(default=None),
    gsc_position_min: float | None = Query(default=None),
    gsc_position_max: float | None = Query(default=None),
    gsc_top_queries_min: int | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedPageResponse:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    if status_code_min is not None and status_code_max is not None and status_code_min > status_code_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status_code_min cannot be greater than status_code_max.")
    if gsc_clicks_min is not None and gsc_clicks_max is not None and gsc_clicks_min > gsc_clicks_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="gsc_clicks_min cannot be greater than gsc_clicks_max.")
    if gsc_impressions_min is not None and gsc_impressions_max is not None and gsc_impressions_min > gsc_impressions_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="gsc_impressions_min cannot be greater than gsc_impressions_max.")
    if gsc_ctr_min is not None and gsc_ctr_max is not None and gsc_ctr_min > gsc_ctr_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="gsc_ctr_min cannot be greater than gsc_ctr_max.")
    if gsc_position_min is not None and gsc_position_max is not None and gsc_position_min > gsc_position_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="gsc_position_min cannot be greater than gsc_position_max.")
    if priority_score_min is not None and priority_score_max is not None and priority_score_min > priority_score_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="priority_score_min cannot be greater than priority_score_max.")
    if (
        page_type_confidence_min is not None
        and page_type_confidence_max is not None
        and page_type_confidence_min > page_type_confidence_max
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_type_confidence_min cannot be greater than page_type_confidence_max.",
        )

    try:
        pages, total_items, available_status_codes, has_gsc_integration = crawl_job_service.get_pages_for_job(
            session,
            job_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
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
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    return PaginatedPageResponse(
        items=[PageResponse.model_validate(item) for item in pages],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        available_status_codes=available_status_codes,
        has_gsc_integration=has_gsc_integration,
    )


@router.get("/{job_id}/page-taxonomy/summary", response_model=PageTaxonomySummaryResponse)
def get_crawl_job_page_taxonomy_summary(
    job_id: int,
    session: Session = Depends(get_db),
) -> PageTaxonomySummaryResponse:
    try:
        payload = page_taxonomy_service.build_page_taxonomy_summary(session, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PageTaxonomySummaryResponse.model_validate(payload)
