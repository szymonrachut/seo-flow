from __future__ import annotations

import logging
from typing import Literal
from urllib.parse import urlencode, urlparse, parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.integrations.gsc.auth import GscAuthError, build_authorization_url, exchange_code_for_credentials
from app.integrations.gsc.client import GscApiError
from app.schemas.gsc import (
    GscDateRangeLabel,
    GscImportRequest,
    GscImportResponse,
    GscPropertyOptionResponse,
    GscPropertySelectionRequest,
    GscSelectedPropertyResponse,
    GscSiteSummaryResponse,
    GscSummaryResponse,
    GscTopQueriesPageContextResponse,
    GscTopQueryRowResponse,
    PaginatedGscTopQueriesResponse,
)
from app.services import crawl_job_service, gsc_service
from app.services.gsc_service import GscServiceError

router = APIRouter(tags=["gsc"])
logger = logging.getLogger(__name__)


def _raise_http_for_gsc_service_error(exc: GscServiceError) -> None:
    detail = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/sites/{site_id}/gsc/oauth/start", include_in_schema=False, response_model=None)
def start_site_gsc_oauth(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    frontend_redirect_url: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        active_crawl = gsc_service.get_active_crawl_for_site(session, site_id, active_crawl_id=active_crawl_id)
        redirect_url = gsc_service.resolve_frontend_site_gsc_redirect(
            site_id,
            active_crawl_id=active_crawl.id if active_crawl is not None else None,
            redirect_url=frontend_redirect_url,
        )
        authorization_url = build_authorization_url(redirect_url=redirect_url)
    except GscAuthError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except GscServiceError as exc:
        _raise_http_for_gsc_service_error(exc)

    return RedirectResponse(authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/crawl-jobs/{job_id}/gsc/oauth/start", include_in_schema=False, response_model=None)
def start_gsc_oauth(
    job_id: int,
    frontend_redirect_url: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> RedirectResponse:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    try:
        redirect_url = gsc_service.resolve_frontend_gsc_redirect(job_id, frontend_redirect_url)
        authorization_url = build_authorization_url(redirect_url=redirect_url)
    except GscAuthError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except GscServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/gsc/oauth/callback", include_in_schema=False, response_model=None)
def finish_gsc_oauth(
    state: str,
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse | HTMLResponse:
    if error:
        return HTMLResponse(
            f"<h1>Google Search Console OAuth failed</h1><p>{error}</p>",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if not code:
        return HTMLResponse(
            "<h1>Google Search Console OAuth failed</h1><p>Missing authorization code.</p>",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        state_payload = exchange_code_for_credentials(state=state, code=code)
    except GscAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - last-resort guard for unexpected callback failures
        logger.exception("Unexpected error while finishing Google Search Console OAuth callback.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected Google OAuth callback failure. Check backend logs and restart the GSC flow.",
        ) from exc

    redirect_url = _append_query_params(state_payload.redirect_url, {"oauth": "success"})
    return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/crawl-jobs/{job_id}/gsc/properties", response_model=list[GscPropertyOptionResponse])
def list_gsc_properties(job_id: int, session: Session = Depends(get_db)) -> list[GscPropertyOptionResponse]:
    try:
        payload = gsc_service.list_accessible_properties_for_job(session, job_id)
    except GscServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GscAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except GscApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return [GscPropertyOptionResponse.model_validate(item) for item in payload]


@router.get("/sites/{site_id}/gsc/properties", response_model=list[GscPropertyOptionResponse])
def list_site_gsc_properties(site_id: int, session: Session = Depends(get_db)) -> list[GscPropertyOptionResponse]:
    try:
        payload = gsc_service.list_accessible_properties_for_site(session, site_id)
    except GscServiceError as exc:
        _raise_http_for_gsc_service_error(exc)
    except GscAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except GscApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return [GscPropertyOptionResponse.model_validate(item) for item in payload]


@router.put("/crawl-jobs/{job_id}/gsc/property", response_model=GscSelectedPropertyResponse)
def select_gsc_property(
    job_id: int,
    payload: GscPropertySelectionRequest,
    session: Session = Depends(get_db),
) -> GscSelectedPropertyResponse:
    try:
        gsc_property = gsc_service.select_property_for_job(session, job_id, payload.property_uri)
    except GscServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except GscAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except GscApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    session.commit()
    session.refresh(gsc_property)
    return GscSelectedPropertyResponse.model_validate(gsc_property)


@router.put("/sites/{site_id}/gsc/property", response_model=GscSelectedPropertyResponse)
def select_site_gsc_property(
    site_id: int,
    payload: GscPropertySelectionRequest,
    session: Session = Depends(get_db),
) -> GscSelectedPropertyResponse:
    try:
        gsc_property = gsc_service.select_property_for_site(session, site_id, payload.property_uri)
    except GscServiceError as exc:
        _raise_http_for_gsc_service_error(exc)
    except GscAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except GscApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    session.commit()
    session.refresh(gsc_property)
    return GscSelectedPropertyResponse.model_validate(gsc_property)


@router.get("/crawl-jobs/{job_id}/gsc/summary", response_model=GscSummaryResponse)
def get_gsc_summary(job_id: int, session: Session = Depends(get_db)) -> GscSummaryResponse:
    try:
        payload = gsc_service.build_gsc_summary(session, job_id)
    except GscServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return GscSummaryResponse.model_validate(payload)


@router.get("/sites/{site_id}/gsc/summary", response_model=GscSiteSummaryResponse)
def get_site_gsc_summary(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_db),
) -> GscSiteSummaryResponse:
    try:
        payload = gsc_service.build_site_gsc_summary(session, site_id, active_crawl_id=active_crawl_id)
    except GscServiceError as exc:
        _raise_http_for_gsc_service_error(exc)
    return GscSiteSummaryResponse.model_validate(payload)


@router.post("/crawl-jobs/{job_id}/gsc/import", response_model=GscImportResponse)
def import_gsc_data(
    job_id: int,
    payload: GscImportRequest,
    session: Session = Depends(get_db),
) -> GscImportResponse:
    try:
        result = gsc_service.import_gsc_for_job(
            session,
            job_id,
            date_ranges=payload.date_ranges,
            top_queries_limit=payload.top_queries_limit,
        )
    except GscServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except GscAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except GscApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    session.commit()
    return GscImportResponse.model_validate(result)


@router.post("/sites/{site_id}/gsc/import", response_model=GscImportResponse)
def import_site_gsc_data(
    site_id: int,
    payload: GscImportRequest,
    active_crawl_id: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_db),
) -> GscImportResponse:
    try:
        result = gsc_service.import_gsc_for_site(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            date_ranges=payload.date_ranges,
            top_queries_limit=payload.top_queries_limit,
        )
    except GscServiceError as exc:
        _raise_http_for_gsc_service_error(exc)
    except GscAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except GscApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    session.commit()
    return GscImportResponse.model_validate(result)


@router.get("/crawl-jobs/{job_id}/gsc/top-queries", response_model=PaginatedGscTopQueriesResponse)
def list_job_top_queries(
    job_id: int,
    page_id: int | None = Query(default=None),
    date_range_label: GscDateRangeLabel = Query(default="last_28_days"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: Literal["query", "clicks", "impressions", "ctr", "position", "url"] = Query(default="clicks"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    query_contains: str | None = Query(default=None),
    query_excludes: str | None = Query(default=None),
    clicks_min: int | None = Query(default=None),
    impressions_min: int | None = Query(default=None),
    ctr_max: float | None = Query(default=None),
    position_min: float | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedGscTopQueriesResponse:
    return _build_top_queries_response(
        session,
        job_id,
        page_id=page_id,
        date_range_label=date_range_label,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        query_contains=query_contains,
        query_excludes=query_excludes,
        clicks_min=clicks_min,
        impressions_min=impressions_min,
        ctr_max=ctr_max,
        position_min=position_min,
    )


@router.get("/crawl-jobs/{job_id}/pages/{page_id}/gsc/top-queries", response_model=PaginatedGscTopQueriesResponse)
def list_page_top_queries(
    job_id: int,
    page_id: int,
    date_range_label: GscDateRangeLabel = Query(default="last_28_days"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: Literal["query", "clicks", "impressions", "ctr", "position", "url"] = Query(default="clicks"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    query_contains: str | None = Query(default=None),
    query_excludes: str | None = Query(default=None),
    clicks_min: int | None = Query(default=None),
    impressions_min: int | None = Query(default=None),
    ctr_max: float | None = Query(default=None),
    position_min: float | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedGscTopQueriesResponse:
    return _build_top_queries_response(
        session,
        job_id,
        page_id=page_id,
        date_range_label=date_range_label,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        query_contains=query_contains,
        query_excludes=query_excludes,
        clicks_min=clicks_min,
        impressions_min=impressions_min,
        ctr_max=ctr_max,
        position_min=position_min,
    )


def _build_top_queries_response(
    session: Session,
    job_id: int,
    *,
    page_id: int | None,
    date_range_label: GscDateRangeLabel,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    query_contains: str | None,
    query_excludes: str | None,
    clicks_min: int | None,
    impressions_min: int | None,
    ctr_max: float | None,
    position_min: float | None,
) -> PaginatedGscTopQueriesResponse:
    try:
        items, total_items, page_context = gsc_service.list_top_queries(
            session,
            job_id,
            page_id=page_id,
            date_range_label=date_range_label,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            query_contains=query_contains,
            query_excludes=query_excludes,
            clicks_min=clicks_min,
            impressions_min=impressions_min,
            ctr_max=ctr_max,
            position_min=position_min,
        )
    except GscServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    return PaginatedGscTopQueriesResponse(
        items=[GscTopQueryRowResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        page_context=(
            GscTopQueriesPageContextResponse.model_validate(page_context)
            if page_context is not None
            else None
        ),
    )


def _append_query_params(url: str, params: dict[str, str]) -> str:
    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_params.update(params)
    return parsed._replace(query=urlencode(query_params)).geturl()
