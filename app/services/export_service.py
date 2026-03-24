from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.services import (
    cannibalization_service,
    competitive_gap_service,
    content_recommendation_service,
    crawl_job_service,
    gsc_service,
    internal_linking_service,
    trends_service,
)
from app.services.audit_service import build_audit_report

UTF8_BOM = "\ufeff"


def build_pages_csv(
    session,
    crawl_job_id: int,
    **filters: Any,
) -> str:
    pages = crawl_job_service.get_all_pages_for_job(session, crawl_job_id, **filters)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "crawl_job_id",
            "url",
            "normalized_url",
            "final_url",
            "status_code",
            "title",
            "title_length",
            "meta_description",
            "meta_description_length",
            "h1",
            "h1_count",
            "h2_count",
            "canonical_url",
            "canonical_target_url",
            "canonical_target_status_code",
            "robots_meta",
            "x_robots_tag",
            "content_type",
            "word_count",
            "content_text_hash",
            "images_count",
            "images_missing_alt_count",
            "html_size_bytes",
            "was_rendered",
            "render_attempted",
            "fetch_mode_used",
            "js_heavy_like",
            "render_reason",
            "render_error_message",
            "schema_present",
            "schema_count",
            "schema_types",
            "page_type",
            "page_bucket",
            "page_type_confidence",
            "page_type_version",
            "page_type_rationale",
            "clicks_28d",
            "impressions_28d",
            "ctr_28d",
            "position_28d",
            "top_queries_count_28d",
            "gsc_fetched_at_28d",
            "clicks_90d",
            "impressions_90d",
            "ctr_90d",
            "position_90d",
            "top_queries_count_90d",
            "gsc_fetched_at_90d",
            "has_technical_issue",
            "technical_issue_count",
            "incoming_internal_links",
            "incoming_internal_linking_pages",
            "priority_score",
            "priority_level",
            "traffic_component",
            "issue_component",
            "opportunity_component",
            "internal_linking_component",
            "opportunity_count",
            "primary_opportunity_type",
            "opportunity_types",
            "has_cannibalization",
            "cannibalization_cluster_id",
            "cannibalization_severity",
            "cannibalization_impact_level",
            "cannibalization_recommendation_type",
            "cannibalization_competing_urls_count",
            "cannibalization_strongest_competing_url",
            "cannibalization_dominant_competing_url",
            "cannibalization_common_queries_count",
            "cannibalization_weighted_overlap_by_impressions",
            "cannibalization_weighted_overlap_by_clicks",
            "cannibalization_overlap_ratio",
            "cannibalization_overlap_strength",
            "cannibalization_shared_top_queries",
            "cannibalization_rationale",
            "priority_rationale",
            "response_time_ms",
            "is_internal",
            "depth",
            "fetched_at",
            "error_message",
            "title_too_short",
            "title_too_long",
            "meta_description_too_short",
            "meta_description_too_long",
            "multiple_h1",
            "missing_h2",
            "self_canonical",
            "canonical_to_other_url",
            "canonical_to_non_200",
            "canonical_to_redirect",
            "noindex_like",
            "non_indexable_like",
            "thin_content",
            "duplicate_content",
            "missing_alt_images",
            "no_images",
            "oversized",
            "created_at",
        ]
    )
    for page in pages:
        writer.writerow(
            [
                _page_value(page, "id"),
                _page_value(page, "crawl_job_id"),
                _page_value(page, "url"),
                _page_value(page, "normalized_url"),
                _page_value(page, "final_url"),
                _page_value(page, "status_code"),
                _page_value(page, "title"),
                _page_value(page, "title_length"),
                _page_value(page, "meta_description"),
                _page_value(page, "meta_description_length"),
                _page_value(page, "h1"),
                _page_value(page, "h1_count"),
                _page_value(page, "h2_count"),
                _page_value(page, "canonical_url"),
                _page_value(page, "canonical_target_url"),
                _page_value(page, "canonical_target_status_code"),
                _page_value(page, "robots_meta"),
                _page_value(page, "x_robots_tag"),
                _page_value(page, "content_type"),
                _page_value(page, "word_count"),
                _page_value(page, "content_text_hash"),
                _page_value(page, "images_count"),
                _page_value(page, "images_missing_alt_count"),
                _page_value(page, "html_size_bytes"),
                _page_value(page, "was_rendered"),
                _page_value(page, "render_attempted"),
                _page_value(page, "fetch_mode_used"),
                _page_value(page, "js_heavy_like"),
                _page_value(page, "render_reason"),
                _page_value(page, "render_error_message"),
                _page_value(page, "schema_present"),
                _page_value(page, "schema_count"),
                ", ".join(_page_value(page, "schema_types_json") or []),
                _page_value(page, "page_type"),
                _page_value(page, "page_bucket"),
                _page_value(page, "page_type_confidence"),
                _page_value(page, "page_type_version"),
                _page_value(page, "page_type_rationale"),
                _page_value(page, "clicks_28d"),
                _page_value(page, "impressions_28d"),
                _page_value(page, "ctr_28d"),
                _page_value(page, "position_28d"),
                _page_value(page, "top_queries_count_28d"),
                _serialize_datetime(_page_value(page, "gsc_fetched_at_28d")),
                _page_value(page, "clicks_90d"),
                _page_value(page, "impressions_90d"),
                _page_value(page, "ctr_90d"),
                _page_value(page, "position_90d"),
                _page_value(page, "top_queries_count_90d"),
                _serialize_datetime(_page_value(page, "gsc_fetched_at_90d")),
                _page_value(page, "has_technical_issue"),
                _page_value(page, "technical_issue_count"),
                _page_value(page, "incoming_internal_links"),
                _page_value(page, "incoming_internal_linking_pages"),
                _page_value(page, "priority_score"),
                _page_value(page, "priority_level"),
                _page_value(page, "traffic_component"),
                _page_value(page, "issue_component"),
                _page_value(page, "opportunity_component"),
                _page_value(page, "internal_linking_component"),
                _page_value(page, "opportunity_count"),
                _page_value(page, "primary_opportunity_type"),
                ", ".join(_page_value(page, "opportunity_types") or []),
                _page_value(page, "has_cannibalization"),
                _page_value(page, "cannibalization_cluster_id"),
                _page_value(page, "cannibalization_severity"),
                _page_value(page, "cannibalization_impact_level"),
                _page_value(page, "cannibalization_recommendation_type"),
                _page_value(page, "cannibalization_competing_urls_count"),
                _page_value(page, "cannibalization_strongest_competing_url"),
                _page_value(page, "cannibalization_dominant_competing_url"),
                _page_value(page, "cannibalization_common_queries_count"),
                _page_value(page, "cannibalization_weighted_overlap_by_impressions"),
                _page_value(page, "cannibalization_weighted_overlap_by_clicks"),
                _page_value(page, "cannibalization_overlap_ratio"),
                _page_value(page, "cannibalization_overlap_strength"),
                " | ".join(_page_value(page, "cannibalization_shared_top_queries") or []),
                _page_value(page, "cannibalization_rationale"),
                _page_value(page, "priority_rationale"),
                _page_value(page, "response_time_ms"),
                _page_value(page, "is_internal"),
                _page_value(page, "depth"),
                _serialize_datetime(_page_value(page, "fetched_at")),
                _page_value(page, "error_message"),
                _page_value(page, "title_too_short"),
                _page_value(page, "title_too_long"),
                _page_value(page, "meta_description_too_short"),
                _page_value(page, "meta_description_too_long"),
                _page_value(page, "multiple_h1"),
                _page_value(page, "missing_h2"),
                _page_value(page, "self_canonical"),
                _page_value(page, "canonical_to_other_url"),
                _page_value(page, "canonical_to_non_200"),
                _page_value(page, "canonical_to_redirect"),
                _page_value(page, "noindex_like"),
                _page_value(page, "non_indexable_like"),
                _page_value(page, "thin_content"),
                _page_value(page, "duplicate_content"),
                _page_value(page, "missing_alt_images"),
                _page_value(page, "no_images"),
                _page_value(page, "oversized"),
                _serialize_datetime(_page_value(page, "created_at")),
            ]
        )
    return UTF8_BOM + buffer.getvalue()


