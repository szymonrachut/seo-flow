from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.crawl_job import CrawlJobCreateRequest, CrawlJobDetailResponse, CrawlJobResponse
from app.services import crawl_job_service

router = APIRouter(prefix="/crawl-jobs", tags=["crawl-jobs"])


@router.post("", response_model=CrawlJobResponse, status_code=status.HTTP_201_CREATED)
def create_crawl_job(
    payload: CrawlJobCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> CrawlJobResponse:
    try:
        crawl_job = crawl_job_service.create_crawl_job(
            session=session,
            root_url=payload.root_url,
            max_urls=payload.max_urls,
            max_depth=payload.max_depth,
            delay=payload.delay,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    session.commit()
    session.refresh(crawl_job)

    start_url = str(crawl_job.settings_json.get("start_url", payload.root_url))
    background_tasks.add_task(
        crawl_job_service.run_crawl_job_subprocess,
        crawl_job.id,
        root_url=start_url,
        max_urls=payload.max_urls,
        max_depth=payload.max_depth,
        delay=payload.delay,
    )
    return CrawlJobResponse.model_validate(crawl_job)


@router.get("/{job_id}", response_model=CrawlJobDetailResponse)
def get_crawl_job(job_id: int, session: Session = Depends(get_db)) -> CrawlJobDetailResponse:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")
    payload = crawl_job_service.build_crawl_job_detail(session, crawl_job)
    return CrawlJobDetailResponse.model_validate(payload)


@router.post("/{job_id}/stop", response_model=CrawlJobDetailResponse)
def stop_crawl_job(job_id: int, session: Session = Depends(get_db)) -> CrawlJobDetailResponse:
    crawl_job = crawl_job_service.stop_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")
    session.commit()
    session.refresh(crawl_job)
    payload = crawl_job_service.build_crawl_job_detail(session, crawl_job)
    return CrawlJobDetailResponse.model_validate(payload)
