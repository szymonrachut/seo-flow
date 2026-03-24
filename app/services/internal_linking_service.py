from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CrawlJob, Link
from app.schemas.opportunities import PriorityLevel
from app.services.internal_linking_rules import (
    InternalLinkingIssueType,
    InternalLinkingRules,
    get_internal_linking_rules,
)
from app.services.priority_rules import get_priority_rules
from app.services.priority_service import apply_priority_metadata
from app.services.seo_analysis import build_page_records, text_value_missing

GSC_DATE_RANGE_SUFFIX = {
    "last_28_days": "28d",
    "last_90_days": "90d",
}
EMPTY_ANCHOR_KEY = "__empty__"
WORD_SPLIT_RE = re.compile(r"[^a-z0-9]+")


class InternalLinkingServiceError(RuntimeError):
    pass


def build_internal_linking_overview(
    session: Session,
    crawl_job_id: int,
    *,
    gsc_date_range: str = "last_28_days",
    rules: InternalLinkingRules | None = None,
) -> dict[str, Any]:
    all_rows, _ = _build_internal_linking_rows(
        session,
        crawl_job_id,
        gsc_date_range=gsc_date_range,
        rules=rules,
    )
    link_equity_scores = [float(row["link_equity_score"]) for row in all_rows]
    anchor_diversity_scores = [float(row["anchor_diversity_score"]) for row in all_rows]
    body_like_shares = [float(row["body_like_share"]) for row in all_rows if row["incoming_follow_links"] > 0]

    return {
        "crawl_job_id": crawl_job_id,
        "gsc_date_range": gsc_date_range,
        "total_internal_pages": len(all_rows),
        "issue_pages": sum(1 for row in all_rows if int(row["issue_count"]) > 0),
        "orphan_like_pages": sum(1 for row in all_rows if bool(row["orphan_like"])),
        "weakly_linked_important_pages": sum(1 for row in all_rows if bool(row["weakly_linked_important"])),
        "low_anchor_diversity_pages": sum(1 for row in all_rows if bool(row["low_anchor_diversity"])),
        "exact_match_anchor_concentration_pages": sum(
            1 for row in all_rows if bool(row["exact_match_anchor_concentration"])
        ),
        "boilerplate_dominated_pages": sum(1 for row in all_rows if bool(row["boilerplate_dominated"])),
        "low_link_equity_pages": sum(1 for row in all_rows if bool(row["low_link_equity"])),
        "median_link_equity_score": round(float(median(link_equity_scores)) if link_equity_scores else 0.0, 2),
        "average_anchor_diversity_score": round(
            (sum(anchor_diversity_scores) / len(anchor_diversity_scores)) if anchor_diversity_scores else 0.0,
            2,
        ),
        "average_body_like_share": round(
            (sum(body_like_shares) / len(body_like_shares)) if body_like_shares else 0.0,
            4,
        ),
    }