def build_links_csv(
    session,
    crawl_job_id: int,
    **filters: Any,
) -> str:
    links = crawl_job_service.get_all_links_for_job(session, crawl_job_id, **filters)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "crawl_job_id",
            "source_page_id",
            "source_url",
            "target_url",
            "target_normalized_url",
            "target_domain",
            "anchor_text",
            "rel_attr",
            "is_nofollow",
            "is_internal",
            "target_status_code",
            "final_url",
            "redirect_hops",
            "target_canonical_url",
            "target_noindex_like",
            "target_non_indexable_like",
            "broken_internal",
            "redirecting_internal",
            "unresolved_internal",
            "to_noindex_like",
            "to_canonicalized",
            "redirect_chain",
            "created_at",
        ]
    )
    for link in links:
        writer.writerow(
            [
                _link_value(link, "id"),
                _link_value(link, "crawl_job_id"),
                _link_value(link, "source_page_id"),
                _link_value(link, "source_url"),
                _link_value(link, "target_url"),
                _link_value(link, "target_normalized_url"),
                _link_value(link, "target_domain"),
                _link_value(link, "anchor_text"),
                _link_value(link, "rel_attr"),
                _link_value(link, "is_nofollow"),
                _link_value(link, "is_internal"),
                _link_value(link, "target_status_code"),
                _link_value(link, "final_url"),
                _link_value(link, "redirect_hops"),
                _link_value(link, "target_canonical_url"),
                _link_value(link, "target_noindex_like"),
                _link_value(link, "target_non_indexable_like"),
                _link_value(link, "broken_internal"),
                _link_value(link, "redirecting_internal"),
                _link_value(link, "unresolved_internal"),
                _link_value(link, "to_noindex_like"),
                _link_value(link, "to_canonicalized"),
                _link_value(link, "redirect_chain"),
                _serialize_datetime(_link_value(link, "created_at")),
            ]
        )
    return UTF8_BOM + buffer.getvalue()


