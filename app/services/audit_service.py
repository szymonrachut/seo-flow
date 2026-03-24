from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.seo_analysis import build_link_records, build_page_records, get_duplicate_groups


def build_audit_report(session: Session, crawl_job_id: int) -> dict[str, Any]:
    page_records = build_page_records(session, crawl_job_id)
    link_records = build_link_records(session, crawl_job_id, page_records=page_records)

    pages_missing_title = _page_refs(page_records, "title_missing")
    pages_title_too_short = _page_refs(page_records, "title_too_short")
    pages_title_too_long = _page_refs(page_records, "title_too_long")
    pages_missing_meta_description = _page_refs(page_records, "meta_description_missing")
    pages_meta_description_too_short = _page_refs(page_records, "meta_description_too_short")
    pages_meta_description_too_long = _page_refs(page_records, "meta_description_too_long")
    pages_missing_h1 = _page_refs(page_records, "h1_missing")
    pages_multiple_h1 = _page_refs(page_records, "multiple_h1")
    pages_missing_h2 = _page_refs(page_records, "missing_h2")
    pages_missing_canonical = _page_refs(page_records, "canonical_missing")
    pages_self_canonical = _page_refs(page_records, "self_canonical")
    pages_canonical_to_other_url = _page_refs(page_records, "canonical_to_other_url")
    pages_canonical_to_non_200 = _page_refs(page_records, "canonical_to_non_200")
    pages_canonical_to_redirect = _page_refs(page_records, "canonical_to_redirect")
    pages_noindex_like = _page_refs(page_records, "noindex_like")
    pages_non_indexable_like = _page_refs(page_records, "non_indexable_like")
    pages_thin_content = _page_refs(page_records, "thin_content")
    pages_with_missing_alt_images = _page_refs(page_records, "missing_alt_images")
    pages_with_no_images = _page_refs(page_records, "no_images")
    oversized_pages = _page_refs(page_records, "oversized")
    js_heavy_like_pages = _page_refs(page_records, "js_heavy_like")
    rendered_pages = _page_refs(page_records, "was_rendered")
    pages_with_render_errors = _page_refs(page_records, "has_render_error")
    pages_with_schema = _page_refs(page_records, "schema_present")
    pages_missing_schema = _page_refs(page_records, "schema_missing")
    pages_with_x_robots_tag = _page_refs(page_records, "has_x_robots_tag")
    pages_with_schema_types_summary = _schema_type_groups(page_records)

    duplicate_title_groups = _duplicate_groups(page_records, "title")
    duplicate_meta_groups = _duplicate_groups(page_records, "meta_description")
    duplicate_content_groups = _duplicate_groups(page_records, "content_text_hash")

    broken_internal_links = _link_refs(link_records, "broken_internal")
    unresolved_internal_targets = _link_refs(link_records, "unresolved_internal")
    redirecting_internal_links = _link_refs(link_records, "redirecting_internal")
    internal_links_to_noindex_like_pages = _link_refs(link_records, "to_noindex_like")
    internal_links_to_canonicalized_pages = _link_refs(link_records, "to_canonicalized")
    redirect_chains_internal = _link_refs(link_records, "redirect_chain")

    summary = {
        "total_pages": len(page_records),
        "pages_missing_title": len(pages_missing_title),
        "pages_title_too_short": len(pages_title_too_short),
        "pages_title_too_long": len(pages_title_too_long),
        "pages_missing_meta_description": len(pages_missing_meta_description),
        "pages_meta_description_too_short": len(pages_meta_description_too_short),
        "pages_meta_description_too_long": len(pages_meta_description_too_long),
        "pages_missing_h1": len(pages_missing_h1),
        "pages_multiple_h1": len(pages_multiple_h1),
        "pages_missing_h2": len(pages_missing_h2),
        "pages_missing_canonical": len(pages_missing_canonical),
        "pages_self_canonical": len(pages_self_canonical),
        "pages_canonical_to_other_url": len(pages_canonical_to_other_url),
        "pages_canonical_to_non_200": len(pages_canonical_to_non_200),
        "pages_canonical_to_redirect": len(pages_canonical_to_redirect),
        "pages_noindex_like": len(pages_noindex_like),
        "pages_non_indexable_like": len(pages_non_indexable_like),
        "pages_duplicate_title_groups": len(duplicate_title_groups),
        "pages_duplicate_meta_description_groups": len(duplicate_meta_groups),
        "pages_thin_content": len(pages_thin_content),
        "pages_duplicate_content_groups": len(duplicate_content_groups),
        "pages_with_missing_alt_images": len(pages_with_missing_alt_images),
        "pages_with_no_images": len(pages_with_no_images),
        "oversized_pages": len(oversized_pages),
        "js_heavy_like_pages": len(js_heavy_like_pages),
        "rendered_pages": len(rendered_pages),
        "pages_with_render_errors": len(pages_with_render_errors),
        "pages_with_schema": len(pages_with_schema),
        "pages_missing_schema": len(pages_missing_schema),
        "pages_with_x_robots_tag": len(pages_with_x_robots_tag),
        "pages_with_schema_types_summary": len(pages_with_schema_types_summary),
        "broken_internal_links": len(broken_internal_links),
        "unresolved_internal_targets": len(unresolved_internal_targets),
        "redirecting_internal_links": len(redirecting_internal_links),
        "internal_links_to_noindex_like_pages": len(internal_links_to_noindex_like_pages),
        "internal_links_to_canonicalized_pages": len(internal_links_to_canonicalized_pages),
        "redirect_chains_internal": len(redirect_chains_internal),
    }

    return {
        "crawl_job_id": crawl_job_id,
        "summary": summary,
        "pages_missing_title": pages_missing_title,
        "pages_title_too_short": pages_title_too_short,
        "pages_title_too_long": pages_title_too_long,
        "pages_missing_meta_description": pages_missing_meta_description,
        "pages_meta_description_too_short": pages_meta_description_too_short,
        "pages_meta_description_too_long": pages_meta_description_too_long,
        "pages_missing_h1": pages_missing_h1,
        "pages_multiple_h1": pages_multiple_h1,
        "pages_missing_h2": pages_missing_h2,
        "pages_missing_canonical": pages_missing_canonical,
        "pages_self_canonical": pages_self_canonical,
        "pages_canonical_to_other_url": pages_canonical_to_other_url,
        "pages_canonical_to_non_200": pages_canonical_to_non_200,
        "pages_canonical_to_redirect": pages_canonical_to_redirect,
        "pages_noindex_like": pages_noindex_like,
        "pages_non_indexable_like": pages_non_indexable_like,
        "pages_duplicate_title": duplicate_title_groups,
        "pages_duplicate_meta_description": duplicate_meta_groups,
        "pages_thin_content": pages_thin_content,
        "pages_duplicate_content": duplicate_content_groups,
        "pages_with_missing_alt_images": pages_with_missing_alt_images,
        "pages_with_no_images": pages_with_no_images,
        "oversized_pages": oversized_pages,
        "js_heavy_like_pages": js_heavy_like_pages,
        "rendered_pages": rendered_pages,
        "pages_with_render_errors": pages_with_render_errors,
        "pages_with_schema": pages_with_schema,
        "pages_missing_schema": pages_missing_schema,
        "pages_with_x_robots_tag": pages_with_x_robots_tag,
        "pages_with_schema_types_summary": pages_with_schema_types_summary,
        "broken_internal_links": broken_internal_links,
        "unresolved_internal_targets": unresolved_internal_targets,
        "redirecting_internal_links": redirecting_internal_links,
        "internal_links_to_noindex_like_pages": internal_links_to_noindex_like_pages,
        "internal_links_to_canonicalized_pages": internal_links_to_canonicalized_pages,
        "redirect_chains_internal": redirect_chains_internal,
    }


