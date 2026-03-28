from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.text_processing import normalize_text_for_hash
from app.crawler.normalization.urls import extract_registered_domain
from app.db.models import (
    Site,
    SiteSemstormCompetitor,
    SiteSemstormCompetitorQuery,
    SiteSemstormDiscoveryRun,
    SiteSemstormPromotedItem,
    utcnow,
)
from app.integrations.semstorm.client import SemstormApiClient, SemstormConfigurationError, SemstormIntegrationError
from app.services import (
    crawl_job_service,
    semstorm_coverage_service,
    semstorm_opportunity_state_service,
    semstorm_plan_service,
)


SemstormResultType = Literal["organic", "paid"]
SemstormCompetitorsType = Literal["all", "similar"]
SemstormOpportunityBucket = Literal["quick_win", "core_opportunity", "watchlist"]
SemstormCoverageStatus = Literal["missing", "weak_coverage", "covered"]
SemstormDecisionType = Literal["create_new_page", "expand_existing_page", "monitor_only"]
SemstormGscSignalStatus = Literal["none", "weak", "present"]
SemstormOpportunityStateStatus = Literal["new", "accepted", "dismissed", "promoted"]


class SemstormServiceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "semstorm_error",
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def build_semstorm_discovery_preview(
    session: Session,
    site_id: int,
    *,
    max_competitors: int = 5,
    max_keywords_per_competitor: int = 10,
    result_type: SemstormResultType = "organic",
    include_basic_stats: bool = False,
    competitors_type: SemstormCompetitorsType = "all",
    client: SemstormApiClient | None = None,
) -> dict[str, Any]:
    site = _get_site_or_raise(session, site_id)
    source_domain = _resolve_source_domain(site)
    settings = get_settings()

    response_payload: dict[str, Any] = {
        "site_id": site.id,
        "source_domain": source_domain,
        "semstorm_enabled": bool(settings.semstorm_enabled),
        "result_type": result_type,
        "competitors_type": competitors_type,
        "include_basic_stats": include_basic_stats,
        "max_competitors": int(max_competitors),
        "max_keywords_per_competitor": int(max_keywords_per_competitor),
        "competitors": [],
    }
    if not settings.semstorm_enabled:
        return response_payload

    semstorm_client = client or SemstormApiClient()
    response_payload["competitors"] = _discover_competitors_payload(
        semstorm_client,
        source_domain=source_domain,
        max_competitors=max_competitors,
        max_keywords_per_competitor=max_keywords_per_competitor,
        result_type=result_type,
        include_basic_stats=include_basic_stats,
        competitors_type=competitors_type,
    )
    return response_payload


def run_semstorm_discovery(
    session: Session,
    site_id: int,
    *,
    max_competitors: int = 10,
    max_keywords_per_competitor: int = 25,
    result_type: SemstormResultType = "organic",
    include_basic_stats: bool = True,
    competitors_type: SemstormCompetitorsType = "all",
    client: SemstormApiClient | None = None,
) -> dict[str, Any]:
    site = _get_site_or_raise(session, site_id)
    source_domain = _resolve_source_domain(site)
    run = _create_discovery_run(
        session,
        site_id=site.id,
        source_domain=source_domain,
        max_competitors=max_competitors,
        max_keywords_per_competitor=max_keywords_per_competitor,
        result_type=result_type,
        include_basic_stats=include_basic_stats,
        competitors_type=competitors_type,
    )
    session.flush()

    try:
        _ensure_semstorm_enabled()
        competitors_payload = _discover_competitors_payload(
            client or SemstormApiClient(),
            source_domain=source_domain,
            max_competitors=max_competitors,
            max_keywords_per_competitor=max_keywords_per_competitor,
            result_type=result_type,
            include_basic_stats=include_basic_stats,
            competitors_type=competitors_type,
        )
        summary = _persist_discovery_payload(session, run, competitors_payload)
        _complete_discovery_run(run, summary=summary)
        session.flush()
        session.refresh(run)
        return _serialize_discovery_run(run, include_competitors=True)
    except SemstormServiceError as exc:
        _fail_discovery_run(run, exc)
        session.flush()
        raise


def list_semstorm_discovery_runs(session: Session, site_id: int) -> list[dict[str, Any]]:
    _get_site_or_raise(session, site_id)
    runs = list(
        session.scalars(
            select(SiteSemstormDiscoveryRun)
            .where(SiteSemstormDiscoveryRun.site_id == site_id)
            .order_by(SiteSemstormDiscoveryRun.run_id.desc())
        )
    )
    return [_serialize_discovery_run(run, include_competitors=False) for run in runs]


def get_semstorm_discovery_run(session: Session, site_id: int, run_id: int) -> dict[str, Any]:
    run = _get_discovery_run_or_raise(session, site_id=site_id, run_id=run_id, include_competitors=True)
    return _serialize_discovery_run(run, include_competitors=True)