def build_audit_csv(session, crawl_job_id: int) -> str:
    report = build_audit_report(session, crawl_job_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["issue_type", "key", "value", "url", "details"])

    for key, value in report["summary"].items():
        writer.writerow(["summary", key, value, "", ""])

    page_sections = [
        "pages_missing_title",
        "pages_title_too_short",
        "pages_title_too_long",
        "pages_missing_meta_description",
        "pages_meta_description_too_short",
        "pages_meta_description_too_long",
        "pages_missing_h1",
        "pages_multiple_h1",
        "pages_missing_h2",
        "pages_missing_canonical",
        "pages_self_canonical",
        "pages_canonical_to_other_url",
        "pages_canonical_to_non_200",
        "pages_canonical_to_redirect",
        "pages_noindex_like",
        "pages_non_indexable_like",
        "pages_thin_content",
        "pages_with_missing_alt_images",
        "pages_with_no_images",
        "oversized_pages",
        "js_heavy_like_pages",
        "rendered_pages",
        "pages_with_render_errors",
        "pages_with_schema",
        "pages_missing_schema",
        "pages_with_x_robots_tag",
    ]
    for section in page_sections:
        _write_page_issue_rows(writer, section, report[section])

    _write_duplicate_rows(writer, "pages_duplicate_title", report["pages_duplicate_title"])
    _write_duplicate_rows(writer, "pages_duplicate_meta_description", report["pages_duplicate_meta_description"])
    _write_duplicate_rows(writer, "pages_duplicate_content", report["pages_duplicate_content"])
    _write_duplicate_rows(writer, "pages_with_schema_types_summary", report["pages_with_schema_types_summary"])

    link_sections = [
        "broken_internal_links",
        "unresolved_internal_targets",
        "redirecting_internal_links",
        "internal_links_to_noindex_like_pages",
        "internal_links_to_canonicalized_pages",
        "redirect_chains_internal",
    ]
    for section in link_sections:
        _write_link_issue_rows(writer, section, report[section])

    return UTF8_BOM + buffer.getvalue()


