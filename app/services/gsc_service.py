from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crawler.normalization.urls import extract_registered_domain, normalize_url
from app.db.models import CrawlJob, CrawlJobStatus, GscProperty, GscTopQuery, GscUrlMetric, Page, Site
from app.integrations.gsc.auth import GscTokenStore
from app.integrations.gsc.client import GscApiError, SearchConsoleApiClient
from app.schemas.gsc import GscDateRangeLabel
from app.services.seo_analysis import build_page_records

logger = logging.getLogger(__name__)

DATE_RANGE_TO_DAYS: dict[GscDateRangeLabel, int] = {
    "last_28_days": 28,
    "last_90_days": 90,
}
DATE_RANGE_SUFFIX = {
    "last_28_days": "28d",
    "last_90_days": "90d",
}
DEFAULT_TOP_QUERY_SORT = "clicks"
DEFAULT_TOP_QUERY_ORDER = "desc"


class GscServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class ImportRangeResult:
    date_range_label: GscDateRangeLabel
    imported_url_metrics: int
    imported_top_queries: int
    pages_with_top_queries: int
    failed_pages: int
    errors: list[str]


@dataclass(slots=True)
class UrlMetricsImportResult:
    imported_url_metrics: int
    matched_page_ids: set[int]


def build_frontend_gsc_redirect(job_id: int) -> str:
    settings = get_settings()
    return f"{settings.frontend_app_url.rstrip('/')}/jobs/{job_id}/gsc"


def build_frontend_site_gsc_redirect(site_id: int, *, active_crawl_id: int | None = None) -> str:
    settings = get_settings()
    base = f"{settings.frontend_app_url.rstrip('/')}/sites/{site_id}/gsc"
    if active_crawl_id is not None:
        return f"{base}?active_crawl_id={active_crawl_id}"
    return base


def resolve_frontend_gsc_redirect(job_id: int, redirect_url: str | None = None) -> str:
    if redirect_url:
        normalized_redirect_url = redirect_url.strip()
        if normalized_redirect_url:
            _validate_frontend_redirect_url(normalized_redirect_url, job_id)
            return normalized_redirect_url

    return build_frontend_gsc_redirect(job_id)


def resolve_frontend_site_gsc_redirect(
    site_id: int,
    *,
    active_crawl_id: int | None = None,
    redirect_url: str | None = None,
) -> str:
    if redirect_url:
        normalized_redirect_url = redirect_url.strip()
        if normalized_redirect_url:
            _validate_site_frontend_redirect_url(
                normalized_redirect_url,
                site_id,
                active_crawl_id=active_crawl_id,
            )
            return normalized_redirect_url

    return build_frontend_site_gsc_redirect(site_id, active_crawl_id=active_crawl_id)


def get_selected_property_for_site(session: Session, site_id: int) -> GscProperty | None:
    _get_site_or_raise(session, site_id)
    return session.scalar(select(GscProperty).where(GscProperty.site_id == site_id))


def get_selected_property_for_job(session: Session, crawl_job_id: int) -> GscProperty | None:
    crawl_job = session.get(CrawlJob, crawl_job_id)
    if crawl_job is None:
        return None
    return get_selected_property_for_site(session, crawl_job.site_id)


def get_active_crawl_for_site(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
) -> CrawlJob | None:
    _get_site_or_raise(session, site_id)
    crawl_jobs = session.scalars(
        select(CrawlJob)
        .where(CrawlJob.site_id == site_id)
        .order_by(CrawlJob.created_at.desc(), CrawlJob.id.desc())
    ).all()
    if not crawl_jobs:
        if active_crawl_id is not None:
            raise GscServiceError(f"Active crawl {active_crawl_id} does not belong to site {site_id}.")
        return None

    if active_crawl_id is None:
        return crawl_jobs[0]

    for crawl_job in crawl_jobs:
        if crawl_job.id == active_crawl_id:
            return crawl_job
    raise GscServiceError(f"Active crawl {active_crawl_id} does not belong to site {site_id}.")


