from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.competitive_gap import (
    ContentGapReviewRunResponse,
    CompetitiveGapSemanticRerunRequest,
    CompetitiveGapSemanticRerunResponse,
    CompetitiveGapExplanationRequest,
    CompetitiveGapExplanationResponse,
    CompetitiveGapStrategyResponse,
    PaginatedSiteCompetitorReviewResponse,
    CompetitiveGapStrategyUpsertRequest,
    PaginatedCompetitiveGapResponse,
    SiteCompetitorCreateRequest,
    SiteCompetitorResponse,
    SiteCompetitorSyncRunResponse,
    SiteCompetitorSyncAllResponse,
    SiteCompetitorUpdateRequest,
)
from app.schemas.gsc import GscDateRangeLabel
from app.services import (
    content_gap_review_llm_service,
    content_gap_review_run_service,
    competitive_gap_explanation_service,
    competitive_gap_language_service,
    competitive_gap_semantic_arbiter_service,
    competitive_gap_sync_service,
    competitive_gap_sync_run_service,
    competitive_gap_service,
    export_service,
    site_competitor_service,
    site_content_strategy_service,
)

router = APIRouter(prefix="/sites", tags=["site-competitive-gap"])


def _raise_http_error(exc: Exception) -> None:
    detail = str(exc)
    error_code = getattr(exc, "code", None)
    if error_code == "not_found" or "not found" in detail.lower():
        status_code = status.HTTP_404_NOT_FOUND
    elif (
        error_code in {"already_running", "not_retryable"}
        or "mismatch" in detail.lower()
        or "already queued or running" in detail.lower()
    ):
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=detail) from exc


def _export_filename(site_id: int, *, filtered: bool = False) -> str:
    suffix = "_view" if filtered else ""
    return f'attachment; filename="site_{site_id}_competitive_content_gap{suffix}.csv"'


def _resolve_output_language(request: Request) -> str:
    return competitive_gap_language_service.resolve_output_language(
        request.headers.get("X-UI-Language"),
        request.headers.get("Accept-Language"),
    )


@router.get("/{site_id}/competitive-content-gap/strategy", response_model=CompetitiveGapStrategyResponse | None)
def get_site_content_strategy(
    site_id: int,
    session: Session = Depends(get_db),
) -> CompetitiveGapStrategyResponse | None:
    try:
        payload = site_content_strategy_service.get_site_content_strategy(session, site_id)
    except site_content_strategy_service.SiteContentStrategyServiceError as exc:
        _raise_http_error(exc)
    if payload is None:
        return None
    return CompetitiveGapStrategyResponse.model_validate(payload)


