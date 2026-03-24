from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.gsc import GscDateRangeLabel
from app.schemas.opportunities import OpportunitiesSummaryResponse, OpportunityType, PriorityLevel
from app.services import crawl_job_service, priority_service

router = APIRouter(prefix="/crawl-jobs", tags=["opportunities"])


@router.get("/{job_id}/opportunities", response_model=OpportunitiesSummaryResponse)
def get_job_opportunities(
    job_id: int,
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    priority_level: PriorityLevel | None = Query(default=None),
    opportunity_type: OpportunityType | None = Query(default=None),
    priority_score_min: int | None = Query(default=None),
    priority_score_max: int | None = Query(default=None),
    sort_by: Literal["count", "top_priority_score", "top_opportunity_score", "type"] = Query(default="count"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    top_pages_limit: int = Query(default=5, ge=1, le=20),
    session: Session = Depends(get_db),
) -> OpportunitiesSummaryResponse:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")
    if priority_score_min is not None and priority_score_max is not None and priority_score_min > priority_score_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="priority_score_min cannot be greater than priority_score_max.")

    records = crawl_job_service.get_all_pages_for_job(
        session,
        job_id,
        sort_by="priority_score",
        sort_order="desc",
        gsc_date_range=gsc_date_range,
        priority_level=priority_level,
        opportunity_type=opportunity_type,
        priority_score_min=priority_score_min,
        priority_score_max=priority_score_max,
    )
    payload = priority_service.build_opportunities_summary(
        records,
        gsc_date_range=gsc_date_range,
        sort_by=sort_by,
        sort_order=sort_order,
        top_pages_limit=top_pages_limit,
    )
    payload["crawl_job_id"] = job_id
    return OpportunitiesSummaryResponse.model_validate(payload)