def _page_refs(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return [_page_ref(record) for record in records if bool(record.get(key))]


def _duplicate_groups(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups = get_duplicate_groups(records, key)
    return [
        {
            "value": group["value"],
            "count": group["count"],
            "pages": [_page_ref(record) for record in group["pages"]],
        }
        for group in groups
    ]


def _schema_type_groups(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for record in records:
        for schema_type in record.get("schema_types_json") or []:
            grouped.setdefault(str(schema_type), []).append(record)

    groups = [
        {
            "value": schema_type,
            "count": len(group_records),
            "pages": [_page_ref(record) for record in group_records],
        }
        for schema_type, group_records in grouped.items()
    ]
    groups.sort(key=lambda item: (-int(item["count"]), str(item["value"]).lower()))
    return groups


def _link_refs(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return [_link_ref(record) for record in records if bool(record.get(key))]


def _page_ref(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "page_id": record["id"],
        "url": record["url"],
        "normalized_url": record["normalized_url"],
        "final_url": record.get("final_url"),
        "status_code": record.get("status_code"),
        "title": record.get("title"),
        "title_length": record.get("title_length"),
        "meta_description": record.get("meta_description"),
        "meta_description_length": record.get("meta_description_length"),
        "h1": record.get("h1"),
        "h1_count": record.get("h1_count"),
        "h2_count": record.get("h2_count"),
        "canonical_url": record.get("canonical_url"),
        "canonical_target_url": record.get("canonical_target_url"),
        "canonical_target_status_code": record.get("canonical_target_status_code"),
        "canonical_target_final_url": record.get("canonical_target_final_url"),
        "robots_meta": record.get("robots_meta"),
        "x_robots_tag": record.get("x_robots_tag"),
        "word_count": record.get("word_count"),
        "content_text_hash": record.get("content_text_hash"),
        "images_count": record.get("images_count"),
        "images_missing_alt_count": record.get("images_missing_alt_count"),
        "html_size_bytes": record.get("html_size_bytes"),
        "was_rendered": bool(record.get("was_rendered")),
        "js_heavy_like": bool(record.get("js_heavy_like")),
        "render_reason": record.get("render_reason"),
        "render_error_message": record.get("render_error_message"),
        "schema_present": bool(record.get("schema_present")),
        "schema_count": record.get("schema_count"),
        "schema_types_json": list(record.get("schema_types_json") or []),
    }


def _link_ref(record: dict[str, Any]) -> dict[str, Any]:
    signals: list[str] = []
    if record.get("broken_internal"):
        signals.append("broken_internal")
    if record.get("unresolved_internal"):
        signals.append("unresolved_internal")
    if record.get("redirecting_internal"):
        signals.append("redirecting_internal")
    if record.get("to_noindex_like"):
        signals.append("to_noindex_like")
    if record.get("to_canonicalized"):
        signals.append("to_canonicalized")
    if record.get("redirect_chain"):
        signals.append("redirect_chain")

    return {
        "link_id": record["id"],
        "source_url": record["source_url"],
        "target_url": record["target_url"],
        "target_normalized_url": record.get("target_normalized_url"),
        "target_status_code": record.get("target_status_code"),
        "final_url": record.get("final_url"),
        "redirect_hops": record.get("redirect_hops"),
        "target_canonical_url": record.get("target_canonical_url"),
        "target_noindex_like": record.get("target_noindex_like"),
        "target_non_indexable_like": record.get("target_non_indexable_like"),
        "signals": signals,
    }
