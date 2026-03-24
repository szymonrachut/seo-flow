from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.content_recommendations import (
    ContentRecommendationMarkDoneRequest,
    ContentRecommendationMarkDoneResponse,
    PaginatedContentRecommendationsResponse,
)
from app.schemas.gsc import GscDateRangeLabel
from app.services import content_recommendation_service, export_service

router = APIRouter(prefix="/sites", tags=["site-content-recommendations"])


def _raise_http_for_content_recommendation_error(exc: Exception) -> None:
    detail = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=detail) from exc


def _export_filename(site_id: int, *, filtered: bool = False) -> str:
    suffix = "_view" if filtered else ""
    return f'attachment; filename="site_{site_id}_content_recommendations{suffix}.csv"'


@router.get("/{site_id}/content-recommendations", response_model=PaginatedContentRecommendationsResponse)
def get_site_content_recommendations(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    baseline_crawl_id: int | None = Query(default=None, ge=1),
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: Literal["priority_score", "confidence", "impact", "effort", "cluster_label", "recommendation_type", "page_type"] = Query(default="priority_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    recommendation_type: Literal[
        "MISSING_SUPPORTING_CONTENT",
        "THIN_CLUSTER",
        "EXPAND_EXISTING_PAGE",
        "MISSING_STRUCTURAL_PAGE_TYPE",
        "INTERNAL_LINKING_SUPPORT",
    ] | None = Query(default=None),
    segment: Literal["create_new_page", "expand_existing_page", "strengthen_cluster", "improve_internal_support"] | None = Query(default=None),
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
    cluster: str | None = Query(default=None),
    confidence_min: float | None = Query(default=None, ge=0, le=1),
    priority_score_min: int | None = Query(default=None, ge=0, le=100),
    implemented_outcome_window: Literal["7d", "30d", "90d", "all"] = Query(default="30d"),
    implemented_status_filter: Literal[
        "all",
        "improved",
        "worsened",
        "unchanged",
        "pending",
        "limited",
        "unavailable",
        "too_early",
    ] = Query(default="all"),
    implemented_mode_filter: Literal[
        "all",
        "gsc",
        "internal_linking",
        "cannibalization",
        "issue_flags",
        "mixed",
        "unknown",
    ] = Query(default="all"),
    implemented_search: str | None = Query(default=None),
    implemented_sort: Literal[
        "implemented_at_desc",
        "implemented_at_asc",
        "outcome",
        "recommendation_type",
        "title",
    ] = Query(default="implemented_at_desc"),
    session: Session = Depends(get_db),
) -> PaginatedContentRecommendationsResponse:
    try:
        payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range=gsc_date_range,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            recommendation_type=recommendation_type,
            segment=segment,
            page_type=page_type,
            cluster=cluster,
            confidence_min=confidence_min,
            priority_score_min=priority_score_min,
            implemented_outcome_window=implemented_outcome_window,
            implemented_status_filter=implemented_status_filter,
            implemented_mode_filter=implemented_mode_filter,
            implemented_search=implemented_search,
            implemented_sort=implemented_sort,
        )
    except content_recommendation_service.ContentRecommendationServiceError as exc:
        _raise_http_for_content_recommendation_error(exc)
    except RuntimeError as exc:
        _raise_http_for_content_recommendation_error(exc)
    return PaginatedContentRecommendationsResponse.model_validate(payload)


@router.post(
    "/{site_id}/content-recommendations/mark-done",
    response_model=ContentRecommendationMarkDoneResponse,
)
def mark_site_content_recommendation_done(
    site_id: int,
    input_data: ContentRecommendationMarkDoneRequest,
    session: Session = Depends(get_db),
) -> ContentRecommendationMarkDoneResponse:
    try:
        payload = content_recommendation_service.mark_site_content_recommendation_done(
            session,
            site_id,
            recommendation_key=input_data.recommendation_key,
            active_crawl_id=input_data.active_crawl_id,
            baseline_crawl_id=input_data.baseline_crawl_id,
            gsc_date_range=input_data.gsc_date_range,
        )
    except content_recommendation_service.ContentRecommendationServiceError as exc:
        _raise_http_for_content_recommendation_error(exc)
    except RuntimeError as exc:
        _raise_http_for_content_recommendation_error(exc)
    return ContentRecommendationMarkDoneResponse.model_validate(payload)


@router.get("/{site_id}/export/content-recommendations.csv")
def export_site_content_recommendations_csv(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    baseline_crawl_id: int | None = Query(default=None, ge=1),
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    sort_by: Literal["priority_score", "confidence", "impact", "effort", "cluster_label", "recommendation_type", "page_type"] = Query(default="priority_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    recommendation_type: Literal[
        "MISSING_SUPPORTING_CONTENT",
        "THIN_CLUSTER",
        "EXPAND_EXISTING_PAGE",
        "MISSING_STRUCTURAL_PAGE_TYPE",
        "INTERNAL_LINKING_SUPPORT",
    ] | None = Query(default=None),
    segment: Literal["create_new_page", "expand_existing_page", "strengthen_cluster", "improve_internal_support"] | None = Query(default=None),
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
    cluster: str | None = Query(default=None),
    confidence_min: float | None = Query(default=None, ge=0, le=1),
    priority_score_min: int | None = Query(default=None, ge=0, le=100),
    session: Session = Depends(get_db),
) -> Response:
    try:
        content = export_service.build_site_content_recommendations_csv(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range=gsc_date_range,
            sort_by=sort_by,
            sort_order=sort_order,
            recommendation_type=recommendation_type,
            segment=segment,
            page_type=page_type,
            cluster=cluster,
            confidence_min=confidence_min,
            priority_score_min=priority_score_min,
        )
    except content_recommendation_service.ContentRecommendationServiceError as exc:
        _raise_http_for_content_recommendation_error(exc)
    except RuntimeError as exc:
        _raise_http_for_content_recommendation_error(exc)

    filtered = any(
        value is not None and value != ""
        for value in [active_crawl_id, baseline_crawl_id, recommendation_type, segment, page_type, cluster, confidence_min, priority_score_min]
    ) or gsc_date_range != "last_28_days" or sort_by != "priority_score" or sort_order != "desc"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": _export_filename(site_id, filtered=filtered)},
    )
