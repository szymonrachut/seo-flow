from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.page import PageResponse, PaginatedPageResponse
from app.services import crawl_job_service

router = APIRouter(prefix="/crawl-jobs", tags=["pages"])


@router.get("/{job_id}/pages", response_model=PaginatedPageResponse)
def get_crawl_job_pages(
    job_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: Literal["url", "status_code", "depth", "title", "fetched_at", "response_time_ms"] = Query(default="url"),
    sort_order: Literal["asc", "desc"] = Query(default="asc"),
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
    non_indexable_like: bool | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedPageResponse:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    if status_code_min is not None and status_code_max is not None and status_code_min > status_code_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status_code_min cannot be greater than status_code_max.")

    try:
        pages, total_items = crawl_job_service.get_pages_for_job(
            session,
            job_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
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
            non_indexable_like=non_indexable_like,
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
    )
