from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.crawl_job import CrawlJobResponse
from app.schemas.site import (
    SiteCrawlCreateRequest,
    SiteCrawlListItemResponse,
    SiteDetailResponse,
    SiteListItemResponse,
)
from app.services import crawl_job_service, site_service

router = APIRouter(prefix="/sites", tags=["sites"])


def _raise_http_for_site_error(exc: Exception) -> None:
    detail = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("", response_model=list[SiteListItemResponse])
def list_sites(session: Session = Depends(get_db)) -> list[SiteListItemResponse]:
    payload = site_service.list_sites(session)
    return [SiteListItemResponse.model_validate(item) for item in payload]


@router.get("/{site_id}", response_model=SiteDetailResponse)
def get_site_detail(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    baseline_crawl_id: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_db),
) -> SiteDetailResponse:
    try:
        payload = site_service.build_site_detail(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
        )
    except site_service.SiteServiceError as exc:
        _raise_http_for_site_error(exc)
    return SiteDetailResponse.model_validate(payload)


@router.get("/{site_id}/crawls", response_model=list[SiteCrawlListItemResponse])
def list_site_crawls(site_id: int, session: Session = Depends(get_db)) -> list[SiteCrawlListItemResponse]:
    try:
        payload = site_service.list_site_crawls(session, site_id)
    except site_service.SiteServiceError as exc:
        _raise_http_for_site_error(exc)
    return [SiteCrawlListItemResponse.model_validate(item) for item in payload]


@router.post("/{site_id}/crawls", response_model=CrawlJobResponse, status_code=status.HTTP_201_CREATED)
def create_site_crawl(
    site_id: int,
    payload: SiteCrawlCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> CrawlJobResponse:
    site = crawl_job_service.get_site(session, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Site {site_id} not found.")

    root_url = payload.root_url or site.root_url
    try:
        crawl_job = crawl_job_service.create_crawl_job_for_site(
            session=session,
            site_id=site_id,
            root_url=root_url,
            max_urls=payload.max_urls,
            max_depth=payload.max_depth,
            delay=payload.delay,
            render_mode=payload.render_mode,
            render_timeout_ms=payload.render_timeout_ms,
            max_rendered_pages_per_job=payload.max_rendered_pages_per_job,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    session.commit()
    session.refresh(crawl_job)

    start_url = str(crawl_job.settings_json.get("start_url", root_url))
    background_tasks.add_task(
        crawl_job_service.run_crawl_job_subprocess,
        crawl_job.id,
        root_url=start_url,
        max_urls=payload.max_urls,
        max_depth=payload.max_depth,
        delay=payload.delay,
        render_mode=payload.render_mode,
        render_timeout_ms=payload.render_timeout_ms,
        max_rendered_pages_per_job=payload.max_rendered_pages_per_job,
    )
    return CrawlJobResponse.model_validate(crawl_job)
