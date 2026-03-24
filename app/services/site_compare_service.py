from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import CrawlJob, Site
from app.services import audit_service, internal_linking_service, site_service, trends_service
from app.services.priority_rules import get_priority_rules
from app.services.trend_rules import get_trend_rules

AUDIT_SECTION_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("pages_missing_title", "pages"),
    ("pages_title_too_short", "pages"),
    ("pages_title_too_long", "pages"),
    ("pages_missing_meta_description", "pages"),
    ("pages_meta_description_too_short", "pages"),
    ("pages_meta_description_too_long", "pages"),
    ("pages_missing_h1", "pages"),
    ("pages_multiple_h1", "pages"),
    ("pages_missing_h2", "pages"),
    ("pages_missing_canonical", "pages"),
    ("pages_canonical_to_other_url", "pages"),
    ("pages_canonical_to_non_200", "pages"),
    ("pages_canonical_to_redirect", "pages"),
    ("pages_noindex_like", "pages"),
    ("pages_non_indexable_like", "pages"),
    ("pages_duplicate_title", "duplicates"),
    ("pages_duplicate_meta_description", "duplicates"),
    ("pages_thin_content", "pages"),
    ("pages_duplicate_content", "duplicates"),
    ("pages_with_missing_alt_images", "pages"),
    ("pages_with_no_images", "pages"),
    ("oversized_pages", "pages"),
    ("js_heavy_like_pages", "pages"),
    ("pages_with_render_errors", "pages"),
    ("pages_with_schema", "pages"),
    ("pages_missing_schema", "pages"),
    ("pages_with_x_robots_tag", "pages"),
    ("pages_with_schema_types_summary", "duplicates"),
    ("broken_internal_links", "links"),
    ("unresolved_internal_targets", "links"),
    ("redirecting_internal_links", "links"),
    ("internal_links_to_noindex_like_pages", "links"),
    ("internal_links_to_canonicalized_pages", "links"),
    ("redirect_chains_internal", "links"),
)
AUDIT_STATUS_ORDER: dict[str, int] = {
    "worsened": 4,
    "new": 3,
    "improved": 2,
    "resolved": 1,
    "unchanged": 0,
}
TREND_ORDER: dict[str, int] = {
    "improved": 2,
    "flat": 1,
    "worsened": 0,
}
INTERNAL_LINKING_EQUITY_THRESHOLD = 5.0
INTERNAL_LINKING_ANCHOR_THRESHOLD = 5.0
INTERNAL_LINKING_BOILERPLATE_THRESHOLD = 0.05
INTERNAL_LINKING_PAGES_THRESHOLD = 1
SAMPLE_PREVIEW_LIMIT = 3


class SiteCompareServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class ResolvedCompareContext:
    site: Site
    active_crawl: CrawlJob | None
    baseline_crawl: CrawlJob | None
    compare_available: bool
    compare_unavailable_reason: str | None


def _resolve_compare_context(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None,
    baseline_crawl_id: int | None,
) -> ResolvedCompareContext:
    try:
        workspace_context = site_service.resolve_site_workspace_context(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
        )
    except site_service.SiteServiceError as exc:
        raise SiteCompareServiceError(str(exc)) from exc

    active_crawl = workspace_context["active_crawl"]
    baseline_crawl = workspace_context["baseline_crawl"]
    compare_available = active_crawl is not None and baseline_crawl is not None
    compare_unavailable_reason: str | None = None
    if active_crawl is None:
        compare_unavailable_reason = "No active crawl is available for this site."
    elif baseline_crawl is None:
        compare_unavailable_reason = "Compare becomes available after at least two crawl snapshots exist for the site."

    return ResolvedCompareContext(
        site=workspace_context["site"],
        active_crawl=active_crawl,
        baseline_crawl=baseline_crawl,
        compare_available=compare_available,
        compare_unavailable_reason=compare_unavailable_reason,
    )


def _serialize_context(context: ResolvedCompareContext) -> dict[str, Any]:
    return {
        "site_id": context.site.id,
        "site_domain": context.site.domain,
        "active_crawl_id": context.active_crawl.id if context.active_crawl is not None else None,
        "baseline_crawl_id": context.baseline_crawl.id if context.baseline_crawl is not None else None,
        "compare_available": context.compare_available,
        "compare_unavailable_reason": context.compare_unavailable_reason,
        "active_crawl": _serialize_crawl(context.active_crawl, context.site),
        "baseline_crawl": _serialize_crawl(context.baseline_crawl, context.site),
    }


def _serialize_crawl(crawl_job: CrawlJob | None, site: Site) -> dict[str, Any] | None:
    if crawl_job is None:
        return None
    settings = crawl_job.settings_json if isinstance(crawl_job.settings_json, dict) else {}
    status = crawl_job.status.value if hasattr(crawl_job.status, "value") else str(crawl_job.status)
    return {
        "id": crawl_job.id,
        "status": status,
        "created_at": crawl_job.created_at,
        "started_at": crawl_job.started_at,
        "finished_at": crawl_job.finished_at,
        "root_url": settings.get("start_url") or site.root_url,
    }


def _apply_boolean_filter(rows: list[dict[str, Any]], *, key: str, value: bool | None) -> list[dict[str, Any]]:
    if value is None:
        return rows
    return [row for row in rows if bool(row.get(key)) is value]


def _apply_text_filter(rows: list[dict[str, Any]], *, key: str, value: str | None) -> list[dict[str, Any]]:
    tokens = _normalize_filter_tokens(value)
    if not tokens:
        return rows
    return [row for row in rows if str(row.get(key) or "").lower() in tokens]


def _normalize_filter_tokens(value: str | None, *, mode: str = "lower") -> set[str]:
    if not value:
        return set()

    normalized: set[str] = set()
    for raw_token in value.split(","):
        token = raw_token.strip()
        if not token:
            continue
        normalized.add(token.upper() if mode == "upper" else token.lower())
    return normalized


def _apply_url_contains_filter(rows: list[dict[str, Any]], *, url_contains: str | None) -> list[dict[str, Any]]:
    if not url_contains:
        return rows
    token = url_contains.strip().lower()
    if not token:
        return rows
    return [row for row in rows if token in str(row.get("url") or "").lower()]


def _row_contains_any_token(values: list[Any], filter_value: str | None) -> bool:
    tokens = _normalize_filter_tokens(filter_value, mode="upper")
    if not tokens:
        return True
    normalized_values = {str(value).upper() for value in values if value is not None}
    return bool(tokens & normalized_values)