def get_semstorm_opportunities(
    session: Session,
    site_id: int,
    *,
    run_id: int | None = None,
    coverage_status: SemstormCoverageStatus | None = None,
    bucket: SemstormOpportunityBucket | None = None,
    decision_type: SemstormDecisionType | None = None,
    state_status: SemstormOpportunityStateStatus | None = None,
    has_gsc_signal: bool | None = None,
    only_actionable: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    run = _resolve_completed_discovery_run(session, site_id=site_id, run_id=run_id)
    items_payload, coverage_context = _build_opportunity_items_for_run(
        session,
        site_id=site_id,
        run=run,
    )
    items_payload = _apply_opportunity_filters(
        items_payload,
        coverage_status=coverage_status,
        bucket=bucket,
        decision_type=decision_type,
        state_status=state_status,
        has_gsc_signal=has_gsc_signal,
        only_actionable=only_actionable,
    )
    normalized_limit = max(1, int(limit or 1))
    return {
        "site_id": run.site_id,
        "run_id": run.run_id,
        "source_domain": run.source_domain,
        "active_crawl_id": coverage_context.active_crawl_id,
        "summary": {
            "total_items": len(items_payload),
            "bucket_counts": _build_bucket_counts(items_payload),
            "decision_type_counts": _build_decision_type_counts(items_payload),
            "coverage_status_counts": _build_coverage_status_counts(items_payload),
            "state_counts": _build_state_counts(items_payload),
            "total_competitors": run.total_competitors,
            "total_queries": run.total_queries,
            "unique_keywords": run.unique_keywords,
            "created_at": run.created_at,
        },
        "items": items_payload[:normalized_limit],
    }


def get_semstorm_opportunity_seeds(
    session: Session,
    site_id: int,
    *,
    run_id: int | None = None,
) -> dict[str, Any]:
    return get_semstorm_opportunities(session, site_id, run_id=run_id)


def accept_semstorm_opportunities(
    session: Session,
    site_id: int,
    *,
    run_id: int | None,
    keywords: Sequence[str],
    note: str | None = None,
) -> dict[str, Any]:
    return _apply_semstorm_opportunity_state_action(
        session,
        site_id,
        run_id=run_id,
        keywords=keywords,
        note=note,
        target_state="accepted",
        action="accept",
    )


def dismiss_semstorm_opportunities(
    session: Session,
    site_id: int,
    *,
    run_id: int | None,
    keywords: Sequence[str],
    note: str | None = None,
) -> dict[str, Any]:
    return _apply_semstorm_opportunity_state_action(
        session,
        site_id,
        run_id=run_id,
        keywords=keywords,
        note=note,
        target_state="dismissed",
        action="dismiss",
    )


def promote_semstorm_opportunities(
    session: Session,
    site_id: int,
    *,
    run_id: int | None,
    keywords: Sequence[str],
    note: str | None = None,
) -> dict[str, Any]:
    run = _resolve_completed_discovery_run(session, site_id=site_id, run_id=run_id)
    items, _coverage_context = _build_opportunity_items_for_run(session, site_id=site_id, run=run)
    item_lookup = _build_opportunity_lookup(items)
    requested_keywords = _normalize_requested_keywords(keywords)
    states_by_keyword = semstorm_opportunity_state_service.load_opportunity_states(
        session,
        site_id,
        item_lookup.keys(),
    )
    promoted_by_keyword = semstorm_opportunity_state_service.load_promoted_items(
        session,
        site_id,
        item_lookup.keys(),
    )

    promoted_items: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    updated_keywords: list[str] = []

    for requested_keyword in requested_keywords:
        normalized_keyword = _normalize_keyword(requested_keyword)
        if not normalized_keyword:
            skipped.append({"keyword": requested_keyword, "reason": "invalid_keyword"})
            continue

        item = item_lookup.get(normalized_keyword)
        if item is None:
            skipped.append({"keyword": requested_keyword, "reason": "keyword_not_in_run"})
            continue

        current_state = states_by_keyword.get(normalized_keyword)
        current_state_status = _state_status_from_row(current_state)
        if current_state_status == "dismissed":
            skipped.append({"keyword": item["keyword"], "reason": "dismissed_requires_accept"})
            continue
        if current_state_status == "promoted":
            skipped.append({"keyword": item["keyword"], "reason": "already_promoted"})
            continue
        if promoted_by_keyword.get(normalized_keyword) is not None:
            skipped.append({"keyword": item["keyword"], "reason": "already_promoted"})
            continue

        promoted_item, created = semstorm_opportunity_state_service.create_promoted_item(
            session,
            site_id=site_id,
            source_run_id=run.run_id,
            keyword=str(item["keyword"]),
            normalized_keyword=normalized_keyword,
            bucket=str(item["bucket"]),
            decision_type=str(item["decision_type"]),
            opportunity_score_v2=int(item["opportunity_score_v2"]),
            coverage_status=str(item["coverage_status"]),
            best_match_page_url=_extract_best_match_page_url(item),
            gsc_signal_status=str(item["gsc_signal_status"]),
            source_payload_json=_build_promoted_source_payload(item),
        )
        if not created:
            skipped.append({"keyword": item["keyword"], "reason": "already_promoted"})
            continue

        semstorm_opportunity_state_service.upsert_opportunity_state(
            session,
            site_id=site_id,
            normalized_keyword=normalized_keyword,
            state_status="promoted",
            source_run_id=run.run_id,
            note=note,
        )
        session.flush()
        session.refresh(promoted_item)
        promoted_by_keyword[normalized_keyword] = promoted_item
        promoted_items.append(semstorm_opportunity_state_service.serialize_promoted_item(promoted_item))
        updated_keywords.append(str(item["keyword"]))

    return {
        "action": "promote",
        "site_id": site_id,
        "run_id": run.run_id,
        "note": _normalize_note(note),
        "requested_count": len(requested_keywords),
        "updated_count": len(updated_keywords),
        "promoted_count": len(promoted_items),
        "state_status": "promoted",
        "updated_keywords": updated_keywords,
        "promoted_items": promoted_items,
        "skipped_count": len(skipped),
        "skipped": skipped,
    }


def list_semstorm_promoted_items(session: Session, site_id: int) -> dict[str, Any]:
    _get_site_or_raise(session, site_id)
    rows = list(
        session.scalars(
            select(SiteSemstormPromotedItem)
            .where(SiteSemstormPromotedItem.site_id == site_id)
            .order_by(SiteSemstormPromotedItem.created_at.desc(), SiteSemstormPromotedItem.id.desc())
        )
    )
    plan_by_promoted_id = semstorm_plan_service.load_plan_items_by_promoted_ids(
        session,
        site_id,
        [int(row.id) for row in rows],
    )
    items = [
        {
            **semstorm_opportunity_state_service.serialize_promoted_item(row),
            "has_plan": int(row.id) in plan_by_promoted_id,
            "plan_id": plan_by_promoted_id[int(row.id)].id if int(row.id) in plan_by_promoted_id else None,
            "plan_state_status": (
                plan_by_promoted_id[int(row.id)].state_status if int(row.id) in plan_by_promoted_id else None
            ),
        }
        for row in rows
    ]
    active_count = sum(1 for item in items if str(item.get("promotion_status")) == "active")
    archived_count = sum(1 for item in items if str(item.get("promotion_status")) == "archived")
    return {
        "site_id": site_id,
        "summary": {
            "total_items": len(items),
            "promotion_status_counts": {
                "active": active_count,
                "archived": archived_count,
            },
        },
        "items": items,
    }


def _get_site_or_raise(session: Session, site_id: int) -> Site:
    site = crawl_job_service.get_site(session, site_id)
    if site is None:
        raise SemstormServiceError(f"Site {site_id} not found.", code="not_found", status_code=404)
    return site


def _resolve_source_domain(site: Site) -> str:
    source_domain = str(site.domain or "").strip().lower()
    if source_domain:
        return source_domain

    inferred = extract_registered_domain(str(site.root_url or "").strip())
    if inferred:
        return inferred.lower()
    raise SemstormServiceError(
        f"Site {site.id} is missing a valid root domain.",
        code="invalid_site_domain",
        status_code=400,
    )


def _ensure_semstorm_enabled() -> None:
    settings = get_settings()
    if not settings.semstorm_enabled:
        raise SemstormServiceError(
            "Semstorm discovery is disabled by configuration.",
            code="semstorm_disabled",
            status_code=503,
        )


def _create_discovery_run(
    session: Session,
    *,
    site_id: int,
    source_domain: str,
    max_competitors: int,
    max_keywords_per_competitor: int,
    result_type: SemstormResultType,
    include_basic_stats: bool,
    competitors_type: SemstormCompetitorsType,
) -> SiteSemstormDiscoveryRun:
    next_run_id = (
        session.scalar(
            select(func.coalesce(func.max(SiteSemstormDiscoveryRun.run_id), 0) + 1).where(
                SiteSemstormDiscoveryRun.site_id == site_id
            )
        )
        or 1
    )
    now = utcnow()
    run = SiteSemstormDiscoveryRun(
        site_id=site_id,
        run_id=int(next_run_id),
        status="running",
        stage="discovering",
        source_domain=source_domain[:255],
        result_type=result_type[:16],
        competitors_type=competitors_type[:32],
        include_basic_stats=bool(include_basic_stats),
        max_competitors=max(1, int(max_competitors)),
        max_keywords_per_competitor=max(1, int(max_keywords_per_competitor)),
        started_at=now,
        finished_at=None,
        error_code=None,
        error_message_safe=None,
    )
    session.add(run)
    return run


def _complete_discovery_run(
    run: SiteSemstormDiscoveryRun,
    *,
    summary: dict[str, int],
) -> None:
    now = utcnow()
    run.status = "completed"
    run.stage = "completed"
    run.total_competitors = int(summary["total_competitors"])
    run.total_queries = int(summary["total_queries"])
    run.unique_keywords = int(summary["unique_keywords"])
    run.finished_at = now
    run.error_code = None
    run.error_message_safe = None


def _fail_discovery_run(run: SiteSemstormDiscoveryRun, exc: SemstormServiceError) -> None:
    now = utcnow()
    run.status = "failed"
    run.stage = "failed"
    run.finished_at = now
    run.error_code = exc.code[:64] if exc.code else "semstorm_error"
    run.error_message_safe = str(exc)


def _discover_competitors_payload(
    client: SemstormApiClient,
    *,
    source_domain: str,
    max_competitors: int,
    max_keywords_per_competitor: int,
    result_type: SemstormResultType,
    include_basic_stats: bool,
    competitors_type: SemstormCompetitorsType,
) -> list[dict[str, Any]]:
    try:
        raw_competitors = client.get_competitors(
            domains=[source_domain],
            result_type=result_type,
            competitors_type=competitors_type,
            max_items=max_competitors,
        )
        selected_competitors = _select_competitors(
            raw_competitors,
            source_domain=source_domain,
            limit=max_competitors,
        )
        basic_stats_by_domain = (
            _load_basic_stats_by_domain(
                client,
                domains=[item["domain"] for item in selected_competitors],
                result_type=result_type,
            )
            if include_basic_stats
            else {}
        )
        competitors_payload: list[dict[str, Any]] = []
        for rank, competitor in enumerate(selected_competitors, start=1):
            raw_keywords = client.get_keywords(
                domains=[competitor["domain"]],
                result_type=result_type,
                max_items=max_keywords_per_competitor,
                sorting={"field": "traffic:0", "sort": "desc"},
            )
            top_queries = _normalize_top_queries(
                raw_keywords,
                competitor_domain=competitor["domain"],
                limit=max_keywords_per_competitor,
            )
            competitors_payload.append(
                {
                    "rank": rank,
                    "domain": competitor["domain"],
                    "common_keywords": competitor["common_keywords"],
                    "traffic": competitor["traffic"],
                    "queries_count": len(top_queries),
                    "basic_stats": basic_stats_by_domain.get(competitor["domain"]),
                    "top_queries": top_queries,
                }
            )
        return competitors_payload
    except SemstormServiceError:
        raise
    except (SemstormConfigurationError, SemstormIntegrationError) as exc:
        raise SemstormServiceError(
            str(exc),
            code=getattr(exc, "code", "semstorm_error"),
            status_code=getattr(exc, "status_code", 502),
        ) from exc


def _persist_discovery_payload(
    session: Session,
    run: SiteSemstormDiscoveryRun,
    competitors_payload: Sequence[dict[str, Any]],
) -> dict[str, int]:
    unique_keywords: set[str] = set()
    total_queries = 0

    for competitor_payload in competitors_payload:
        basic_stats_payload = competitor_payload.get("basic_stats")
        basic_stats = basic_stats_payload if isinstance(basic_stats_payload, dict) else None
        competitor = SiteSemstormCompetitor(
            site_id=run.site_id,
            rank=max(1, int(competitor_payload.get("rank") or 1)),
            domain=str(competitor_payload.get("domain") or "")[:255],
            common_keywords=_int_or_zero(competitor_payload.get("common_keywords")),
            traffic=_int_or_zero(competitor_payload.get("traffic")),
            queries_count=_int_or_zero(competitor_payload.get("queries_count")),
            basic_stats_keywords=_int_or_none(basic_stats.get("keywords")) if basic_stats else None,
            basic_stats_keywords_top=_int_or_none(basic_stats.get("keywords_top")) if basic_stats else None,
            basic_stats_traffic=_int_or_none(basic_stats.get("traffic")) if basic_stats else None,
            basic_stats_traffic_potential=(
                _int_or_none(basic_stats.get("traffic_potential")) if basic_stats else None
            ),
            basic_stats_search_volume=_int_or_none(basic_stats.get("search_volume")) if basic_stats else None,
            basic_stats_search_volume_top=(
                _int_or_none(basic_stats.get("search_volume_top")) if basic_stats else None
            ),
        )
        run.competitors.append(competitor)

        raw_queries = competitor_payload.get("top_queries")
        queries_payload = raw_queries if isinstance(raw_queries, list) else []
        for query_rank, query_payload in enumerate(queries_payload, start=1):
            if not isinstance(query_payload, dict):
                continue
            keyword = str(query_payload.get("keyword") or "").strip()
            if not keyword:
                continue
            normalized_keyword = _normalize_keyword(keyword)
            competitor.queries.append(
                SiteSemstormCompetitorQuery(
                    site_id=run.site_id,
                    discovery_run=run,
                    rank=query_rank,
                    keyword=keyword[:512],
                    normalized_keyword=(normalized_keyword or keyword.lower())[:512],
                    position=_int_or_none(query_payload.get("position")),
                    position_change=_int_or_none(query_payload.get("position_change")),
                    url=_string_or_none(query_payload.get("url")),
                    traffic=_int_or_none(query_payload.get("traffic")),
                    traffic_change=_int_or_none(query_payload.get("traffic_change")),
                    volume=_int_or_none(query_payload.get("volume")),
                    competitors=_int_or_none(query_payload.get("competitors")),
                    cpc=_float_or_none(query_payload.get("cpc")),
                    trends_json=_normalize_trends(query_payload.get("trends")),
                )
            )
            if normalized_keyword:
                unique_keywords.add(normalized_keyword)
            total_queries += 1

        competitor.queries_count = len(competitor.queries)

    session.flush()
    return {
        "total_competitors": len(run.competitors),
        "total_queries": total_queries,
        "unique_keywords": len(unique_keywords),
    }


def _get_discovery_run_or_raise(
    session: Session,
    *,
    site_id: int,
    run_id: int,
    include_competitors: bool,
) -> SiteSemstormDiscoveryRun:
    options = []
    if include_competitors:
        options.append(
            selectinload(SiteSemstormDiscoveryRun.competitors).selectinload(SiteSemstormCompetitor.queries)
        )
    statement = (
        select(SiteSemstormDiscoveryRun)
        .where(
            SiteSemstormDiscoveryRun.site_id == site_id,
            SiteSemstormDiscoveryRun.run_id == run_id,
        )
        .options(*options)
    )
    run = session.scalar(statement)
    if run is None:
        raise SemstormServiceError(
            f"Semstorm discovery run {run_id} not found.",
            code="not_found",
            status_code=404,
        )
    return run


def _get_latest_completed_discovery_run_or_raise(
    session: Session,
    *,
    site_id: int,
) -> SiteSemstormDiscoveryRun:
    run = session.scalar(
        select(SiteSemstormDiscoveryRun)
        .where(
            SiteSemstormDiscoveryRun.site_id == site_id,
            SiteSemstormDiscoveryRun.status == "completed",
        )
        .options(selectinload(SiteSemstormDiscoveryRun.competitors).selectinload(SiteSemstormCompetitor.queries))
        .order_by(SiteSemstormDiscoveryRun.run_id.desc())
        .limit(1)
    )
    if run is None:
        raise SemstormServiceError(
            "No completed Semstorm discovery run found for this site.",
            code="not_found",
            status_code=404,
        )
    return run


def _resolve_completed_discovery_run(
    session: Session,
    *,
    site_id: int,
    run_id: int | None,
) -> SiteSemstormDiscoveryRun:
    if run_id is None:
        return _get_latest_completed_discovery_run_or_raise(session, site_id=site_id)

    run = _get_discovery_run_or_raise(session, site_id=site_id, run_id=run_id, include_competitors=True)
    if run.status != "completed":
        raise SemstormServiceError(
            f"Semstorm discovery run {run_id} is not completed.",
            code="run_not_completed",
            status_code=409,
        )
    return run


def _serialize_discovery_run(run: SiteSemstormDiscoveryRun, *, include_competitors: bool) -> dict[str, Any]:
    payload = {
        "id": run.id,
        "site_id": run.site_id,
        "run_id": run.run_id,
        "status": run.status,
        "stage": run.stage,
        "source_domain": run.source_domain,
        "params": {
            "max_competitors": run.max_competitors,
            "max_keywords_per_competitor": run.max_keywords_per_competitor,
            "result_type": run.result_type,
            "include_basic_stats": run.include_basic_stats,
            "competitors_type": run.competitors_type,
        },
        "summary": {
            "total_competitors": run.total_competitors,
            "total_queries": run.total_queries,
            "unique_keywords": run.unique_keywords,
            "created_at": run.created_at,
        },
        "error_code": run.error_code,
        "error_message_safe": run.error_message_safe,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "competitors": [],
    }
    if include_competitors:
        payload["competitors"] = [
            _serialize_discovery_competitor(competitor)
            for competitor in sorted(run.competitors, key=lambda item: (item.rank, item.domain))
        ]
    return payload


def _serialize_discovery_competitor(competitor: SiteSemstormCompetitor) -> dict[str, Any]:
    return {
        "rank": competitor.rank,
        "domain": competitor.domain,
        "common_keywords": competitor.common_keywords,
        "traffic": competitor.traffic,
        "queries_count": competitor.queries_count,
        "basic_stats": _serialize_basic_stats(competitor),
        "top_queries": [
            _serialize_query(query)
            for query in sorted(competitor.queries, key=lambda item: (item.rank, item.keyword.lower()))
        ],
    }


def _serialize_basic_stats(competitor: SiteSemstormCompetitor) -> dict[str, int] | None:
    values = {
        "keywords": competitor.basic_stats_keywords,
        "keywords_top": competitor.basic_stats_keywords_top,
        "traffic": competitor.basic_stats_traffic,
        "traffic_potential": competitor.basic_stats_traffic_potential,
        "search_volume": competitor.basic_stats_search_volume,
        "search_volume_top": competitor.basic_stats_search_volume_top,
    }
    if all(value is None for value in values.values()):
        return None
    return {key: _int_or_zero(value) for key, value in values.items()}


def _serialize_query(query: SiteSemstormCompetitorQuery) -> dict[str, Any]:
    return {
        "keyword": query.keyword,
        "position": query.position,
        "position_change": query.position_change,
        "url": query.url,
        "traffic": query.traffic,
        "traffic_change": query.traffic_change,
        "volume": query.volume,
        "competitors": query.competitors,
        "cpc": query.cpc,
        "trends": list(query.trends_json or []),
    }


def _build_opportunity_items_for_run(
    session: Session,
    *,
    site_id: int,
    run: SiteSemstormDiscoveryRun,
) -> tuple[list[dict[str, Any]], semstorm_coverage_service.SiteCoverageContext]:
    coverage_context = semstorm_coverage_service.build_site_coverage_context(session, site_id)
    items = _build_opportunity_items(
        run,
        coverage_context=coverage_context,
    )
    states_by_keyword = semstorm_opportunity_state_service.load_opportunity_states(
        session,
        site_id,
        [str(item.get("normalized_keyword") or "") for item in items],
    )
    return _apply_opportunity_states(items, states_by_keyword=states_by_keyword), coverage_context


def _build_opportunity_items(
    run: SiteSemstormDiscoveryRun,
    *,
    coverage_context: semstorm_coverage_service.SiteCoverageContext,
) -> list[dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}

    for competitor in sorted(run.competitors, key=lambda item: (item.rank, item.domain)):
        for query in sorted(competitor.queries, key=lambda item: (item.rank, item.keyword.lower())):
            keyword = str(query.keyword or "").strip()
            if not keyword:
                continue
            keyword_key = str(query.normalized_keyword or _normalize_keyword(keyword) or keyword.lower()).strip()
            if not keyword_key:
                continue

            record = aggregated.setdefault(
                keyword_key,
                {
                    "keyword": keyword,
                    "best_position": None,
                    "max_traffic": 0,
                    "max_volume": 0,
                    "cpc_values": [],
                    "competitor_domains": set(),
                    "sample_competitor_metrics": {},
                    "display_priority": (-1, -1, -1, keyword.lower()),
                },
            )
            record["competitor_domains"].add(competitor.domain)
            if query.cpc is not None:
                record["cpc_values"].append(float(query.cpc))
            if query.traffic is not None:
                record["max_traffic"] = max(int(record["max_traffic"]), int(query.traffic))
            if query.volume is not None:
                record["max_volume"] = max(int(record["max_volume"]), int(query.volume))
            if query.position is not None:
                current_best = record["best_position"]
                if current_best is None or int(query.position) < int(current_best):
                    record["best_position"] = int(query.position)

            display_priority = (
                _int_or_zero(query.volume),
                _int_or_zero(query.traffic),
                _position_priority_value(query.position),
                keyword.lower(),
            )
            if display_priority > record["display_priority"]:
                record["keyword"] = keyword
                record["display_priority"] = display_priority

            domain_metrics = record["sample_competitor_metrics"].get(competitor.domain)
            candidate_metrics = (
                _position_priority_value(query.position),
                _int_or_zero(query.traffic),
            )
            if domain_metrics is None or candidate_metrics > domain_metrics:
                record["sample_competitor_metrics"][competitor.domain] = candidate_metrics

    items: list[dict[str, Any]] = []
    for record in aggregated.values():
        competitor_count = len(record["competitor_domains"])
        best_position = record["best_position"]
        max_traffic = int(record["max_traffic"])
        max_volume = int(record["max_volume"])
        avg_cpc = None
        if record["cpc_values"]:
            avg_cpc = round(sum(record["cpc_values"]) / len(record["cpc_values"]), 2)
        bucket = _classify_opportunity_bucket(
            competitor_count=competitor_count,
            best_position=best_position,
            max_volume=max_volume,
            max_traffic=max_traffic,
        )
        opportunity_score_v1 = _compute_opportunity_score_v1(
            competitor_count=competitor_count,
            best_position=best_position,
            max_volume=max_volume,
            max_traffic=max_traffic,
            avg_cpc=avg_cpc,
            bucket=bucket,
        )
        coverage_payload = semstorm_coverage_service.evaluate_keyword_coverage(coverage_context, record["keyword"])
        best_match_page_payload = coverage_payload.get("best_match_page")
        best_match_page = best_match_page_payload if isinstance(best_match_page_payload, dict) else None
        coverage_status = str(coverage_payload.get("coverage_status") or "missing")
        coverage_score_v1 = _int_or_zero(coverage_payload.get("coverage_score_v1"))
        matched_pages_count = _int_or_zero(coverage_payload.get("matched_pages_count"))
        gsc_payload = semstorm_coverage_service.evaluate_keyword_gsc_signal(
            coverage_context,
            record["keyword"],
            best_match_page_id=_int_or_none(best_match_page.get("page_id")) if best_match_page else None,
        )
        gsc_signal_status = str(gsc_payload.get("gsc_signal_status") or "none")
        gsc_summary_payload = gsc_payload.get("gsc_summary")
        gsc_summary = gsc_summary_payload if isinstance(gsc_summary_payload, dict) else None
        decision_type = _classify_opportunity_decision_type(
            coverage_status=coverage_status,
            competitor_count=competitor_count,
            max_volume=max_volume,
            max_traffic=max_traffic,
        )
        opportunity_score_v2 = _compute_opportunity_score_v2(
            opportunity_score_v1=opportunity_score_v1,
            coverage_status=coverage_status,
            gsc_signal_status=gsc_signal_status,
            decision_type=decision_type,
        )
        sample_competitors = [
            domain
            for domain, _metrics in sorted(
                record["sample_competitor_metrics"].items(),
                key=lambda item: (-item[1][0], -item[1][1], item[0]),
            )[:3]
        ]
        items.append(
            {
                "keyword": record["keyword"],
                "normalized_keyword": semstorm_opportunity_state_service.normalize_semstorm_keyword(record["keyword"]),
                "competitor_count": competitor_count,
                "best_position": best_position,
                "max_traffic": max_traffic,
                "max_volume": max_volume,
                "avg_cpc": avg_cpc,
                "bucket": bucket,
                "decision_type": decision_type,
                "opportunity_score_v1": opportunity_score_v1,
                "opportunity_score_v2": opportunity_score_v2,
                "coverage_status": coverage_status,
                "coverage_score_v1": coverage_score_v1,
                "matched_pages_count": matched_pages_count,
                "best_match_page": best_match_page,
                "gsc_signal_status": gsc_signal_status,
                "gsc_summary": gsc_summary,
                "sample_competitors": sample_competitors,
            }
        )

    return sorted(
        items,
        key=lambda item: (
            -int(item["opportunity_score_v2"]),
            -int(item["opportunity_score_v1"]),
            -int(item["competitor_count"]),
            -int(item["max_volume"]),
            str(item["keyword"]).lower(),
        ),
    )


def _apply_opportunity_states(
    items: Sequence[dict[str, Any]],
    *,
    states_by_keyword: dict[str, Any],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        normalized_keyword = str(item.get("normalized_keyword") or _normalize_keyword(str(item.get("keyword") or "")))
        state = states_by_keyword.get(normalized_keyword)
        state_payload = semstorm_opportunity_state_service.serialize_opportunity_state(state)
        state_status = str(state_payload.get("state_status") or "new")
        can_accept = state_status in {"new", "dismissed"}
        can_dismiss = state_status in {"new", "accepted"}
        can_promote = state_status in {"new", "accepted"}
        enriched.append(
            {
                **item,
                "state_status": state_status,
                "state_note": state_payload.get("state_note"),
                "can_accept": can_accept,
                "can_dismiss": can_dismiss,
                "can_promote": can_promote,
            }
        )
    return enriched


def _build_bucket_counts(items: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "quick_win": 0,
        "core_opportunity": 0,
        "watchlist": 0,
    }
    for item in items:
        bucket = str(item.get("bucket") or "")
        if bucket in counts:
            counts[bucket] += 1
    return counts


def _build_decision_type_counts(items: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "create_new_page": 0,
        "expand_existing_page": 0,
        "monitor_only": 0,
    }
    for item in items:
        decision_type = str(item.get("decision_type") or "")
        if decision_type in counts:
            counts[decision_type] += 1
    return counts


def _build_coverage_status_counts(items: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "missing": 0,
        "weak_coverage": 0,
        "covered": 0,
    }
    for item in items:
        coverage_status = str(item.get("coverage_status") or "")
        if coverage_status in counts:
            counts[coverage_status] += 1
    return counts


def _build_state_counts(items: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "new": 0,
        "accepted": 0,
        "dismissed": 0,
        "promoted": 0,
    }
    for item in items:
        state_status = str(item.get("state_status") or "new")
        if state_status in counts:
            counts[state_status] += 1
    return counts


def _apply_opportunity_filters(
    items: Sequence[dict[str, Any]],
    *,
    coverage_status: SemstormCoverageStatus | None,
    bucket: SemstormOpportunityBucket | None,
    decision_type: SemstormDecisionType | None,
    state_status: SemstormOpportunityStateStatus | None,
    has_gsc_signal: bool | None,
    only_actionable: bool,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in items:
        if coverage_status is not None and str(item.get("coverage_status")) != coverage_status:
            continue
        if bucket is not None and str(item.get("bucket")) != bucket:
            continue
        if decision_type is not None and str(item.get("decision_type")) != decision_type:
            continue
        if state_status is not None and str(item.get("state_status") or "new") != state_status:
            continue
        if has_gsc_signal is True and str(item.get("gsc_signal_status")) == "none":
            continue
        if has_gsc_signal is False and str(item.get("gsc_signal_status")) != "none":
            continue
        if only_actionable and str(item.get("state_status") or "new") in {"dismissed", "promoted"}:
            continue
        filtered.append(item)
    return filtered


def _apply_semstorm_opportunity_state_action(
    session: Session,
    site_id: int,
    *,
    run_id: int | None,
    keywords: Sequence[str],
    note: str | None,
    target_state: Literal["accepted", "dismissed"],
    action: Literal["accept", "dismiss"],
) -> dict[str, Any]:
    run = _resolve_completed_discovery_run(session, site_id=site_id, run_id=run_id)
    items, _coverage_context = _build_opportunity_items_for_run(session, site_id=site_id, run=run)
    item_lookup = _build_opportunity_lookup(items)
    requested_keywords = _normalize_requested_keywords(keywords)
    updated_keywords: list[str] = []
    skipped: list[dict[str, str]] = []

    for requested_keyword in requested_keywords:
        normalized_keyword = _normalize_keyword(requested_keyword)
        if not normalized_keyword:
            skipped.append({"keyword": requested_keyword, "reason": "invalid_keyword"})
            continue

        item = item_lookup.get(normalized_keyword)
        if item is None:
            skipped.append({"keyword": requested_keyword, "reason": "keyword_not_in_run"})
            continue

        semstorm_opportunity_state_service.upsert_opportunity_state(
            session,
            site_id=site_id,
            normalized_keyword=normalized_keyword,
            state_status=target_state,
            source_run_id=run.run_id,
            note=note,
        )
        updated_keywords.append(str(item["keyword"]))

    return {
        "action": action,
        "site_id": site_id,
        "run_id": run.run_id,
        "note": _normalize_note(note),
        "requested_count": len(requested_keywords),
        "updated_count": len(updated_keywords),
        "promoted_count": 0,
        "state_status": target_state,
        "updated_keywords": updated_keywords,
        "promoted_items": [],
        "skipped_count": len(skipped),
        "skipped": skipped,
    }


def _build_opportunity_lookup(items: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in items:
        normalized_keyword = str(item.get("normalized_keyword") or _normalize_keyword(str(item.get("keyword") or "")))
        if normalized_keyword:
            lookup[normalized_keyword] = dict(item)
    return lookup


def _normalize_requested_keywords(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        normalized = _normalize_keyword(text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(text)
    return deduped


def _state_status_from_row(row: Any) -> str:
    if row is None:
        return "new"
    return str(getattr(row, "state_status", None) or "new")


def _build_promoted_source_payload(item: dict[str, Any]) -> dict[str, Any]:
    best_match_page_payload = item.get("best_match_page")
    gsc_summary_payload = item.get("gsc_summary")
    return {
        "keyword": item.get("keyword"),
        "competitor_count": item.get("competitor_count"),
        "best_position": item.get("best_position"),
        "max_traffic": item.get("max_traffic"),
        "max_volume": item.get("max_volume"),
        "avg_cpc": item.get("avg_cpc"),
        "bucket": item.get("bucket"),
        "decision_type": item.get("decision_type"),
        "opportunity_score_v1": item.get("opportunity_score_v1"),
        "opportunity_score_v2": item.get("opportunity_score_v2"),
        "coverage_status": item.get("coverage_status"),
        "coverage_score_v1": item.get("coverage_score_v1"),
        "matched_pages_count": item.get("matched_pages_count"),
        "best_match_page": dict(best_match_page_payload) if isinstance(best_match_page_payload, dict) else None,
        "gsc_signal_status": item.get("gsc_signal_status"),
        "gsc_summary": dict(gsc_summary_payload) if isinstance(gsc_summary_payload, dict) else None,
        "sample_competitors": list(item.get("sample_competitors") or []),
    }


def _extract_best_match_page_url(item: dict[str, Any]) -> str | None:
    best_match_page = item.get("best_match_page")
    if not isinstance(best_match_page, dict):
        return None
    return _string_or_none(best_match_page.get("url"))


def _classify_opportunity_bucket(
    *,
    competitor_count: int,
    best_position: int | None,
    max_volume: int,
    max_traffic: int,
) -> SemstormOpportunityBucket:
    normalized_position = best_position if best_position is not None else 999
    if competitor_count >= 2 and normalized_position <= 5 and (max_volume >= 100 or max_traffic >= 20):
        return "core_opportunity"
    if competitor_count >= 2 and normalized_position <= 10 and max_volume >= 50:
        return "quick_win"
    return "watchlist"


def _classify_opportunity_decision_type(
    *,
    coverage_status: str,
    competitor_count: int,
    max_volume: int,
    max_traffic: int,
) -> SemstormDecisionType:
    if coverage_status == "missing" and competitor_count >= 2 and (max_volume >= 50 or max_traffic >= 20):
        return "create_new_page"
    if coverage_status == "weak_coverage" and competitor_count >= 2:
        return "expand_existing_page"
    return "monitor_only"


def _compute_opportunity_score_v1(
    *,
    competitor_count: int,
    best_position: int | None,
    max_volume: int,
    max_traffic: int,
    avg_cpc: float | None,
    bucket: SemstormOpportunityBucket,
) -> int:
    score = 0
    score += min(30, competitor_count * 10)

    normalized_position = best_position if best_position is not None else 999
    if normalized_position <= 3:
        score += 25
    elif normalized_position <= 5:
        score += 20
    elif normalized_position <= 10:
        score += 12

    score += min(25, max_volume // 10)
    score += min(15, max_traffic // 10)
    if avg_cpc is not None:
        score += min(5, int(round(avg_cpc)))

    if bucket == "core_opportunity":
        score += 5
    elif bucket == "quick_win":
        score += 2
    return min(100, score)


def _compute_opportunity_score_v2(
    *,
    opportunity_score_v1: int,
    coverage_status: str,
    gsc_signal_status: str,
    decision_type: str,
) -> int:
    score = int(opportunity_score_v1)

    if coverage_status == "missing":
        score += 20
    elif coverage_status == "weak_coverage":
        score += 12
    elif coverage_status == "covered":
        score -= 22

    if gsc_signal_status == "present":
        score -= 14
    elif gsc_signal_status == "weak":
        score -= 6

    if decision_type == "create_new_page":
        score += 5
    elif decision_type == "expand_existing_page":
        score += 3
    elif decision_type == "monitor_only":
        score -= 5

    return max(0, min(100, score))


def _select_competitors(
    raw_items: Sequence[dict[str, Any]],
    *,
    source_domain: str,
    limit: int,
) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    normalized_limit = max(1, int(limit or 1))

    for raw_item in raw_items:
        domain = _normalize_result_domain(raw_item.get("competitor"))
        if domain is None or _is_self_match(domain, source_domain):
            continue

        dedupe_key = str(extract_registered_domain(domain) or domain).lower()
        normalized = {
            "domain": domain,
            "common_keywords": _int_or_zero(raw_item.get("common_keywords")),
            "traffic": _int_or_zero(raw_item.get("traffic")),
        }
        existing = deduped.get(dedupe_key)
        if existing is None or _competitor_sort_tuple(normalized) > _competitor_sort_tuple(existing):
            deduped[dedupe_key] = normalized

    return sorted(
        deduped.values(),
        key=lambda item: (
            -item["common_keywords"],
            -item["traffic"],
            item["domain"],
        ),
    )[:normalized_limit]


def _load_basic_stats_by_domain(
    client: SemstormApiClient,
    *,
    domains: Sequence[str],
    result_type: SemstormResultType,
) -> dict[str, dict[str, int]]:
    normalized_domains = [domain for domain in domains if domain]
    if not normalized_domains:
        return {}

    payload: dict[str, dict[str, int]] = {}
    for domain_batch in _chunked(normalized_domains, size=5):
        raw_stats = client.get_keywords_basic_stats(domains=domain_batch, result_type=result_type)
        for raw_domain, raw_value in raw_stats.items():
            domain = _normalize_result_domain(raw_domain)
            if domain is None:
                continue
            normalized = _normalize_basic_stats(raw_value)
            payload[domain] = normalized
            registered = extract_registered_domain(domain)
            if registered:
                payload.setdefault(registered, normalized)
    return payload


def _normalize_basic_stats(value: Any) -> dict[str, int]:
    payload = value if isinstance(value, dict) else {}
    return {
        "keywords": _int_or_zero(payload.get("keywords")),
        "keywords_top": _int_or_zero(payload.get("keywords_top")),
        "traffic": _int_or_zero(payload.get("traffic")),
        "traffic_potential": _int_or_zero(payload.get("traffic_potential")),
        "search_volume": _int_or_zero(payload.get("search_volume")),
        "search_volume_top": _int_or_zero(payload.get("search_volume_top")),
    }


def _normalize_top_queries(
    raw_items: Sequence[dict[str, Any]],
    *,
    competitor_domain: str,
    limit: int,
) -> list[dict[str, Any]]:
    normalized_limit = max(1, int(limit or 1))
    normalized: list[dict[str, Any]] = []
    for raw_item in raw_items:
        keyword = str(raw_item.get("keyword") or "").strip()
        if not keyword:
            continue
        normalized.append(
            {
                "keyword": keyword,
                "position": _int_or_none(_domain_value(raw_item.get("position"), competitor_domain)),
                "position_change": _int_or_none(_domain_value(raw_item.get("position_c"), competitor_domain)),
                "url": _string_or_none(_domain_value(raw_item.get("url"), competitor_domain)),
                "traffic": _int_or_none(_domain_value(raw_item.get("traffic"), competitor_domain)),
                "traffic_change": _int_or_none(_domain_value(raw_item.get("traffic_c"), competitor_domain)),
                "volume": _int_or_none(raw_item.get("volume")),
                "competitors": _int_or_none(raw_item.get("competitors")),
                "cpc": _float_or_none(raw_item.get("cpc")),
                "trends": _normalize_trends(raw_item.get("trends")),
            }
        )
        if len(normalized) >= normalized_limit:
            break
    return normalized


def _domain_value(value: Any, domain: str) -> Any:
    if isinstance(value, dict):
        normalized_domain = _normalize_result_domain(domain)
        registered_domain = extract_registered_domain(normalized_domain or "")
        for key, candidate in value.items():
            candidate_domain = _normalize_result_domain(key)
            if candidate_domain is None:
                continue
            candidate_registered_domain = extract_registered_domain(candidate_domain)
            if candidate_domain == normalized_domain or (
                registered_domain and candidate_registered_domain == registered_domain
            ):
                return candidate
        if len(value) == 1:
            return next(iter(value.values()))
        return None
    if isinstance(value, list):
        if not value:
            return None
        return value[0]
    return value


def _normalize_result_domain(value: Any) -> str | None:
    if value is None:
        return None

    raw = str(value).strip().lower()
    if not raw:
        return None
    if "://" in raw:
        host = raw.split("://", 1)[1]
    else:
        host = raw
    host = host.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    host = host.strip().strip(".")
    if not host:
        return None
    return str(extract_registered_domain(host) or host).lower()


def _normalize_keyword(value: str | None) -> str:
    return normalize_text_for_hash(value)


def _is_self_match(candidate_domain: str, source_domain: str) -> bool:
    normalized_candidate = _normalize_result_domain(candidate_domain)
    if normalized_candidate is None:
        return True
    if normalized_candidate == source_domain or normalized_candidate.endswith(f".{source_domain}"):
        return True
    return str(extract_registered_domain(normalized_candidate) or "").lower() == source_domain


def _competitor_sort_tuple(value: dict[str, Any]) -> tuple[int, int, str]:
    return (
        _int_or_zero(value.get("common_keywords")),
        _int_or_zero(value.get("traffic")),
        str(value.get("domain") or ""),
    )


def _position_priority_value(value: int | None) -> int:
    if value is None:
        return 0
    return max(0, 1_000 - int(value))


def _normalize_trends(value: Any) -> list[int]:
    if isinstance(value, str):
        raw_items = [item.strip() for item in value.split(",")]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        raw_items = [str(item).strip() for item in value]
    else:
        return []

    normalized: list[int] = []
    for item in raw_items:
        if not item:
            continue
        try:
            normalized.append(int(item))
        except (TypeError, ValueError):
            continue
    return normalized


def _chunked(values: Sequence[str], *, size: int) -> Iterable[list[str]]:
    step = max(1, int(size or 1))
    for index in range(0, len(values), step):
        yield list(values[index : index + step])


def _int_or_zero(value: Any) -> int:
    normalized = _int_or_none(value)
    return normalized if normalized is not None else 0


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_note(value: str | None) -> str | None:
    return _string_or_none(value)
