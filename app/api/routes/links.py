from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.link import LinkResponse, PaginatedLinkResponse
from app.services import crawl_job_service

router = APIRouter(prefix="/crawl-jobs", tags=["links"])


@router.get("/{job_id}/links", response_model=PaginatedLinkResponse)
def get_crawl_job_links(
    job_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: Literal["source_url", "target_url", "target_domain", "anchor_text", "is_internal", "is_nofollow"] = Query(
        default="source_url"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="asc"),
    is_internal: bool | None = Query(default=None),
    is_nofollow: bool | None = Query(default=None),
    target_domain: str | None = Query(default=None),
    has_anchor: bool | None = Query(default=None),
    broken_internal: bool | None = Query(default=None),
    redirecting_internal: bool | None = Query(default=None),
    unresolved_internal: bool | None = Query(default=None),
    to_noindex_like: bool | None = Query(default=None),
    to_canonicalized: bool | None = Query(default=None),
    redirect_chain: bool | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedLinkResponse:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    links, total_items = crawl_job_service.get_links_for_job(
        session,
        job_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        is_internal=is_internal,
        is_nofollow=is_nofollow,
        target_domain=target_domain,
        has_anchor=has_anchor,
        broken_internal=broken_internal,
        redirecting_internal=redirecting_internal,
        unresolved_internal=unresolved_internal,
        to_noindex_like=to_noindex_like,
        to_canonicalized=to_canonicalized,
        redirect_chain=redirect_chain,
    )
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    return PaginatedLinkResponse(
        items=[LinkResponse.model_validate(item) for item in links],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