def build_gsc_top_queries_csv(
    session,
    crawl_job_id: int,
    *,
    page_id: int | None = None,
    date_range_label: str = "last_28_days",
    sort_by: str = "clicks",
    sort_order: str = "desc",
    query_contains: str | None = None,
    query_excludes: str | None = None,
    clicks_min: int | None = None,
    impressions_min: int | None = None,
    ctr_max: float | None = None,
    position_min: float | None = None,
) -> str:
    rows, _, _ = gsc_service.list_top_queries(
        session,
        crawl_job_id,
        page_id=page_id,
        date_range_label=date_range_label,
        page=1,
        page_size=100_000,
        sort_by=sort_by,
        sort_order=sort_order,
        query_contains=query_contains,
        query_excludes=query_excludes,
        clicks_min=clicks_min,
        impressions_min=impressions_min,
        ctr_max=ctr_max,
        position_min=position_min,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "page_id",
            "url",
            "date_range_label",
            "query",
            "clicks",
            "impressions",
            "ctr",
            "position",
            "fetched_at",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.get("id"),
                row.get("page_id"),
                row.get("url"),
                row.get("date_range_label"),
                row.get("query"),
                row.get("clicks"),
                row.get("impressions"),
                row.get("ctr"),
                row.get("position"),
                _serialize_datetime(row.get("fetched_at")),
            ]
        )
    return UTF8_BOM + buffer.getvalue()


def build_opportunities_csv(
    session,
    crawl_job_id: int,
    **filters: Any,
) -> str:
    pages = crawl_job_service.get_all_pages_for_job(session, crawl_job_id, **filters)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "page_id",
            "url",
            "priority_score",
            "priority_level",
            "priority_rationale",
            "primary_opportunity_type",
            "opportunity_count",
            "opportunity_types",
            "clicks",
            "impressions",
            "ctr",
            "position",
            "incoming_internal_links",
            "incoming_internal_linking_pages",
            "technical_issue_count",
        ]
    )

    gsc_date_range = str(filters.get("gsc_date_range") or "last_28_days")
    gsc_suffix = "90d" if gsc_date_range == "last_90_days" else "28d"
    for page in pages:
        if int(page.get("opportunity_count") or 0) == 0:
            continue
        writer.writerow(
            [
                _page_value(page, "id"),
                _page_value(page, "url"),
                _page_value(page, "priority_score"),
                _page_value(page, "priority_level"),
                _page_value(page, "priority_rationale"),
                _page_value(page, "primary_opportunity_type"),
                _page_value(page, "opportunity_count"),
                ", ".join(_page_value(page, "opportunity_types") or []),
                _page_value(page, f"clicks_{gsc_suffix}"),
                _page_value(page, f"impressions_{gsc_suffix}"),
                _page_value(page, f"ctr_{gsc_suffix}"),
                _page_value(page, f"position_{gsc_suffix}"),
                _page_value(page, "incoming_internal_links"),
                _page_value(page, "incoming_internal_linking_pages"),
                _page_value(page, "technical_issue_count"),
            ]
        )
    return UTF8_BOM + buffer.getvalue()


def build_site_content_recommendations_csv(
    session,
    site_id: int,
    **filters: Any,
) -> str:
    rows = content_recommendation_service.get_all_site_content_recommendations(session, site_id, **filters)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "recommendation_type",
            "segment",
            "cluster_key",
            "cluster_label",
            "target_page_id",
            "target_url",
            "page_type",
            "target_page_type",
            "suggested_page_type",
            "priority_score",
            "confidence",
            "impact",
            "effort",
            "cluster_strength",
            "coverage_gap_score",
            "internal_support_score",
            "rationale",
            "signals",
            "reasons",
            "prerequisites",
            "supporting_urls",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.get("id"),
                row.get("recommendation_type"),
                row.get("segment"),
                row.get("cluster_key"),
                row.get("cluster_label"),
                row.get("target_page_id"),
                row.get("target_url"),
                row.get("page_type"),
                row.get("target_page_type"),
                row.get("suggested_page_type"),
                row.get("priority_score"),
                row.get("confidence"),
                row.get("impact"),
                row.get("effort"),
                row.get("cluster_strength"),
                row.get("coverage_gap_score"),
                row.get("internal_support_score"),
                row.get("rationale"),
                " | ".join(row.get("signals") or []),
                " | ".join(row.get("reasons") or []),
                " | ".join(row.get("prerequisites") or []),
                " | ".join(row.get("supporting_urls") or []),
            ]
        )
    return UTF8_BOM + buffer.getvalue()


