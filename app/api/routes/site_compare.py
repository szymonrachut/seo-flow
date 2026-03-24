from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.gsc import GscDateRangeLabel
from app.schemas.site_compare import (
    PaginatedSiteInternalLinkingCompareResponse,
    PaginatedSiteOpportunitiesCompareResponse,
    PaginatedSitePagesCompareResponse,
    SiteAuditCompareResponse,
)
from app.services import site_compare_service

router = APIRouter(prefix="/sites", tags=["site-compare"])


def _raise_http_for_compare_error(exc: site_compare_service.SiteCompareServiceError) -> None:
    detail = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/{site_id}/pages", response_model=PaginatedSitePagesCompareResponse)
def get_site_pages_compare(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    baseline_crawl_id: int | None = Query(default=None, ge=1),
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: Literal[
        "url",
        "change_type",
        "active_status_code",
        "delta_priority_score",
        "active_priority_score",
        "delta_word_count",
        "delta_response_time_ms",
        "delta_incoming_internal_links",
        "delta_incoming_internal_linking_pages",
        "priority_trend",
        "word_count_trend",
        "response_time_trend",
        "internal_linking_trend",
    ] = Query(default="change_type"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    change_type: str | None = Query(default=None),
    changed: bool | None = Query(default=None),
    status_changed: bool | None = Query(default=None),
    title_changed: bool | None = Query(default=None),
    meta_description_changed: bool | None = Query(default=None),
    h1_changed: bool | None = Query(default=None),
    canonical_changed: bool | None = Query(default=None),
    noindex_changed: bool | None = Query(default=None),
    priority_trend: str | None = Query(default=None),
    internal_linking_trend: str | None = Query(default=None),
    content_trend: str | None = Query(default=None),
    response_time_trend: str | None = Query(default=None),
    url_contains: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedSitePagesCompareResponse:
    try:
        payload = site_compare_service.build_site_pages_compare(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range=gsc_date_range,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            change_type=change_type,
            changed=changed,
            status_changed=status_changed,
            title_changed=title_changed,
            meta_description_changed=meta_description_changed,
            h1_changed=h1_changed,
            canonical_changed=canonical_changed,
            noindex_changed=noindex_changed,
            priority_trend=priority_trend,
            internal_linking_trend=internal_linking_trend,
            content_trend=content_trend,
            response_time_trend=response_time_trend,
            url_contains=url_contains,
        )
    except site_compare_service.SiteCompareServiceError as exc:
        _raise_http_for_compare_error(exc)
    return PaginatedSitePagesCompareResponse.model_validate(payload)


@router.get("/{site_id}/audit", response_model=SiteAuditCompareResponse)
def get_site_audit_compare(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    baseline_crawl_id: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
    session: Session = Depends(get_db),
) -> SiteAuditCompareResponse:
    try:
        payload = site_compare_service.build_site_audit_compare(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            status=status_filter,
        )
    except site_compare_service.SiteCompareServiceError as exc:
        _raise_http_for_compare_error(exc)
    return SiteAuditCompareResponse.model_validate(payload)


@router.get("/{site_id}/opportunities", response_model=PaginatedSiteOpportunitiesCompareResponse)
def get_site_opportunities_compare(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    baseline_crawl_id: int | None = Query(default=None, ge=1),
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: Literal["url", "change_type", "active_priority_score", "delta_priority_score", "active_opportunity_count"] = Query(default="delta_priority_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    change_kind: str | None = Query(default=None),
    opportunity_type: str | None = Query(default=None),
    url_contains: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedSiteOpportunitiesCompareResponse:
    try:
        payload = site_compare_service.build_site_opportunities_compare(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range=gsc_date_range,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            change_kind=change_kind,
            opportunity_type=opportunity_type,
            url_contains=url_contains,
        )
    except site_compare_service.SiteCompareServiceError as exc:
        _raise_http_for_compare_error(exc)
    return PaginatedSiteOpportunitiesCompareResponse.model_validate(payload)


@router.get("/{site_id}/internal-linking", response_model=PaginatedSiteInternalLinkingCompareResponse)
def get_site_internal_linking_compare(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    baseline_crawl_id: int | None = Query(default=None, ge=1),
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: Literal[
        "url",
        "change_type",
        "delta_internal_linking_score",
        "delta_link_equity_score",
        "delta_incoming_follow_linking_pages",
        "delta_anchor_diversity_score",
        "delta_boilerplate_like_share",
    ] = Query(default="delta_internal_linking_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    change_type: str | None = Query(default=None),
    compare_kind: str | None = Query(default=None),
    issue_type: str | None = Query(default=None),
    url_contains: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> PaginatedSiteInternalLinkingCompareResponse:
    try:
        payload = site_compare_service.build_site_internal_linking_compare(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range=gsc_date_range,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            change_type=change_type,
            compare_kind=compare_kind,
            issue_type=issue_type,
            url_contains=url_contains,
        )
    except site_compare_service.SiteCompareServiceError as exc:
        _raise_http_for_compare_error(exc)
    return PaginatedSiteInternalLinkingCompareResponse.model_validate(payload)