def list_accessible_properties_for_site(
    session: Session,
    site_id: int,
    *,
    client: SearchConsoleApiClient | None = None,
) -> list[dict[str, Any]]:
    site = _get_site_or_raise(session, site_id)
    selected_property = get_selected_property_for_site(session, site.id)

    resolved_client = client or SearchConsoleApiClient()
    entries = resolved_client.list_sites()
    options: list[dict[str, Any]] = []
    for entry in entries:
        property_uri = str(entry.get("siteUrl") or "").strip()
        if not property_uri:
            continue
        options.append(
            {
                "property_uri": property_uri,
                "permission_level": entry.get("permissionLevel"),
                "matches_site": property_matches_site(property_uri, site),
                "is_selected": bool(selected_property and selected_property.property_uri == property_uri),
            }
        )

    options.sort(
        key=lambda item: (
            not bool(item["matches_site"]),
            item["property_uri"].lower(),
        )
    )
    return options


def list_accessible_properties_for_job(
    session: Session,
    crawl_job_id: int,
    *,
    client: SearchConsoleApiClient | None = None,
) -> list[dict[str, Any]]:
    crawl_job = _get_crawl_job_or_raise(session, crawl_job_id)
    return list_accessible_properties_for_site(session, crawl_job.site_id, client=client)


def select_property_for_site(
    session: Session,
    site_id: int,
    property_uri: str,
    *,
    client: SearchConsoleApiClient | None = None,
) -> GscProperty:
    site = _get_site_or_raise(session, site_id)
    normalized_property_uri = property_uri.strip()
    if not normalized_property_uri:
        raise GscServiceError("property_uri cannot be empty.")

    options = list_accessible_properties_for_site(session, site_id, client=client)
    option_lookup = {item["property_uri"]: item for item in options}
    option = option_lookup.get(normalized_property_uri)
    if option is None:
        raise GscServiceError("Selected GSC property is not available for the current OAuth connection.")
    if not option["matches_site"]:
        raise GscServiceError("Selected GSC property does not match the current site domain.")

    gsc_property = get_selected_property_for_site(session, site.id)
    if gsc_property is None:
        gsc_property = GscProperty(
            site_id=site.id,
            property_uri=normalized_property_uri,
            permission_level=option.get("permission_level"),
        )
        session.add(gsc_property)
    else:
        gsc_property.property_uri = normalized_property_uri
        gsc_property.permission_level = option.get("permission_level")
        gsc_property.updated_at = datetime.now(timezone.utc)

    session.flush()
    return gsc_property


def select_property_for_job(
    session: Session,
    crawl_job_id: int,
    property_uri: str,
    *,
    client: SearchConsoleApiClient | None = None,
) -> GscProperty:
    crawl_job = _get_crawl_job_or_raise(session, crawl_job_id)
    return select_property_for_site(session, crawl_job.site_id, property_uri, client=client)


def import_gsc_for_job(
    session: Session,
    crawl_job_id: int,
    *,
    date_ranges: list[GscDateRangeLabel],
    top_queries_limit: int | None = None,
    client: SearchConsoleApiClient | None = None,
) -> dict[str, Any]:
    crawl_job = _get_crawl_job_or_raise(session, crawl_job_id)
    gsc_property = _get_selected_property_or_raise(session, crawl_job.site_id)

    pages = session.scalars(
        select(Page)
        .where(Page.crawl_job_id == crawl_job_id, Page.is_internal.is_(True))
        .order_by(Page.id.asc())
    ).all()
    if not pages:
        raise GscServiceError(f"Crawl job {crawl_job_id} does not contain any internal pages to match against GSC.")

    resolved_client = client or SearchConsoleApiClient()
    resolved_top_queries_limit = top_queries_limit or get_settings().gsc_default_top_queries_limit
    imported_at = datetime.now(timezone.utc)

    range_results: list[ImportRangeResult] = []
    for date_range_label in dict.fromkeys(date_ranges):
        range_result = _import_range(
            session,
            crawl_job=crawl_job,
            gsc_property=gsc_property,
            pages=pages,
            date_range_label=date_range_label,
            top_queries_limit=resolved_top_queries_limit,
            imported_at=imported_at,
            client=resolved_client,
        )
        range_results.append(range_result)
        _persist_import_stats(crawl_job, imported_at=imported_at, results=range_results)
        session.commit()

    return {
        "crawl_job_id": crawl_job_id,
        "property_uri": gsc_property.property_uri,
        "imported_at": imported_at,
        "ranges": [asdict(result) for result in range_results],
    }