def _paginate_records(records: list[dict[str, Any]], *, page: int, page_size: int) -> tuple[list[dict[str, Any]], int, int]:
    total_items = len(records)
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    start = (page - 1) * page_size
    end = start + page_size
    return records[start:end], total_items, total_pages


def _sort_records(
    records: list[dict[str, Any]],
    *,
    sort_by: str,
    sort_order: str,
    custom_order: dict[str, int] | None = None,
) -> None:
    present_records = [record for record in records if record.get(sort_by) is not None]
    missing_records = [record for record in records if record.get(sort_by) is None]
    present_records.sort(
        key=lambda item: (
            _normalize_sort_value(item.get(sort_by), custom_order=custom_order),
            _normalize_sort_value(item.get("url")),
        ),
        reverse=sort_order == "desc",
    )
    missing_records.sort(key=lambda item: _normalize_sort_value(item.get("url")))
    records[:] = present_records + missing_records


def _normalize_sort_value(value: Any, *, custom_order: dict[str, int] | None = None) -> tuple[int, Any]:
    if value is None:
        return (1, "")
    if custom_order and isinstance(value, str):
        return (0, custom_order.get(value.lower(), custom_order.get(value, 0)))
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, str):
        return (0, value.lower())
    return (0, value)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _delta_optional_int(active: Any, baseline: Any) -> int | None:
    if active is None or baseline is None:
        return None
    return int(active) - int(baseline)


def _delta_optional_float(active: Any, baseline: Any) -> float | None:
    if active is None or baseline is None:
        return None
    return float(active) - float(baseline)


def _record_value(record: dict[str, Any] | None, key: str) -> Any:
    if record is None:
        return None
    return record.get(key)


def _is_flag_enabled(record: dict[str, Any] | None, key: str) -> bool:
    return bool(record.get(key)) if record is not None else False


def _classify_delta_trend(delta: Any, *, threshold: int) -> str | None:
    if delta is None:
        return None
    if int(delta) >= threshold:
        return "improved"
    if int(delta) <= -threshold:
        return "worsened"
    return "flat"


def _classify_priority_trend(delta: Any) -> str | None:
    if delta is None:
        return None
    if int(delta) > 0:
        return "improved"
    if int(delta) < 0:
        return "worsened"
    return "flat"


def _classify_response_time_trend(delta: Any, *, threshold: int) -> str | None:
    if delta is None:
        return None
    if int(delta) <= -threshold:
        return "improved"
    if int(delta) >= threshold:
        return "worsened"
    return "flat"


def _classify_internal_linking_trend(delta_links: Any, delta_linking_pages: Any) -> str | None:
    if delta_links is None and delta_linking_pages is None:
        return None
    score = 0
    if delta_links is not None:
        score += 1 if int(delta_links) > 0 else -1 if int(delta_links) < 0 else 0
    if delta_linking_pages is not None:
        score += 2 if int(delta_linking_pages) > 0 else -2 if int(delta_linking_pages) < 0 else 0
    if score > 0:
        return "improved"
    if score < 0:
        return "worsened"
    return "flat"


