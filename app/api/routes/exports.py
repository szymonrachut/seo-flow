from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.gsc import GscDateRangeLabel
from app.schemas.opportunities import ImpactLevel, OpportunityType, PriorityLevel
from app.services import cannibalization_service, crawl_job_service, export_service, internal_linking_service, trends_service
from app.services.gsc_service import GscServiceError

router = APIRouter(prefix="/crawl-jobs", tags=["exports"])


def _export_filename(job_id: int, kind: str, *, filtered: bool = False) -> str:
    suffix = "_view" if filtered else ""
    return f'attachment; filename="crawl_job_{job_id}_{kind}{suffix}.csv"'


@router.get("/{job_id}/export/pages.csv")
def export_pages_csv(
    job_id: int,
    sort_by: Literal[
        "url",
        "status_code",
        "depth",
        "page_type",
        "page_bucket",
        "page_type_confidence",
        "title",
        "title_length",
        "meta_description",
        "meta_description_length",
        "h1",
        "h1_length",
        "h1_count",
        "h2_count",
        "canonical_url",
        "robots_meta",
        "x_robots_tag",
        "word_count",
        "was_rendered",
        "js_heavy_like",
        "schema_count",
        "images_count",
        "images_missing_alt_count",
        "html_size_bytes",
        "gsc_clicks",
        "gsc_impressions",
        "gsc_ctr",
        "gsc_position",
        "gsc_top_queries_count",
        "priority_score",
        "fetched_at",
        "response_time_ms",
    ] = Query(default="url"),
    sort_order: Literal["asc", "desc"] = Query(default="asc"),
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    url_contains: str | None = Query(default=None),
    title_contains: str | None = Query(default=None),
    page_type: Literal[
        "home",
        "category",
        "product",
        "service",
        "blog_article",
        "blog_index",
        "contact",
        "about",
        "faq",
        "location",
        "legal",
        "utility",
        "other",
    ] | None = Query(default=None),
    page_bucket: Literal["commercial", "informational", "utility", "trust", "other"] | None = Query(default=None),
    page_type_confidence_min: float | None = Query(default=None, ge=0, le=1),
    page_type_confidence_max: float | None = Query(default=None, ge=0, le=1),
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
    noindex_like: bool | None = Query(default=None),
    non_indexable_like: bool | None = Query(default=None),
    title_exact: str | None = Query(default=None),
    meta_description_exact: str | None = Query(default=None),
    content_text_hash_exact: str | None = Query(default=None),
    title_too_short: bool | None = Query(default=None),
    title_too_long: bool | None = Query(default=None),
    meta_too_short: bool | None = Query(default=None),
    meta_too_long: bool | None = Query(default=None),
    multiple_h1: bool | None = Query(default=None),
    missing_h2: bool | None = Query(default=None),
    self_canonical: bool | None = Query(default=None),
    canonical_to_other_url: bool | None = Query(default=None),
    canonical_to_non_200: bool | None = Query(default=None),
    canonical_to_redirect: bool | None = Query(default=None),
    thin_content: bool | None = Query(default=None),
    duplicate_content: bool | None = Query(default=None),
    missing_alt_images: bool | None = Query(default=None),
    no_images: bool | None = Query(default=None),
    oversized: bool | None = Query(default=None),
    was_rendered: bool | None = Query(default=None),
    js_heavy_like: bool | None = Query(default=None),
    schema_present: bool | None = Query(default=None),
    schema_type: str | None = Query(default=None),
    has_render_error: bool | None = Query(default=None),
    has_x_robots_tag: bool | None = Query(default=None),
    has_technical_issue: bool | None = Query(default=None),
    has_gsc_data: bool | None = Query(default=None),
    has_cannibalization: bool | None = Query(default=None),
    priority_level: PriorityLevel | None = Query(default=None),
    opportunity_type: OpportunityType | None = Query(default=None),
    priority_score_min: int | None = Query(default=None),
    priority_score_max: int | None = Query(default=None),
    gsc_clicks_min: int | None = Query(default=None),
    gsc_clicks_max: int | None = Query(default=None),
    gsc_impressions_min: int | None = Query(default=None),
    gsc_impressions_max: int | None = Query(default=None),
    gsc_ctr_min: float | None = Query(default=None),
    gsc_ctr_max: float | None = Query(default=None),
    gsc_position_min: float | None = Query(default=None),
    gsc_position_max: float | None = Query(default=None),
    gsc_top_queries_min: int | None = Query(default=None),
    session: Session = Depends(get_db),
) -> Response:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    if status_code_min is not None and status_code_max is not None and status_code_min > status_code_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status_code_min cannot be greater than status_code_max.",
        )
    if gsc_clicks_min is not None and gsc_clicks_max is not None and gsc_clicks_min > gsc_clicks_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="gsc_clicks_min cannot be greater than gsc_clicks_max.")
    if gsc_impressions_min is not None and gsc_impressions_max is not None and gsc_impressions_min > gsc_impressions_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="gsc_impressions_min cannot be greater than gsc_impressions_max.")
    if gsc_ctr_min is not None and gsc_ctr_max is not None and gsc_ctr_min > gsc_ctr_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="gsc_ctr_min cannot be greater than gsc_ctr_max.")
    if gsc_position_min is not None and gsc_position_max is not None and gsc_position_min > gsc_position_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="gsc_position_min cannot be greater than gsc_position_max.")
    if priority_score_min is not None and priority_score_max is not None and priority_score_min > priority_score_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="priority_score_min cannot be greater than priority_score_max.")
    if (
        page_type_confidence_min is not None
        and page_type_confidence_max is not None
        and page_type_confidence_min > page_type_confidence_max
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_type_confidence_min cannot be greater than page_type_confidence_max.",
        )

    content = export_service.build_pages_csv(
        session,
        job_id,
        sort_by=sort_by,
        sort_order=sort_order,
        gsc_date_range=gsc_date_range,
        url_contains=url_contains,
        title_contains=title_contains,
        page_type=page_type,
        page_bucket=page_bucket,
        page_type_confidence_min=page_type_confidence_min,
        page_type_confidence_max=page_type_confidence_max,
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
        noindex_like=noindex_like,
        non_indexable_like=non_indexable_like,
        title_exact=title_exact,
        meta_description_exact=meta_description_exact,
        content_text_hash_exact=content_text_hash_exact,
        title_too_short=title_too_short,
        title_too_long=title_too_long,
        meta_too_short=meta_too_short,
        meta_too_long=meta_too_long,
        multiple_h1=multiple_h1,
        missing_h2=missing_h2,
        self_canonical=self_canonical,
        canonical_to_other_url=canonical_to_other_url,
        canonical_to_non_200=canonical_to_non_200,
        canonical_to_redirect=canonical_to_redirect,
        thin_content=thin_content,
        duplicate_content=duplicate_content,
        missing_alt_images=missing_alt_images,
        no_images=no_images,
        oversized=oversized,
        was_rendered=was_rendered,
        js_heavy_like=js_heavy_like,
        schema_present=schema_present,
        schema_type=schema_type,
        has_render_error=has_render_error,
        has_x_robots_tag=has_x_robots_tag,
        has_technical_issue=has_technical_issue,
        has_gsc_data=has_gsc_data,
        has_cannibalization=has_cannibalization,
        priority_level=priority_level,
        opportunity_type=opportunity_type,
        priority_score_min=priority_score_min,
        priority_score_max=priority_score_max,
        gsc_clicks_min=gsc_clicks_min,
        gsc_clicks_max=gsc_clicks_max,
        gsc_impressions_min=gsc_impressions_min,
        gsc_impressions_max=gsc_impressions_max,
        gsc_ctr_min=gsc_ctr_min,
        gsc_ctr_max=gsc_ctr_max,
        gsc_position_min=gsc_position_min,
        gsc_position_max=gsc_position_max,
        gsc_top_queries_min=gsc_top_queries_min,
    )
    filtered = any(
        value is not None and value != ""
        for value in [
            missing_title,
            url_contains,
            title_contains,
            page_type,
            page_bucket,
            page_type_confidence_min,
            page_type_confidence_max,
            missing_meta_description,
            missing_h1,
            has_title,
            has_meta_description,
            has_h1,
            status_code,
            status_code_min,
            status_code_max,
            canonical_missing,
            robots_meta_contains,
            noindex_like,
            non_indexable_like,
            title_exact,
            meta_description_exact,
            content_text_hash_exact,
            title_too_short,
            title_too_long,
            meta_too_short,
            meta_too_long,
            multiple_h1,
            missing_h2,
            self_canonical,
            canonical_to_other_url,
            canonical_to_non_200,
            canonical_to_redirect,
            thin_content,
            duplicate_content,
            missing_alt_images,
            no_images,
            oversized,
            was_rendered,
            js_heavy_like,
            schema_present,
            schema_type,
            has_render_error,
            has_x_robots_tag,
            has_technical_issue,
            has_gsc_data,
            has_cannibalization,
            priority_level,
            opportunity_type,
            priority_score_min,
            priority_score_max,
            gsc_clicks_min,
            gsc_clicks_max,
            gsc_impressions_min,
            gsc_impressions_max,
            gsc_ctr_min,
            gsc_ctr_max,
            gsc_position_min,
            gsc_position_max,
            gsc_top_queries_min,
        ]
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": _export_filename(job_id, "pages", filtered=filtered)},
    )


