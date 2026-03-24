from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.gsc import GscDateRangeLabel
from app.schemas.trends import PaginatedCrawlCompareResponse, PaginatedGscCompareResponse, TrendsOverviewResponse
from app.services import crawl_job_service, trends_service

router = APIRouter(prefix="/crawl-jobs", tags=["trends"])


def _raise_http_for_trends_error(exc: trends_service.TrendsServiceError) -> None:
    detail = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/{job_id}/trends/overview", response_model=TrendsOverviewResponse)
def get_trends_overview(job_id: int, session: Session = Depends(get_db)) -> TrendsOverviewResponse:
    try:
        payload = trends_service.build_trends_overview(session, job_id)
    except trends_service.TrendsServiceError as exc:
        _raise_http_for_trends_error(exc)
    return TrendsOverviewResponse.model_validate(payload)


@router.get("/{job_id}/trends/crawl", response_model=PaginatedCrawlCompareResponse)
def get_crawl_compare(
    job_id: int,
    baseline_job_id: int = Query(..., ge=1),
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: Literal[
        "url",
        "change_type",
        "issues_resolved_count",
        "issues_added_count",
        "delta_priority_score",
        "delta_word_count",
        "delta_schema_count",
        "delta_response_time_ms",
        "delta_incoming_internal_links",
        "delta_incoming_internal_linking_pages",
    ] = Query(default="delta_priority_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    change_type: Literal["improved", "worsened", "unchanged", "new", "missing"] | None = Query(default=None),
    resolved_issues_min: int | None = Query(default=None, ge=0),
    added_issues_min: int | None = Query(default=None, ge=0),
    url_contains: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedCrawlCompareResponse:
    try:
        payload = trends_service.build_crawl_compare(
            session,
            job_id,
            baseline_job_id=baseline_job_id,
            gsc_date_range=gsc_date_range,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            change_type=change_type,
            resolved_issues_min=resolved_issues_min,
            added_issues_min=added_issues_min,
            url_contains=url_contains,
        )
    except trends_service.TrendsServiceError as exc:
        _raise_http_for_trends_error(exc)
    return PaginatedCrawlCompareResponse.model_validate(payload)


@router.get("/{job_id}/trends/gsc", response_model=PaginatedGscCompareResponse)
def get_gsc_compare(
    job_id: int,
    baseline_gsc_range: GscDateRangeLabel = Query(default="last_90_days"),
    target_gsc_range: GscDateRangeLabel = Query(default="last_28_days"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: Literal[
        "url",
        "overall_trend",
        "delta_clicks",
        "delta_impressions",
        "delta_ctr",
        "delta_position",
        "delta_top_queries_count",
    ] = Query(default="delta_clicks"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    clicks_trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    impressions_trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    ctr_trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    position_trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    top_queries_trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    url_contains: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedGscCompareResponse:
    try:
        payload = trends_service.build_gsc_compare(
            session,
            job_id,
            baseline_gsc_range=baseline_gsc_range,
            target_gsc_range=target_gsc_range,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            trend=trend,
            clicks_trend=clicks_trend,
            impressions_trend=impressions_trend,
            ctr_trend=ctr_trend,
            position_trend=position_trend,
            top_queries_trend=top_queries_trend,
            url_contains=url_contains,
        )
    except trends_service.TrendsServiceError as exc:
        _raise_http_for_trends_error(exc)
    return PaginatedGscCompareResponse.model_validate(payload)