def build_site_competitive_gap_csv(
    session,
    site_id: int,
    **filters: Any,
) -> str:
    rows = competitive_gap_service.get_all_competitive_gap_rows(session, site_id, **filters)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "gap_key",
            "gap_type",
            "segment",
            "topic_key",
            "topic_label",
            "semantic_cluster_key",
            "canonical_topic_label",
            "merged_topic_count",
            "own_match_status",
            "coverage_type",
            "coverage_confidence",
            "gap_detail_type",
            "own_match_source",
            "target_page_id",
            "target_url",
            "page_type",
            "target_page_type",
            "suggested_page_type",
            "cluster_member_count",
            "cluster_confidence",
            "cluster_intent_profile",
            "cluster_geo_scope",
            "cluster_entities",
            "coverage_best_own_urls",
            "mismatch_notes",
            "supporting_evidence",
            "competitor_ids",
            "competitor_count",
            "competitor_urls",
            "consensus_score",
            "competitor_coverage_score",
            "own_coverage_score",
            "strategy_alignment_score",
            "business_value_score",
            "priority_score",
            "confidence",
            "rationale",
            "signals",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.get("gap_key"),
                row.get("gap_type"),
                row.get("segment"),
                row.get("topic_key"),
                row.get("topic_label"),
                row.get("semantic_cluster_key"),
                row.get("canonical_topic_label"),
                row.get("merged_topic_count"),
                row.get("own_match_status"),
                row.get("coverage_type"),
                row.get("coverage_confidence"),
                row.get("gap_detail_type"),
                row.get("own_match_source"),
                row.get("target_page_id"),
                row.get("target_url"),
                row.get("page_type"),
                row.get("target_page_type"),
                row.get("suggested_page_type"),
                row.get("cluster_member_count"),
                row.get("cluster_confidence"),
                row.get("cluster_intent_profile"),
                row.get("cluster_geo_scope"),
                " | ".join(row.get("cluster_entities") or []),
                " | ".join(row.get("coverage_best_own_urls") or []),
                " | ".join(row.get("mismatch_notes") or []),
                " | ".join(row.get("supporting_evidence") or []),
                ", ".join(str(value) for value in row.get("competitor_ids") or []),
                row.get("competitor_count"),
                " | ".join(row.get("competitor_urls") or []),
                row.get("consensus_score"),
                row.get("competitor_coverage_score"),
                row.get("own_coverage_score"),
                row.get("strategy_alignment_score"),
                row.get("business_value_score"),
                row.get("priority_score"),
                row.get("confidence"),
                row.get("rationale"),
                json.dumps(row.get("signals") or {}, ensure_ascii=True, sort_keys=True),
            ]
        )
    return UTF8_BOM + buffer.getvalue()


def build_internal_linking_csv(
    session,
    crawl_job_id: int,
    **filters: Any,
) -> str:
    rows = internal_linking_service.get_all_internal_linking_issue_rows(session, crawl_job_id, **filters)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "page_id",
            "url",
            "normalized_url",
            "internal_linking_score",
            "issue_count",
            "primary_issue_type",
            "issue_types",
            "priority_score",
            "priority_level",
            "primary_opportunity_type",
            "clicks",
            "impressions",
            "ctr",
            "position",
            "incoming_internal_links",
            "incoming_internal_linking_pages",
            "incoming_follow_links",
            "incoming_follow_linking_pages",
            "incoming_nofollow_links",
            "body_like_links",
            "body_like_linking_pages",
            "body_like_share",
            "boilerplate_like_links",
            "boilerplate_like_linking_pages",
            "boilerplate_like_share",
            "unique_anchor_count",
            "anchor_diversity_score",
            "exact_match_anchor_count",
            "exact_match_anchor_ratio",
            "link_equity_score",
            "link_equity_rank",
            "technical_issue_count",
            "top_anchor_samples",
            "rationale",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row.get("page_id"),
                row.get("url"),
                row.get("normalized_url"),
                row.get("internal_linking_score"),
                row.get("issue_count"),
                row.get("primary_issue_type"),
                ", ".join(row.get("issue_types") or []),
                row.get("priority_score"),
                row.get("priority_level"),
                row.get("primary_opportunity_type"),
                row.get("clicks"),
                row.get("impressions"),
                row.get("ctr"),
                row.get("position"),
                row.get("incoming_internal_links"),
                row.get("incoming_internal_linking_pages"),
                row.get("incoming_follow_links"),
                row.get("incoming_follow_linking_pages"),
                row.get("incoming_nofollow_links"),
                row.get("body_like_links"),
                row.get("body_like_linking_pages"),
                row.get("body_like_share"),
                row.get("boilerplate_like_links"),
                row.get("boilerplate_like_linking_pages"),
                row.get("boilerplate_like_share"),
                row.get("unique_anchor_count"),
                row.get("anchor_diversity_score"),
                row.get("exact_match_anchor_count"),
                row.get("exact_match_anchor_ratio"),
                row.get("link_equity_score"),
                row.get("link_equity_rank"),
                row.get("technical_issue_count"),
                " | ".join(
                    f"{sample.get('anchor_text')} ({sample.get('links')})"
                    for sample in row.get("top_anchor_samples") or []
                ),
                row.get("rationale"),
            ]
        )
    return UTF8_BOM + buffer.getvalue()