@router.get("/{job_id}/export/links.csv")
def export_links_csv(
    job_id: int,
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
) -> Response:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    content = export_service.build_links_csv(
        session,
        job_id,
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
    filtered = any(
        value is not None and value != ""
        for value in [
            is_internal,
            is_nofollow,
            target_domain,
            has_anchor,
            broken_internal,
            redirecting_internal,
            unresolved_internal,
            to_noindex_like,
            to_canonicalized,
            redirect_chain,
        ]
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": _export_filename(job_id, "links", filtered=filtered)},
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
        headers={"Content-Disposition": _export_filename(job_id, "audit")},
    )


@router.get("/{job_id}/export/gsc-top-queries.csv")
def export_gsc_top_queries_csv(
    job_id: int,
    page_id: int | None = Query(default=None),
    date_range_label: GscDateRangeLabel = Query(default="last_28_days"),
    sort_by: Literal["query", "clicks", "impressions", "ctr", "position", "url"] = Query(default="clicks"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    query_contains: str | None = Query(default=None),
    query_excludes: str | None = Query(default=None),
    clicks_min: int | None = Query(default=None),
    impressions_min: int | None = Query(default=None),
    ctr_max: float | None = Query(default=None),
    position_min: float | None = Query(default=None),
    session: Session = Depends(get_db),
) -> Response:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    try:
        content = export_service.build_gsc_top_queries_csv(
            session,
            job_id,
            page_id=page_id,
            date_range_label=date_range_label,
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
    filtered = any(
        value is not None and value != ""
        for value in [
            page_id,
            query_contains,
            query_excludes,
            clicks_min,
            impressions_min,
            ctr_max,
            position_min,
        ]
    ) or date_range_label != "last_28_days"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": _export_filename(job_id, "gsc_top_queries", filtered=filtered)},
    )


@router.get("/{job_id}/export/opportunities.csv")
def export_opportunities_csv(
    job_id: int,
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    priority_level: PriorityLevel | None = Query(default=None),
    opportunity_type: OpportunityType | None = Query(default=None),
    priority_score_min: int | None = Query(default=None),
    priority_score_max: int | None = Query(default=None),
    sort_by: Literal["url", "priority_score", "gsc_impressions", "gsc_clicks"] = Query(default="priority_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    session: Session = Depends(get_db),
) -> Response:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")
    if priority_score_min is not None and priority_score_max is not None and priority_score_min > priority_score_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="priority_score_min cannot be greater than priority_score_max.")

    content = export_service.build_opportunities_csv(
        session,
        job_id,
        gsc_date_range=gsc_date_range,
        priority_level=priority_level,
        opportunity_type=opportunity_type,
        priority_score_min=priority_score_min,
        priority_score_max=priority_score_max,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    filtered = any(
        value is not None and value != ""
        for value in [
            priority_level,
            opportunity_type,
            priority_score_min,
            priority_score_max,
        ]
    ) or gsc_date_range != "last_28_days" or sort_by != "priority_score" or sort_order != "desc"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": _export_filename(job_id, "opportunities", filtered=filtered)},
    )


@router.get("/{job_id}/export/internal-linking.csv")
def export_internal_linking_csv(
    job_id: int,
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    issue_type: Literal[
        "ORPHAN_LIKE",
        "WEAKLY_LINKED_IMPORTANT",
        "LOW_ANCHOR_DIVERSITY",
        "EXACT_MATCH_ANCHOR_CONCENTRATION",
        "BOILERPLATE_DOMINATED",
        "LOW_LINK_EQUITY",
    ] | None = Query(default=None),
    priority_level: PriorityLevel | None = Query(default=None),
    opportunity_type: OpportunityType | None = Query(default=None),
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
    url_contains: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> Response:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    try:
        content = export_service.build_internal_linking_csv(
            session,
            job_id,
            gsc_date_range=gsc_date_range,
            issue_type=issue_type,
            priority_level=priority_level,
            opportunity_type=opportunity_type,
            sort_by=sort_by,
            sort_order=sort_order,
            url_contains=url_contains,
        )
    except internal_linking_service.InternalLinkingServiceError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    filtered = any(
        value is not None and value != ""
        for value in [issue_type, priority_level, opportunity_type, url_contains]
    ) or gsc_date_range != "last_28_days" or sort_by != "internal_linking_score" or sort_order != "desc"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": _export_filename(job_id, "internal_linking", filtered=filtered)},
    )


@router.get("/{job_id}/export/cannibalization.csv")
def export_cannibalization_csv(
    job_id: int,
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    sort_by: Literal[
        "severity",
        "impact_level",
        "weighted_overlap",
        "shared_queries_count",
        "shared_query_impressions",
        "shared_query_clicks",
        "urls_count",
        "dominant_url_confidence",
        "recommendation_type",
        "cluster_id",
    ] = Query(default="severity"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    severity: Literal["low", "medium", "high", "critical"] | None = Query(default=None),
    impact_level: ImpactLevel | None = Query(default=None),
    recommendation_type: Literal[
        "MERGE_CANDIDATE",
        "SPLIT_INTENT_CANDIDATE",
        "REINFORCE_PRIMARY_URL",
        "QUERY_CLUSTER_WITHOUT_CLEAR_PRIMARY",
        "LOW_VALUE_OVERLAP",
        "HIGH_IMPACT_CANNIBALIZATION",
    ] | None = Query(default=None),
    has_clear_primary: bool | None = Query(default=None),
    url_contains: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> Response:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    try:
        content = export_service.build_cannibalization_csv(
            session,
            job_id,
            gsc_date_range=gsc_date_range,
            sort_by=sort_by,
            sort_order=sort_order,
            severity=severity,
            impact_level=impact_level,
            recommendation_type=recommendation_type,
            has_clear_primary=has_clear_primary,
            url_contains=url_contains,
        )
    except cannibalization_service.CannibalizationServiceError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    filtered = any(
        value is not None and value != ""
        for value in [severity, impact_level, recommendation_type, has_clear_primary, url_contains]
    ) or gsc_date_range != "last_28_days" or sort_by != "severity" or sort_order != "desc"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": _export_filename(job_id, "cannibalization", filtered=filtered)},
    )


@router.get("/{job_id}/export/crawl-compare.csv")
def export_crawl_compare_csv(
    job_id: int,
    baseline_job_id: int = Query(..., ge=1),
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    sort_by: Literal[
        "url",
        "change_type",
        "issues_resolved_count",
        "issues_added_count",
        "delta_priority_score",
        "delta_word_count",
        "delta_schema_count",
        "delta_response_time_ms",
        "delta_incoming_internal_links",
        "delta_incoming_internal_linking_pages",
    ] = Query(default="delta_priority_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    change_type: Literal["improved", "worsened", "unchanged", "new", "missing"] | None = Query(default=None),
    resolved_issues_min: int | None = Query(default=None, ge=0),
    added_issues_min: int | None = Query(default=None, ge=0),
    url_contains: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> Response:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    try:
        content = export_service.build_crawl_compare_csv(
            session,
            job_id,
            baseline_job_id=baseline_job_id,
            gsc_date_range=gsc_date_range,
            sort_by=sort_by,
            sort_order=sort_order,
            change_type=change_type,
            resolved_issues_min=resolved_issues_min,
            added_issues_min=added_issues_min,
            url_contains=url_contains,
        )
    except trends_service.TrendsServiceError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    filtered = any(
        value is not None and value != ""
        for value in [change_type, resolved_issues_min, added_issues_min, url_contains]
    ) or sort_by != "delta_priority_score" or sort_order != "desc" or gsc_date_range != "last_28_days"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": _export_filename(job_id, "crawl_compare", filtered=filtered)},
    )


@router.get("/{job_id}/export/gsc-compare.csv")
def export_gsc_compare_csv(
    job_id: int,
    baseline_gsc_range: GscDateRangeLabel = Query(default="last_90_days"),
    target_gsc_range: GscDateRangeLabel = Query(default="last_28_days"),
    sort_by: Literal[
        "url",
        "overall_trend",
        "delta_clicks",
        "delta_impressions",
        "delta_ctr",
        "delta_position",
        "delta_top_queries_count",
    ] = Query(default="delta_clicks"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    clicks_trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    impressions_trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    ctr_trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    position_trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    top_queries_trend: Literal["improved", "worsened", "flat"] | None = Query(default=None),
    url_contains: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> Response:
    crawl_job = crawl_job_service.get_crawl_job(session, job_id)
    if crawl_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Crawl job {job_id} not found.")

    try:
        content = export_service.build_gsc_compare_csv(
            session,
            job_id,
            baseline_gsc_range=baseline_gsc_range,
            target_gsc_range=target_gsc_range,
            sort_by=sort_by,
            sort_order=sort_order,
            trend=trend,
            clicks_trend=clicks_trend,
            impressions_trend=impressions_trend,
            ctr_trend=ctr_trend,
            position_trend=position_trend,
            top_queries_trend=top_queries_trend,
            url_contains=url_contains,
        )
    except trends_service.TrendsServiceError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    filtered = any(
        value is not None and value != ""
        for value in [trend, clicks_trend, impressions_trend, ctr_trend, position_trend, top_queries_trend, url_contains]
    ) or baseline_gsc_range != "last_90_days" or target_gsc_range != "last_28_days" or sort_by != "delta_clicks" or sort_order != "desc"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": _export_filename(job_id, "gsc_compare", filtered=filtered)},
    )
