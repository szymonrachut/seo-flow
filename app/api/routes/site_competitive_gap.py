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
from app.schemas.semstorm import (
    SemstormBriefEnrichmentApplyResponse,
    SemstormBriefEnrichmentRunResponse,
    SemstormBriefEnrichmentRunsResponse,
    SemstormBriefExecutionStatusUpdateRequest,
    SemstormBriefImplementationStatusUpdateRequest,
    SemstormBriefExecutionUpdateRequest,
    SemstormBriefItemResponse,
    SemstormBriefItemsResponse,
    SemstormBriefStatusUpdateRequest,
    SemstormBriefUpdateRequest,
    SemstormCreateBriefRequest,
    SemstormCreateBriefResponse,
    SemstormCreatePlanRequest,
    SemstormCreatePlanResponse,
    SemstormDiscoveryPreviewRequest,
    SemstormDiscoveryPreviewResponse,
    SemstormDiscoveryRunCreateRequest,
    SemstormDiscoveryRunListItemResponse,
    SemstormDiscoveryRunResponse,
    SemstormExecutionItemsResponse,
    SemstormImplementedItemsResponse,
    SemstormOpportunityActionRequest,
    SemstormOpportunityActionResponse,
    SemstormOpportunitySeedsResponse,
    SemstormPlanItemResponse,
    SemstormPlanItemsResponse,
    SemstormPlanStatusUpdateRequest,
    SemstormPlanUpdateRequest,
    SemstormPromotedItemsResponse,
)
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
    semstorm_brief_service,
    semstorm_brief_llm_service,
    semstorm_plan_service,
    semstorm_service,
    site_competitor_service,
    site_content_strategy_service,
)

router = APIRouter(prefix="/sites", tags=["site-competitive-gap"])


def _raise_http_error(exc: Exception) -> None:
    detail = str(exc)
    explicit_status = getattr(exc, "status_code", None)
    if isinstance(explicit_status, int) and 400 <= explicit_status <= 599:
        raise HTTPException(status_code=explicit_status, detail=detail) from exc
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
    "/{site_id}/competitive-content-gap/semstorm/discovery-preview",
    response_model=SemstormDiscoveryPreviewResponse,
)
def create_semstorm_discovery_preview(
    site_id: int,
    payload: SemstormDiscoveryPreviewRequest,
    session: Session = Depends(get_db),
) -> SemstormDiscoveryPreviewResponse:
    try:
        result = semstorm_service.build_semstorm_discovery_preview(
            session,
            site_id,
            max_competitors=payload.max_competitors,
            max_keywords_per_competitor=payload.max_keywords_per_competitor,
            result_type=payload.result_type,
            include_basic_stats=payload.include_basic_stats,
            competitors_type=payload.competitors_type,
        )
    except semstorm_service.SemstormServiceError as exc:
        _raise_http_error(exc)
    return SemstormDiscoveryPreviewResponse.model_validate(result)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/discovery-runs",
    response_model=SemstormDiscoveryRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_semstorm_discovery_run(
    site_id: int,
    payload: SemstormDiscoveryRunCreateRequest,
    session: Session = Depends(get_db),
) -> SemstormDiscoveryRunResponse:
    try:
        result = semstorm_service.run_semstorm_discovery(
            session,
            site_id,
            max_competitors=payload.max_competitors,
            max_keywords_per_competitor=payload.max_keywords_per_competitor,
            result_type=payload.result_type,
            include_basic_stats=payload.include_basic_stats,
            competitors_type=payload.competitors_type,
        )
    except semstorm_service.SemstormServiceError as exc:
        session.commit()
        _raise_http_error(exc)
    session.commit()
    return SemstormDiscoveryRunResponse.model_validate(result)


@router.get(
    "/{site_id}/competitive-content-gap/semstorm/discovery-runs",
    response_model=list[SemstormDiscoveryRunListItemResponse],
)
def list_semstorm_discovery_runs(
    site_id: int,
    session: Session = Depends(get_db),
) -> list[SemstormDiscoveryRunListItemResponse]:
    try:
        payload = semstorm_service.list_semstorm_discovery_runs(session, site_id)
    except semstorm_service.SemstormServiceError as exc:
        _raise_http_error(exc)
    return [SemstormDiscoveryRunListItemResponse.model_validate(item) for item in payload]