def import_gsc_for_site(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None,
    date_ranges: list[GscDateRangeLabel],
    top_queries_limit: int | None = None,
    client: SearchConsoleApiClient | None = None,
) -> dict[str, Any]:
    active_crawl = get_active_crawl_for_site(session, site_id, active_crawl_id=active_crawl_id)
    if active_crawl is None:
        raise GscServiceError(f"Site {site_id} does not have any crawl jobs to import GSC into yet.")

    return import_gsc_for_job(
        session,
        active_crawl.id,
        date_ranges=date_ranges,
        top_queries_limit=top_queries_limit,
        client=client,
    )


def build_gsc_summary(session: Session, crawl_job_id: int) -> dict[str, Any]:
    crawl_job = _get_crawl_job_or_raise(session, crawl_job_id)
    gsc_property = get_selected_property_for_site(session, crawl_job.site_id)
    page_records = build_page_records(session, crawl_job_id)

    ranges: list[dict[str, Any]] = []
    for date_range_label, suffix in DATE_RANGE_SUFFIX.items():
        clicks_key = f"clicks_{suffix}"
        impressions_key = f"impressions_{suffix}"
        top_queries_key = f"top_queries_count_{suffix}"
        last_imported_at = session.scalar(
            select(func.max(GscUrlMetric.fetched_at)).where(
                GscUrlMetric.crawl_job_id == crawl_job_id,
                GscUrlMetric.date_range_label == date_range_label,
            )
        )
        imported_pages = sum(1 for record in page_records if record.get(clicks_key) is not None)
        pages_with_impressions = sum(1 for record in page_records if (record.get(impressions_key) or 0) > 0)
        pages_with_clicks = sum(1 for record in page_records if (record.get(clicks_key) or 0) > 0)
        pages_with_top_queries = sum(1 for record in page_records if (record.get(top_queries_key) or 0) > 0)
        total_top_queries = sum(int(record.get(top_queries_key) or 0) for record in page_records)
        opportunities_with_impressions = sum(
            1
            for record in page_records
            if record.get("has_technical_issue") and (record.get(impressions_key) or 0) > 0
        )
        opportunities_with_clicks = sum(
            1
            for record in page_records
            if record.get("has_technical_issue") and (record.get(clicks_key) or 0) > 0
        )

        ranges.append(
            {
                "date_range_label": date_range_label,
                "imported_pages": imported_pages,
                "pages_with_impressions": pages_with_impressions,
                "pages_with_clicks": pages_with_clicks,
                "pages_with_top_queries": pages_with_top_queries,
                "total_top_queries": total_top_queries,
                "opportunities_with_impressions": opportunities_with_impressions,
                "opportunities_with_clicks": opportunities_with_clicks,
                "last_imported_at": last_imported_at,
            }
        )

    return {
        "crawl_job_id": crawl_job.id,
        "site_id": crawl_job.site_id,
        "auth_connected": _has_gsc_token(),
        "selected_property_uri": gsc_property.property_uri if gsc_property else None,
        "selected_property_permission_level": gsc_property.permission_level if gsc_property else None,
        "available_date_ranges": list(DATE_RANGE_TO_DAYS.keys()),
        "ranges": ranges,
    }


def build_site_gsc_summary(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
) -> dict[str, Any]:
    site = _get_site_or_raise(session, site_id)
    gsc_property = get_selected_property_for_site(session, site.id)
    active_crawl = get_active_crawl_for_site(session, site.id, active_crawl_id=active_crawl_id)

    ranges: list[dict[str, Any]] = []
    if active_crawl is not None:
        ranges = build_gsc_summary(session, active_crawl.id)["ranges"]

    return {
        "site_id": site.id,
        "site_domain": site.domain,
        "site_root_url": site.root_url,
        "auth_connected": _has_gsc_token(),
        "selected_property_uri": gsc_property.property_uri if gsc_property else None,
        "selected_property_permission_level": gsc_property.permission_level if gsc_property else None,
        "available_date_ranges": list(DATE_RANGE_TO_DAYS.keys()),
        "active_crawl_id": active_crawl.id if active_crawl is not None else None,
        "active_crawl_has_gsc_data": any(item.get("last_imported_at") is not None for item in ranges),
        "active_crawl": _serialize_active_crawl_context(active_crawl),
        "ranges": ranges,
    }


