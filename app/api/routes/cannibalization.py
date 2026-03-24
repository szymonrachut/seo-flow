from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.cannibalization import (
    CannibalizationClusterResponse,
    CannibalizationPageDetailsResponse,
    CannibalizationRecommendationType,
    CannibalizationSeverity,
    PaginatedCannibalizationClustersResponse,
)
from app.schemas.gsc import GscDateRangeLabel
from app.schemas.opportunities import ImpactLevel
from app.services import cannibalization_service

router = APIRouter(prefix="/crawl-jobs", tags=["cannibalization"])


def _raise_http_for_cannibalization_error(exc: cannibalization_service.CannibalizationServiceError) -> None:
    detail = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/{job_id}/cannibalization", response_model=PaginatedCannibalizationClustersResponse)
def get_cannibalization_clusters(
    job_id: int,
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: Literal[
        "severity",
        "impact_level",
        "weighted_overlap",
        "shared_queries_count",
        "shared_query_impressions",
        "shared_query_clicks",
        "urls_count",
        "dominant_url_confidence",
        "recommendation_type",
        "cluster_id",
    ] = Query(default="severity"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    severity: CannibalizationSeverity | None = Query(default=None),
    impact_level: ImpactLevel | None = Query(default=None),
    recommendation_type: CannibalizationRecommendationType | None = Query(default=None),
    has_clear_primary: bool | None = Query(default=None),
    url_contains: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedCannibalizationClustersResponse:
    try:
        payload = cannibalization_service.build_cannibalization_report(
            session,
            job_id,
            gsc_date_range=gsc_date_range,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            severity=severity,
            impact_level=impact_level,
            recommendation_type=recommendation_type,
            has_clear_primary=has_clear_primary,
            url_contains=url_contains,
        )
    except cannibalization_service.CannibalizationServiceError as exc:
        _raise_http_for_cannibalization_error(exc)
    return PaginatedCannibalizationClustersResponse.model_validate(
        {
            **payload,
            "items": [CannibalizationClusterResponse.model_validate(item) for item in payload["items"]],
        }
    )


@router.get("/{job_id}/cannibalization/pages/{page_id}", response_model=CannibalizationPageDetailsResponse)
def get_cannibalization_page_details(
    job_id: int,
    page_id: int,
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    session: Session = Depends(get_db),
) -> CannibalizationPageDetailsResponse:
    try:
        payload = cannibalization_service.build_cannibalization_page_details(
            session,
            job_id,
            page_id,
            gsc_date_range=gsc_date_range,
        )
    except cannibalization_service.CannibalizationServiceError as exc:
        _raise_http_for_cannibalization_error(exc)
    return CannibalizationPageDetailsResponse.model_validate(payload)