def build_internal_linking_issues(
    session: Session,
    crawl_job_id: int,
    *,
    gsc_date_range: str = "last_28_days",
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "internal_linking_score",
    sort_order: str = "desc",
    issue_type: InternalLinkingIssueType | None = None,
    priority_level: PriorityLevel | None = None,
    opportunity_type: str | None = None,
    url_contains: str | None = None,
    rules: InternalLinkingRules | None = None,
) -> dict[str, Any]:
    _, issue_rows = _build_internal_linking_rows(
        session,
        crawl_job_id,
        gsc_date_range=gsc_date_range,
        rules=rules,
    )
    filtered = _filter_issue_rows(
        issue_rows,
        issue_type=issue_type,
        priority_level=priority_level,
        opportunity_type=opportunity_type,
        url_contains=url_contains,
    )
    _sort_records(filtered, sort_by=sort_by, sort_order=sort_order)
    paginated_items, total_items, total_pages = _paginate_records(filtered, page=page, page_size=page_size)

    return {
        "crawl_job_id": crawl_job_id,
        "gsc_date_range": gsc_date_range,
        "items": paginated_items,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def get_all_internal_linking_issue_rows(
    session: Session,
    crawl_job_id: int,
    *,
    gsc_date_range: str = "last_28_days",
    sort_by: str = "internal_linking_score",
    sort_order: str = "desc",
    issue_type: InternalLinkingIssueType | None = None,
    priority_level: PriorityLevel | None = None,
    opportunity_type: str | None = None,
    url_contains: str | None = None,
    rules: InternalLinkingRules | None = None,
) -> list[dict[str, Any]]:
    _, issue_rows = _build_internal_linking_rows(
        session,
        crawl_job_id,
        gsc_date_range=gsc_date_range,
        rules=rules,
    )
    filtered = _filter_issue_rows(
        issue_rows,
        issue_type=issue_type,
        priority_level=priority_level,
        opportunity_type=opportunity_type,
        url_contains=url_contains,
    )
    _sort_records(filtered, sort_by=sort_by, sort_order=sort_order)
    return filtered


def get_all_internal_linking_rows(
    session: Session,
    crawl_job_id: int,
    *,
    gsc_date_range: str = "last_28_days",
    sort_by: str = "internal_linking_score",
    sort_order: str = "desc",
    rules: InternalLinkingRules | None = None,
) -> list[dict[str, Any]]:
    all_rows, _ = _build_internal_linking_rows(
        session,
        crawl_job_id,
        gsc_date_range=gsc_date_range,
        rules=rules,
    )
    _sort_records(all_rows, sort_by=sort_by, sort_order=sort_order)
    return all_rows


def _build_internal_linking_rows(
    session: Session,
    crawl_job_id: int,
    *,
    gsc_date_range: str,
    rules: InternalLinkingRules | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    _get_crawl_job_or_raise(session, crawl_job_id)
    resolved_rules = rules or get_internal_linking_rules()
    priority_rules = get_priority_rules()
    suffix = _resolve_gsc_suffix(gsc_date_range)

    page_records = build_page_records(session, crawl_job_id)
    apply_priority_metadata(page_records, gsc_date_range=gsc_date_range)

    internal_pages = [record for record in page_records if bool(record.get("is_internal"))]
    page_by_id = {int(record["id"]): record for record in internal_pages}
    page_by_normalized_url = {
        str(record["normalized_url"]): record
        for record in internal_pages
        if not text_value_missing(record.get("normalized_url"))
    }

    links = session.scalars(
        select(Link)
        .where(Link.crawl_job_id == crawl_job_id, Link.is_internal.is_(True))
        .order_by(Link.id.asc())
    ).all()
    link_inputs = _collect_link_inputs(links, page_by_id, page_by_normalized_url)
    boilerplate_anchors = _classify_boilerplate_anchors(link_inputs, resolved_rules)
    page_rank = _compute_link_equity_scores(link_inputs, boilerplate_anchors, internal_pages, resolved_rules)
    link_equity_score_map, link_equity_rank_map = _normalize_link_equity(page_rank)
    per_page_stats = _build_per_page_stats(link_inputs, boilerplate_anchors)

    all_rows: list[dict[str, Any]] = []
    for record in internal_pages:
        row = _build_row(
            record,
            per_page_stats=per_page_stats.get(int(record["id"]), {}),
            link_equity_score=link_equity_score_map.get(int(record["id"]), 0.0),
            link_equity_rank=link_equity_rank_map.get(int(record["id"]), len(internal_pages)),
            gsc_suffix=suffix,
            priority_rules=priority_rules,
            rules=resolved_rules,
        )
        all_rows.append(row)

    issue_rows = [row for row in all_rows if int(row["issue_count"]) > 0]
    return all_rows, issue_rows


def _collect_link_inputs(
    links: list[Link],
    page_by_id: dict[int, dict[str, Any]],
    page_by_normalized_url: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    link_inputs: list[dict[str, Any]] = []
    for link in links:
        source_page = page_by_id.get(int(link.source_page_id))
        if source_page is None or text_value_missing(link.target_normalized_url):
            continue
        target_page = page_by_normalized_url.get(str(link.target_normalized_url))
        if target_page is None or int(source_page["id"]) == int(target_page["id"]):
            continue

        anchor_display = _anchor_display_value(link.anchor_text)
        anchor_normalized = _normalize_phrase(anchor_display)
        anchor_key = anchor_normalized if anchor_normalized is not None else EMPTY_ANCHOR_KEY
        link_inputs.append(
            {
                "source_id": int(source_page["id"]),
                "source_url": source_page["url"],
                "source_depth": int(source_page.get("depth") or 0),
                "target_id": int(target_page["id"]),
                "target_url": target_page["url"],
                "target_normalized_url": target_page["normalized_url"],
                "anchor_text": anchor_display,
                "anchor_normalized": anchor_normalized,
                "anchor_key": anchor_key,
                "is_nofollow": bool(link.is_nofollow),
            }
        )
    return link_inputs


def _classify_boilerplate_anchors(
    link_inputs: list[dict[str, Any]],
    rules: InternalLinkingRules,
) -> dict[int, set[str]]:
    target_sources: dict[int, set[int]] = defaultdict(set)
    target_anchor_stats: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)

    for link in link_inputs:
        if bool(link["is_nofollow"]):
            continue
        target_id = int(link["target_id"])
        source_id = int(link["source_id"])
        target_sources[target_id].add(source_id)
        anchor_key = str(link["anchor_key"])
        anchor_entry = target_anchor_stats[target_id].setdefault(
            anchor_key,
            {"links": 0, "sources": set()},
        )
        anchor_entry["links"] += 1
        anchor_entry["sources"].add(source_id)

    boilerplate_anchors: dict[int, set[str]] = defaultdict(set)
    for target_id, anchor_map in target_anchor_stats.items():
        total_linking_pages = len(target_sources[target_id])
        if total_linking_pages < rules.boilerplate_min_linking_pages:
            continue
        for anchor_key, stats in anchor_map.items():
            source_share = len(stats["sources"]) / total_linking_pages
            if (
                source_share >= rules.boilerplate_anchor_share_threshold
                and int(stats["links"]) >= rules.boilerplate_min_links
            ):
                boilerplate_anchors[target_id].add(anchor_key)
    return boilerplate_anchors


def _compute_link_equity_scores(
    link_inputs: list[dict[str, Any]],
    boilerplate_anchors: dict[int, set[str]],
    internal_pages: list[dict[str, Any]],
    rules: InternalLinkingRules,
) -> dict[int, float]:
    page_ids = [int(page["id"]) for page in internal_pages]
    if not page_ids:
        return {}

    unique_edges: dict[tuple[int, int], float] = {}
    for link in link_inputs:
        if bool(link["is_nofollow"]):
            continue
        source_id = int(link["source_id"])
        target_id = int(link["target_id"])
        weight = (
            rules.boilerplate_like_edge_weight
            if str(link["anchor_key"]) in boilerplate_anchors.get(target_id, set())
            else rules.body_like_edge_weight
        )
        edge_key = (source_id, target_id)
        unique_edges[edge_key] = max(float(unique_edges.get(edge_key, 0.0)), float(weight))

    outgoing_edges: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for (source_id, target_id), weight in unique_edges.items():
        outgoing_edges[source_id].append((target_id, float(weight)))

    total_pages = len(page_ids)
    base_score = 1.0 / total_pages
    current = {page_id: base_score for page_id in page_ids}
    for _ in range(rules.link_equity_iterations):
        next_scores = {page_id: rules.link_equity_damping / total_pages for page_id in page_ids}
        sink_score = 0.0
        for page_id in page_ids:
            edges = outgoing_edges.get(page_id, [])
            if not edges:
                sink_score += current[page_id]
                continue
            total_weight = sum(weight for _, weight in edges)
            if total_weight <= 0:
                sink_score += current[page_id]
                continue
            distributable = (1.0 - rules.link_equity_damping) * current[page_id]
            for target_id, weight in edges:
                next_scores[target_id] += distributable * (weight / total_weight)
        if sink_score > 0:
            sink_bonus = ((1.0 - rules.link_equity_damping) * sink_score) / total_pages
            for page_id in page_ids:
                next_scores[page_id] += sink_bonus
        current = next_scores
    return current


def _normalize_link_equity(page_rank: dict[int, float]) -> tuple[dict[int, float], dict[int, int]]:
    if not page_rank:
        return {}, {}
    sorted_items = sorted(page_rank.items(), key=lambda item: item[1], reverse=True)
    max_score = max(score for _, score in sorted_items)
    min_score = min(score for _, score in sorted_items)
    if math.isclose(max_score, min_score):
        normalized = {page_id: 100.0 for page_id, _ in sorted_items}
    else:
        normalized = {
            page_id: round(((score - min_score) / (max_score - min_score)) * 100.0, 2)
            for page_id, score in sorted_items
        }
    ranks = {page_id: index + 1 for index, (page_id, _) in enumerate(sorted_items)}
    return normalized, ranks


def _build_per_page_stats(
    link_inputs: list[dict[str, Any]],
    boilerplate_anchors: dict[int, set[str]],
) -> dict[int, dict[str, Any]]:
    stats_by_page: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "incoming_follow_links": 0,
            "incoming_follow_sources": set(),
            "incoming_nofollow_links": 0,
            "incoming_nofollow_sources": set(),
            "body_like_links": 0,
            "body_like_sources": set(),
            "boilerplate_like_links": 0,
            "boilerplate_like_sources": set(),
            "anchor_stats": {},
        }
    )

    for link in link_inputs:
        target_id = int(link["target_id"])
        source_id = int(link["source_id"])
        page_stats = stats_by_page[target_id]

        if bool(link["is_nofollow"]):
            page_stats["incoming_nofollow_links"] += 1
            page_stats["incoming_nofollow_sources"].add(source_id)
            continue

        page_stats["incoming_follow_links"] += 1
        page_stats["incoming_follow_sources"].add(source_id)

        is_boilerplate = str(link["anchor_key"]) in boilerplate_anchors.get(target_id, set())
        if is_boilerplate:
            page_stats["boilerplate_like_links"] += 1
            page_stats["boilerplate_like_sources"].add(source_id)
        else:
            page_stats["body_like_links"] += 1
            page_stats["body_like_sources"].add(source_id)

        if text_value_missing(link.get("anchor_text")):
            continue
        anchor_key = str(link["anchor_key"])
        anchor_entry = page_stats["anchor_stats"].setdefault(
            anchor_key,
            {
                "links": 0,
                "sources": set(),
                "display_counts": Counter(),
                "normalized": link.get("anchor_normalized"),
                "boilerplate_likely": is_boilerplate,
            },
        )
        anchor_entry["links"] += 1
        anchor_entry["sources"].add(source_id)
        anchor_entry["display_counts"][str(link["anchor_text"])] += 1
        anchor_entry["boilerplate_likely"] = bool(anchor_entry["boilerplate_likely"] or is_boilerplate)

    return stats_by_page