def list_top_queries(
    session: Session,
    crawl_job_id: int,
    *,
    page_id: int | None = None,
    date_range_label: GscDateRangeLabel,
    page: int = 1,
    page_size: int = 25,
    sort_by: str = DEFAULT_TOP_QUERY_SORT,
    sort_order: str = DEFAULT_TOP_QUERY_ORDER,
    query_contains: str | None = None,
    query_excludes: str | None = None,
    clicks_min: int | None = None,
    impressions_min: int | None = None,
    ctr_max: float | None = None,
    position_min: float | None = None,
) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None]:
    _get_crawl_job_or_raise(session, crawl_job_id)

    if page_id is not None:
        page_record = _build_page_lookup(session, crawl_job_id).get(page_id)
        if page_record is None:
            raise GscServiceError(f"Page {page_id} was not found in crawl job {crawl_job_id}.")
    else:
        page_record = None

    stmt = select(GscTopQuery).where(
        GscTopQuery.crawl_job_id == crawl_job_id,
        GscTopQuery.date_range_label == date_range_label,
    )
    if page_id is not None:
        stmt = stmt.where(GscTopQuery.page_id == page_id)

    rows = session.scalars(stmt.order_by(GscTopQuery.id.asc())).all()
    records = [
        {
            "id": row.id,
            "page_id": row.page_id,
            "url": row.url,
            "date_range_label": row.date_range_label,
            "query": row.query,
            "clicks": row.clicks,
            "impressions": row.impressions,
            "ctr": row.ctr,
            "position": row.position,
            "fetched_at": row.fetched_at,
        }
        for row in rows
    ]

    if query_contains:
        token = query_contains.strip().lower()
        if token:
            records = [record for record in records if token in record["query"].lower()]
    if query_excludes:
        token = query_excludes.strip().lower()
        if token:
            records = [record for record in records if token not in record["query"].lower()]
    if clicks_min is not None:
        records = [record for record in records if record["clicks"] >= clicks_min]
    if impressions_min is not None:
        records = [record for record in records if record["impressions"] >= impressions_min]
    if ctr_max is not None:
        records = [record for record in records if record["ctr"] is not None and record["ctr"] <= ctr_max]
    if position_min is not None:
        records = [record for record in records if record["position"] is not None and record["position"] >= position_min]

    records.sort(
        key=lambda item: (_normalize_sort_value(item.get(sort_by)), _normalize_sort_value(item.get("id"))),
        reverse=sort_order == "desc",
    )

    total_items = len(records)
    start = (page - 1) * page_size
    end = start + page_size
    return records[start:end], total_items, page_record


def property_matches_site(property_uri: str, site: Site) -> bool:
    normalized_property_uri = property_uri.strip().lower()
    if normalized_property_uri.startswith("sc-domain:"):
        property_domain = normalized_property_uri.removeprefix("sc-domain:")
        return site.domain.lower() == property_domain or site.domain.lower().endswith(f".{property_domain}")

    normalized_url = normalize_url(property_uri)
    if normalized_url is None:
        return False

    parsed = urlparse(normalized_url)
    property_host = parsed.hostname or ""
    property_domain = extract_registered_domain(normalized_url) or property_host
    if not property_domain:
        return False

    site_domain = site.domain.lower()
    same_domain = site_domain == property_domain or site_domain.endswith(f".{property_domain}")
    if not same_domain:
        return False

    site_root = normalize_url(site.root_url) or site.root_url
    return site_root.startswith(normalized_url)


def _serialize_active_crawl_context(crawl_job: CrawlJob | None) -> dict[str, Any] | None:
    if crawl_job is None:
        return None

    settings = crawl_job.settings_json if isinstance(crawl_job.settings_json, dict) else {}
    root_url = settings.get("start_url") if isinstance(settings.get("start_url"), str) else None
    status_value = crawl_job.status.value if isinstance(crawl_job.status, CrawlJobStatus) else str(crawl_job.status)
    return {
        "id": crawl_job.id,
        "site_id": crawl_job.site_id,
        "status": status_value,
        "root_url": root_url,
        "created_at": crawl_job.created_at,
        "started_at": crawl_job.started_at,
        "finished_at": crawl_job.finished_at,
    }


def _has_gsc_token() -> bool:
    try:
        return GscTokenStore().has_token()
    except Exception:  # pragma: no cover - defensive local fallback
        return False


def _validate_frontend_redirect_url(redirect_url: str, job_id: int) -> None:
    parsed = urlparse(redirect_url)
    _validate_frontend_redirect_origin(parsed)
    expected_path = f"/jobs/{job_id}/gsc"
    if parsed.path.rstrip("/") != expected_path:
        raise GscServiceError(f"frontend_redirect_url must point to '{expected_path}'.")


