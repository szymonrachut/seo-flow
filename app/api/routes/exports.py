from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services import crawl_job_service, export_service

router = APIRouter(prefix="/crawl-jobs", tags=["exports"])


@router.get("/{job_id}/export/pages.csv")
def export_pages_csv(job_id: int, session: Session = Depends(get_db)) -> Response:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    content = export_service.build_pages_csv(session, job_id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="crawl_job_{job_id}_pages.csv"'},
    )


@router.get("/{job_id}/export/links.csv")
def export_links_csv(job_id: int, session: Session = Depends(get_db)) -> Response:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    content = export_service.build_links_csv(session, job_id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="crawl_job_{job_id}_links.csv"'},
    )


@router.get("/{job_id}/export/audit.csv")
def export_audit_csv(job_id: int, session: Session = Depends(get_db)) -> Response:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    content = export_service.build_audit_csv(session, job_id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="crawl_job_{job_id}_audit.csv"'},
    )