@router.get(
    "/{site_id}/competitive-content-gap/semstorm/discovery-runs/{run_id}",
    response_model=SemstormDiscoveryRunResponse,
)
def get_semstorm_discovery_run(
    site_id: int,
    run_id: int,
    session: Session = Depends(get_db),
) -> SemstormDiscoveryRunResponse:
    try:
        payload = semstorm_service.get_semstorm_discovery_run(session, site_id, run_id)
    except semstorm_service.SemstormServiceError as exc:
        _raise_http_error(exc)
    return SemstormDiscoveryRunResponse.model_validate(payload)


@router.get(
    "/{site_id}/competitive-content-gap/semstorm/opportunities",
    response_model=SemstormOpportunitySeedsResponse,
)
def get_semstorm_opportunities(
    site_id: int,
    run_id: int | None = Query(default=None, ge=1),
    coverage_status: Literal["missing", "weak_coverage", "covered"] | None = Query(default=None),
    bucket: Literal["quick_win", "core_opportunity", "watchlist"] | None = Query(default=None),
    decision_type: Literal["create_new_page", "expand_existing_page", "monitor_only"] | None = Query(default=None),
    state_status: Literal["new", "accepted", "dismissed", "promoted"] | None = Query(default=None),
    has_gsc_signal: bool | None = Query(default=None),
    only_actionable: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db),
) -> SemstormOpportunitySeedsResponse:
    try:
        payload = semstorm_service.get_semstorm_opportunities(
            session,
            site_id,
            run_id=run_id,
            coverage_status=coverage_status,
            bucket=bucket,
            decision_type=decision_type,
            state_status=state_status,
            has_gsc_signal=has_gsc_signal,
            only_actionable=only_actionable,
            limit=limit,
        )
    except semstorm_service.SemstormServiceError as exc:
        _raise_http_error(exc)
    return SemstormOpportunitySeedsResponse.model_validate(payload)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/opportunities/actions/accept",
    response_model=SemstormOpportunityActionResponse,
)
def accept_semstorm_opportunities(
    site_id: int,
    payload: SemstormOpportunityActionRequest,
    session: Session = Depends(get_db),
) -> SemstormOpportunityActionResponse:
    try:
        result = semstorm_service.accept_semstorm_opportunities(
            session,
            site_id,
            run_id=payload.run_id,
            keywords=payload.keywords,
            note=payload.note,
        )
    except semstorm_service.SemstormServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormOpportunityActionResponse.model_validate(result)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/opportunities/actions/dismiss",
    response_model=SemstormOpportunityActionResponse,
)
def dismiss_semstorm_opportunities(
    site_id: int,
    payload: SemstormOpportunityActionRequest,
    session: Session = Depends(get_db),
) -> SemstormOpportunityActionResponse:
    try:
        result = semstorm_service.dismiss_semstorm_opportunities(
            session,
            site_id,
            run_id=payload.run_id,
            keywords=payload.keywords,
            note=payload.note,
        )
    except semstorm_service.SemstormServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormOpportunityActionResponse.model_validate(result)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote",
    response_model=SemstormOpportunityActionResponse,
)
def promote_semstorm_opportunities(
    site_id: int,
    payload: SemstormOpportunityActionRequest,
    session: Session = Depends(get_db),
) -> SemstormOpportunityActionResponse:
    try:
        result = semstorm_service.promote_semstorm_opportunities(
            session,
            site_id,
            run_id=payload.run_id,
            keywords=payload.keywords,
            note=payload.note,
        )
    except semstorm_service.SemstormServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormOpportunityActionResponse.model_validate(result)