def _validate_site_frontend_redirect_url(
    redirect_url: str,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
) -> None:
    parsed = urlparse(redirect_url)
    _validate_frontend_redirect_origin(parsed)

    expected_path = f"/sites/{site_id}/gsc"
    if parsed.path.rstrip("/") != expected_path:
        raise GscServiceError(f"frontend_redirect_url must point to '{expected_path}'.")

    if active_crawl_id is None:
        return

    query_params = parse_qs(parsed.query, keep_blank_values=False)
    raw_active_values = query_params.get("active_crawl_id")
    if not raw_active_values:
        return

    try:
        parsed_active_crawl_id = int(raw_active_values[0])
    except ValueError as exc:
        raise GscServiceError("frontend_redirect_url contains an invalid active_crawl_id.") from exc

    if parsed_active_crawl_id != active_crawl_id:
        raise GscServiceError("frontend_redirect_url must preserve the current active_crawl_id.")


def _validate_frontend_redirect_origin(parsed: Any) -> None:
    settings = get_settings()
    if parsed.scheme not in {"http", "https"}:
        raise GscServiceError("frontend_redirect_url must use http or https.")
    if not parsed.netloc:
        raise GscServiceError("frontend_redirect_url must be an absolute URL.")

    origin = f"{parsed.scheme}://{parsed.netloc}"
    normalized_allowed_origins = {item.rstrip("/").lower() for item in settings.frontend_dev_origins}
    origin_matches_regex = bool(re.match(settings.frontend_dev_origin_regex, origin, flags=re.IGNORECASE))
    if origin.lower() not in normalized_allowed_origins and not origin_matches_regex:
        raise GscServiceError("frontend_redirect_url must match an allowed local frontend origin.")


def _import_range(
    session: Session,
    *,
    crawl_job: CrawlJob,
    gsc_property: GscProperty,
    pages: list[Page],
    date_range_label: GscDateRangeLabel,
    top_queries_limit: int,
    imported_at: datetime,
    client: SearchConsoleApiClient,
) -> ImportRangeResult:
    errors: list[str] = []
    range_window = _resolve_date_window(date_range_label)
    matched_page_ids: set[int] = set()
    url_metrics_loaded = False

    try:
        url_metrics_result = _import_url_metrics_for_range(
            session,
            crawl_job_id=crawl_job.id,
            gsc_property=gsc_property,
            pages=pages,
            date_range_label=date_range_label,
            start_date=range_window["start_date"],
            end_date=range_window["end_date"],
            imported_at=imported_at,
            client=client,
        )
        imported_url_metrics = url_metrics_result.imported_url_metrics
        matched_page_ids = url_metrics_result.matched_page_ids
        url_metrics_loaded = True
        session.commit()
    except GscApiError as exc:
        logger.warning("GSC URL metrics import failed for job=%s range=%s: %s", crawl_job.id, date_range_label, exc)
        errors.append(str(exc))
        imported_url_metrics = 0

    if not url_metrics_loaded:
        return ImportRangeResult(
            date_range_label=date_range_label,
            imported_url_metrics=imported_url_metrics,
            imported_top_queries=0,
            pages_with_top_queries=0,
            failed_pages=0,
            errors=errors,
        )

    _prune_stale_top_queries_for_range(
        session,
        crawl_job_id=crawl_job.id,
        date_range_label=date_range_label,
        matched_page_ids=matched_page_ids,
    )
    session.commit()

    imported_top_queries = 0
    pages_with_top_queries = 0
    failed_pages = 0
    for page in pages:
        if page.id not in matched_page_ids:
            continue
        try:
            inserted_rows = _import_top_queries_for_page(
                session,
                crawl_job_id=crawl_job.id,
                gsc_property=gsc_property,
                page=page,
                date_range_label=date_range_label,
                start_date=range_window["start_date"],
                end_date=range_window["end_date"],
                top_queries_limit=top_queries_limit,
                imported_at=imported_at,
                client=client,
            )
            imported_top_queries += inserted_rows
            if inserted_rows > 0:
                pages_with_top_queries += 1
            session.commit()
        except GscApiError as exc:
            failed_pages += 1
            logger.warning(
                "GSC top queries import failed for job=%s page_id=%s range=%s: %s",
                crawl_job.id,
                page.id,
                date_range_label,
                exc,
            )
            errors.append(f"{page.url}: {exc}")

    return ImportRangeResult(
        date_range_label=date_range_label,
        imported_url_metrics=imported_url_metrics,
        imported_top_queries=imported_top_queries,
        pages_with_top_queries=pages_with_top_queries,
        failed_pages=failed_pages,
        errors=errors,
    )


