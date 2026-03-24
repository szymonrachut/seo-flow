from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crawler.normalization.urls import normalize_url
from app.db.models import GscTopQuery, GscUrlMetric, Link, Page
from app.services.audit_thresholds import AuditThresholds, get_audit_thresholds
from app.services import page_taxonomy_service

GSC_DATE_RANGE_SUFFIX = {
    "last_28_days": "28d",
    "last_90_days": "90d",
}


def text_value_missing(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def has_noindex_directive(*robots_values: str | None) -> bool:
    return any("noindex" in str(value or "").lower() for value in robots_values)


def normalize_robots_directives(value: str | None) -> set[str]:
    if text_value_missing(value):
        return set()
    return {
        token.strip().lower()
        for token in str(value).replace(";", ",").split(",")
        if token and token.strip()
    }


def is_non_indexable_status(status_code: int | None) -> bool:
    return status_code is not None and not (200 <= int(status_code) <= 299)


def get_normalized_final_url(record: dict[str, Any]) -> str | None:
    final_url = record.get("final_url")
    if text_value_missing(final_url):
        return None
    normalized = normalize_url(str(final_url))
    if normalized:
        return normalized
    final_value = str(final_url).strip()
    return final_value or None


def get_effective_page_url(record: dict[str, Any]) -> str | None:
    return get_normalized_final_url(record) or record.get("normalized_url")


def page_redirects(record: dict[str, Any]) -> bool:
    normalized_final = get_normalized_final_url(record)
    if normalized_final and normalized_final != record.get("normalized_url"):
        return True

    status_code = record.get("status_code")
    return status_code is not None and 300 <= int(status_code) <= 399


def build_page_records(
    session: Session,
    crawl_job_id: int,
    *,
    thresholds: AuditThresholds | None = None,
) -> list[dict[str, Any]]:
    resolved_thresholds = thresholds or get_audit_thresholds()
    page_taxonomy_service.ensure_page_taxonomy_for_job(session, crawl_job_id)
    pages = session.scalars(select(Page).where(Page.crawl_job_id == crawl_job_id).order_by(Page.id.asc())).all()
    gsc_metrics = _load_gsc_url_metrics(session, crawl_job_id)
    gsc_top_queries_counts = _load_gsc_top_query_counts(session, crawl_job_id)
    internal_link_support = _load_internal_link_support(session, crawl_job_id)

    raw_records = [_serialize_page(page) for page in pages]
    page_lookup = {
        record["normalized_url"]: record
        for record in raw_records
        if not text_value_missing(record.get("normalized_url"))
    }
    duplicate_titles = _duplicate_values(raw_records, "title")
    duplicate_meta_descriptions = _duplicate_values(raw_records, "meta_description")
    duplicate_content_hashes = _duplicate_values(raw_records, "content_text_hash")

    records: list[dict[str, Any]] = []
    for raw_record in raw_records:
        record = dict(raw_record)
        title_length = _page_title_length(record)
        meta_description_length = _page_meta_description_length(record)
        h1_length = _page_h1_length(record)
        h1_count = _page_h1_count(record)
        h2_count = _optional_int(record.get("h2_count"))
        word_count = _optional_int(record.get("word_count"))
        images_count = _optional_int(record.get("images_count"))
        images_missing_alt_count = _optional_int(record.get("images_missing_alt_count"))
        html_size_bytes = _optional_int(record.get("html_size_bytes"))

        record["title_length"] = title_length
        record["meta_description_length"] = meta_description_length
        record["h1_length"] = h1_length
        record["h1_count"] = h1_count
        record["h2_count"] = h2_count
        record["word_count"] = word_count
        record["images_count"] = images_count
        record["images_missing_alt_count"] = images_missing_alt_count
        record["html_size_bytes"] = html_size_bytes

        record["title_missing"] = text_value_missing(record.get("title"))
        record["meta_description_missing"] = text_value_missing(record.get("meta_description"))
        record["h1_missing"] = h1_count == 0
        record["title_too_short"] = (
            title_length is not None
            and not record["title_missing"]
            and title_length < resolved_thresholds.title_too_short
        )
        record["title_too_long"] = (
            title_length is not None
            and not record["title_missing"]
            and title_length > resolved_thresholds.title_too_long
        )
        record["meta_description_too_short"] = (
            meta_description_length is not None
            and not record["meta_description_missing"]
            and meta_description_length < resolved_thresholds.meta_description_too_short
        )
        record["meta_description_too_long"] = (
            meta_description_length is not None
            and not record["meta_description_missing"]
            and meta_description_length > resolved_thresholds.meta_description_too_long
        )
        record["multiple_h1"] = h1_count is not None and h1_count > 1
        record["missing_h2"] = h2_count is not None and h2_count == 0

        canonical_url = record.get("canonical_url")
        self_canonical = _is_self_canonical(record)
        canonical_target = _resolve_canonical_target(record, page_lookup)
        record["canonical_missing"] = text_value_missing(canonical_url)
        record["self_canonical"] = self_canonical
        record["canonical_to_other_url"] = bool(not record["canonical_missing"] and not self_canonical)
        record["canonical_target_url"] = canonical_target.get("normalized_url") if canonical_target else canonical_url
        record["canonical_target_status_code"] = canonical_target.get("status_code") if canonical_target else None
        record["canonical_target_final_url"] = canonical_target.get("final_url") if canonical_target else None
        record["canonical_to_non_200"] = (
            not record["canonical_missing"] and _canonical_target_non_200(canonical_target)
        )
        record["canonical_to_redirect"] = (
            not record["canonical_missing"] and canonical_target is not None and page_redirects(canonical_target)
        )

        record["noindex_like"] = has_noindex_directive(record.get("robots_meta"), record.get("x_robots_tag"))
        record["non_indexable_like"] = record["noindex_like"] or is_non_indexable_status(record.get("status_code"))
        record["has_render_error"] = not text_value_missing(record.get("render_error_message"))
        record["has_x_robots_tag"] = not text_value_missing(record.get("x_robots_tag"))
        record["schema_present"] = bool(record.get("schema_present"))
        record["schema_count"] = _optional_int(record.get("schema_count")) or 0
        record["schema_types_json"] = _normalize_schema_types(record.get("schema_types_json"))
        record["schema_types_text"] = ", ".join(record["schema_types_json"])
        record["schema_missing"] = not record["schema_present"]
        record["was_rendered"] = bool(record.get("was_rendered"))
        record["render_attempted"] = bool(record.get("render_attempted"))
        record["js_heavy_like"] = bool(record.get("js_heavy_like"))
        record["robots_meta_directives"] = normalize_robots_directives(record.get("robots_meta"))
        record["x_robots_tag_directives"] = normalize_robots_directives(record.get("x_robots_tag"))
        record["thin_content"] = (
            word_count is not None and word_count < resolved_thresholds.thin_content_word_count
        )
        record["duplicate_title"] = _normalized_group_value(record.get("title")) in duplicate_titles
        record["duplicate_meta_description"] = (
            _normalized_group_value(record.get("meta_description")) in duplicate_meta_descriptions
        )
        record["duplicate_content"] = (
            _normalized_group_value(record.get("content_text_hash")) in duplicate_content_hashes
        )
        record["missing_alt_images"] = images_missing_alt_count is not None and images_missing_alt_count > 0
        record["no_images"] = images_count is not None and images_count == 0
        record["oversized"] = (
            html_size_bytes is not None and html_size_bytes > resolved_thresholds.oversized_page_bytes
        )
        link_support = internal_link_support.get(str(record["normalized_url"]), {"incoming_internal_links": 0, "incoming_internal_linking_pages": 0})
        record["incoming_internal_links"] = int(link_support["incoming_internal_links"])
        record["incoming_internal_linking_pages"] = int(link_support["incoming_internal_linking_pages"])
        _attach_gsc_metrics(record, gsc_metrics, gsc_top_queries_counts)
        record["technical_issue_count"] = _count_technical_issues(record)
        record["has_technical_issue"] = record["technical_issue_count"] > 0

        records.append(record)

    return records


def build_link_records(
    session: Session,
    crawl_job_id: int,
    *,
    page_records: list[dict[str, Any]] | None = None,
    thresholds: AuditThresholds | None = None,
) -> list[dict[str, Any]]:
    resolved_page_records = page_records or build_page_records(
        session,
        crawl_job_id,
        thresholds=thresholds,
    )
    page_lookup = {
        record["normalized_url"]: record
        for record in resolved_page_records
        if not text_value_missing(record.get("normalized_url"))
    }
    links = session.scalars(select(Link).where(Link.crawl_job_id == crawl_job_id).order_by(Link.id.asc())).all()

    records: list[dict[str, Any]] = []
    for link in links:
        target_record = (
            page_lookup.get(link.target_normalized_url)
            if not text_value_missing(link.target_normalized_url)
            else None
        )
        redirect_hops, terminal_final_url = _resolve_redirect_hops(target_record, page_lookup)
        broken_internal = bool(
            link.is_internal
            and target_record is not None
            and target_record.get("status_code") is not None
            and int(target_record["status_code"]) >= 400
        )
        unresolved_internal = bool(link.is_internal and target_record is None and link.target_normalized_url)
        redirecting_internal = bool(link.is_internal and redirect_hops >= 1)
        to_noindex_like = bool(
            link.is_internal and target_record is not None and target_record.get("non_indexable_like")
        )
        to_canonicalized = bool(
            link.is_internal and target_record is not None and target_record.get("canonical_to_other_url")
        )
        redirect_chain = bool(link.is_internal and redirect_hops > 1)

        records.append(
            {
                "id": link.id,
                "crawl_job_id": link.crawl_job_id,
                "source_page_id": link.source_page_id,
                "source_url": link.source_url,
                "target_url": link.target_url,
                "target_normalized_url": link.target_normalized_url,
                "target_domain": link.target_domain,
                "anchor_text": link.anchor_text,
                "rel_attr": link.rel_attr,
                "is_nofollow": link.is_nofollow,
                "is_internal": link.is_internal,
                "target_status_code": target_record.get("status_code") if target_record is not None else None,
                "final_url": terminal_final_url,
                "target_canonical_url": target_record.get("canonical_url") if target_record is not None else None,
                "target_noindex_like": bool(target_record.get("noindex_like")) if target_record is not None else False,
                "target_non_indexable_like": bool(target_record.get("non_indexable_like")) if target_record is not None else False,
                "target_canonicalized": bool(target_record.get("canonical_to_other_url")) if target_record is not None else False,
                "broken_internal": broken_internal,
                "unresolved_internal": unresolved_internal,
                "redirecting_internal": redirecting_internal,
                "to_noindex_like": to_noindex_like,
                "to_canonicalized": to_canonicalized,
                "redirect_chain": redirect_chain,
                "redirect_hops": redirect_hops if redirect_hops > 0 else None,
                "created_at": link.created_at,
            }
        )

    return records


def get_duplicate_groups(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        value = _normalized_group_value(record.get(key))
        if value is None:
            continue
        grouped.setdefault(value, []).append(record)

    groups = [
        {
            "value": value,
            "count": len(group_records),
            "pages": group_records,
        }
        for value, group_records in grouped.items()
        if len(group_records) > 1
    ]
    groups.sort(key=lambda item: (-int(item["count"]), str(item["value"]).lower()))
    return groups


def _serialize_page(page: Page) -> dict[str, Any]:
    return {
        "id": page.id,
        "crawl_job_id": page.crawl_job_id,
        "url": page.url,
        "normalized_url": page.normalized_url,
        "final_url": page.final_url,
        "status_code": page.status_code,
        "title": page.title,
        "title_length": page.title_length,
        "meta_description": page.meta_description,
        "meta_description_length": page.meta_description_length,
        "h1": page.h1,
        "h1_count": page.h1_count,
        "h2_count": page.h2_count,
        "canonical_url": page.canonical_url,
        "robots_meta": page.robots_meta,
        "x_robots_tag": page.x_robots_tag,
        "content_type": page.content_type,
        "word_count": page.word_count,
        "content_text_hash": page.content_text_hash,
        "images_count": page.images_count,
        "images_missing_alt_count": page.images_missing_alt_count,
        "html_size_bytes": page.html_size_bytes,
        "was_rendered": page.was_rendered,
        "render_attempted": page.render_attempted,
        "fetch_mode_used": page.fetch_mode_used,
        "js_heavy_like": page.js_heavy_like,
        "render_reason": page.render_reason,
        "render_error_message": page.render_error_message,
        "schema_present": page.schema_present,
        "schema_count": page.schema_count,
        "schema_types_json": page.schema_types_json,
        "page_type": page.page_type,
        "page_bucket": page.page_bucket,
        "page_type_confidence": page.page_type_confidence,
        "page_type_version": page.page_type_version,
        "page_type_rationale": page.page_type_rationale,
        "response_time_ms": page.response_time_ms,
        "is_internal": page.is_internal,
        "depth": page.depth,
        "fetched_at": page.fetched_at,
        "error_message": page.error_message,
        "created_at": page.created_at,
    }


def _duplicate_values(records: list[dict[str, Any]], key: str) -> set[str]:
    counts: dict[str, int] = {}
    for record in records:
        value = _normalized_group_value(record.get(key))
        if value is None:
            continue
        counts[value] = counts.get(value, 0) + 1
    return {value for value, count in counts.items() if count > 1}


def _normalized_group_value(value: Any) -> str | None:
    if text_value_missing(value):
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _load_gsc_url_metrics(session: Session, crawl_job_id: int) -> dict[tuple[int, str], dict[str, Any]]:
    rows = session.scalars(
        select(GscUrlMetric)
        .where(GscUrlMetric.crawl_job_id == crawl_job_id)
        .order_by(GscUrlMetric.id.asc())
    ).all()
    return {
        (int(row.page_id), row.date_range_label): {
            "clicks": row.clicks,
            "impressions": row.impressions,
            "ctr": row.ctr,
            "position": row.position,
            "fetched_at": row.fetched_at,
        }
        for row in rows
        if row.page_id is not None
    }


def _load_gsc_top_query_counts(session: Session, crawl_job_id: int) -> dict[tuple[int, str], int]:
    rows = session.execute(
        select(
            GscTopQuery.page_id,
            GscTopQuery.date_range_label,
            func.count(GscTopQuery.id),
        )
        .where(GscTopQuery.crawl_job_id == crawl_job_id, GscTopQuery.page_id.is_not(None))
        .group_by(GscTopQuery.page_id, GscTopQuery.date_range_label)
    ).all()
    return {
        (int(page_id), str(date_range_label)): int(count)
        for page_id, date_range_label, count in rows
        if page_id is not None
    }


def _load_internal_link_support(session: Session, crawl_job_id: int) -> dict[str, dict[str, int]]:
    rows = session.execute(
        select(
            Link.target_normalized_url,
            func.count(Link.id),
            func.count(func.distinct(Link.source_page_id)),
        )
        .where(
            Link.crawl_job_id == crawl_job_id,
            Link.is_internal.is_(True),
            Link.target_normalized_url.is_not(None),
        )
        .group_by(Link.target_normalized_url)
    ).all()
    return {
        str(target_normalized_url): {
            "incoming_internal_links": int(link_count),
            "incoming_internal_linking_pages": int(unique_sources),
        }
        for target_normalized_url, link_count, unique_sources in rows
        if target_normalized_url is not None
    }


def _attach_gsc_metrics(
    record: dict[str, Any],
    gsc_metrics: dict[tuple[int, str], dict[str, Any]],
    gsc_top_queries_counts: dict[tuple[int, str], int],
) -> None:
    page_id = int(record["id"])
    for date_range_label, suffix in GSC_DATE_RANGE_SUFFIX.items():
        metrics = gsc_metrics.get((page_id, date_range_label))
        record[f"clicks_{suffix}"] = metrics.get("clicks") if metrics else None
        record[f"impressions_{suffix}"] = metrics.get("impressions") if metrics else None
        record[f"ctr_{suffix}"] = metrics.get("ctr") if metrics else None
        record[f"position_{suffix}"] = metrics.get("position") if metrics else None
        record[f"gsc_fetched_at_{suffix}"] = metrics.get("fetched_at") if metrics else None
        record[f"top_queries_count_{suffix}"] = int(gsc_top_queries_counts.get((page_id, date_range_label), 0))
        record[f"has_gsc_{suffix}"] = metrics is not None


def _normalize_schema_types(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized_values: list[str] = []
    for item in value:
        if text_value_missing(item):
            continue
        normalized_values.append(str(item).strip())
    return normalized_values


def _page_title_length(record: dict[str, Any]) -> int | None:
    if record.get("title_length") is not None:
        return int(record["title_length"])
    title = _normalized_group_value(record.get("title"))
    return len(title) if title is not None else None


def _page_meta_description_length(record: dict[str, Any]) -> int | None:
    if record.get("meta_description_length") is not None:
        return int(record["meta_description_length"])
    meta_description = _normalized_group_value(record.get("meta_description"))
    return len(meta_description) if meta_description is not None else None


def _page_h1_length(record: dict[str, Any]) -> int | None:
    h1 = _normalized_group_value(record.get("h1"))
    return len(h1) if h1 is not None else None


def _page_h1_count(record: dict[str, Any]) -> int | None:
    if record.get("h1_count") is not None:
        return int(record["h1_count"])
    return 0 if text_value_missing(record.get("h1")) else 1


def _is_self_canonical(record: dict[str, Any]) -> bool:
    canonical_url = _normalized_group_value(record.get("canonical_url"))
    if canonical_url is None:
        return False

    effective_url = get_effective_page_url(record)
    return canonical_url in {record.get("normalized_url"), effective_url}


def _resolve_canonical_target(
    record: dict[str, Any],
    page_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    canonical_url = _normalized_group_value(record.get("canonical_url"))
    if canonical_url is None:
        return None

    if canonical_url in {record.get("normalized_url"), get_effective_page_url(record)}:
        return record

    return page_lookup.get(canonical_url)


def _canonical_target_non_200(target_record: dict[str, Any] | None) -> bool:
    if target_record is None:
        return True

    status_code = target_record.get("status_code")
    if status_code is None:
        return True

    status_code_int = int(status_code)
    return status_code_int < 200 or status_code_int >= 400


def _resolve_redirect_hops(
    target_record: dict[str, Any] | None,
    page_lookup: dict[str, dict[str, Any]],
) -> tuple[int, str | None]:
    if target_record is None:
        return 0, None

    hops = 0
    terminal_final_url = target_record.get("final_url")
    current_record: dict[str, Any] | None = target_record
    seen_urls: set[str] = set()

    while current_record is not None and page_redirects(current_record):
        current_normalized_url = str(current_record.get("normalized_url") or "")
        if current_normalized_url in seen_urls:
            break
        seen_urls.add(current_normalized_url)

        hops += 1
        if current_record.get("final_url"):
            terminal_final_url = current_record.get("final_url")

        next_normalized_url = get_normalized_final_url(current_record)
        if next_normalized_url is None:
            break

        next_record = page_lookup.get(next_normalized_url)
        if next_record is None or next_record.get("normalized_url") == current_record.get("normalized_url"):
            break

        current_record = next_record

    return hops, terminal_final_url


def _count_technical_issues(record: dict[str, Any]) -> int:
    technical_issue_keys = [
        "title_missing",
        "meta_description_missing",
        "h1_missing",
        "title_too_short",
        "title_too_long",
        "meta_description_too_short",
        "meta_description_too_long",
        "multiple_h1",
        "missing_h2",
        "canonical_missing",
        "canonical_to_non_200",
        "canonical_to_redirect",
        "noindex_like",
        "thin_content",
        "duplicate_content",
        "missing_alt_images",
        "oversized",
    ]
    return sum(1 for key in technical_issue_keys if bool(record.get(key)))