@router.get(
    "/{site_id}/competitive-content-gap/semstorm/promoted",
    response_model=SemstormPromotedItemsResponse,
)
def list_semstorm_promoted_items(
    site_id: int,
    session: Session = Depends(get_db),
) -> SemstormPromotedItemsResponse:
    try:
        payload = semstorm_service.list_semstorm_promoted_items(session, site_id)
    except semstorm_service.SemstormServiceError as exc:
        _raise_http_error(exc)
    return SemstormPromotedItemsResponse.model_validate(payload)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/promoted/actions/create-plan",
    response_model=SemstormCreatePlanResponse,
)
def create_semstorm_plan_items(
    site_id: int,
    payload: SemstormCreatePlanRequest,
    session: Session = Depends(get_db),
) -> SemstormCreatePlanResponse:
    try:
        result = semstorm_plan_service.create_semstorm_plan_items(
            session,
            site_id,
            promoted_item_ids=payload.promoted_item_ids,
            target_page_type=payload.defaults.target_page_type if payload.defaults else None,
        )
    except semstorm_plan_service.SemstormPlanServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormCreatePlanResponse.model_validate(result)


@router.get(
    "/{site_id}/competitive-content-gap/semstorm/plans",
    response_model=SemstormPlanItemsResponse,
)
def list_semstorm_plan_items(
    site_id: int,
    state_status: Literal["planned", "in_progress", "done", "archived"] | None = Query(default=None),
    target_page_type: Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"] | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db),
) -> SemstormPlanItemsResponse:
    try:
        payload = semstorm_plan_service.list_semstorm_plan_items(
            session,
            site_id,
            state_status=state_status,
            target_page_type=target_page_type,
            search=search,
            limit=limit,
        )
    except semstorm_plan_service.SemstormPlanServiceError as exc:
        _raise_http_error(exc)
    return SemstormPlanItemsResponse.model_validate(payload)


@router.get(
    "/{site_id}/competitive-content-gap/semstorm/plans/{plan_id}",
    response_model=SemstormPlanItemResponse,
)
def get_semstorm_plan_item(
    site_id: int,
    plan_id: int,
    session: Session = Depends(get_db),
) -> SemstormPlanItemResponse:
    try:
        payload = semstorm_plan_service.get_semstorm_plan_item(session, site_id, plan_id)
    except semstorm_plan_service.SemstormPlanServiceError as exc:
        _raise_http_error(exc)
    return SemstormPlanItemResponse.model_validate(payload)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/plans/{plan_id}/status",
    response_model=SemstormPlanItemResponse,
)
def update_semstorm_plan_item_status(
    site_id: int,
    plan_id: int,
    payload: SemstormPlanStatusUpdateRequest,
    session: Session = Depends(get_db),
) -> SemstormPlanItemResponse:
    try:
        result = semstorm_plan_service.update_semstorm_plan_item_status(
            session,
            site_id,
            plan_id,
            state_status=payload.state_status,
        )
    except semstorm_plan_service.SemstormPlanServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormPlanItemResponse.model_validate(result)


@router.put(
    "/{site_id}/competitive-content-gap/semstorm/plans/{plan_id}",
    response_model=SemstormPlanItemResponse,
)
def update_semstorm_plan_item(
    site_id: int,
    plan_id: int,
    payload: SemstormPlanUpdateRequest,
    session: Session = Depends(get_db),
) -> SemstormPlanItemResponse:
    try:
        result = semstorm_plan_service.update_semstorm_plan_item(
            session,
            site_id,
            plan_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except semstorm_plan_service.SemstormPlanServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormPlanItemResponse.model_validate(result)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/plans/actions/create-brief",
    response_model=SemstormCreateBriefResponse,
)
def create_semstorm_brief_items(
    site_id: int,
    payload: SemstormCreateBriefRequest,
    session: Session = Depends(get_db),
) -> SemstormCreateBriefResponse:
    try:
        result = semstorm_brief_service.create_semstorm_brief_items(
            session,
            site_id,
            plan_item_ids=payload.plan_item_ids,
        )
    except semstorm_brief_service.SemstormBriefServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormCreateBriefResponse.model_validate(result)