def _build_row(
    record: dict[str, Any],
    *,
    per_page_stats: dict[str, Any],
    link_equity_score: float,
    link_equity_rank: int,
    gsc_suffix: str,
    priority_rules,
    rules: InternalLinkingRules,
) -> dict[str, Any]:
    page_id = int(record["id"])
    anchor_stats = per_page_stats.get("anchor_stats", {})
    anchor_references = sum(int(anchor["links"]) for anchor in anchor_stats.values())
    unique_anchor_count = len(anchor_stats)
    dominant_anchor_count = max((int(anchor["links"]) for anchor in anchor_stats.values()), default=0)
    dominant_anchor_ratio = (dominant_anchor_count / anchor_references) if anchor_references > 0 else 0.0
    anchor_diversity_score = round(_normalized_anchor_entropy(anchor_stats) * 100.0, 2)
    exact_match_targets = _build_exact_match_targets(record, rules)
    exact_match_anchor_count = sum(
        int(anchor["links"])
        for anchor in anchor_stats.values()
        if anchor.get("normalized") and anchor.get("normalized") in exact_match_targets
    )
    exact_match_anchor_ratio = round(
        (exact_match_anchor_count / anchor_references) if anchor_references > 0 else 0.0,
        4,
    )

    top_anchor_samples: list[dict[str, Any]] = []
    for _, anchor in sorted(
        anchor_stats.items(),
        key=lambda item: (-int(item[1]["links"]), -len(item[1]["sources"]), str(item[0])),
    )[: rules.anchor_preview_limit]:
        anchor_normalized = anchor.get("normalized")
        top_anchor_samples.append(
            {
                "anchor_text": anchor["display_counts"].most_common(1)[0][0],
                "links": int(anchor["links"]),
                "linking_pages": len(anchor["sources"]),
                "exact_match": bool(anchor_normalized and anchor_normalized in exact_match_targets),
                "boilerplate_likely": bool(anchor["boilerplate_likely"]),
            }
        )

    incoming_follow_links = int(per_page_stats.get("incoming_follow_links", 0))
    incoming_follow_linking_pages = len(per_page_stats.get("incoming_follow_sources", set()))
    body_like_links = int(per_page_stats.get("body_like_links", 0))
    body_like_linking_pages = len(per_page_stats.get("body_like_sources", set()))
    boilerplate_like_links = int(per_page_stats.get("boilerplate_like_links", 0))
    boilerplate_like_linking_pages = len(per_page_stats.get("boilerplate_like_sources", set()))
    body_like_share = round((body_like_links / incoming_follow_links) if incoming_follow_links > 0 else 0.0, 4)
    boilerplate_like_share = round(
        (boilerplate_like_links / incoming_follow_links) if incoming_follow_links > 0 else 0.0,
        4,
    )

    clicks = int(record.get(f"clicks_{gsc_suffix}") or 0)
    impressions = int(record.get(f"impressions_{gsc_suffix}") or 0)
    ctr = float(record.get(f"ctr_{gsc_suffix}") or 0.0)
    position = float(record.get(f"position_{gsc_suffix}")) if record.get(f"position_{gsc_suffix}") is not None else None
    priority_score = int(record.get("priority_score") or 0)
    important_page = _is_important_page(
        record,
        clicks=clicks,
        impressions=impressions,
        priority_rules=priority_rules,
        rules=rules,
    )

    orphan_like = bool(
        int(record.get("depth") or 0) > rules.orphan_like_excluded_depth
        and incoming_follow_linking_pages <= rules.orphan_like_max_follow_linking_pages
    )
    weakly_linked_important = bool(
        important_page
        and incoming_follow_links <= rules.weakly_linked_max_follow_links
        and incoming_follow_linking_pages <= rules.weakly_linked_max_follow_linking_pages
    )
    low_anchor_diversity = bool(
        anchor_references >= rules.anchor_diversity_min_anchor_links
        and (
            anchor_diversity_score < rules.anchor_diversity_score_threshold
            or (
                unique_anchor_count <= rules.anchor_diversity_max_unique_anchors
                and dominant_anchor_ratio >= rules.anchor_diversity_dominant_anchor_ratio_threshold
            )
        )
    )
    exact_match_anchor_concentration = bool(
        anchor_references >= rules.exact_match_min_anchor_links
        and exact_match_anchor_count >= rules.exact_match_min_count
        and exact_match_anchor_ratio >= rules.exact_match_ratio_threshold
    )
    boilerplate_dominated = bool(
        incoming_follow_linking_pages >= rules.boilerplate_min_linking_pages
        and boilerplate_like_links >= rules.boilerplate_min_links
        and boilerplate_like_share >= rules.boilerplate_dominated_ratio_threshold
        and body_like_linking_pages <= rules.boilerplate_body_like_max_linking_pages
    )
    low_link_equity = bool(important_page and link_equity_score < rules.low_link_equity_score_threshold)

    issue_types = [
        issue_type
        for issue_type, is_active in [
            ("ORPHAN_LIKE", orphan_like),
            ("WEAKLY_LINKED_IMPORTANT", weakly_linked_important),
            ("LOW_LINK_EQUITY", low_link_equity),
            ("BOILERPLATE_DOMINATED", boilerplate_dominated),
            ("EXACT_MATCH_ANCHOR_CONCENTRATION", exact_match_anchor_concentration),
            ("LOW_ANCHOR_DIVERSITY", low_anchor_diversity),
        ]
        if is_active
    ]
    internal_linking_score = min(
        100,
        sum(int(rules.issue_weights[issue_type]) for issue_type in issue_types)
        + min(25, max(0, priority_score // 4)),
    )

    return {
        "page_id": page_id,
        "url": record["url"],
        "normalized_url": record["normalized_url"],
        "priority_score": priority_score,
        "priority_level": record.get("priority_level") or "low",
        "priority_rationale": record.get("priority_rationale") or "",
        "primary_opportunity_type": record.get("primary_opportunity_type"),
        "opportunity_types": list(record.get("opportunity_types") or []),
        "technical_issue_count": int(record.get("technical_issue_count") or 0),
        "clicks": clicks,
        "impressions": impressions,
        "ctr": ctr,
        "position": position,
        "incoming_internal_links": int(record.get("incoming_internal_links") or 0),
        "incoming_internal_linking_pages": int(record.get("incoming_internal_linking_pages") or 0),
        "incoming_follow_links": incoming_follow_links,
        "incoming_follow_linking_pages": incoming_follow_linking_pages,
        "incoming_nofollow_links": int(per_page_stats.get("incoming_nofollow_links", 0)),
        "body_like_links": body_like_links,
        "body_like_linking_pages": body_like_linking_pages,
        "boilerplate_like_links": boilerplate_like_links,
        "boilerplate_like_linking_pages": boilerplate_like_linking_pages,
        "body_like_share": body_like_share,
        "boilerplate_like_share": boilerplate_like_share,
        "unique_anchor_count": unique_anchor_count,
        "anchor_diversity_score": anchor_diversity_score,
        "exact_match_anchor_count": exact_match_anchor_count,
        "exact_match_anchor_ratio": exact_match_anchor_ratio,
        "link_equity_score": round(float(link_equity_score), 2),
        "link_equity_rank": int(link_equity_rank),
        "internal_linking_score": int(internal_linking_score),
        "issue_count": len(issue_types),
        "orphan_like": orphan_like,
        "weakly_linked_important": weakly_linked_important,
        "low_anchor_diversity": low_anchor_diversity,
        "exact_match_anchor_concentration": exact_match_anchor_concentration,
        "boilerplate_dominated": boilerplate_dominated,
        "low_link_equity": low_link_equity,
        "issue_types": issue_types,
        "primary_issue_type": issue_types[0] if issue_types else None,
        "top_anchor_samples": top_anchor_samples,
        "rationale": _build_row_rationale(
            issue_types=issue_types,
            incoming_follow_links=incoming_follow_links,
            incoming_follow_linking_pages=incoming_follow_linking_pages,
            body_like_linking_pages=body_like_linking_pages,
            boilerplate_like_share=boilerplate_like_share,
            anchor_references=anchor_references,
            unique_anchor_count=unique_anchor_count,
            exact_match_anchor_ratio=exact_match_anchor_ratio,
            link_equity_score=link_equity_score,
        ),
    }


def _is_important_page(
    record: dict[str, Any],
    *,
    clicks: int,
    impressions: int,
    priority_rules,
    rules: InternalLinkingRules,
) -> bool:
    priority_level = str(record.get("priority_level") or "low").lower()
    return bool(
        int(record.get("priority_score") or 0) >= rules.important_priority_score_threshold
        or priority_level in {"high", "critical"}
        or impressions >= int(priority_rules.important_impressions_threshold)
        or clicks >= int(priority_rules.important_clicks_threshold)
    )


def _build_row_rationale(
    *,
    issue_types: list[InternalLinkingIssueType],
    incoming_follow_links: int,
    incoming_follow_linking_pages: int,
    body_like_linking_pages: int,
    boilerplate_like_share: float,
    anchor_references: int,
    unique_anchor_count: int,
    exact_match_anchor_ratio: float,
    link_equity_score: float,
) -> str:
    clauses: list[str] = []
    for issue_type in issue_types:
        if issue_type == "ORPHAN_LIKE":
            clauses.append("no followed internal links from crawled pages")
        elif issue_type == "WEAKLY_LINKED_IMPORTANT":
            clauses.append(
                f"important URL has only {incoming_follow_links} followed links from {incoming_follow_linking_pages} linking pages"
            )
        elif issue_type == "LOW_LINK_EQUITY":
            clauses.append(f"link equity proxy is low at {link_equity_score:.1f}")
        elif issue_type == "BOILERPLATE_DOMINATED":
            clauses.append(
                f"{boilerplate_like_share * 100:.0f}% of followed support looks boilerplate-like and only {body_like_linking_pages} linking pages look body-like"
            )
        elif issue_type == "EXACT_MATCH_ANCHOR_CONCENTRATION":
            clauses.append(f"{exact_match_anchor_ratio * 100:.0f}% of anchor references look exact-match")
        elif issue_type == "LOW_ANCHOR_DIVERSITY":
            clauses.append(f"{unique_anchor_count} unique anchors across {anchor_references} anchor references")
        if len(clauses) == 2:
            break

    if not clauses:
        return "internal linking profile looks balanced in the current crawl snapshot"
    if len(clauses) == 1:
        return clauses[0]
    return f"{clauses[0]}; {clauses[1]}"


def _build_exact_match_targets(record: dict[str, Any], rules: InternalLinkingRules) -> set[str]:
    candidates = {
        _normalize_phrase(record.get("title")),
        _normalize_phrase(record.get("h1")),
        _normalize_phrase(_slug_to_phrase(record.get("normalized_url"))),
    }
    return {
        candidate
        for candidate in candidates
        if candidate is not None
        and candidate not in rules.generic_anchor_terms
        and len(candidate.split()) >= rules.exact_match_min_words
    }


def _slug_to_phrase(url: Any) -> str | None:
    if text_value_missing(url):
        return None
    url_text = str(url).strip().rstrip("/")
    if "/" not in url_text:
        return None
    slug = url_text.rsplit("/", 1)[-1]
    return slug.replace("-", " ").replace("_", " ") if slug else None


def _normalized_anchor_entropy(anchor_stats: dict[str, dict[str, Any]]) -> float:
    total_links = sum(int(anchor["links"]) for anchor in anchor_stats.values())
    if total_links <= 0 or len(anchor_stats) <= 1:
        return 0.0
    entropy = 0.0
    for anchor in anchor_stats.values():
        probability = int(anchor["links"]) / total_links
        entropy -= probability * math.log2(probability)
    max_entropy = math.log2(len(anchor_stats))
    return entropy / max_entropy if max_entropy > 0 else 0.0


def _filter_issue_rows(
    rows: list[dict[str, Any]],
    *,
    issue_type: InternalLinkingIssueType | None,
    priority_level: PriorityLevel | None,
    opportunity_type: str | None,
    url_contains: str | None,
) -> list[dict[str, Any]]:
    filtered = rows
    if issue_type:
        filtered = [row for row in filtered if issue_type in (row.get("issue_types") or [])]
    if priority_level:
        token = str(priority_level).lower()
        filtered = [row for row in filtered if str(row.get("priority_level") or "").lower() == token]
    if opportunity_type:
        token = str(opportunity_type).upper()
        filtered = [
            row
            for row in filtered
            if token in {str(item).upper() for item in row.get("opportunity_types") or []}
        ]
    if url_contains:
        token = str(url_contains).strip().lower()
        if token:
            filtered = [row for row in filtered if token in str(row.get("url") or "").lower()]
    return filtered


def _sort_records(rows: list[dict[str, Any]], *, sort_by: str, sort_order: str) -> None:
    present = [row for row in rows if row.get(sort_by) is not None]
    missing = [row for row in rows if row.get(sort_by) is None]
    present.sort(
        key=lambda row: (
            _normalize_sort_value(row.get(sort_by)),
            _normalize_sort_value(row.get("url")),
        ),
        reverse=sort_order == "desc",
    )
    missing.sort(key=lambda row: _normalize_sort_value(row.get("url")))
    rows[:] = present + missing


def _paginate_records(
    rows: list[dict[str, Any]],
    *,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int, int]:
    total_items = len(rows)
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    start = (page - 1) * page_size
    end = start + page_size
    return rows[start:end], total_items, total_pages


def _anchor_display_value(value: Any) -> str:
    if text_value_missing(value):
        return ""
    return str(value).strip()


def _normalize_phrase(value: Any) -> str | None:
    if text_value_missing(value):
        return None
    normalized = WORD_SPLIT_RE.sub(" ", str(value).lower()).strip()
    normalized = " ".join(part for part in normalized.split() if part)
    return normalized or None


def _normalize_sort_value(value: Any) -> tuple[int, Any]:
    if value is None:
        return (1, "")
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, str):
        return (0, value.lower())
    return (0, value)


def _resolve_gsc_suffix(gsc_date_range: str) -> str:
    suffix = GSC_DATE_RANGE_SUFFIX.get(gsc_date_range)
    if suffix is None:
        raise InternalLinkingServiceError(f"Unsupported GSC date range '{gsc_date_range}'.")
    return suffix


def _get_crawl_job_or_raise(session: Session, crawl_job_id: int) -> CrawlJob:
    crawl_job = session.get(CrawlJob, crawl_job_id)
    if crawl_job is None:
        raise InternalLinkingServiceError(f"Crawl job {crawl_job_id} not found.")
    return crawl_job