def build_cannibalization_csv(
    session,
    crawl_job_id: int,
    **filters: Any,
) -> str:
    rows = cannibalization_service.get_all_cannibalization_cluster_rows(session, crawl_job_id, **filters)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "cluster_id",
            "severity",
            "impact_level",
            "recommendation_type",
            "has_clear_primary",
            "urls_count",
            "shared_queries_count",
            "shared_query_impressions",
            "shared_query_clicks",
            "weighted_overlap",
            "dominant_url",
            "dominant_url_page_id",
            "dominant_url_confidence",
            "dominant_url_score",
            "sample_queries",
            "candidate_urls",
            "rationale",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row.get("cluster_id"),
                row.get("severity"),
                row.get("impact_level"),
                row.get("recommendation_type"),
                row.get("has_clear_primary"),
                row.get("urls_count"),
                row.get("shared_queries_count"),
                row.get("shared_query_impressions"),
                row.get("shared_query_clicks"),
                row.get("weighted_overlap"),
                row.get("dominant_url"),
                row.get("dominant_url_page_id"),
                row.get("dominant_url_confidence"),
                row.get("dominant_url_score"),
                " | ".join(row.get("sample_queries") or []),
                " | ".join(
                    f"{candidate.get('url')} [p{candidate.get('page_id')}]"
                    for candidate in row.get("candidate_urls") or []
                ),
                row.get("rationale"),
            ]
        )
    return UTF8_BOM + buffer.getvalue()