def _import_url_metrics_for_range(
    session: Session,
    *,
    crawl_job_id: int,
    gsc_property: GscProperty,
    pages: list[Page],
    date_range_label: GscDateRangeLabel,
    start_date: date,
    end_date: date,
    imported_at: datetime,
    client: SearchConsoleApiClient,
) -> UrlMetricsImportResult:
    settings = get_settings()
    page_lookup = _build_page_candidates_lookup(pages)
    rows: list[dict[str, Any]] = []
    start_row = 0

    while True:
        request = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["page"],
            "aggregationType": "byPage",
            "rowLimit": settings.gsc_metrics_row_limit,
            "startRow": start_row,
        }
        batch = client.query_search_analytics(gsc_property.property_uri, request)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < settings.gsc_metrics_row_limit:
            break
        start_row += settings.gsc_metrics_row_limit

    matched_metrics: list[GscUrlMetric] = []
    matched_page_ids: set[int] = set()
    for row in rows:
        keys = row.get("keys") or []
        if not keys:
            continue
        raw_url = str(keys[0]).strip()
        normalized_metric_url = normalize_url(raw_url) or raw_url
        page = page_lookup.get(normalized_metric_url)
        if page is None:
            continue
        matched_page_ids.add(page.id)
        matched_metrics.append(
            GscUrlMetric(
                gsc_property_id=gsc_property.id,
                crawl_job_id=crawl_job_id,
                page_id=page.id,
                url=raw_url,
                normalized_url=normalized_metric_url,
                date_range_label=date_range_label,
                clicks=int(row.get("clicks") or 0),
                impressions=int(row.get("impressions") or 0),
                ctr=_optional_float(row.get("ctr")),
                position=_optional_float(row.get("position")),
                fetched_at=imported_at,
            )
        )

    session.execute(
        delete(GscUrlMetric).where(
            GscUrlMetric.crawl_job_id == crawl_job_id,
            GscUrlMetric.date_range_label == date_range_label,
        )
    )
    session.add_all(matched_metrics)
    return UrlMetricsImportResult(
        imported_url_metrics=len(matched_metrics),
        matched_page_ids=matched_page_ids,
    )


def _import_top_queries_for_page(
    session: Session,
    *,
    crawl_job_id: int,
    gsc_property: GscProperty,
    page: Page,
    date_range_label: GscDateRangeLabel,
    start_date: date,
    end_date: date,
    top_queries_limit: int,
    imported_at: datetime,
    client: SearchConsoleApiClient,
) -> int:
    request_template = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["query"],
        "aggregationType": "byPage",
        "rowLimit": top_queries_limit,
    }

    candidates = _build_page_query_candidates(page)
    rows: list[dict[str, Any]] = []
    for candidate_url in candidates:
        request = {
            **request_template,
            "dimensionFilterGroups": [
                {
                    "filters": [
                        {
                            "dimension": "page",
                            "operator": "equals",
                            "expression": candidate_url,
                        }
                    ]
                }
            ],
        }
        rows = client.query_search_analytics(gsc_property.property_uri, request)
        if rows:
            break

    session.execute(
        delete(GscTopQuery).where(
            GscTopQuery.crawl_job_id == crawl_job_id,
            GscTopQuery.date_range_label == date_range_label,
            GscTopQuery.page_id == page.id,
        )
    )

    normalized_url = normalize_url(page.final_url or page.normalized_url or page.url) or page.normalized_url
    payload = [
        GscTopQuery(
            gsc_property_id=gsc_property.id,
            crawl_job_id=crawl_job_id,
            page_id=page.id,
            url=page.final_url or page.normalized_url or page.url,
            normalized_url=normalized_url,
            date_range_label=date_range_label,
            query=str(row.get("keys", [""])[0]).strip(),
            clicks=int(row.get("clicks") or 0),
            impressions=int(row.get("impressions") or 0),
            ctr=_optional_float(row.get("ctr")),
            position=_optional_float(row.get("position")),
            fetched_at=imported_at,
        )
        for row in rows
        if row.get("keys")
    ]
    session.add_all(payload)
    return len(payload)