@router.get(
    "/{site_id}/competitive-content-gap/semstorm/execution",
    response_model=SemstormExecutionItemsResponse,
)
def list_semstorm_execution_items(
    site_id: int,
    execution_status: Literal["draft", "ready", "in_execution", "completed", "archived"] | None = Query(default=None),
    assignee: str | None = Query(default=None),
    brief_type: Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"] | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db),
) -> SemstormExecutionItemsResponse:
    try:
        payload = semstorm_brief_service.list_semstorm_execution_items(
            session,
            site_id,
            execution_status=execution_status,
            assignee=assignee,
            brief_type=brief_type,
            search=search,
            limit=limit,
        )
    except semstorm_brief_service.SemstormBriefServiceError as exc:
        _raise_http_error(exc)
    return SemstormExecutionItemsResponse.model_validate(payload)


@router.get(
    "/{site_id}/competitive-content-gap/semstorm/implemented",
    response_model=SemstormImplementedItemsResponse,
)
def list_semstorm_implemented_items(
    site_id: int,
    implementation_status: Literal["too_early", "implemented", "evaluated", "archived"] | None = Query(default=None),
    outcome_status: Literal["too_early", "no_signal", "weak_signal", "positive_signal"] | None = Query(default=None),
    brief_type: Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"] | None = Query(default=None),
    search: str | None = Query(default=None),
    window_days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db),
) -> SemstormImplementedItemsResponse:
    try:
        payload = semstorm_brief_service.list_semstorm_implemented_items(
            session,
            site_id,
            implementation_status=implementation_status,
            outcome_status=outcome_status,
            brief_type=brief_type,
            search=search,
            window_days=window_days,
            limit=limit,
        )
    except semstorm_brief_service.SemstormBriefServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormImplementedItemsResponse.model_validate(payload)


@router.get(
    "/{site_id}/competitive-content-gap/semstorm/briefs",
    response_model=SemstormBriefItemsResponse,
)
def list_semstorm_brief_items(
    site_id: int,
    state_status: Literal["draft", "ready", "in_execution", "completed", "archived"] | None = Query(default=None),
    brief_type: Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"] | None = Query(default=None),
    search_intent: Literal["informational", "commercial", "transactional", "navigational", "mixed"] | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db),
) -> SemstormBriefItemsResponse:
    try:
        payload = semstorm_brief_service.list_semstorm_brief_items(
            session,
            site_id,
            state_status=state_status,
            brief_type=brief_type,
            search_intent=search_intent,
            search=search,
            limit=limit,
        )
    except semstorm_brief_service.SemstormBriefServiceError as exc:
        _raise_http_error(exc)
    return SemstormBriefItemsResponse.model_validate(payload)


@router.get(
    "/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}",
    response_model=SemstormBriefItemResponse,
)
def get_semstorm_brief_item(
    site_id: int,
    brief_id: int,
    session: Session = Depends(get_db),
) -> SemstormBriefItemResponse:
    try:
        payload = semstorm_brief_service.get_semstorm_brief_item(session, site_id, brief_id)
    except semstorm_brief_service.SemstormBriefServiceError as exc:
        _raise_http_error(exc)
    return SemstormBriefItemResponse.model_validate(payload)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/status",
    response_model=SemstormBriefItemResponse,
)
def update_semstorm_brief_item_status(
    site_id: int,
    brief_id: int,
    payload: SemstormBriefStatusUpdateRequest,
    session: Session = Depends(get_db),
) -> SemstormBriefItemResponse:
    try:
        result = semstorm_brief_service.update_semstorm_brief_item_status(
            session,
            site_id,
            brief_id,
            state_status=payload.state_status,
        )
    except semstorm_brief_service.SemstormBriefServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormBriefItemResponse.model_validate(result)


