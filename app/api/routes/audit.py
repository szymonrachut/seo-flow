from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.audit import AuditReportResponse
from app.services import audit_service, crawl_job_service

router = APIRouter(prefix="/crawl-jobs", tags=["audit"])


@router.get("/{job_id}/audit", response_model=AuditReportResponse)
def get_crawl_job_audit(job_id: int, session: Session = Depends(get_db)) -> AuditReportResponse:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    report = audit_service.build_audit_report(session, job_id)
    return AuditReportResponse.model_validate(report)