@router.put("/{site_id}/competitive-content-gap/strategy", response_model=CompetitiveGapStrategyResponse)
def upsert_site_content_strategy(
    site_id: int,
    payload: CompetitiveGapStrategyUpsertRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> CompetitiveGapStrategyResponse:
    try:
        result = site_content_strategy_service.upsert_site_content_strategy(
            session,
            site_id,
            raw_user_input=payload.raw_user_input,
            normalized_strategy_json=payload.normalized_strategy_json,
            output_language=_resolve_output_language(request),
        )
    except site_content_strategy_service.SiteContentStrategyServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return CompetitiveGapStrategyResponse.model_validate(result)


@router.delete("/{site_id}/competitive-content-gap/strategy", status_code=status.HTTP_204_NO_CONTENT)
def delete_site_content_strategy(
    site_id: int,
    session: Session = Depends(get_db),
) -> Response:
    try:
        site_content_strategy_service.delete_site_content_strategy(session, site_id)
    except site_content_strategy_service.SiteContentStrategyServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{site_id}/competitive-content-gap/competitors", response_model=list[SiteCompetitorResponse])
def list_site_competitors(
    site_id: int,
    session: Session = Depends(get_db),
) -> list[SiteCompetitorResponse]:
    try:
        payload = site_competitor_service.list_site_competitors(session, site_id)
    except site_competitor_service.SiteCompetitorServiceError as exc:
        _raise_http_error(exc)
    return [SiteCompetitorResponse.model_validate(item) for item in payload]


@router.post(
    "/{site_id}/competitive-content-gap/competitors",
    response_model=SiteCompetitorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_site_competitor(
    site_id: int,
    payload: SiteCompetitorCreateRequest,
    session: Session = Depends(get_db),
) -> SiteCompetitorResponse:
    try:
        result = site_competitor_service.create_site_competitor(
            session,
            site_id,
            root_url=payload.root_url,
            label=payload.label,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except site_competitor_service.SiteCompetitorServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SiteCompetitorResponse.model_validate(result)


@router.put(
    "/{site_id}/competitive-content-gap/competitors/{competitor_id}",
    response_model=SiteCompetitorResponse,
)
def update_site_competitor(
    site_id: int,
    competitor_id: int,
    payload: SiteCompetitorUpdateRequest,
    session: Session = Depends(get_db),
) -> SiteCompetitorResponse:
    try:
        result = site_competitor_service.update_site_competitor(
            session,
            site_id,
            competitor_id,
            root_url=payload.root_url,
            label=payload.label,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except site_competitor_service.SiteCompetitorServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SiteCompetitorResponse.model_validate(result)


@router.delete(
    "/{site_id}/competitive-content-gap/competitors/{competitor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_site_competitor(
    site_id: int,
    competitor_id: int,
    session: Session = Depends(get_db),
) -> Response:
    try:
        site_competitor_service.delete_site_competitor(session, site_id, competitor_id)
    except site_competitor_service.SiteCompetitorServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{site_id}/competitive-content-gap/semantic/re-run",
    response_model=CompetitiveGapSemanticRerunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def rerun_site_competitive_gap_semantic_layer(
    site_id: int,
    payload: CompetitiveGapSemanticRerunRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_db),
) -> CompetitiveGapSemanticRerunResponse:
    output_language = _resolve_output_language(request)
    try:
        result = competitive_gap_semantic_arbiter_service.queue_site_semantic_rerun(
            session,
            site_id,
            mode=payload.mode,
            active_crawl_id=payload.active_crawl_id,
        )
    except (
        competitive_gap_semantic_arbiter_service.CompetitiveGapSemanticArbiterError,
        competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError,
    ) as exc:
        _raise_http_error(exc)
    session.commit()
    for queued_run in result["queued_runs"]:
        background_tasks.add_task(
            competitive_gap_semantic_arbiter_service.run_site_competitor_semantic_task,
            site_id,
            int(queued_run["competitor_id"]),
            int(queued_run["run_id"]),
            output_language,
        )
    return CompetitiveGapSemanticRerunResponse.model_validate(result)


@router.post(
    "/{site_id}/competitive-content-gap/competitors/{competitor_id}/sync",
    response_model=SiteCompetitorResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def sync_site_competitor(
    site_id: int,
    competitor_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_db),
) -> SiteCompetitorResponse:
    output_language = _resolve_output_language(request)
    try:
        payload = competitive_gap_sync_service.queue_site_competitor_sync(session, site_id, competitor_id)
    except (
        competitive_gap_sync_service.CompetitiveGapSyncServiceError,
        competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError,
    ) as exc:
        _raise_http_error(exc)
    session.commit()
    background_tasks.add_task(
        competitive_gap_sync_service.run_site_competitor_sync_task,
        site_id,
        competitor_id,
        int(payload["last_sync_run_id"]),
        output_language,
    )
    return SiteCompetitorResponse.model_validate(payload)


@router.post(
    "/{site_id}/competitive-content-gap/competitors/sync-all",
    response_model=SiteCompetitorSyncAllResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def sync_all_site_competitors(
    site_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_db),
) -> SiteCompetitorSyncAllResponse:
    output_language = _resolve_output_language(request)
    try:
        payload = competitive_gap_sync_service.queue_all_site_competitor_syncs(session, site_id)
    except (
        competitive_gap_sync_service.CompetitiveGapSyncServiceError,
        competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError,
    ) as exc:
        _raise_http_error(exc)
    session.commit()
    for queued_run in payload["queued_runs"]:
        background_tasks.add_task(
            competitive_gap_sync_service.run_site_competitor_sync_task,
            site_id,
            int(queued_run["competitor_id"]),
            int(queued_run["run_id"]),
            output_language,
        )
    return SiteCompetitorSyncAllResponse.model_validate(payload)


@router.get(
    "/{site_id}/competitive-content-gap/competitors/{competitor_id}/sync-runs",
    response_model=list[SiteCompetitorSyncRunResponse],
)
def list_site_competitor_sync_runs(
    site_id: int,
    competitor_id: int,
    limit: int = Query(default=10, ge=1, le=25),
    session: Session = Depends(get_db),
) -> list[SiteCompetitorSyncRunResponse]:
    try:
        payload = competitive_gap_sync_service.list_site_competitor_sync_runs(
            session,
            site_id,
            competitor_id,
            limit=limit,
        )
    except (
        competitive_gap_sync_service.CompetitiveGapSyncServiceError,
        competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError,
    ) as exc:
        _raise_http_error(exc)
    return [SiteCompetitorSyncRunResponse.model_validate(item) for item in payload]


@router.get(
    "/{site_id}/competitive-content-gap/review-runs",
    response_model=list[ContentGapReviewRunResponse],
)
def list_site_content_gap_review_runs(
    site_id: int,
    limit: int = Query(default=5, ge=1, le=25),
    session: Session = Depends(get_db),
) -> list[ContentGapReviewRunResponse]:
    try:
        payload = content_gap_review_run_service.list_review_runs(
            session,
            site_id=site_id,
            limit=limit,
        )
    except content_gap_review_run_service.ContentGapReviewRunServiceError as exc:
        _raise_http_error(exc)
    return [ContentGapReviewRunResponse.model_validate(item) for item in payload]


@router.post(
    "/{site_id}/competitive-content-gap/review-runs/{run_id}/retry",
    response_model=ContentGapReviewRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_site_content_gap_review_run(
    site_id: int,
    run_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> ContentGapReviewRunResponse:
    try:
        existing_runs = content_gap_review_run_service.list_review_runs(session, site_id=site_id, limit=25)
    except content_gap_review_run_service.ContentGapReviewRunServiceError as exc:
        _raise_http_error(exc)

    source_run = next((item for item in existing_runs if int(item["run_id"]) == run_id), None)
    if source_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Content Gap review run {run_id} not found.")

    active_payload = competitive_gap_service.build_competitive_gap_payload(session, site_id)
    active_crawl_id = active_payload["context"].get("active_crawl_id")
    if active_crawl_id is None or int(source_run["basis_crawl_job_id"]) != int(active_crawl_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only review runs for the current active crawl snapshot can be retried.",
        )

    try:
        retry_payload = content_gap_review_run_service.retry_review_run(
            session,
            site_id=site_id,
            run_id=run_id,
        )
    except content_gap_review_run_service.ContentGapReviewRunServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    background_tasks.add_task(
        content_gap_review_llm_service.execute_review_run_task,
        site_id,
        int(retry_payload["run_id"]),
    )
    return ContentGapReviewRunResponse.model_validate(retry_payload)


@router.get(
    "/{site_id}/competitive-content-gap/competitors/{competitor_id}/page-review",
    response_model=PaginatedSiteCompetitorReviewResponse,
)
def list_site_competitor_page_review_records(
    site_id: int,
    competitor_id: int,
    review_status: Literal["all", "accepted", "rejected"] = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_db),
) -> PaginatedSiteCompetitorReviewResponse:
    try:
        payload = site_competitor_service.list_site_competitor_review_records(
            session,
            site_id,
            competitor_id,
            review_status=review_status,
            page=page,
            page_size=page_size,
        )
    except site_competitor_service.SiteCompetitorServiceError as exc:
        _raise_http_error(exc)
    return PaginatedSiteCompetitorReviewResponse.model_validate(payload)


@router.post(
    "/{site_id}/competitive-content-gap/competitors/{competitor_id}/retry-sync",
    response_model=SiteCompetitorResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_site_competitor_sync(
    site_id: int,
    competitor_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_db),
) -> SiteCompetitorResponse:
    output_language = _resolve_output_language(request)
    try:
        payload = competitive_gap_sync_service.retry_site_competitor_sync(session, site_id, competitor_id)
    except (
        competitive_gap_sync_service.CompetitiveGapSyncServiceError,
        competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError,
    ) as exc:
        _raise_http_error(exc)
    session.commit()
    background_tasks.add_task(
        competitive_gap_sync_service.run_site_competitor_sync_task,
        site_id,
        competitor_id,
        int(payload["last_sync_run_id"]),
        output_language,
    )
    return SiteCompetitorResponse.model_validate(payload)


@router.post(
    "/{site_id}/competitive-content-gap/competitors/{competitor_id}/reset-sync",
    response_model=SiteCompetitorResponse,
)
def reset_site_competitor_sync(
    site_id: int,
    competitor_id: int,
    session: Session = Depends(get_db),
) -> SiteCompetitorResponse:
    try:
        payload = competitive_gap_sync_service.reset_site_competitor_sync(session, site_id, competitor_id)
    except (
        competitive_gap_sync_service.CompetitiveGapSyncServiceError,
        competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError,
    ) as exc:
        _raise_http_error(exc)
    session.commit()
    return SiteCompetitorResponse.model_validate(payload)


@router.get("/{site_id}/competitive-content-gap", response_model=PaginatedCompetitiveGapResponse)
def get_competitive_content_gap(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: Literal[
        "priority_score",
        "consensus_score",
        "competitor_count",
        "competitor_coverage_score",
        "own_coverage_score",
        "strategy_alignment_score",
        "business_value_score",
        "merged_topic_count",
        "confidence",
        "topic_label",
        "gap_type",
        "page_type",
    ] = Query(default="priority_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    gap_type: Literal["NEW_TOPIC", "EXPAND_EXISTING_TOPIC", "MISSING_SUPPORTING_PAGE"] | None = Query(default=None),
    segment: Literal["create_new_page", "expand_existing_page", "strengthen_cluster"] | None = Query(default=None),
    competitor_id: int | None = Query(default=None, ge=1),
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
    own_match_status: Literal[
        "exact_match",
        "semantic_match",
        "partial_coverage",
        "no_meaningful_match",
    ] | None = Query(default=None),
    topic: str | None = Query(default=None),
    priority_score_min: int | None = Query(default=None, ge=0, le=100),
    consensus_min: int | None = Query(default=None, ge=0, le=100),
    session: Session = Depends(get_db),
) -> PaginatedCompetitiveGapResponse:
    try:
        payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            gsc_date_range=gsc_date_range,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            gap_type=gap_type,
            segment=segment,
            competitor_id=competitor_id,
            page_type=page_type,
            own_match_status=own_match_status,
            topic=topic,
            priority_score_min=priority_score_min,
            consensus_min=consensus_min,
        )
    except competitive_gap_service.CompetitiveGapServiceError as exc:
        _raise_http_error(exc)
    except RuntimeError as exc:
        _raise_http_error(exc)
    return PaginatedCompetitiveGapResponse.model_validate(payload)


@router.get("/{site_id}/export/competitive-content-gap.csv")
def export_competitive_content_gap_csv(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    gsc_date_range: GscDateRangeLabel = Query(default="last_28_days"),
    sort_by: Literal[
        "priority_score",
        "consensus_score",
        "competitor_count",
        "competitor_coverage_score",
        "own_coverage_score",
        "strategy_alignment_score",
        "business_value_score",
        "merged_topic_count",
        "confidence",
        "topic_label",
        "gap_type",
        "page_type",
    ] = Query(default="priority_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    gap_type: Literal["NEW_TOPIC", "EXPAND_EXISTING_TOPIC", "MISSING_SUPPORTING_PAGE"] | None = Query(default=None),
    segment: Literal["create_new_page", "expand_existing_page", "strengthen_cluster"] | None = Query(default=None),
    competitor_id: int | None = Query(default=None, ge=1),
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
    own_match_status: Literal[
        "exact_match",
        "semantic_match",
        "partial_coverage",
        "no_meaningful_match",
    ] | None = Query(default=None),
    topic: str | None = Query(default=None),
    priority_score_min: int | None = Query(default=None, ge=0, le=100),
    consensus_min: int | None = Query(default=None, ge=0, le=100),
    session: Session = Depends(get_db),
) -> Response:
    try:
        content = export_service.build_site_competitive_gap_csv(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            gsc_date_range=gsc_date_range,
            sort_by=sort_by,
            sort_order=sort_order,
            gap_type=gap_type,
            segment=segment,
            competitor_id=competitor_id,
            page_type=page_type,
            own_match_status=own_match_status,
            topic=topic,
            priority_score_min=priority_score_min,
            consensus_min=consensus_min,
        )
    except competitive_gap_service.CompetitiveGapServiceError as exc:
        _raise_http_error(exc)
    except RuntimeError as exc:
        _raise_http_error(exc)

    filtered = any(
        value is not None and value != ""
        for value in [active_crawl_id, gap_type, segment, competitor_id, page_type, own_match_status, topic, priority_score_min, consensus_min]
    ) or gsc_date_range != "last_28_days" or sort_by != "priority_score" or sort_order != "desc"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": _export_filename(site_id, filtered=filtered)},
    )


@router.post(
    "/{site_id}/competitive-content-gap/explanation",
    response_model=CompetitiveGapExplanationResponse,
)
def create_competitive_gap_explanation(
    site_id: int,
    payload: CompetitiveGapExplanationRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> CompetitiveGapExplanationResponse:
    try:
        result = competitive_gap_explanation_service.build_gap_explanation_response(
            session,
            site_id,
            gap_key=payload.gap_key,
            active_crawl_id=payload.active_crawl_id,
            gsc_date_range=payload.gsc_date_range,
            gap_signature=payload.gap_signature,
            output_language=_resolve_output_language(request),
        )
    except competitive_gap_explanation_service.CompetitiveGapExplanationServiceError as exc:
        _raise_http_error(exc)
    except competitive_gap_service.CompetitiveGapServiceError as exc:
        _raise_http_error(exc)
    return CompetitiveGapExplanationResponse.model_validate(result)