@router.put(
    "/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/execution",
    response_model=SemstormBriefItemResponse,
)
def update_semstorm_brief_execution(
    site_id: int,
    brief_id: int,
    payload: SemstormBriefExecutionUpdateRequest,
    session: Session = Depends(get_db),
) -> SemstormBriefItemResponse:
    try:
        result = semstorm_brief_service.update_semstorm_brief_execution(
            session,
            site_id,
            brief_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except semstorm_brief_service.SemstormBriefServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormBriefItemResponse.model_validate(result)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/execution-status",
    response_model=SemstormBriefItemResponse,
)
def update_semstorm_brief_execution_status(
    site_id: int,
    brief_id: int,
    payload: SemstormBriefExecutionStatusUpdateRequest,
    session: Session = Depends(get_db),
) -> SemstormBriefItemResponse:
    try:
        result = semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            site_id,
            brief_id,
            execution_status=payload.execution_status,
        )
    except semstorm_brief_service.SemstormBriefServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormBriefItemResponse.model_validate(result)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/implementation-status",
    response_model=SemstormBriefItemResponse,
)
def update_semstorm_brief_implementation_status(
    site_id: int,
    brief_id: int,
    payload: SemstormBriefImplementationStatusUpdateRequest,
    session: Session = Depends(get_db),
) -> SemstormBriefItemResponse:
    try:
        result = semstorm_brief_service.update_semstorm_brief_implementation_status(
            session,
            site_id,
            brief_id,
            implementation_status=payload.implementation_status,
            evaluation_note=payload.evaluation_note,
            implementation_url_override=payload.implementation_url_override,
        )
    except semstorm_brief_service.SemstormBriefServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormBriefItemResponse.model_validate(result)


@router.put(
    "/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}",
    response_model=SemstormBriefItemResponse,
)
def update_semstorm_brief_item(
    site_id: int,
    brief_id: int,
    payload: SemstormBriefUpdateRequest,
    session: Session = Depends(get_db),
) -> SemstormBriefItemResponse:
    try:
        result = semstorm_brief_service.update_semstorm_brief_item(
            session,
            site_id,
            brief_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except semstorm_brief_service.SemstormBriefServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormBriefItemResponse.model_validate(result)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrich",
    response_model=SemstormBriefEnrichmentRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def enrich_semstorm_brief(
    site_id: int,
    brief_id: int,
    request: Request,
    session: Session = Depends(get_db),
) -> SemstormBriefEnrichmentRunResponse:
    try:
        result = semstorm_brief_llm_service.enrich_semstorm_brief(
            session,
            site_id,
            brief_id,
            output_language=_resolve_output_language(request),
        )
    except semstorm_brief_llm_service.SemstormBriefLlmServiceError as exc:
        session.commit()
        _raise_http_error(exc)
    session.commit()
    return SemstormBriefEnrichmentRunResponse.model_validate(result)


@router.get(
    "/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrichment-runs",
    response_model=SemstormBriefEnrichmentRunsResponse,
)
def list_semstorm_brief_enrichment_runs(
    site_id: int,
    brief_id: int,
    session: Session = Depends(get_db),
) -> SemstormBriefEnrichmentRunsResponse:
    try:
        payload = semstorm_brief_llm_service.list_semstorm_brief_enrichment_runs(session, site_id, brief_id)
    except semstorm_brief_llm_service.SemstormBriefLlmServiceError as exc:
        _raise_http_error(exc)
    return SemstormBriefEnrichmentRunsResponse.model_validate(payload)


@router.post(
    "/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrichment-runs/{run_id}/apply",
    response_model=SemstormBriefEnrichmentApplyResponse,
)
def apply_semstorm_brief_enrichment_run(
    site_id: int,
    brief_id: int,
    run_id: int,
    session: Session = Depends(get_db),
) -> SemstormBriefEnrichmentApplyResponse:
    try:
        result = semstorm_brief_llm_service.apply_semstorm_brief_enrichment_run(
            session,
            site_id,
            brief_id,
            run_id,
        )
    except semstorm_brief_llm_service.SemstormBriefLlmServiceError as exc:
        _raise_http_error(exc)
    session.commit()
    return SemstormBriefEnrichmentApplyResponse.model_validate(result)


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