def build_crawl_compare_csv(
    session,
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
) -> str:
    rows = trends_service.get_all_crawl_compare_rows(
        session,
        target_job_id,
        baseline_job_id=baseline_job_id,
        gsc_date_range=gsc_date_range,
        sort_by=sort_by,
        sort_order=sort_order,
        change_type=change_type,
        resolved_issues_min=resolved_issues_min,
        added_issues_min=added_issues_min,
        url_contains=url_contains,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "url",
            "normalized_url",
            "change_type",
            "change_rationale",
            "baseline_page_id",
            "target_page_id",
            "new_in_target",
            "missing_in_target",
            "present_in_both",
            "issues_resolved_count",
            "issues_added_count",
            "resolved_issues",
            "added_issues",
            "baseline_status_code",
            "target_status_code",
            "baseline_canonical_url",
            "target_canonical_url",
            "baseline_noindex_like",
            "target_noindex_like",
            "baseline_non_indexable_like",
            "target_non_indexable_like",
            "baseline_title_length",
            "target_title_length",
            "baseline_meta_description_length",
            "target_meta_description_length",
            "baseline_h1_count",
            "target_h1_count",
            "baseline_word_count",
            "target_word_count",
            "delta_word_count",
            "baseline_images_missing_alt_count",
            "target_images_missing_alt_count",
            "baseline_schema_count",
            "target_schema_count",
            "delta_schema_count",
            "baseline_html_size_bytes",
            "target_html_size_bytes",
            "baseline_was_rendered",
            "target_was_rendered",
            "baseline_js_heavy_like",
            "target_js_heavy_like",
            "baseline_response_time_ms",
            "target_response_time_ms",
            "delta_response_time_ms",
            "baseline_incoming_internal_links",
            "target_incoming_internal_links",
            "delta_incoming_internal_links",
            "baseline_incoming_internal_linking_pages",
            "target_incoming_internal_linking_pages",
            "delta_incoming_internal_linking_pages",
            "baseline_priority_score",
            "target_priority_score",
            "delta_priority_score",
            "baseline_priority_level",
            "target_priority_level",
            "baseline_opportunity_count",
            "target_opportunity_count",
            "baseline_primary_opportunity_type",
            "target_primary_opportunity_type",
            "baseline_opportunity_types",
            "target_opportunity_types",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row.get("url"),
                row.get("normalized_url"),
                row.get("change_type"),
                row.get("change_rationale"),
                row.get("baseline_page_id"),
                row.get("target_page_id"),
                row.get("new_in_target"),
                row.get("missing_in_target"),
                row.get("present_in_both"),
                row.get("issues_resolved_count"),
                row.get("issues_added_count"),
                ", ".join(row.get("resolved_issues") or []),
                ", ".join(row.get("added_issues") or []),
                row.get("baseline_status_code"),
                row.get("target_status_code"),
                row.get("baseline_canonical_url"),
                row.get("target_canonical_url"),
                row.get("baseline_noindex_like"),
                row.get("target_noindex_like"),
                row.get("baseline_non_indexable_like"),
                row.get("target_non_indexable_like"),
                row.get("baseline_title_length"),
                row.get("target_title_length"),
                row.get("baseline_meta_description_length"),
                row.get("target_meta_description_length"),
                row.get("baseline_h1_count"),
                row.get("target_h1_count"),
                row.get("baseline_word_count"),
                row.get("target_word_count"),
                row.get("delta_word_count"),
                row.get("baseline_images_missing_alt_count"),
                row.get("target_images_missing_alt_count"),
                row.get("baseline_schema_count"),
                row.get("target_schema_count"),
                row.get("delta_schema_count"),
                row.get("baseline_html_size_bytes"),
                row.get("target_html_size_bytes"),
                row.get("baseline_was_rendered"),
                row.get("target_was_rendered"),
                row.get("baseline_js_heavy_like"),
                row.get("target_js_heavy_like"),
                row.get("baseline_response_time_ms"),
                row.get("target_response_time_ms"),
                row.get("delta_response_time_ms"),
                row.get("baseline_incoming_internal_links"),
                row.get("target_incoming_internal_links"),
                row.get("delta_incoming_internal_links"),
                row.get("baseline_incoming_internal_linking_pages"),
                row.get("target_incoming_internal_linking_pages"),
                row.get("delta_incoming_internal_linking_pages"),
                row.get("baseline_priority_score"),
                row.get("target_priority_score"),
                row.get("delta_priority_score"),
                row.get("baseline_priority_level"),
                row.get("target_priority_level"),
                row.get("baseline_opportunity_count"),
                row.get("target_opportunity_count"),
                row.get("baseline_primary_opportunity_type"),
                row.get("target_primary_opportunity_type"),
                ", ".join(row.get("baseline_opportunity_types") or []),
                ", ".join(row.get("target_opportunity_types") or []),
            ]
        )

    return UTF8_BOM + buffer.getvalue()


def build_gsc_compare_csv(
    session,
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
) -> str:
    rows = trends_service.get_all_gsc_compare_rows(
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
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "page_id",
            "url",
            "normalized_url",
            "has_baseline_data",
            "has_target_data",
            "baseline_clicks",
            "target_clicks",
            "delta_clicks",
            "baseline_impressions",
            "target_impressions",
            "delta_impressions",
            "baseline_ctr",
            "target_ctr",
            "delta_ctr",
            "baseline_position",
            "target_position",
            "delta_position",
            "baseline_top_queries_count",
            "target_top_queries_count",
            "delta_top_queries_count",
            "overall_trend",
            "clicks_trend",
            "impressions_trend",
            "ctr_trend",
            "position_trend",
            "top_queries_trend",
            "rationale",
            "has_technical_issue",
            "priority_score",
            "priority_level",
            "primary_opportunity_type",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row.get("page_id"),
                row.get("url"),
                row.get("normalized_url"),
                row.get("has_baseline_data"),
                row.get("has_target_data"),
                row.get("baseline_clicks"),
                row.get("target_clicks"),
                row.get("delta_clicks"),
                row.get("baseline_impressions"),
                row.get("target_impressions"),
                row.get("delta_impressions"),
                row.get("baseline_ctr"),
                row.get("target_ctr"),
                row.get("delta_ctr"),
                row.get("baseline_position"),
                row.get("target_position"),
                row.get("delta_position"),
                row.get("baseline_top_queries_count"),
                row.get("target_top_queries_count"),
                row.get("delta_top_queries_count"),
                row.get("overall_trend"),
                row.get("clicks_trend"),
                row.get("impressions_trend"),
                row.get("ctr_trend"),
                row.get("position_trend"),
                row.get("top_queries_trend"),
                row.get("rationale"),
                row.get("has_technical_issue"),
                row.get("priority_score"),
                row.get("priority_level"),
                row.get("primary_opportunity_type"),
            ]
        )

    return UTF8_BOM + buffer.getvalue()