def _persist_import_stats(
    crawl_job: CrawlJob,
    *,
    imported_at: datetime,
    results: list[ImportRangeResult],
) -> None:
    stats_json = crawl_job.stats_json if isinstance(crawl_job.stats_json, dict) else {}
    gsc_stats = stats_json.get("gsc_imports")
    if not isinstance(gsc_stats, dict):
        gsc_stats = {}

    for result in results:
        gsc_stats[result.date_range_label] = {
            "imported_at": imported_at.isoformat(),
            "imported_url_metrics": result.imported_url_metrics,
            "imported_top_queries": result.imported_top_queries,
            "pages_with_top_queries": result.pages_with_top_queries,
            "failed_pages": result.failed_pages,
            "errors": list(result.errors),
        }

    stats_json["gsc_imports"] = gsc_stats
    crawl_job.stats_json = stats_json


def _prune_stale_top_queries_for_range(
    session: Session,
    *,
    crawl_job_id: int,
    date_range_label: GscDateRangeLabel,
    matched_page_ids: set[int],
) -> None:
    stmt = delete(GscTopQuery).where(
        GscTopQuery.crawl_job_id == crawl_job_id,
        GscTopQuery.date_range_label == date_range_label,
    )
    if matched_page_ids:
        stmt = stmt.where(
            or_(
                GscTopQuery.page_id.is_(None),
                GscTopQuery.page_id.not_in(matched_page_ids),
            )
        )
    session.execute(stmt)


def _resolve_date_window(date_range_label: GscDateRangeLabel) -> dict[str, date]:
    days = DATE_RANGE_TO_DAYS[date_range_label]
    end_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    return {
        "start_date": start_date,
        "end_date": end_date,
    }


def _build_page_candidates_lookup(pages: list[Page]) -> dict[str, Page]:
    lookup: dict[str, Page] = {}
    for page in pages:
        for candidate in _build_page_query_candidates(page):
            lookup.setdefault(candidate, page)
    return lookup


def _build_page_query_candidates(page: Page) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for value in [page.url, page.normalized_url]:
        _append_page_query_candidate(candidates, seen, value)

    # Do not reuse a distinct final URL as a GSC lookup key for this page.
    # Redirected or soft-redirected URLs can otherwise import the target page's
    # queries/metrics twice and collide on the unique normalized_url constraint.
    if _page_final_url_matches_identity(page):
        _append_page_query_candidate(candidates, seen, page.final_url)
    return candidates


def _append_page_query_candidate(candidates: list[str], seen: set[str], value: str | None) -> None:
    if not value:
        return
    raw_value = str(value).strip()
    if raw_value and raw_value not in seen:
        seen.add(raw_value)
        candidates.append(raw_value)

    normalized_value = normalize_url(raw_value)
    if normalized_value and normalized_value not in seen:
        seen.add(normalized_value)
        candidates.append(normalized_value)


def _page_final_url_matches_identity(page: Page) -> bool:
    final_url = _normalize_or_preserve_url(page.final_url)
    if final_url is None:
        return False

    page_identity_url = _normalize_or_preserve_url(page.normalized_url) or _normalize_or_preserve_url(page.url)
    if page_identity_url is None:
        return True
    return final_url == page_identity_url


def _normalize_or_preserve_url(value: str | None) -> str | None:
    if not value:
        return None
    raw_value = str(value).strip()
    if not raw_value:
        return None
    return normalize_url(raw_value) or raw_value


def _build_page_lookup(session: Session, crawl_job_id: int) -> dict[int, dict[str, Any]]:
    records = build_page_records(session, crawl_job_id)
    return {int(record["id"]): record for record in records}


def _get_crawl_job_or_raise(session: Session, crawl_job_id: int) -> CrawlJob:
    crawl_job = session.get(CrawlJob, crawl_job_id)
    if crawl_job is None:
        raise GscServiceError(f"Crawl job {crawl_job_id} not found.")
    return crawl_job


def _get_site_or_raise(session: Session, site_id: int) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        raise GscServiceError(f"Site {site_id} not found.")
    return site


def _get_selected_property_or_raise(session: Session, site_id: int) -> GscProperty:
    gsc_property = get_selected_property_for_site(session, site_id)
    if gsc_property is None:
        raise GscServiceError("No GSC property is selected for this site yet.")
    return gsc_property


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _normalize_sort_value(value: Any) -> tuple[int, Any]:
    if value is None:
        return (1, "")
    if isinstance(value, str):
        return (0, value.lower())
    return (0, value)
