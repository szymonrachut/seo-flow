from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CrawlJob, Site
from app.services import crawl_job_service
from app.services.trend_rules import TrendRules, get_trend_rules

GSC_DATE_RANGE_SUFFIX = {
    "last_28_days": "28d",
    "last_90_days": "90d",
}
AVAILABLE_GSC_RANGES = tuple(GSC_DATE_RANGE_SUFFIX.keys())
CRAWL_CHANGE_TYPE_ORDER: dict[str, int] = {
    "worsened": 4,
    "new": 3,
    "improved": 2,
    "missing": 1,
    "unchanged": 0,
}
METRIC_TREND_ORDER: dict[str, int] = {
    "improved": 2,
    "flat": 1,
    "worsened": 0,
}
ISSUE_LABELS = {
    "title_missing": "missing title",
    "title_too_short": "title too short",
    "title_too_long": "title too long",
    "meta_description_missing": "missing meta description",
    "meta_description_too_short": "meta description too short",
    "meta_description_too_long": "meta description too long",
    "h1_missing": "missing H1",
    "multiple_h1": "multiple H1",
    "missing_h2": "missing H2",
    "canonical_missing": "missing canonical",
    "canonical_to_other_url": "canonical issue",
    "canonical_to_non_200": "canonical points to non-200",
    "canonical_to_redirect": "canonical points to redirect",
    "noindex_like": "noindex_like",
    "non_indexable_like": "non_indexable_like",
    "thin_content": "thin content",
    "duplicate_content": "duplicate content",
    "missing_alt_images": "missing alt images",
    "oversized": "oversized page",
}


class TrendsServiceError(RuntimeError):
    pass


def build_trends_overview(session: Session, target_job_id: int) -> dict[str, Any]:
    target_job = _get_crawl_job_or_raise(session, target_job_id)
    site = _get_site_or_raise(session, target_job.site_id)
    candidates = session.scalars(
        select(CrawlJob)
        .where(CrawlJob.site_id == target_job.site_id, CrawlJob.id != target_job.id)
        .order_by(CrawlJob.created_at.desc(), CrawlJob.id.desc())
    ).all()

    default_baseline_job_id = None
    older_candidates = [job for job in candidates if job.created_at <= target_job.created_at]
    if older_candidates:
        default_baseline_job_id = older_candidates[0].id
    elif candidates:
        default_baseline_job_id = candidates[0].id

    return {
        "crawl_job_id": target_job.id,
        "site_id": site.id,
        "site_domain": site.domain,
        "default_baseline_job_id": default_baseline_job_id,
        "baseline_candidates": [_serialize_job_option(job, site) for job in candidates],
        "available_gsc_ranges": list(AVAILABLE_GSC_RANGES),
    }