def build_site_pages_compare(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
    baseline_crawl_id: int | None = None,
    gsc_date_range: str = "last_28_days",
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "change_type",
    sort_order: str = "desc",
    change_type: str | None = None,
    changed: bool | None = None,
    status_changed: bool | None = None,
    title_changed: bool | None = None,
    meta_description_changed: bool | None = None,
    h1_changed: bool | None = None,
    canonical_changed: bool | None = None,
    noindex_changed: bool | None = None,
    priority_trend: str | None = None,
    internal_linking_trend: str | None = None,
    content_trend: str | None = None,
    response_time_trend: str | None = None,
    url_contains: str | None = None,
) -> dict[str, Any]:
    context = _resolve_compare_context(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        baseline_crawl_id=baseline_crawl_id,
    )
    if not context.compare_available:
        return {
            "context": _serialize_context(context),
            "gsc_date_range": gsc_date_range,
            "summary": _empty_pages_compare_summary(),
            "items": [],
            "page": page,
            "page_size": page_size,
            "total_items": 0,
            "total_pages": 0,
        }

    trend_rules = get_trend_rules()
    base_rows = trends_service.get_all_crawl_compare_rows(
        session,
        context.active_crawl.id,
        baseline_job_id=context.baseline_crawl.id,
        gsc_date_range=gsc_date_range,
        sort_by="url",
        sort_order="asc",
    )
    rows = [_build_pages_compare_row(row, trend_rules=trend_rules) for row in base_rows]
    summary = _build_pages_compare_summary(rows)
    filtered = _filter_pages_compare_rows(
        rows,
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
    _sort_records(
        filtered,
        sort_by=sort_by,
        sort_order=sort_order,
        custom_order=trends_service.CRAWL_CHANGE_TYPE_ORDER if sort_by == "change_type" else TREND_ORDER if sort_by.endswith("_trend") else None,
    )
    paginated_items, total_items, total_pages = _paginate_records(filtered, page=page, page_size=page_size)

    return {
        "context": _serialize_context(context),
        "gsc_date_range": gsc_date_range,
        "summary": summary,
        "items": paginated_items,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def _build_pages_compare_row(base_row: dict[str, Any], *, trend_rules) -> dict[str, Any]:
    changed_fields = {
        str(field_name)
        for field_name in base_row.get("changed_fields") or []
        if field_name not in {"new_url", "missing_url"}
    }
    word_count_trend = _classify_delta_trend(base_row.get("delta_word_count"), threshold=trend_rules.word_count_delta_threshold)
    response_time_trend = _classify_response_time_trend(
        base_row.get("delta_response_time_ms"),
        threshold=trend_rules.response_time_delta_threshold_ms,
    )
    priority_trend = _classify_priority_trend(base_row.get("delta_priority_score"))
    internal_linking_trend = _classify_internal_linking_trend(
        base_row.get("delta_incoming_internal_links"),
        base_row.get("delta_incoming_internal_linking_pages"),
    )
    if word_count_trend in {"improved", "worsened"}:
        changed_fields.add("word_count")
    if response_time_trend in {"improved", "worsened"}:
        changed_fields.add("response_time_ms")
    if priority_trend in {"improved", "worsened"}:
        changed_fields.add("priority_score")
    if internal_linking_trend in {"improved", "worsened"}:
        changed_fields.add("internal_linking")

    return {
        "url": base_row["url"],
        "normalized_url": base_row["normalized_url"],
        "active_page_id": base_row.get("target_page_id"),
        "baseline_page_id": base_row.get("baseline_page_id"),
        "change_type": base_row.get("change_type"),
        "changed_fields": sorted(changed_fields),
        "change_rationale": base_row.get("change_rationale") or "",
        "active_status_code": base_row.get("target_status_code"),
        "baseline_status_code": base_row.get("baseline_status_code"),
        "status_code_changed": bool(base_row.get("status_code_changed")),
        "active_title": base_row.get("target_title"),
        "baseline_title": base_row.get("baseline_title"),
        "title_changed": bool(base_row.get("title_changed")),
        "active_meta_description": base_row.get("target_meta_description"),
        "baseline_meta_description": base_row.get("baseline_meta_description"),
        "meta_description_changed": bool(base_row.get("meta_description_changed")),
        "active_h1": base_row.get("target_h1"),
        "baseline_h1": base_row.get("baseline_h1"),
        "h1_changed": bool(base_row.get("h1_changed")),
        "active_canonical_url": base_row.get("target_canonical_url"),
        "baseline_canonical_url": base_row.get("baseline_canonical_url"),
        "canonical_changed": bool(base_row.get("canonical_url_changed")),
        "active_noindex_like": base_row.get("target_noindex_like"),
        "baseline_noindex_like": base_row.get("baseline_noindex_like"),
        "noindex_changed": bool(base_row.get("noindex_like_changed")),
        "active_word_count": base_row.get("target_word_count"),
        "baseline_word_count": base_row.get("baseline_word_count"),
        "delta_word_count": base_row.get("delta_word_count"),
        "word_count_trend": word_count_trend,
        "active_response_time_ms": base_row.get("target_response_time_ms"),
        "baseline_response_time_ms": base_row.get("baseline_response_time_ms"),
        "delta_response_time_ms": base_row.get("delta_response_time_ms"),
        "response_time_trend": response_time_trend,
        "active_incoming_internal_links": base_row.get("target_incoming_internal_links"),
        "baseline_incoming_internal_links": base_row.get("baseline_incoming_internal_links"),
        "delta_incoming_internal_links": base_row.get("delta_incoming_internal_links"),
        "active_incoming_internal_linking_pages": base_row.get("target_incoming_internal_linking_pages"),
        "baseline_incoming_internal_linking_pages": base_row.get("baseline_incoming_internal_linking_pages"),
        "delta_incoming_internal_linking_pages": base_row.get("delta_incoming_internal_linking_pages"),
        "internal_linking_trend": internal_linking_trend,
        "active_priority_score": base_row.get("target_priority_score"),
        "baseline_priority_score": base_row.get("baseline_priority_score"),
        "delta_priority_score": base_row.get("delta_priority_score"),
        "priority_trend": priority_trend,
        "active_priority_level": base_row.get("target_priority_level"),
        "baseline_priority_level": base_row.get("baseline_priority_level"),
        "active_primary_opportunity_type": base_row.get("target_primary_opportunity_type"),
    }


def _build_pages_compare_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "active_urls": sum(1 for row in rows if row.get("active_page_id") is not None),
        "baseline_urls": sum(1 for row in rows if row.get("baseline_page_id") is not None),
        "shared_urls": sum(1 for row in rows if row.get("active_page_id") is not None and row.get("baseline_page_id") is not None),
        "new_urls": sum(1 for row in rows if row.get("change_type") == "new"),
        "missing_urls": sum(1 for row in rows if row.get("change_type") == "missing"),
        "changed_urls": sum(1 for row in rows if _row_has_pages_compare_change(row)),
        "improved_urls": sum(1 for row in rows if row.get("change_type") == "improved"),
        "worsened_urls": sum(1 for row in rows if row.get("change_type") == "worsened"),
        "unchanged_urls": sum(1 for row in rows if row.get("change_type") == "unchanged"),
        "status_changed_urls": sum(1 for row in rows if bool(row.get("status_code_changed"))),
        "title_changed_urls": sum(1 for row in rows if bool(row.get("title_changed"))),
        "meta_description_changed_urls": sum(1 for row in rows if bool(row.get("meta_description_changed"))),
        "h1_changed_urls": sum(1 for row in rows if bool(row.get("h1_changed"))),
        "canonical_changed_urls": sum(1 for row in rows if bool(row.get("canonical_changed"))),
        "noindex_changed_urls": sum(1 for row in rows if bool(row.get("noindex_changed"))),
        "priority_improved_urls": sum(1 for row in rows if row.get("priority_trend") == "improved"),
        "priority_worsened_urls": sum(1 for row in rows if row.get("priority_trend") == "worsened"),
        "internal_linking_improved_urls": sum(1 for row in rows if row.get("internal_linking_trend") == "improved"),
        "internal_linking_worsened_urls": sum(1 for row in rows if row.get("internal_linking_trend") == "worsened"),
        "content_growth_urls": sum(1 for row in rows if row.get("word_count_trend") == "improved"),
        "content_drop_urls": sum(1 for row in rows if row.get("word_count_trend") == "worsened"),
    }


def _filter_pages_compare_rows(
    rows: list[dict[str, Any]],
    *,
    change_type: str | None,
    changed: bool | None,
    status_changed: bool | None,
    title_changed: bool | None,
    meta_description_changed: bool | None,
    h1_changed: bool | None,
    canonical_changed: bool | None,
    noindex_changed: bool | None,
    priority_trend: str | None,
    internal_linking_trend: str | None,
    content_trend: str | None,
    response_time_trend: str | None,
    url_contains: str | None,
) -> list[dict[str, Any]]:
    filtered = rows
    filtered = _apply_text_filter(filtered, key="change_type", value=change_type)
    if changed is not None:
        filtered = [row for row in filtered if _row_has_pages_compare_change(row) is changed]
    filtered = _apply_boolean_filter(filtered, key="status_code_changed", value=status_changed)
    filtered = _apply_boolean_filter(filtered, key="title_changed", value=title_changed)
    filtered = _apply_boolean_filter(filtered, key="meta_description_changed", value=meta_description_changed)
    filtered = _apply_boolean_filter(filtered, key="h1_changed", value=h1_changed)
    filtered = _apply_boolean_filter(filtered, key="canonical_changed", value=canonical_changed)
    filtered = _apply_boolean_filter(filtered, key="noindex_changed", value=noindex_changed)
    filtered = _apply_text_filter(filtered, key="priority_trend", value=priority_trend)
    filtered = _apply_text_filter(filtered, key="internal_linking_trend", value=internal_linking_trend)
    filtered = _apply_text_filter(filtered, key="word_count_trend", value=content_trend)
    filtered = _apply_text_filter(filtered, key="response_time_trend", value=response_time_trend)
    filtered = _apply_url_contains_filter(filtered, url_contains=url_contains)
    return filtered


def _empty_pages_compare_summary() -> dict[str, int]:
    return {
        "active_urls": 0,
        "baseline_urls": 0,
        "shared_urls": 0,
        "new_urls": 0,
        "missing_urls": 0,
        "changed_urls": 0,
        "improved_urls": 0,
        "worsened_urls": 0,
        "unchanged_urls": 0,
        "status_changed_urls": 0,
        "title_changed_urls": 0,
        "meta_description_changed_urls": 0,
        "h1_changed_urls": 0,
        "canonical_changed_urls": 0,
        "noindex_changed_urls": 0,
        "priority_improved_urls": 0,
        "priority_worsened_urls": 0,
        "internal_linking_improved_urls": 0,
        "internal_linking_worsened_urls": 0,
        "content_growth_urls": 0,
        "content_drop_urls": 0,
    }


def _row_has_pages_compare_change(row: dict[str, Any]) -> bool:
    if row.get("change_type") in {"new", "missing", "improved", "worsened"}:
        return True
    return bool(row.get("changed_fields"))


def build_site_audit_compare(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
    baseline_crawl_id: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    context = _resolve_compare_context(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        baseline_crawl_id=baseline_crawl_id,
    )
    if not context.compare_available:
        return {
            "context": _serialize_context(context),
            "summary": _empty_audit_compare_summary(),
            "sections": [],
        }

    active_report = audit_service.build_audit_report(session, context.active_crawl.id)
    baseline_report = audit_service.build_audit_report(session, context.baseline_crawl.id)
    sections = [
        _build_audit_compare_section(
            key=key,
            area=area,
            active_items=active_report.get(key) or [],
            baseline_items=baseline_report.get(key) or [],
        )
        for key, area in AUDIT_SECTION_DEFINITIONS
    ]
    summary = _build_audit_compare_summary(sections)
    filtered = _filter_audit_compare_sections(sections, status=status)
    _sort_records(filtered, sort_by="status", sort_order="desc", custom_order=AUDIT_STATUS_ORDER)

    return {
        "context": _serialize_context(context),
        "summary": summary,
        "sections": filtered,
    }


def _build_audit_compare_section(
    *,
    key: str,
    area: str,
    active_items: list[dict[str, Any]],
    baseline_items: list[dict[str, Any]],
) -> dict[str, Any]:
    active_identifiers = _audit_identifiers(key, active_items)
    baseline_identifiers = _audit_identifiers(key, baseline_items)
    resolved_items = sorted(baseline_identifiers - active_identifiers)
    new_items = sorted(active_identifiers - baseline_identifiers)
    active_count = len(active_items)
    baseline_count = len(baseline_items)

    return {
        "key": key,
        "area": area,
        "active_count": active_count,
        "baseline_count": baseline_count,
        "delta": active_count - baseline_count,
        "status": _classify_audit_section_status(
            active_count=active_count,
            baseline_count=baseline_count,
            resolved_items_count=len(resolved_items),
            new_items_count=len(new_items),
        ),
        "resolved_items_count": len(resolved_items),
        "new_items_count": len(new_items),
        "sample_resolved_items": resolved_items[:SAMPLE_PREVIEW_LIMIT],
        "sample_new_items": new_items[:SAMPLE_PREVIEW_LIMIT],
    }


def _build_audit_compare_summary(sections: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_sections": len(sections),
        "resolved_sections": sum(1 for section in sections if section["status"] == "resolved"),
        "new_sections": sum(1 for section in sections if section["status"] == "new"),
        "improved_sections": sum(1 for section in sections if section["status"] == "improved"),
        "worsened_sections": sum(1 for section in sections if section["status"] == "worsened"),
        "unchanged_sections": sum(1 for section in sections if section["status"] == "unchanged"),
        "resolved_issues_total": sum(int(section["resolved_items_count"]) for section in sections),
        "new_issues_total": sum(int(section["new_items_count"]) for section in sections),
        "active_issues_total": sum(int(section["active_count"]) for section in sections),
        "baseline_issues_total": sum(int(section["baseline_count"]) for section in sections),
    }


def _filter_audit_compare_sections(
    sections: list[dict[str, Any]],
    *,
    status: str | None,
) -> list[dict[str, Any]]:
    tokens = _normalize_filter_tokens(status)
    if not tokens:
        return sections
    return [section for section in sections if str(section.get("status") or "").lower() in tokens]


def _empty_audit_compare_summary() -> dict[str, int]:
    return {
        "total_sections": 0,
        "resolved_sections": 0,
        "new_sections": 0,
        "improved_sections": 0,
        "worsened_sections": 0,
        "unchanged_sections": 0,
        "resolved_issues_total": 0,
        "new_issues_total": 0,
        "active_issues_total": 0,
        "baseline_issues_total": 0,
    }


def _audit_identifiers(key: str, items: list[dict[str, Any]]) -> set[str]:
    identifiers: set[str] = set()
    if key.startswith("pages_duplicate") or key == "pages_with_schema_types_summary":
        for item in items:
            value = item.get("value")
            if value is not None:
                identifiers.add(str(value))
        return identifiers

    if key.startswith("pages_") or key in {"oversized_pages", "js_heavy_like_pages", "rendered_pages"}:
        for item in items:
            identifier = item.get("normalized_url") or item.get("url")
            if identifier:
                identifiers.add(str(identifier))
        return identifiers

    for item in items:
        source = item.get("source_url") or ""
        target = item.get("target_normalized_url") or item.get("target_url") or ""
        identifiers.add(f"{source} -> {target}")
    return identifiers


def _classify_audit_section_status(
    *,
    active_count: int,
    baseline_count: int,
    resolved_items_count: int,
    new_items_count: int,
) -> str:
    if active_count == 0 and baseline_count > 0:
        return "resolved"
    if baseline_count == 0 and active_count > 0:
        return "new"
    if new_items_count > resolved_items_count or active_count > baseline_count:
        return "worsened"
    if resolved_items_count > new_items_count or active_count < baseline_count:
        return "improved"
    return "unchanged"


def build_site_opportunities_compare(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
    baseline_crawl_id: int | None = None,
    gsc_date_range: str = "last_28_days",
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "delta_priority_score",
    sort_order: str = "desc",
    change_kind: str | None = None,
    opportunity_type: str | None = None,
    url_contains: str | None = None,
) -> dict[str, Any]:
    context = _resolve_compare_context(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        baseline_crawl_id=baseline_crawl_id,
    )
    actionable_threshold = int(get_priority_rules().priority_level_thresholds["high"])
    if not context.compare_available:
        return {
            "context": _serialize_context(context),
            "gsc_date_range": gsc_date_range,
            "actionable_priority_score_threshold": actionable_threshold,
            "summary": _empty_opportunities_compare_summary(),
            "items": [],
            "page": page,
            "page_size": page_size,
            "total_items": 0,
            "total_pages": 0,
        }

    base_rows = trends_service.get_all_crawl_compare_rows(
        session,
        context.active_crawl.id,
        baseline_job_id=context.baseline_crawl.id,
        gsc_date_range=gsc_date_range,
        sort_by="url",
        sort_order="asc",
    )
    rows = [
        _build_opportunities_compare_row(
            row,
            actionable_threshold=actionable_threshold,
        )
        for row in base_rows
    ]
    summary = _build_opportunities_compare_summary(rows, actionable_threshold=actionable_threshold)
    filtered = _filter_opportunities_compare_rows(
        rows,
        change_kind=change_kind,
        opportunity_type=opportunity_type,
        url_contains=url_contains,
    )
    _sort_records(
        filtered,
        sort_by=sort_by,
        sort_order=sort_order,
        custom_order=trends_service.CRAWL_CHANGE_TYPE_ORDER if sort_by == "change_type" else None,
    )
    paginated_items, total_items, total_pages = _paginate_records(filtered, page=page, page_size=page_size)

    return {
        "context": _serialize_context(context),
        "gsc_date_range": gsc_date_range,
        "actionable_priority_score_threshold": actionable_threshold,
        "summary": summary,
        "items": paginated_items,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def _build_opportunities_compare_row(base_row: dict[str, Any], *, actionable_threshold: int) -> dict[str, Any]:
    active_priority_score = _safe_int(base_row.get("target_priority_score"))
    baseline_priority_score = _safe_int(base_row.get("baseline_priority_score"))
    active_opportunity_types = list(base_row.get("target_opportunity_types") or [])
    baseline_opportunity_types = list(base_row.get("baseline_opportunity_types") or [])
    new_opportunity_types = sorted(set(active_opportunity_types) - set(baseline_opportunity_types))
    resolved_opportunity_types = sorted(set(baseline_opportunity_types) - set(active_opportunity_types))
    entered_actionable = bool(
        active_priority_score is not None
        and baseline_priority_score is not None
        and active_priority_score >= actionable_threshold
        and baseline_priority_score < actionable_threshold
    )
    left_actionable = bool(
        active_priority_score is not None
        and baseline_priority_score is not None
        and baseline_priority_score >= actionable_threshold
        and active_priority_score < actionable_threshold
    )

    highlights: list[str] = []
    if base_row.get("change_type") == "new":
        highlights.append("NEW_URL")
    if base_row.get("change_type") == "missing":
        highlights.append("MISSING_URL")
    if new_opportunity_types:
        highlights.append("NEW_OPPORTUNITY")
    if resolved_opportunity_types:
        highlights.append("RESOLVED_OPPORTUNITY")
    if _safe_int(base_row.get("delta_priority_score")) not in {None, 0}:
        highlights.append("PRIORITY_UP" if int(base_row["delta_priority_score"]) > 0 else "PRIORITY_DOWN")
    if entered_actionable:
        highlights.append("ENTERED_ACTIONABLE")
    if left_actionable:
        highlights.append("LEFT_ACTIONABLE")

    return {
        "url": base_row["url"],
        "normalized_url": base_row["normalized_url"],
        "active_page_id": base_row.get("target_page_id"),
        "baseline_page_id": base_row.get("baseline_page_id"),
        "change_type": base_row.get("change_type"),
        "highlights": highlights,
        "active_priority_score": active_priority_score,
        "baseline_priority_score": baseline_priority_score,
        "delta_priority_score": _safe_int(base_row.get("delta_priority_score")),
        "active_priority_level": base_row.get("target_priority_level"),
        "baseline_priority_level": base_row.get("baseline_priority_level"),
        "active_opportunity_count": int(base_row.get("target_opportunity_count") or 0),
        "baseline_opportunity_count": int(base_row.get("baseline_opportunity_count") or 0),
        "active_primary_opportunity_type": base_row.get("target_primary_opportunity_type"),
        "baseline_primary_opportunity_type": base_row.get("baseline_primary_opportunity_type"),
        "active_opportunity_types": active_opportunity_types,
        "baseline_opportunity_types": baseline_opportunity_types,
        "new_opportunity_types": new_opportunity_types,
        "resolved_opportunity_types": resolved_opportunity_types,
        "entered_actionable": entered_actionable,
        "left_actionable": left_actionable,
        "change_rationale": _build_opportunities_compare_rationale(
            base_row=base_row,
            new_opportunity_types=new_opportunity_types,
            resolved_opportunity_types=resolved_opportunity_types,
            entered_actionable=entered_actionable,
            left_actionable=left_actionable,
        ),
    }


def _build_opportunities_compare_summary(rows: list[dict[str, Any]], *, actionable_threshold: int) -> dict[str, Any]:
    return {
        "total_urls": len(rows),
        "active_urls_with_opportunities": sum(1 for row in rows if int(row.get("active_opportunity_count") or 0) > 0),
        "active_actionable_urls": sum(1 for row in rows if (row.get("active_priority_score") or 0) >= actionable_threshold),
        "new_opportunity_urls": sum(1 for row in rows if "NEW_OPPORTUNITY" in (row.get("highlights") or [])),
        "resolved_opportunity_urls": sum(1 for row in rows if "RESOLVED_OPPORTUNITY" in (row.get("highlights") or [])),
        "priority_up_urls": sum(1 for row in rows if "PRIORITY_UP" in (row.get("highlights") or [])),
        "priority_down_urls": sum(1 for row in rows if "PRIORITY_DOWN" in (row.get("highlights") or [])),
        "entered_actionable_urls": sum(1 for row in rows if bool(row.get("entered_actionable"))),
        "left_actionable_urls": sum(1 for row in rows if bool(row.get("left_actionable"))),
    }


def _filter_opportunities_compare_rows(
    rows: list[dict[str, Any]],
    *,
    change_kind: str | None,
    opportunity_type: str | None,
    url_contains: str | None,
) -> list[dict[str, Any]]:
    filtered = rows
    if _normalize_filter_tokens(change_kind, mode="upper"):
        filtered = [row for row in filtered if _row_contains_any_token(list(row.get("highlights") or []), change_kind)]
    if _normalize_filter_tokens(opportunity_type, mode="upper"):
        filtered = [
            row
            for row in filtered
            if _row_contains_any_token(list(row.get("active_opportunity_types") or []), opportunity_type)
            or _row_contains_any_token(list(row.get("baseline_opportunity_types") or []), opportunity_type)
            or _row_contains_any_token(list(row.get("new_opportunity_types") or []), opportunity_type)
            or _row_contains_any_token(list(row.get("resolved_opportunity_types") or []), opportunity_type)
        ]
    filtered = _apply_url_contains_filter(filtered, url_contains=url_contains)
    return filtered


def _empty_opportunities_compare_summary() -> dict[str, int]:
    return {
        "total_urls": 0,
        "active_urls_with_opportunities": 0,
        "active_actionable_urls": 0,
        "new_opportunity_urls": 0,
        "resolved_opportunity_urls": 0,
        "priority_up_urls": 0,
        "priority_down_urls": 0,
        "entered_actionable_urls": 0,
        "left_actionable_urls": 0,
    }


def _build_opportunities_compare_rationale(
    *,
    base_row: dict[str, Any],
    new_opportunity_types: list[str],
    resolved_opportunity_types: list[str],
    entered_actionable: bool,
    left_actionable: bool,
) -> str:
    clauses: list[str] = []
    if new_opportunity_types:
        clauses.append(f"new opportunities: {', '.join(new_opportunity_types[:2])}")
    if resolved_opportunity_types and len(clauses) < 2:
        clauses.append(f"resolved opportunities: {', '.join(resolved_opportunity_types[:2])}")
    if entered_actionable and len(clauses) < 2:
        clauses.append("entered the actionable priority band")
    if left_actionable and len(clauses) < 2:
        clauses.append("fell out of the actionable priority band")
    delta_priority_score = _safe_int(base_row.get("delta_priority_score"))
    if delta_priority_score not in {None, 0} and len(clauses) < 2:
        direction = "up" if int(delta_priority_score) > 0 else "down"
        clauses.append(f"priority score {direction} by {abs(int(delta_priority_score))}")
    if not clauses:
        return str(base_row.get("change_rationale") or "no material opportunity change detected")
    if len(clauses) == 1:
        return clauses[0]
    return f"{clauses[0]} and {clauses[1]}"


def build_site_internal_linking_compare(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
    baseline_crawl_id: int | None = None,
    gsc_date_range: str = "last_28_days",
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "delta_internal_linking_score",
    sort_order: str = "desc",
    change_type: str | None = None,
    compare_kind: str | None = None,
    issue_type: str | None = None,
    url_contains: str | None = None,
) -> dict[str, Any]:
    context = _resolve_compare_context(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
        baseline_crawl_id=baseline_crawl_id,
    )
    if not context.compare_available:
        return {
            "context": _serialize_context(context),
            "gsc_date_range": gsc_date_range,
            "summary": _empty_internal_linking_compare_summary(),
            "items": [],
            "page": page,
            "page_size": page_size,
            "total_items": 0,
            "total_pages": 0,
        }

    active_rows = {
        str(row.get("normalized_url") or row.get("url") or ""): row
        for row in internal_linking_service.get_all_internal_linking_rows(
            session,
            context.active_crawl.id,
            gsc_date_range=gsc_date_range,
            sort_by="url",
            sort_order="asc",
        )
        if row.get("normalized_url") or row.get("url")
    }
    baseline_rows = {
        str(row.get("normalized_url") or row.get("url") or ""): row
        for row in internal_linking_service.get_all_internal_linking_rows(
            session,
            context.baseline_crawl.id,
            gsc_date_range=gsc_date_range,
            sort_by="url",
            sort_order="asc",
        )
        if row.get("normalized_url") or row.get("url")
    }
    rows = [
        _build_internal_linking_compare_row(
            baseline_row=baseline_rows.get(normalized_url),
            active_row=active_rows.get(normalized_url),
        )
        for normalized_url in sorted({*baseline_rows.keys(), *active_rows.keys()})
    ]
    summary = _build_internal_linking_compare_summary(rows)
    filtered = _filter_internal_linking_compare_rows(
        rows,
        change_type=change_type,
        compare_kind=compare_kind,
        issue_type=issue_type,
        url_contains=url_contains,
    )
    _sort_records(
        filtered,
        sort_by=sort_by,
        sort_order=sort_order,
        custom_order=trends_service.CRAWL_CHANGE_TYPE_ORDER if sort_by == "change_type" else None,
    )
    paginated_items, total_items, total_pages = _paginate_records(filtered, page=page, page_size=page_size)

    return {
        "context": _serialize_context(context),
        "gsc_date_range": gsc_date_range,
        "summary": summary,
        "items": paginated_items,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def _build_internal_linking_compare_row(
    *,
    baseline_row: dict[str, Any] | None,
    active_row: dict[str, Any] | None,
) -> dict[str, Any]:
    if baseline_row is None and active_row is None:  # pragma: no cover - guarded by caller
        raise SiteCompareServiceError("Cannot compare an empty internal linking row.")

    reference_row = active_row or baseline_row or {}
    url = str(reference_row.get("url") or reference_row.get("normalized_url") or "")
    normalized_url = str(reference_row.get("normalized_url") or url)
    new_in_active = baseline_row is None and active_row is not None
    missing_in_active = baseline_row is not None and active_row is None
    active_issue_types = list(active_row.get("issue_types") or []) if active_row else []
    baseline_issue_types = list(baseline_row.get("issue_types") or []) if baseline_row else []
    new_issue_types = sorted(set(active_issue_types) - set(baseline_issue_types))
    resolved_issue_types = sorted(set(baseline_issue_types) - set(active_issue_types))
    delta_internal_linking_score = _delta_optional_int(
        _record_value(active_row, "internal_linking_score"),
        _record_value(baseline_row, "internal_linking_score"),
    )
    delta_link_equity_score = _delta_optional_float(
        _record_value(active_row, "link_equity_score"),
        _record_value(baseline_row, "link_equity_score"),
    )
    delta_incoming_follow_linking_pages = _delta_optional_int(
        _record_value(active_row, "incoming_follow_linking_pages"),
        _record_value(baseline_row, "incoming_follow_linking_pages"),
    )
    delta_anchor_diversity_score = _delta_optional_float(
        _record_value(active_row, "anchor_diversity_score"),
        _record_value(baseline_row, "anchor_diversity_score"),
    )
    delta_boilerplate_like_share = _delta_optional_float(
        _record_value(active_row, "boilerplate_like_share"),
        _record_value(baseline_row, "boilerplate_like_share"),
    )

    highlights: list[str] = []
    if _is_flag_enabled(active_row, "orphan_like") and not _is_flag_enabled(baseline_row, "orphan_like"):
        highlights.append("NEW_ORPHAN_LIKE")
    if _is_flag_enabled(baseline_row, "orphan_like") and not _is_flag_enabled(active_row, "orphan_like"):
        highlights.append("RESOLVED_ORPHAN_LIKE")
    if _is_flag_enabled(active_row, "weakly_linked_important") and not _is_flag_enabled(baseline_row, "weakly_linked_important"):
        highlights.append("WEAKLY_LINKED_WORSENED")
    if _is_flag_enabled(baseline_row, "weakly_linked_important") and not _is_flag_enabled(active_row, "weakly_linked_important"):
        highlights.append("WEAKLY_LINKED_IMPROVED")
    if delta_link_equity_score is not None:
        if delta_link_equity_score >= INTERNAL_LINKING_EQUITY_THRESHOLD:
            highlights.append("LINK_EQUITY_IMPROVED")
        elif delta_link_equity_score <= -INTERNAL_LINKING_EQUITY_THRESHOLD:
            highlights.append("LINK_EQUITY_WORSENED")
    if delta_incoming_follow_linking_pages is not None:
        if delta_incoming_follow_linking_pages >= INTERNAL_LINKING_PAGES_THRESHOLD:
            highlights.append("LINKING_PAGES_UP")
        elif delta_incoming_follow_linking_pages <= -INTERNAL_LINKING_PAGES_THRESHOLD:
            highlights.append("LINKING_PAGES_DOWN")
    if delta_anchor_diversity_score is not None:
        if delta_anchor_diversity_score >= INTERNAL_LINKING_ANCHOR_THRESHOLD:
            highlights.append("ANCHOR_DIVERSITY_IMPROVED")
        elif delta_anchor_diversity_score <= -INTERNAL_LINKING_ANCHOR_THRESHOLD:
            highlights.append("ANCHOR_DIVERSITY_WORSENED")
    if delta_boilerplate_like_share is not None:
        if delta_boilerplate_like_share <= -INTERNAL_LINKING_BOILERPLATE_THRESHOLD:
            highlights.append("BOILERPLATE_IMPROVED")
        elif delta_boilerplate_like_share >= INTERNAL_LINKING_BOILERPLATE_THRESHOLD:
            highlights.append("BOILERPLATE_WORSENED")

    change_type_value = _classify_internal_linking_change_type(
        new_in_active=new_in_active,
        missing_in_active=missing_in_active,
        new_issue_types=new_issue_types,
        resolved_issue_types=resolved_issue_types,
        highlights=highlights,
    )

    return {
        "url": url,
        "normalized_url": normalized_url,
        "active_page_id": _record_value(active_row, "page_id"),
        "baseline_page_id": _record_value(baseline_row, "page_id"),
        "change_type": change_type_value,
        "highlights": highlights,
        "active_issue_types": active_issue_types,
        "baseline_issue_types": baseline_issue_types,
        "new_issue_types": new_issue_types,
        "resolved_issue_types": resolved_issue_types,
        "active_internal_linking_score": _record_value(active_row, "internal_linking_score"),
        "baseline_internal_linking_score": _record_value(baseline_row, "internal_linking_score"),
        "delta_internal_linking_score": delta_internal_linking_score,
        "active_link_equity_score": _record_value(active_row, "link_equity_score"),
        "baseline_link_equity_score": _record_value(baseline_row, "link_equity_score"),
        "delta_link_equity_score": delta_link_equity_score,
        "active_incoming_follow_linking_pages": _record_value(active_row, "incoming_follow_linking_pages"),
        "baseline_incoming_follow_linking_pages": _record_value(baseline_row, "incoming_follow_linking_pages"),
        "delta_incoming_follow_linking_pages": delta_incoming_follow_linking_pages,
        "active_anchor_diversity_score": _record_value(active_row, "anchor_diversity_score"),
        "baseline_anchor_diversity_score": _record_value(baseline_row, "anchor_diversity_score"),
        "delta_anchor_diversity_score": delta_anchor_diversity_score,
        "active_boilerplate_like_share": _record_value(active_row, "boilerplate_like_share"),
        "baseline_boilerplate_like_share": _record_value(baseline_row, "boilerplate_like_share"),
        "delta_boilerplate_like_share": delta_boilerplate_like_share,
        "active_orphan_like": _record_value(active_row, "orphan_like"),
        "baseline_orphan_like": _record_value(baseline_row, "orphan_like"),
        "active_weakly_linked_important": _record_value(active_row, "weakly_linked_important"),
        "baseline_weakly_linked_important": _record_value(baseline_row, "weakly_linked_important"),
        "change_rationale": _build_internal_linking_compare_rationale(
            change_type=change_type_value,
            new_issue_types=new_issue_types,
            resolved_issue_types=resolved_issue_types,
            highlights=highlights,
            delta_link_equity_score=delta_link_equity_score,
            delta_incoming_follow_linking_pages=delta_incoming_follow_linking_pages,
            delta_anchor_diversity_score=delta_anchor_diversity_score,
            delta_boilerplate_like_share=delta_boilerplate_like_share,
        ),
    }


def _build_internal_linking_compare_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_urls": len(rows),
        "issue_urls_in_active": sum(1 for row in rows if row.get("active_issue_types")),
        "new_orphan_like_urls": sum(1 for row in rows if "NEW_ORPHAN_LIKE" in (row.get("highlights") or [])),
        "resolved_orphan_like_urls": sum(1 for row in rows if "RESOLVED_ORPHAN_LIKE" in (row.get("highlights") or [])),
        "weakly_linked_improved_urls": sum(1 for row in rows if "WEAKLY_LINKED_IMPROVED" in (row.get("highlights") or [])),
        "weakly_linked_worsened_urls": sum(1 for row in rows if "WEAKLY_LINKED_WORSENED" in (row.get("highlights") or [])),
        "link_equity_improved_urls": sum(1 for row in rows if "LINK_EQUITY_IMPROVED" in (row.get("highlights") or [])),
        "link_equity_worsened_urls": sum(1 for row in rows if "LINK_EQUITY_WORSENED" in (row.get("highlights") or [])),
        "linking_pages_up_urls": sum(1 for row in rows if "LINKING_PAGES_UP" in (row.get("highlights") or [])),
        "linking_pages_down_urls": sum(1 for row in rows if "LINKING_PAGES_DOWN" in (row.get("highlights") or [])),
        "anchor_diversity_improved_urls": sum(1 for row in rows if "ANCHOR_DIVERSITY_IMPROVED" in (row.get("highlights") or [])),
        "anchor_diversity_worsened_urls": sum(1 for row in rows if "ANCHOR_DIVERSITY_WORSENED" in (row.get("highlights") or [])),
        "boilerplate_improved_urls": sum(1 for row in rows if "BOILERPLATE_IMPROVED" in (row.get("highlights") or [])),
        "boilerplate_worsened_urls": sum(1 for row in rows if "BOILERPLATE_WORSENED" in (row.get("highlights") or [])),
    }


def _filter_internal_linking_compare_rows(
    rows: list[dict[str, Any]],
    *,
    change_type: str | None,
    compare_kind: str | None,
    issue_type: str | None,
    url_contains: str | None,
) -> list[dict[str, Any]]:
    filtered = rows
    if _normalize_filter_tokens(change_type):
        filtered = [
            row for row in filtered if str(row.get("change_type") or "").lower() in _normalize_filter_tokens(change_type)
        ]
    if _normalize_filter_tokens(compare_kind, mode="upper"):
        filtered = [row for row in filtered if _row_contains_any_token(list(row.get("highlights") or []), compare_kind)]
    if _normalize_filter_tokens(issue_type, mode="upper"):
        filtered = [
            row
            for row in filtered
            if _row_contains_any_token(list(row.get("active_issue_types") or []), issue_type)
            or _row_contains_any_token(list(row.get("baseline_issue_types") or []), issue_type)
            or _row_contains_any_token(list(row.get("new_issue_types") or []), issue_type)
            or _row_contains_any_token(list(row.get("resolved_issue_types") or []), issue_type)
        ]
    filtered = _apply_url_contains_filter(filtered, url_contains=url_contains)
    return filtered


def _empty_internal_linking_compare_summary() -> dict[str, int]:
    return {
        "total_urls": 0,
        "issue_urls_in_active": 0,
        "new_orphan_like_urls": 0,
        "resolved_orphan_like_urls": 0,
        "weakly_linked_improved_urls": 0,
        "weakly_linked_worsened_urls": 0,
        "link_equity_improved_urls": 0,
        "link_equity_worsened_urls": 0,
        "linking_pages_up_urls": 0,
        "linking_pages_down_urls": 0,
        "anchor_diversity_improved_urls": 0,
        "anchor_diversity_worsened_urls": 0,
        "boilerplate_improved_urls": 0,
        "boilerplate_worsened_urls": 0,
    }


def _classify_internal_linking_change_type(
    *,
    new_in_active: bool,
    missing_in_active: bool,
    new_issue_types: list[str],
    resolved_issue_types: list[str],
    highlights: list[str],
) -> str:
    if new_in_active:
        return "new"
    if missing_in_active:
        return "missing"
    worsening_highlights = {
        "NEW_ORPHAN_LIKE",
        "WEAKLY_LINKED_WORSENED",
        "LINK_EQUITY_WORSENED",
        "LINKING_PAGES_DOWN",
        "ANCHOR_DIVERSITY_WORSENED",
        "BOILERPLATE_WORSENED",
    }
    improvement_highlights = {
        "RESOLVED_ORPHAN_LIKE",
        "WEAKLY_LINKED_IMPROVED",
        "LINK_EQUITY_IMPROVED",
        "LINKING_PAGES_UP",
        "ANCHOR_DIVERSITY_IMPROVED",
        "BOILERPLATE_IMPROVED",
    }
    score = 0
    score += len(resolved_issue_types) * 2
    score -= len(new_issue_types) * 2
    score += sum(1 for item in highlights if item in improvement_highlights)
    score -= sum(1 for item in highlights if item in worsening_highlights)
    if score > 0:
        return "improved"
    if score < 0:
        return "worsened"
    return "unchanged"


def _build_internal_linking_compare_rationale(
    *,
    change_type: str,
    new_issue_types: list[str],
    resolved_issue_types: list[str],
    highlights: list[str],
    delta_link_equity_score: float | None,
    delta_incoming_follow_linking_pages: int | None,
    delta_anchor_diversity_score: float | None,
    delta_boilerplate_like_share: float | None,
) -> str:
    if change_type == "new":
        return "new URL entered the active crawl"
    if change_type == "missing":
        return "URL disappeared from the active crawl"

    clauses: list[str] = []
    if resolved_issue_types:
        clauses.append(f"resolved {resolved_issue_types[0]}")
    if new_issue_types and len(clauses) < 2:
        clauses.append(f"new {new_issue_types[0]}")
    if "LINK_EQUITY_IMPROVED" in highlights and delta_link_equity_score is not None and len(clauses) < 2:
        clauses.append(f"link equity up by {delta_link_equity_score:.1f}")
    if "LINK_EQUITY_WORSENED" in highlights and delta_link_equity_score is not None and len(clauses) < 2:
        clauses.append(f"link equity down by {abs(delta_link_equity_score):.1f}")
    if "LINKING_PAGES_UP" in highlights and delta_incoming_follow_linking_pages is not None and len(clauses) < 2:
        clauses.append(f"gained {delta_incoming_follow_linking_pages} linking pages")
    if "LINKING_PAGES_DOWN" in highlights and delta_incoming_follow_linking_pages is not None and len(clauses) < 2:
        clauses.append(f"lost {abs(delta_incoming_follow_linking_pages)} linking pages")
    if "ANCHOR_DIVERSITY_IMPROVED" in highlights and delta_anchor_diversity_score is not None and len(clauses) < 2:
        clauses.append(f"anchor diversity up by {delta_anchor_diversity_score:.1f}")
    if "ANCHOR_DIVERSITY_WORSENED" in highlights and delta_anchor_diversity_score is not None and len(clauses) < 2:
        clauses.append(f"anchor diversity down by {abs(delta_anchor_diversity_score):.1f}")
    if "BOILERPLATE_IMPROVED" in highlights and delta_boilerplate_like_share is not None and len(clauses) < 2:
        clauses.append(f"boilerplate share down by {abs(delta_boilerplate_like_share) * 100:.1f}pp")
    if "BOILERPLATE_WORSENED" in highlights and delta_boilerplate_like_share is not None and len(clauses) < 2:
        clauses.append(f"boilerplate share up by {abs(delta_boilerplate_like_share) * 100:.1f}pp")
    if not clauses:
        return "no material internal linking change detected"
    if len(clauses) == 1:
        return clauses[0]
    return f"{clauses[0]} and {clauses[1]}"
