from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.gsc import GscDateRangeLabel
from app.schemas.internal_linking import (
    InternalLinkingIssueType,
    InternalLinkingOverviewResponse,
    PaginatedInternalLinkingIssuesResponse,
)
from app.schemas.opportunities import OpportunityType, PriorityLevel
from app.services import internal_linking_service

router = APIRouter(prefix="/crawl-jobs", tags=["internal-linking"])


def _raise_http_for_internal_linking_error(exc: internal_linking_service.InternalLinkingServiceError) -> None:
    detail = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/{job_id}/internal-linking/overview", response_model=InternalLinkingOverviewResponse)
def get_internal_linking_overview(
    job_id: int,
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    session: Session = Depends(get_db),
) -> InternalLinkingOverviewResponse:
    try:
        payload = internal_linking_service.build_internal_linking_overview(
            session,
            job_id,
            gsc_date_range=gsc_date_range,
        )
    except internal_linking_service.InternalLinkingServiceError as exc:
        _raise_http_for_internal_linking_error(exc)
    return InternalLinkingOverviewResponse.model_validate(payload)


@router.get("/{job_id}/internal-linking/issues", response_model=PaginatedInternalLinkingIssuesResponse)
def get_internal_linking_issues(
    job_id: int,
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: Literal[
        "url",
        "internal_linking_score",
        "priority_score",
        "link_equity_score",
        "link_equity_rank",
        "incoming_follow_links",
        "incoming_follow_linking_pages",
        "body_like_share",
        "boilerplate_like_share",
        "anchor_diversity_score",
        "exact_match_anchor_ratio",
        "issue_count",
    ] = Query(default="internal_linking_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    issue_type: InternalLinkingIssueType | None = Query(default=None),
    priority_level: PriorityLevel | None = Query(default=None),
    opportunity_type: OpportunityType | None = Query(default=None),
    url_contains: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedInternalLinkingIssuesResponse:
    try:
        payload = internal_linking_service.build_internal_linking_issues(
            session,
            job_id,
            gsc_date_range=gsc_date_range,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            issue_type=issue_type,
            priority_level=priority_level,
            opportunity_type=opportunity_type,
            url_contains=url_contains,
        )
    except internal_linking_service.InternalLinkingServiceError as exc:
        _raise_http_for_internal_linking_error(exc)
    return PaginatedInternalLinkingIssuesResponse.model_validate(payload)