def _write_page_issue_rows(writer: csv.writer, section: str, issues: list[dict[str, Any]]) -> None:
    for issue in issues:
        details_parts = []
        if issue.get("title_length") is not None:
            details_parts.append(f"title_length={issue['title_length']}")
        if issue.get("meta_description_length") is not None:
            details_parts.append(f"meta_description_length={issue['meta_description_length']}")
        if issue.get("h1_count") is not None:
            details_parts.append(f"h1_count={issue['h1_count']}")
        if issue.get("h2_count") is not None:
            details_parts.append(f"h2_count={issue['h2_count']}")
        if issue.get("word_count") is not None:
            details_parts.append(f"word_count={issue['word_count']}")
        if issue.get("images_count") is not None:
            details_parts.append(f"images_count={issue['images_count']}")
        if issue.get("images_missing_alt_count") is not None:
            details_parts.append(f"images_missing_alt_count={issue['images_missing_alt_count']}")
        if issue.get("html_size_bytes") is not None:
            details_parts.append(f"html_size_bytes={issue['html_size_bytes']}")
        if issue.get("canonical_url"):
            details_parts.append(f"canonical_url={issue['canonical_url']}")
        if issue.get("canonical_target_status_code") is not None:
            details_parts.append(f"canonical_target_status_code={issue['canonical_target_status_code']}")
        if issue.get("x_robots_tag"):
            details_parts.append(f"x_robots_tag={issue['x_robots_tag']}")
        if issue.get("was_rendered"):
            details_parts.append("was_rendered=True")
        if issue.get("js_heavy_like"):
            details_parts.append("js_heavy_like=True")
        if issue.get("render_reason"):
            details_parts.append(f"render_reason={issue['render_reason']}")
        if issue.get("render_error_message"):
            details_parts.append(f"render_error_message={issue['render_error_message']}")
        if issue.get("schema_count") is not None:
            details_parts.append(f"schema_count={issue['schema_count']}")
        if issue.get("schema_types_json"):
            details_parts.append(f"schema_types={','.join(issue['schema_types_json'])}")
        writer.writerow(
            [
                section,
                "page_id",
                issue.get("page_id"),
                issue.get("url", ""),
                "; ".join(details_parts),
            ]
        )


def _write_duplicate_rows(writer: csv.writer, section: str, groups: list[dict[str, Any]]) -> None:
    for group in groups:
        urls = [page.get("url", "") for page in group.get("pages", [])]
        writer.writerow([section, group.get("value", ""), group.get("count", 0), "", " | ".join(urls)])


def _write_link_issue_rows(writer: csv.writer, section: str, issues: list[dict[str, Any]]) -> None:
    for issue in issues:
        details_parts = []
        if issue.get("target_status_code") is not None:
            details_parts.append(f"target_status_code={issue.get('target_status_code')}")
        if issue.get("final_url"):
            details_parts.append(f"final_url={issue.get('final_url')}")
        if issue.get("redirect_hops") is not None:
            details_parts.append(f"redirect_hops={issue.get('redirect_hops')}")
        if issue.get("target_canonical_url"):
            details_parts.append(f"target_canonical_url={issue.get('target_canonical_url')}")
        signals = issue.get("signals") or []
        if signals:
            details_parts.append(f"signals={','.join(signals)}")
        writer.writerow([section, "target_url", issue.get("target_url", ""), issue.get("source_url", ""), "; ".join(details_parts)])


def _page_value(page: dict[str, Any], key: str) -> Any:
    return page.get(key)


def _link_value(link: dict[str, Any], key: str) -> Any:
    return link.get(key)


def _serialize_datetime(value: Any) -> str:
    return value.isoformat() if value else ""