def build_crawl_compare(
    session: Session,
    target_job_id: int,
    *,
    baseline_job_id: int,
    gsc_date_range: str = "last_28_days",
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "delta_priority_score",
    sort_order: str = "desc",
    change_type: str | None = None,
    resolved_issues_min: int | None = None,
    added_issues_min: int | None = None,
    url_contains: str | None = None,
    rules: TrendRules | None = None,
) -> dict[str, Any]:
    resolved_rules = rules or get_trend_rules()
    baseline_job, target_job, site = _load_same_site_compare_jobs(
        session,
        baseline_job_id=baseline_job_id,
        target_job_id=target_job_id,
    )
    baseline_records = _load_page_record_lookup(session, baseline_job.id, gsc_date_range=gsc_date_range)
    target_records = _load_page_record_lookup(session, target_job.id, gsc_date_range=gsc_date_range)

    items = [
        _build_crawl_compare_row(
            baseline_record=baseline_records.get(normalized_url),
            target_record=target_records.get(normalized_url),
            rules=resolved_rules,
        )
        for normalized_url in sorted({*baseline_records.keys(), *target_records.keys()})
    ]
    summary = _build_crawl_compare_summary(
        items,
        baseline_job_id=baseline_job.id,
        target_job_id=target_job.id,
        gsc_date_range=gsc_date_range,
    )
    filtered = _filter_crawl_compare_rows(
        items,
        change_type=change_type,
        resolved_issues_min=resolved_issues_min,
        added_issues_min=added_issues_min,
        url_contains=url_contains,
    )
    _sort_records(filtered, sort_by=sort_by, sort_order=sort_order, custom_order=CRAWL_CHANGE_TYPE_ORDER)
    paginated_items, total_items, total_pages = _paginate_records(filtered, page=page, page_size=page_size)

    return {
        "baseline_job": _serialize_job_option(baseline_job, site),
        "target_job": _serialize_job_option(target_job, site),
        "summary": summary,
        "items": paginated_items,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def get_all_crawl_compare_rows(
    session: Session,
    target_job_id: int,
    *,
    baseline_job_id: int,
    gsc_date_range: str = "last_28_days",
    sort_by: str = "delta_priority_score",
    sort_order: str = "desc",
    change_type: str | None = None,
    resolved_issues_min: int | None = None,
    added_issues_min: int | None = None,
    url_contains: str | None = None,
    rules: TrendRules | None = None,
) -> list[dict[str, Any]]:
    resolved_rules = rules or get_trend_rules()
    baseline_job, target_job, _ = _load_same_site_compare_jobs(
        session,
        baseline_job_id=baseline_job_id,
        target_job_id=target_job_id,
    )
    baseline_records = _load_page_record_lookup(session, baseline_job.id, gsc_date_range=gsc_date_range)
    target_records = _load_page_record_lookup(session, target_job.id, gsc_date_range=gsc_date_range)
    rows = [
        _build_crawl_compare_row(
            baseline_record=baseline_records.get(normalized_url),
            target_record=target_records.get(normalized_url),
            rules=resolved_rules,
        )
        for normalized_url in sorted({*baseline_records.keys(), *target_records.keys()})
    ]
    filtered = _filter_crawl_compare_rows(
        rows,
        change_type=change_type,
        resolved_issues_min=resolved_issues_min,
        added_issues_min=added_issues_min,
        url_contains=url_contains,
    )
    _sort_records(filtered, sort_by=sort_by, sort_order=sort_order, custom_order=CRAWL_CHANGE_TYPE_ORDER)
    return filtered


def build_gsc_compare(
    session: Session,
    crawl_job_id: int,
    *,
    baseline_gsc_range: str = "last_90_days",
    target_gsc_range: str = "last_28_days",
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "delta_clicks",
    sort_order: str = "desc",
    trend: str | None = None,
    clicks_trend: str | None = None,
    impressions_trend: str | None = None,
    ctr_trend: str | None = None,
    position_trend: str | None = None,
    top_queries_trend: str | None = None,
    url_contains: str | None = None,
    rules: TrendRules | None = None,
) -> dict[str, Any]:
    resolved_rules = rules or get_trend_rules()
    rows = get_all_gsc_compare_rows(
        session,
        crawl_job_id,
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
        rules=resolved_rules,
    )
    all_rows = _build_all_gsc_compare_rows(
        session,
        crawl_job_id,
        baseline_gsc_range=baseline_gsc_range,
        target_gsc_range=target_gsc_range,
        rules=resolved_rules,
    )
    summary = _build_gsc_compare_summary(
        all_rows,
        crawl_job_id=crawl_job_id,
        baseline_gsc_range=baseline_gsc_range,
        target_gsc_range=target_gsc_range,
        rules=resolved_rules,
    )
    paginated_items, total_items, total_pages = _paginate_records(rows, page=page, page_size=page_size)
    return {
        "summary": summary,
        "items": paginated_items,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def get_all_gsc_compare_rows(
    session: Session,
    crawl_job_id: int,
    *,
    baseline_gsc_range: str = "last_90_days",
    target_gsc_range: str = "last_28_days",
    sort_by: str = "delta_clicks",
    sort_order: str = "desc",
    trend: str | None = None,
    clicks_trend: str | None = None,
    impressions_trend: str | None = None,
    ctr_trend: str | None = None,
    position_trend: str | None = None,
    top_queries_trend: str | None = None,
    url_contains: str | None = None,
    rules: TrendRules | None = None,
) -> list[dict[str, Any]]:
    resolved_rules = rules or get_trend_rules()
    rows = _build_all_gsc_compare_rows(
        session,
        crawl_job_id,
        baseline_gsc_range=baseline_gsc_range,
        target_gsc_range=target_gsc_range,
        rules=resolved_rules,
    )
    filtered = _filter_gsc_compare_rows(
        rows,
        trend=trend,
        clicks_trend=clicks_trend,
        impressions_trend=impressions_trend,
        ctr_trend=ctr_trend,
        position_trend=position_trend,
        top_queries_trend=top_queries_trend,
        url_contains=url_contains,
    )
    _sort_records(filtered, sort_by=sort_by, sort_order=sort_order, custom_order=METRIC_TREND_ORDER)
    return filtered


def _build_all_gsc_compare_rows(
    session: Session,
    crawl_job_id: int,
    *,
    baseline_gsc_range: str,
    target_gsc_range: str,
    rules: TrendRules,
) -> list[dict[str, Any]]:
    _get_crawl_job_or_raise(session, crawl_job_id)
    records = crawl_job_service.get_all_pages_for_job(
        session,
        crawl_job_id,
        sort_by="url",
        sort_order="asc",
        gsc_date_range=target_gsc_range,
    )
    baseline_suffix = _resolve_gsc_suffix(baseline_gsc_range)
    target_suffix = _resolve_gsc_suffix(target_gsc_range)

    rows: list[dict[str, Any]] = []
    for record in records:
        baseline_metrics = _extract_gsc_metrics(record, baseline_suffix)
        target_metrics = _extract_gsc_metrics(record, target_suffix)
        if not baseline_metrics["has_data"] and not target_metrics["has_data"]:
            continue

        clicks_trend = _classify_numeric_trend(
            baseline_metrics["clicks"],
            target_metrics["clicks"],
            rules.gsc_clicks_flat_threshold,
        )
        impressions_trend = _classify_numeric_trend(
            baseline_metrics["impressions"],
            target_metrics["impressions"],
            rules.gsc_impressions_flat_threshold,
        )
        ctr_trend = _classify_numeric_trend(
            baseline_metrics["ctr"],
            target_metrics["ctr"],
            rules.gsc_ctr_flat_threshold,
        )
        position_trend = _classify_position_trend(
            baseline_metrics["position"],
            target_metrics["position"],
            rules.gsc_position_flat_threshold,
        )
        top_queries_trend = _classify_numeric_trend(
            baseline_metrics["top_queries_count"],
            target_metrics["top_queries_count"],
            rules.gsc_top_queries_flat_threshold,
        )
        overall_trend = _classify_gsc_overall_trend(
            clicks_trend=clicks_trend,
            impressions_trend=impressions_trend,
            ctr_trend=ctr_trend,
            position_trend=position_trend,
            top_queries_trend=top_queries_trend,
            rules=rules,
        )

        rows.append(
            {
                "page_id": int(record["id"]),
                "url": record["url"],
                "normalized_url": record["normalized_url"],
                "has_baseline_data": baseline_metrics["has_data"],
                "has_target_data": target_metrics["has_data"],
                "baseline_clicks": baseline_metrics["clicks"],
                "target_clicks": target_metrics["clicks"],
                "delta_clicks": target_metrics["clicks"] - baseline_metrics["clicks"],
                "baseline_impressions": baseline_metrics["impressions"],
                "target_impressions": target_metrics["impressions"],
                "delta_impressions": target_metrics["impressions"] - baseline_metrics["impressions"],
                "baseline_ctr": baseline_metrics["ctr"],
                "target_ctr": target_metrics["ctr"],
                "delta_ctr": target_metrics["ctr"] - baseline_metrics["ctr"],
                "baseline_position": baseline_metrics["position"],
                "target_position": target_metrics["position"],
                "delta_position": _delta_optional_float(target_metrics["position"], baseline_metrics["position"]),
                "baseline_top_queries_count": baseline_metrics["top_queries_count"],
                "target_top_queries_count": target_metrics["top_queries_count"],
                "delta_top_queries_count": target_metrics["top_queries_count"] - baseline_metrics["top_queries_count"],
                "overall_trend": overall_trend,
                "clicks_trend": clicks_trend,
                "impressions_trend": impressions_trend,
                "ctr_trend": ctr_trend,
                "position_trend": position_trend,
                "top_queries_trend": top_queries_trend,
                "rationale": _build_gsc_rationale(
                    baseline_metrics=baseline_metrics,
                    target_metrics=target_metrics,
                    clicks_trend=clicks_trend,
                    impressions_trend=impressions_trend,
                    ctr_trend=ctr_trend,
                    position_trend=position_trend,
                    top_queries_trend=top_queries_trend,
                ),
                "has_technical_issue": bool(record.get("has_technical_issue")),
                "priority_score": int(record.get("priority_score") or 0),
                "priority_level": record.get("priority_level") or "low",
                "primary_opportunity_type": record.get("primary_opportunity_type"),
            }
        )

    return rows


def _build_crawl_compare_summary(
    rows: list[dict[str, Any]],
    *,
    baseline_job_id: int,
    target_job_id: int,
    gsc_date_range: str,
) -> dict[str, Any]:
    return {
        "baseline_job_id": baseline_job_id,
        "target_job_id": target_job_id,
        "gsc_date_range": gsc_date_range,
        "shared_urls": sum(1 for row in rows if row["present_in_both"]),
        "new_urls": sum(1 for row in rows if row["change_type"] == "new"),
        "missing_urls": sum(1 for row in rows if row["change_type"] == "missing"),
        "improved_urls": sum(1 for row in rows if row["change_type"] == "improved"),
        "worsened_urls": sum(1 for row in rows if row["change_type"] == "worsened"),
        "unchanged_urls": sum(1 for row in rows if row["change_type"] == "unchanged"),
        "resolved_issues_total": sum(int(row.get("issues_resolved_count") or 0) for row in rows),
        "added_issues_total": sum(int(row.get("issues_added_count") or 0) for row in rows),
    }


def _build_gsc_compare_summary(
    rows: list[dict[str, Any]],
    *,
    crawl_job_id: int,
    baseline_gsc_range: str,
    target_gsc_range: str,
    rules: TrendRules,
) -> dict[str, Any]:
    baseline_clicks = sum(int(row["baseline_clicks"]) for row in rows)
    target_clicks = sum(int(row["target_clicks"]) for row in rows)
    baseline_impressions = sum(int(row["baseline_impressions"]) for row in rows)
    target_impressions = sum(int(row["target_impressions"]) for row in rows)
    baseline_top_queries_count = sum(int(row["baseline_top_queries_count"]) for row in rows)
    target_top_queries_count = sum(int(row["target_top_queries_count"]) for row in rows)
    baseline_position = _weighted_average_position(
        rows,
        key="baseline_position",
        impressions_key="baseline_impressions",
        rules=rules,
    )
    target_position = _weighted_average_position(
        rows,
        key="target_position",
        impressions_key="target_impressions",
        rules=rules,
    )

    return {
        "crawl_job_id": crawl_job_id,
        "baseline_gsc_range": baseline_gsc_range,
        "target_gsc_range": target_gsc_range,
        "baseline": {
            "clicks": baseline_clicks,
            "impressions": baseline_impressions,
            "ctr": _safe_ctr(baseline_clicks, baseline_impressions),
            "position": baseline_position,
            "top_queries_count": baseline_top_queries_count,
        },
        "target": {
            "clicks": target_clicks,
            "impressions": target_impressions,
            "ctr": _safe_ctr(target_clicks, target_impressions),
            "position": target_position,
            "top_queries_count": target_top_queries_count,
        },
        "delta_clicks": target_clicks - baseline_clicks,
        "delta_impressions": target_impressions - baseline_impressions,
        "delta_ctr": _safe_ctr(target_clicks, target_impressions) - _safe_ctr(baseline_clicks, baseline_impressions),
        "delta_position": _delta_optional_float(target_position, baseline_position),
        "delta_top_queries_count": target_top_queries_count - baseline_top_queries_count,
        "improved_urls": sum(1 for row in rows if row["overall_trend"] == "improved"),
        "worsened_urls": sum(1 for row in rows if row["overall_trend"] == "worsened"),
        "flat_urls": sum(1 for row in rows if row["overall_trend"] == "flat"),
    }


def _build_crawl_compare_row(
    *,
    baseline_record: dict[str, Any] | None,
    target_record: dict[str, Any] | None,
    rules: TrendRules,
) -> dict[str, Any]:
    if baseline_record is None and target_record is None:  # pragma: no cover - guarded by caller
        raise TrendsServiceError("Cannot compare an empty baseline and target row.")

    reference_record = target_record or baseline_record or {}
    url = str(reference_record.get("url") or reference_record.get("normalized_url") or "")
    normalized_url = str(reference_record.get("normalized_url") or url)
    new_in_target = baseline_record is None and target_record is not None
    missing_in_target = baseline_record is not None and target_record is None
    present_in_both = baseline_record is not None and target_record is not None
    status_code_changed = False
    title_changed = False
    meta_description_changed = False
    h1_changed = False
    canonical_url_changed = False
    noindex_like_changed = False
    changed_fields: list[str] = []

    if present_in_both:
        baseline_issue_keys = _collect_issue_keys(baseline_record, rules)
        target_issue_keys = _collect_issue_keys(target_record, rules)
        resolved_issues = _sorted_issue_labels(baseline_issue_keys - target_issue_keys, rules)
        added_issues = _sorted_issue_labels(target_issue_keys - baseline_issue_keys, rules)
        status_code_changed = _values_differ(baseline_record.get("status_code"), target_record.get("status_code"))
        title_changed = _values_differ(baseline_record.get("title"), target_record.get("title"), normalize_text=True)
        meta_description_changed = _values_differ(
            baseline_record.get("meta_description"),
            target_record.get("meta_description"),
            normalize_text=True,
        )
        h1_changed = _values_differ(baseline_record.get("h1"), target_record.get("h1"), normalize_text=True)
        canonical_url_changed = _values_differ(
            baseline_record.get("canonical_url"),
            target_record.get("canonical_url"),
            normalize_text=True,
        )
        noindex_like_changed = _values_differ(baseline_record.get("noindex_like"), target_record.get("noindex_like"))
        changed_fields = [
            field_name
            for field_name, is_changed in [
                ("status_code", status_code_changed),
                ("title", title_changed),
                ("meta_description", meta_description_changed),
                ("h1", h1_changed),
                ("canonical_url", canonical_url_changed),
                ("noindex_like", noindex_like_changed),
            ]
            if is_changed
        ]
        change_score = _crawl_change_score(
            baseline_record=baseline_record,
            target_record=target_record,
            resolved_issues=resolved_issues,
            added_issues=added_issues,
            rules=rules,
        )
        change_type = "improved" if change_score > 0 else "worsened" if change_score < 0 else "unchanged"
        issues_resolved_count = len(resolved_issues)
        issues_added_count = len(added_issues)
        change_rationale = _build_crawl_change_rationale(
            baseline_record=baseline_record,
            target_record=target_record,
            resolved_issues=resolved_issues,
            added_issues=added_issues,
            rules=rules,
        )
    elif new_in_target:
        resolved_issues = []
        added_issues = []
        change_type = "new"
        issues_resolved_count = 0
        issues_added_count = 0
        changed_fields = ["new_url"]
        change_rationale = "new URL discovered in target crawl"
    else:
        resolved_issues = []
        added_issues = []
        change_type = "missing"
        issues_resolved_count = 0
        issues_added_count = 0
        changed_fields = ["missing_url"]
        change_rationale = "URL missing in target crawl"

    return {
        "url": url,
        "normalized_url": normalized_url,
        "baseline_page_id": _optional_int(baseline_record.get("id")) if baseline_record else None,
        "target_page_id": _optional_int(target_record.get("id")) if target_record else None,
        "new_in_target": new_in_target,
        "missing_in_target": missing_in_target,
        "present_in_both": present_in_both,
        "change_type": change_type,
        "issues_resolved_count": issues_resolved_count,
        "issues_added_count": issues_added_count,
        "resolved_issues": resolved_issues,
        "added_issues": added_issues,
        "changed_fields": changed_fields,
        "change_rationale": change_rationale,
        "baseline_status_code": _record_value(baseline_record, "status_code"),
        "target_status_code": _record_value(target_record, "status_code"),
        "status_code_changed": status_code_changed,
        "baseline_title": _record_value(baseline_record, "title"),
        "target_title": _record_value(target_record, "title"),
        "title_changed": title_changed,
        "baseline_meta_description": _record_value(baseline_record, "meta_description"),
        "target_meta_description": _record_value(target_record, "meta_description"),
        "meta_description_changed": meta_description_changed,
        "baseline_h1": _record_value(baseline_record, "h1"),
        "target_h1": _record_value(target_record, "h1"),
        "h1_changed": h1_changed,
        "baseline_canonical_url": _record_value(baseline_record, "canonical_url"),
        "target_canonical_url": _record_value(target_record, "canonical_url"),
        "canonical_url_changed": canonical_url_changed,
        "baseline_noindex_like": _record_value(baseline_record, "noindex_like"),
        "target_noindex_like": _record_value(target_record, "noindex_like"),
        "noindex_like_changed": noindex_like_changed,
        "baseline_non_indexable_like": _record_value(baseline_record, "non_indexable_like"),
        "target_non_indexable_like": _record_value(target_record, "non_indexable_like"),
        "baseline_title_length": _record_value(baseline_record, "title_length"),
        "target_title_length": _record_value(target_record, "title_length"),
        "baseline_meta_description_length": _record_value(baseline_record, "meta_description_length"),
        "target_meta_description_length": _record_value(target_record, "meta_description_length"),
        "baseline_h1_count": _record_value(baseline_record, "h1_count"),
        "target_h1_count": _record_value(target_record, "h1_count"),
        "baseline_word_count": _record_value(baseline_record, "word_count"),
        "target_word_count": _record_value(target_record, "word_count"),
        "baseline_images_missing_alt_count": _record_value(baseline_record, "images_missing_alt_count"),
        "target_images_missing_alt_count": _record_value(target_record, "images_missing_alt_count"),
        "baseline_schema_count": _record_value(baseline_record, "schema_count"),
        "target_schema_count": _record_value(target_record, "schema_count"),
        "baseline_html_size_bytes": _record_value(baseline_record, "html_size_bytes"),
        "target_html_size_bytes": _record_value(target_record, "html_size_bytes"),
        "baseline_was_rendered": _record_value(baseline_record, "was_rendered"),
        "target_was_rendered": _record_value(target_record, "was_rendered"),
        "baseline_js_heavy_like": _record_value(baseline_record, "js_heavy_like"),
        "target_js_heavy_like": _record_value(target_record, "js_heavy_like"),
        "baseline_response_time_ms": _record_value(baseline_record, "response_time_ms"),
        "target_response_time_ms": _record_value(target_record, "response_time_ms"),
        "baseline_incoming_internal_links": _record_value(baseline_record, "incoming_internal_links"),
        "target_incoming_internal_links": _record_value(target_record, "incoming_internal_links"),
        "baseline_incoming_internal_linking_pages": _record_value(baseline_record, "incoming_internal_linking_pages"),
        "target_incoming_internal_linking_pages": _record_value(target_record, "incoming_internal_linking_pages"),
        "baseline_priority_score": _record_value(baseline_record, "priority_score"),
        "target_priority_score": _record_value(target_record, "priority_score"),
        "baseline_priority_level": _record_value(baseline_record, "priority_level"),
        "target_priority_level": _record_value(target_record, "priority_level"),
        "baseline_opportunity_count": _record_value(baseline_record, "opportunity_count"),
        "target_opportunity_count": _record_value(target_record, "opportunity_count"),
        "baseline_primary_opportunity_type": _record_value(baseline_record, "primary_opportunity_type"),
        "target_primary_opportunity_type": _record_value(target_record, "primary_opportunity_type"),
        "baseline_opportunity_types": list(baseline_record.get("opportunity_types") or []) if baseline_record else [],
        "target_opportunity_types": list(target_record.get("opportunity_types") or []) if target_record else [],
        "delta_priority_score": _delta_optional_int(
            _record_value(target_record, "priority_score"),
            _record_value(baseline_record, "priority_score"),
        ),
        "delta_word_count": _delta_optional_int(
            _record_value(target_record, "word_count"),
            _record_value(baseline_record, "word_count"),
        ),
        "delta_schema_count": _delta_optional_int(
            _record_value(target_record, "schema_count"),
            _record_value(baseline_record, "schema_count"),
        ),
        "delta_response_time_ms": _delta_optional_int(
            _record_value(target_record, "response_time_ms"),
            _record_value(baseline_record, "response_time_ms"),
        ),
        "delta_incoming_internal_links": _delta_optional_int(
            _record_value(target_record, "incoming_internal_links"),
            _record_value(baseline_record, "incoming_internal_links"),
        ),
        "delta_incoming_internal_linking_pages": _delta_optional_int(
            _record_value(target_record, "incoming_internal_linking_pages"),
            _record_value(baseline_record, "incoming_internal_linking_pages"),
        ),
    }


def _crawl_change_score(
    *,
    baseline_record: dict[str, Any],
    target_record: dict[str, Any],
    resolved_issues: list[str],
    added_issues: list[str],
    rules: TrendRules,
) -> int:
    score = min(rules.issue_score_cap, sum(rules.issue_weights[key] for key in resolved_issues))
    score -= min(rules.issue_score_cap, sum(rules.issue_weights[key] for key in added_issues))

    delta_internal_links = _delta_optional_int(target_record.get("incoming_internal_links"), baseline_record.get("incoming_internal_links"))
    if delta_internal_links is not None:
        if delta_internal_links >= rules.internal_links_delta_threshold:
            score += 4
        elif delta_internal_links <= -rules.internal_links_delta_threshold:
            score -= 4

    delta_linking_pages = _delta_optional_int(
        target_record.get("incoming_internal_linking_pages"),
        baseline_record.get("incoming_internal_linking_pages"),
    )
    if delta_linking_pages is not None:
        if delta_linking_pages >= rules.internal_linking_pages_delta_threshold:
            score += 4
        elif delta_linking_pages <= -rules.internal_linking_pages_delta_threshold:
            score -= 4

    delta_word_count = _delta_optional_int(target_record.get("word_count"), baseline_record.get("word_count"))
    if delta_word_count is not None:
        if delta_word_count >= rules.word_count_delta_threshold:
            score += 2
        elif delta_word_count <= -rules.word_count_delta_threshold:
            score -= 2

    delta_schema_count = _delta_optional_int(target_record.get("schema_count"), baseline_record.get("schema_count"))
    if delta_schema_count is not None:
        if delta_schema_count >= rules.schema_count_delta_threshold:
            score += 2
        elif delta_schema_count <= -rules.schema_count_delta_threshold:
            score -= 2

    delta_missing_alt = _delta_optional_int(
        target_record.get("images_missing_alt_count"),
        baseline_record.get("images_missing_alt_count"),
    )
    if delta_missing_alt is not None:
        if delta_missing_alt <= -rules.images_missing_alt_delta_threshold:
            score += 2
        elif delta_missing_alt >= rules.images_missing_alt_delta_threshold:
            score -= 2

    delta_response_time_ms = _delta_optional_int(target_record.get("response_time_ms"), baseline_record.get("response_time_ms"))
    if delta_response_time_ms is not None:
        if delta_response_time_ms <= -rules.response_time_delta_threshold_ms:
            score += 2
        elif delta_response_time_ms >= rules.response_time_delta_threshold_ms:
            score -= 2

    if bool(baseline_record.get("js_heavy_like")) and not bool(target_record.get("js_heavy_like")):
        score += 1
    elif not bool(baseline_record.get("js_heavy_like")) and bool(target_record.get("js_heavy_like")):
        score -= 1

    return score


def _build_crawl_change_rationale(
    *,
    baseline_record: dict[str, Any],
    target_record: dict[str, Any],
    resolved_issues: list[str],
    added_issues: list[str],
    rules: TrendRules,
) -> str:
    clauses: list[str] = []

    if resolved_issues:
        clauses.append(f"resolved {ISSUE_LABELS.get(resolved_issues[0], resolved_issues[0])}")
    if added_issues and len(clauses) < 2:
        clauses.append(f"added {ISSUE_LABELS.get(added_issues[0], added_issues[0])}")

    delta_internal_links = _delta_optional_int(target_record.get("incoming_internal_links"), baseline_record.get("incoming_internal_links"))
    if delta_internal_links is not None and abs(delta_internal_links) >= rules.internal_links_delta_threshold and len(clauses) < 2:
        direction = "gained" if delta_internal_links > 0 else "lost"
        clauses.append(f"{direction} {abs(delta_internal_links)} internal links")

    delta_linking_pages = _delta_optional_int(
        target_record.get("incoming_internal_linking_pages"),
        baseline_record.get("incoming_internal_linking_pages"),
    )
    if delta_linking_pages is not None and abs(delta_linking_pages) >= rules.internal_linking_pages_delta_threshold and len(clauses) < 2:
        direction = "gained" if delta_linking_pages > 0 else "lost"
        clauses.append(f"{direction} {abs(delta_linking_pages)} linking pages")

    delta_word_count = _delta_optional_int(target_record.get("word_count"), baseline_record.get("word_count"))
    if delta_word_count is not None and abs(delta_word_count) >= rules.word_count_delta_threshold and len(clauses) < 2:
        direction = "increased" if delta_word_count > 0 else "decreased"
        clauses.append(f"word count {direction} by {abs(delta_word_count)}")

    delta_missing_alt = _delta_optional_int(
        target_record.get("images_missing_alt_count"),
        baseline_record.get("images_missing_alt_count"),
    )
    if delta_missing_alt is not None and abs(delta_missing_alt) >= rules.images_missing_alt_delta_threshold and len(clauses) < 2:
        clauses.append("missing alt images reduced" if delta_missing_alt < 0 else "missing alt images increased")

    delta_schema_count = _delta_optional_int(target_record.get("schema_count"), baseline_record.get("schema_count"))
    if delta_schema_count is not None and abs(delta_schema_count) >= rules.schema_count_delta_threshold and len(clauses) < 2:
        direction = "increased" if delta_schema_count > 0 else "decreased"
        clauses.append(f"schema count {direction} by {abs(delta_schema_count)}")

    delta_response_time_ms = _delta_optional_int(target_record.get("response_time_ms"), baseline_record.get("response_time_ms"))
    if delta_response_time_ms is not None and abs(delta_response_time_ms) >= rules.response_time_delta_threshold_ms and len(clauses) < 2:
        direction = "improved" if delta_response_time_ms < 0 else "worsened"
        clauses.append(f"response time {direction} by {abs(delta_response_time_ms)} ms")

    delta_priority_score = _delta_optional_int(target_record.get("priority_score"), baseline_record.get("priority_score"))
    if delta_priority_score is not None and abs(delta_priority_score) >= rules.priority_score_delta_threshold and len(clauses) < 2:
        direction = "increased" if delta_priority_score > 0 else "dropped"
        clauses.append(f"priority score {direction} by {abs(delta_priority_score)}")

    if not clauses:
        return "no material change detected"
    if len(clauses) == 1:
        return clauses[0]
    return f"{clauses[0]} and {clauses[1]}"


def _build_gsc_rationale(
    *,
    baseline_metrics: dict[str, Any],
    target_metrics: dict[str, Any],
    clicks_trend: str,
    impressions_trend: str,
    ctr_trend: str,
    position_trend: str,
    top_queries_trend: str,
) -> str:
    clauses: list[str] = []
    delta_clicks = int(target_metrics["clicks"]) - int(baseline_metrics["clicks"])
    delta_impressions = int(target_metrics["impressions"]) - int(baseline_metrics["impressions"])
    delta_ctr = float(target_metrics["ctr"]) - float(baseline_metrics["ctr"])
    delta_top_queries = int(target_metrics["top_queries_count"]) - int(baseline_metrics["top_queries_count"])
    delta_position = _delta_optional_float(target_metrics["position"], baseline_metrics["position"])

    if clicks_trend != "flat":
        clauses.append(f"clicks {'up' if delta_clicks > 0 else 'down'} by {abs(delta_clicks)}")
    if impressions_trend != "flat" and len(clauses) < 2:
        clauses.append(f"impressions {'up' if delta_impressions > 0 else 'down'} by {abs(delta_impressions)}")
    if ctr_trend != "flat" and len(clauses) < 2:
        clauses.append(f"CTR {'up' if delta_ctr > 0 else 'down'} by {abs(delta_ctr) * 100:.2f}pp")
    if position_trend != "flat" and delta_position is not None and len(clauses) < 2:
        clauses.append(f"position {'improved' if delta_position < 0 else 'worsened'} by {abs(delta_position):.2f}")
    if top_queries_trend != "flat" and len(clauses) < 2:
        clauses.append(f"top queries {'up' if delta_top_queries > 0 else 'down'} by {abs(delta_top_queries)}")

    if not clauses:
        return "flat GSC performance between the selected ranges"
    if len(clauses) == 1:
        return clauses[0]
    return f"{clauses[0]} and {clauses[1]}"


def _filter_crawl_compare_rows(
    rows: list[dict[str, Any]],
    *,
    change_type: str | None,
    resolved_issues_min: int | None,
    added_issues_min: int | None,
    url_contains: str | None,
) -> list[dict[str, Any]]:
    filtered = rows
    if change_type:
        normalized_change_type = change_type.strip().lower()
        filtered = [row for row in filtered if str(row.get("change_type") or "").lower() == normalized_change_type]
    if resolved_issues_min is not None:
        filtered = [row for row in filtered if int(row.get("issues_resolved_count") or 0) >= resolved_issues_min]
    if added_issues_min is not None:
        filtered = [row for row in filtered if int(row.get("issues_added_count") or 0) >= added_issues_min]
    if url_contains:
        token = url_contains.strip().lower()
        if token:
            filtered = [row for row in filtered if token in str(row.get("url") or "").lower()]
    return filtered


def _filter_gsc_compare_rows(
    rows: list[dict[str, Any]],
    *,
    trend: str | None,
    clicks_trend: str | None,
    impressions_trend: str | None,
    ctr_trend: str | None,
    position_trend: str | None,
    top_queries_trend: str | None,
    url_contains: str | None,
) -> list[dict[str, Any]]:
    filtered = rows
    if trend:
        normalized_trend = trend.strip().lower()
        filtered = [row for row in filtered if str(row.get("overall_trend") or "").lower() == normalized_trend]
    for key, value in [
        ("clicks_trend", clicks_trend),
        ("impressions_trend", impressions_trend),
        ("ctr_trend", ctr_trend),
        ("position_trend", position_trend),
        ("top_queries_trend", top_queries_trend),
    ]:
        if not value:
            continue
        normalized_value = value.strip().lower()
        filtered = [row for row in filtered if str(row.get(key) or "").lower() == normalized_value]
    if url_contains:
        token = url_contains.strip().lower()
        if token:
            filtered = [row for row in filtered if token in str(row.get("url") or "").lower()]
    return filtered


def _load_same_site_compare_jobs(
    session: Session,
    *,
    baseline_job_id: int,
    target_job_id: int,
) -> tuple[CrawlJob, CrawlJob, Site]:
    baseline_job = _get_crawl_job_or_raise(session, baseline_job_id)
    target_job = _get_crawl_job_or_raise(session, target_job_id)
    if baseline_job.site_id != target_job.site_id:
        raise TrendsServiceError("baseline_job_id must belong to the same site as the target crawl job.")
    site = _get_site_or_raise(session, target_job.site_id)
    return baseline_job, target_job, site


def _load_page_record_lookup(
    session: Session,
    crawl_job_id: int,
    *,
    gsc_date_range: str,
) -> dict[str, dict[str, Any]]:
    records = crawl_job_service.get_all_pages_for_job(
        session,
        crawl_job_id,
        sort_by="url",
        sort_order="asc",
        gsc_date_range=gsc_date_range,
    )
    return {
        str(record.get("normalized_url") or record.get("url") or ""): record
        for record in records
        if record.get("normalized_url") or record.get("url")
    }


def _extract_gsc_metrics(record: dict[str, Any], suffix: str) -> dict[str, Any]:
    clicks = int(record.get(f"clicks_{suffix}") or 0)
    impressions = int(record.get(f"impressions_{suffix}") or 0)
    ctr_value = record.get(f"ctr_{suffix}")
    position_value = record.get(f"position_{suffix}")
    top_queries_count = int(record.get(f"top_queries_count_{suffix}") or 0)
    has_data = any(
        value is not None
        for value in [
            record.get(f"clicks_{suffix}"),
            record.get(f"impressions_{suffix}"),
            record.get(f"ctr_{suffix}"),
            record.get(f"position_{suffix}"),
        ]
    ) or top_queries_count > 0
    return {
        "clicks": clicks,
        "impressions": impressions,
        "ctr": float(ctr_value or 0.0),
        "position": float(position_value) if position_value is not None else None,
        "top_queries_count": top_queries_count,
        "has_data": has_data,
    }


def _collect_issue_keys(record: dict[str, Any], rules: TrendRules) -> set[str]:
    return {
        key
        for key in rules.issue_weights
        if bool(record.get(key))
    }


def _sorted_issue_labels(issue_keys: set[str], rules: TrendRules) -> list[str]:
    return sorted(
        issue_keys,
        key=lambda key: (-rules.issue_weights.get(key, 0), ISSUE_LABELS.get(key, key)),
    )


def _classify_numeric_trend(
    baseline: int | float | None,
    target: int | float | None,
    threshold: int | float,
) -> Literal["improved", "worsened", "flat"]:
    if baseline is None and target is None:
        return "flat"
    if baseline is None:
        return "improved"
    if target is None:
        return "worsened"
    delta = float(target) - float(baseline)
    if abs(delta) <= float(threshold):
        return "flat"
    return "improved" if delta > 0 else "worsened"


def _classify_position_trend(
    baseline: float | None,
    target: float | None,
    threshold: float,
) -> Literal["improved", "worsened", "flat"]:
    if baseline is None and target is None:
        return "flat"
    if baseline is None and target is not None:
        return "improved"
    if baseline is not None and target is None:
        return "worsened"
    if baseline is None or target is None:  # pragma: no cover - guarded above
        return "flat"
    delta = target - baseline
    if abs(delta) <= threshold:
        return "flat"
    return "improved" if delta < 0 else "worsened"


def _classify_gsc_overall_trend(
    *,
    clicks_trend: str,
    impressions_trend: str,
    ctr_trend: str,
    position_trend: str,
    top_queries_trend: str,
    rules: TrendRules,
) -> Literal["improved", "worsened", "flat"]:
    weighted_score = 0
    for metric, trend_value in [
        ("clicks", clicks_trend),
        ("impressions", impressions_trend),
        ("ctr", ctr_trend),
        ("position", position_trend),
        ("top_queries_count", top_queries_trend),
    ]:
        weight = int(rules.gsc_metric_weights.get(metric, 1))
        if trend_value == "improved":
            weighted_score += weight
        elif trend_value == "worsened":
            weighted_score -= weight
    if weighted_score > 0:
        return "improved"
    if weighted_score < 0:
        return "worsened"
    return "flat"


def _weighted_average_position(
    rows: list[dict[str, Any]],
    *,
    key: str,
    impressions_key: str,
    rules: TrendRules,
) -> float | None:
    weighted_sum = 0.0
    total_weight = 0
    fallback_positions: list[float] = []
    for row in rows:
        position = row.get(key)
        if position is None:
            continue
        fallback_positions.append(float(position))
        impressions = int(row.get(impressions_key) or 0)
        if impressions >= rules.summary_position_min_impressions:
            weighted_sum += float(position) * impressions
            total_weight += impressions
    if total_weight > 0:
        return weighted_sum / total_weight
    if fallback_positions:
        return sum(fallback_positions) / len(fallback_positions)
    return None


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


def _paginate_records(
    records: list[dict[str, Any]],
    *,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int, int]:
    total_items = len(records)
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    start = (page - 1) * page_size
    end = start + page_size
    return records[start:end], total_items, total_pages


def _serialize_job_option(crawl_job: CrawlJob, site: Site) -> dict[str, Any]:
    settings = crawl_job.settings_json if isinstance(crawl_job.settings_json, dict) else {}
    root_url = settings.get("start_url") or site.root_url
    status = crawl_job.status.value if hasattr(crawl_job.status, "value") else str(crawl_job.status)
    return {
        "id": crawl_job.id,
        "status": status,
        "created_at": crawl_job.created_at,
        "started_at": crawl_job.started_at,
        "finished_at": crawl_job.finished_at,
        "root_url": root_url,
    }


def _resolve_gsc_suffix(gsc_date_range: str) -> str:
    suffix = GSC_DATE_RANGE_SUFFIX.get(gsc_date_range)
    if suffix is None:
        raise TrendsServiceError(f"Unsupported GSC date range '{gsc_date_range}'.")
    return suffix


def _safe_ctr(clicks: int, impressions: int) -> float:
    if impressions <= 0:
        return 0.0
    return clicks / impressions


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


def _values_differ(left: Any, right: Any, *, normalize_text: bool = False) -> bool:
    if normalize_text:
        return _normalized_optional_text(left) != _normalized_optional_text(right)
    return left != right


def _normalized_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _delta_optional_int(target: Any, baseline: Any) -> int | None:
    if target is None or baseline is None:
        return None
    return int(target) - int(baseline)


def _delta_optional_float(target: Any, baseline: Any) -> float | None:
    if target is None or baseline is None:
        return None
    return float(target) - float(baseline)


def _record_value(record: dict[str, Any] | None, key: str) -> Any:
    if record is None:
        return None
    return record.get(key)


def _get_crawl_job_or_raise(session: Session, crawl_job_id: int) -> CrawlJob:
    crawl_job = session.get(CrawlJob, crawl_job_id)
    if crawl_job is None:
        raise TrendsServiceError(f"Crawl job {crawl_job_id} not found.")
    return crawl_job


def _get_site_or_raise(session: Session, site_id: int) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        raise TrendsServiceError(f"Site {site_id} not found.")
    return site
