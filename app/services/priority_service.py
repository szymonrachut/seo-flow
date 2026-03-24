from __future__ import annotations

from typing import Any

from app.services.priority_rules import (
    EffortLevel,
    ImpactLevel,
    OpportunityType,
    PriorityLevel,
    PriorityRules,
    get_priority_rules,
)

GSC_DATE_RANGE_SUFFIX = {
    "last_28_days": "28d",
    "last_90_days": "90d",
}

SNIPPET_ISSUE_KEYS = (
    "title_missing",
    "title_too_short",
    "title_too_long",
    "meta_description_missing",
    "meta_description_too_short",
    "meta_description_too_long",
)
CONTENT_ISSUE_KEYS = (
    "thin_content",
    "h1_missing",
    "multiple_h1",
    "missing_h2",
    "duplicate_content",
)
CRITICAL_ISSUE_KEYS = (
    "noindex_like",
    "non_indexable_like",
    "canonical_to_other_url",
    "canonical_to_non_200",
    "canonical_to_redirect",
)
LOW_EFFORT_ISSUE_KEYS = (
    "title_missing",
    "title_too_short",
    "title_too_long",
    "meta_description_missing",
    "meta_description_too_short",
    "meta_description_too_long",
    "h1_missing",
    "missing_h2",
    "missing_alt_images",
)
ISSUE_EXPLANATIONS = {
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
    "canonical_to_other_url": "canonical points to another URL",
    "canonical_to_non_200": "canonical target is non-200",
    "canonical_to_redirect": "canonical target redirects",
    "noindex_like": "page looks noindex-like",
    "non_indexable_like": "page looks non-indexable",
    "thin_content": "thin content",
    "duplicate_content": "duplicate content",
    "missing_alt_images": "missing alt text",
    "oversized": "oversized page",
}


def apply_priority_metadata(
    records: list[dict[str, Any]],
    *,
    gsc_date_range: str,
    rules: PriorityRules | None = None,
) -> list[dict[str, Any]]:
    resolved_rules = rules or get_priority_rules()
    suffix = _resolve_gsc_suffix(gsc_date_range)

    for record in records:
        metrics = _active_metrics(record, suffix)
        issue_weight_total = _issue_weight_total(record, resolved_rules)
        opportunities = _classify_opportunities(record, metrics, resolved_rules)
        primary_opportunity = opportunities[0] if opportunities else None

        traffic_component = _traffic_component(metrics, resolved_rules)
        issue_component = min(resolved_rules.issue_component_cap, issue_weight_total)
        opportunity_component = min(
            resolved_rules.opportunity_component_cap,
            sum(resolved_rules.opportunity_priority_bonuses[item["type"]] for item in opportunities),
        )
        internal_linking_component = _internal_linking_component(record, metrics, resolved_rules)
        priority_score = min(
            100,
            traffic_component + issue_component + opportunity_component + internal_linking_component,
        )
        priority_level = _priority_level(priority_score, resolved_rules)

        record["priority_score"] = int(priority_score)
        record["priority_level"] = priority_level
        record["traffic_component"] = int(traffic_component)
        record["issue_component"] = int(issue_component)
        record["opportunity_component"] = int(opportunity_component)
        record["internal_linking_component"] = int(internal_linking_component)
        record["opportunity_count"] = len(opportunities)
        record["primary_opportunity_type"] = primary_opportunity["type"] if primary_opportunity else None
        record["opportunity_types"] = [item["type"] for item in opportunities]
        record["priority_rationale"] = _priority_rationale(
            record,
            metrics,
            primary_opportunity=primary_opportunity,
            rules=resolved_rules,
        )
        record["opportunities"] = opportunities

    return records


def build_opportunities_summary(
    records: list[dict[str, Any]],
    *,
    gsc_date_range: str,
    sort_by: str = "count",
    sort_order: str = "desc",
    top_pages_limit: int = 5,
    rules: PriorityRules | None = None,
) -> dict[str, Any]:
    resolved_rules = rules or get_priority_rules()
    suffix = _resolve_gsc_suffix(gsc_date_range)

    groups: list[dict[str, Any]] = []
    for opportunity_type in resolved_rules.opportunity_order:
        matched_pages = [record for record in records if opportunity_type in (record.get("opportunity_types") or [])]
        if not matched_pages:
            continue

        top_pages = sorted(
            matched_pages,
            key=lambda record: (
                int(_find_opportunity(record, opportunity_type)["opportunity_score"]),
                int(record.get("priority_score") or 0),
            ),
            reverse=True,
        )[:top_pages_limit]

        groups.append(
            {
                "type": opportunity_type,
                "count": len(matched_pages),
                "top_priority_score": max(int(record.get("priority_score") or 0) for record in matched_pages),
                "top_opportunity_score": max(
                    int(_find_opportunity(record, opportunity_type)["opportunity_score"])
                    for record in matched_pages
                ),
                "top_pages": [_build_opportunity_page_preview(record, opportunity_type, suffix) for record in top_pages],
            }
        )

    reverse = sort_order == "desc"
    sort_mapping = {
        "count": lambda item: int(item["count"]),
        "top_priority_score": lambda item: int(item["top_priority_score"]),
        "top_opportunity_score": lambda item: int(item["top_opportunity_score"]),
        "type": lambda item: str(item["type"]).lower(),
    }
    groups.sort(key=sort_mapping.get(sort_by, sort_mapping["count"]), reverse=reverse)

    top_priority_pages = sorted(
        [record for record in records if int(record.get("opportunity_count") or 0) > 0],
        key=lambda record: (int(record.get("priority_score") or 0), int(record.get("opportunity_count") or 0)),
        reverse=True,
    )[:top_pages_limit]

    return {
        "gsc_date_range": gsc_date_range,
        "total_pages": len(records),
        "pages_with_opportunities": sum(1 for record in records if int(record.get("opportunity_count") or 0) > 0),
        "high_priority_pages": sum(1 for record in records if record.get("priority_level") in {"high", "critical"}),
        "critical_priority_pages": sum(1 for record in records if record.get("priority_level") == "critical"),
        "groups": groups,
        "top_priority_pages": [
            _build_opportunity_page_preview(record, None, suffix)
            for record in top_priority_pages
        ],
    }


def _resolve_gsc_suffix(gsc_date_range: str) -> str:
    suffix = GSC_DATE_RANGE_SUFFIX.get(gsc_date_range)
    if suffix is None:
        raise ValueError(f"Unsupported gsc_date_range '{gsc_date_range}'.")
    return suffix


def _active_metrics(record: dict[str, Any], suffix: str) -> dict[str, Any]:
    return {
        "clicks": int(record.get(f"clicks_{suffix}") or 0),
        "impressions": int(record.get(f"impressions_{suffix}") or 0),
        "ctr": float(record.get(f"ctr_{suffix}") or 0.0),
        "position": float(record.get(f"position_{suffix}")) if record.get(f"position_{suffix}") is not None else None,
        "top_queries_count": int(record.get(f"top_queries_count_{suffix}") or 0),
    }


def _issue_weight_total(record: dict[str, Any], rules: PriorityRules) -> int:
    return sum(weight for key, weight in rules.issue_weights.items() if bool(record.get(key)))


def _traffic_component(metrics: dict[str, Any], rules: PriorityRules) -> int:
    score = 0
    impressions = int(metrics["impressions"])
    clicks = int(metrics["clicks"])
    position = metrics["position"]
    top_queries_count = int(metrics["top_queries_count"])

    if impressions >= rules.very_high_impressions_threshold:
        score += 12
    elif impressions >= rules.high_impressions_threshold:
        score += 9
    elif impressions >= rules.important_impressions_threshold:
        score += 6
    elif impressions >= rules.traffic_impressions_threshold:
        score += 3

    if clicks >= 50:
        score += 10
    elif clicks >= 20:
        score += 8
    elif clicks >= rules.important_clicks_threshold:
        score += 6
    elif clicks >= rules.traffic_clicks_threshold:
        score += 3
    elif clicks >= rules.traffic_presence_clicks_threshold:
        score += 1

    if position is not None:
        if rules.quick_win_position_min <= float(position) <= rules.quick_win_position_max:
            score += 5
        elif 1.0 <= float(position) < rules.quick_win_position_min:
            score += 4
        elif float(position) <= 30:
            score += 2

    if top_queries_count >= rules.top_queries_reference:
        score += 3
    elif top_queries_count >= 3:
        score += 2
    elif top_queries_count >= 1:
        score += 1

    return min(30, score)


def _internal_linking_component(record: dict[str, Any], metrics: dict[str, Any], rules: PriorityRules) -> int:
    impressions = int(metrics["impressions"])
    clicks = int(metrics["clicks"])
    incoming_internal_links = int(record.get("incoming_internal_links") or 0)
    incoming_linking_pages = int(record.get("incoming_internal_linking_pages") or 0)

    if impressions < rules.underlinked_impressions_threshold and clicks < rules.traffic_clicks_threshold:
        return 0

    if (
        incoming_internal_links <= rules.underlinked_max_internal_links
        or incoming_linking_pages <= rules.underlinked_max_unique_linking_pages
    ):
        return min(rules.internal_linking_component_cap, 8)

    if (
        incoming_internal_links <= rules.moderate_underlinked_max_internal_links
        or incoming_linking_pages <= rules.moderate_underlinked_max_unique_linking_pages
    ):
        return min(rules.internal_linking_component_cap, 4)

    return 0


def _priority_level(priority_score: int, rules: PriorityRules) -> PriorityLevel:
    if priority_score >= rules.priority_level_thresholds["critical"]:
        return "critical"
    if priority_score >= rules.priority_level_thresholds["high"]:
        return "high"
    if priority_score >= rules.priority_level_thresholds["medium"]:
        return "medium"
    return "low"


def _priority_rationale(
    record: dict[str, Any],
    metrics: dict[str, Any],
    *,
    primary_opportunity: dict[str, Any] | None,
    rules: PriorityRules,
) -> str:
    if primary_opportunity is not None:
        return str(primary_opportunity["rationale"])

    issues = _top_issue_labels(record, limit=2)
    impressions = int(metrics["impressions"])
    clicks = int(metrics["clicks"])
    if impressions > 0 or clicks > 0:
        traffic_bits: list[str] = []
        if impressions > 0:
            traffic_bits.append(f"{impressions} impressions")
        if clicks > 0:
            traffic_bits.append(f"{clicks} clicks")
        if issues:
            return f"URL has {' and '.join(traffic_bits)} with {', '.join(issues)}."
        return f"URL has {' and '.join(traffic_bits)} but limited actionable issues."

    if issues:
        return f"URL has {', '.join(issues)} but no strong traffic signal in the selected GSC range."

    if _internal_linking_component(record, metrics, rules) > 0:
        return "URL has search demand but weak internal linking support."

    return "URL has low traffic and limited optimization pressure in the selected GSC range."


def _classify_opportunities(
    record: dict[str, Any],
    metrics: dict[str, Any],
    rules: PriorityRules,
) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    impressions = int(metrics["impressions"])
    clicks = int(metrics["clicks"])
    ctr = float(metrics["ctr"] or 0.0)
    position = metrics["position"]
    issue_weight_total = _issue_weight_total(record, rules)
    technical_issue_count = int(record.get("technical_issue_count") or 0)

    snippet_issue = any(bool(record.get(key)) for key in SNIPPET_ISSUE_KEYS)
    content_issue = any(bool(record.get(key)) for key in CONTENT_ISSUE_KEYS)
    critical_issue = any(bool(record.get(key)) for key in CRITICAL_ISSUE_KEYS)
    low_effort_issue = any(bool(record.get(key)) for key in LOW_EFFORT_ISSUE_KEYS)
    traffic_present = (
        impressions >= rules.traffic_presence_impressions_threshold
        or clicks >= rules.traffic_presence_clicks_threshold
    )
    important_traffic = impressions >= rules.important_impressions_threshold or clicks >= rules.important_clicks_threshold
    high_impressions = impressions >= rules.high_impressions_threshold
    low_ctr = impressions >= rules.high_impressions_threshold and ctr <= rules.low_ctr_threshold
    mid_position = position is not None and rules.quick_win_position_min <= float(position) <= rules.quick_win_position_max
    underlinked = (
        impressions >= rules.underlinked_impressions_threshold
        and (
            int(record.get("incoming_internal_links") or 0) <= rules.underlinked_max_internal_links
            or int(record.get("incoming_internal_linking_pages") or 0) <= rules.underlinked_max_unique_linking_pages
        )
    )

    if (high_impressions and mid_position and (snippet_issue or content_issue)) or (low_ctr and snippet_issue):
        opportunities.append(
            _opportunity(
                "QUICK_WINS",
                opportunity_score=min(100, 35 + _traffic_signal_score(metrics, rules) + (10 if low_ctr else 0) + (8 if mid_position else 0)),
                impact_level="high" if high_impressions else "medium",
                effort_level="low" if low_effort_issue else "medium",
                rationale=_build_rationale(
                    metrics,
                    "URL sits in the 4-15 position range with room to improve snippet or on-page signals",
                    issue_labels=_top_issue_labels(record, limit=2),
                ),
            )
        )

    if high_impressions and low_ctr and snippet_issue:
        opportunities.append(
            _opportunity(
                "HIGH_IMPRESSIONS_LOW_CTR",
                opportunity_score=min(100, 45 + _traffic_signal_score(metrics, rules)),
                impact_level="high",
                effort_level="low",
                rationale=_build_rationale(
                    metrics,
                    "URL has high impressions and low CTR with snippet issues",
                    issue_labels=_top_issue_labels(record, limit=2),
                ),
            )
        )

    if traffic_present and (bool(record.get("has_technical_issue")) or critical_issue):
        opportunities.append(
            _opportunity(
                "TRAFFIC_WITH_TECHNICAL_ISSUES",
                opportunity_score=min(100, 30 + _traffic_signal_score(metrics, rules) + min(25, issue_weight_total)),
                impact_level="high" if important_traffic else "medium",
                effort_level="high" if critical_issue else "medium",
                rationale=_build_rationale(
                    metrics,
                    "URL already gets traffic or impressions but still has technical issues",
                    issue_labels=_top_issue_labels(record, limit=3),
                ),
            )
        )

    if important_traffic and (content_issue or snippet_issue or bool(record.get("canonical_missing")) or critical_issue):
        opportunities.append(
            _opportunity(
                "IMPORTANT_BUT_WEAK",
                opportunity_score=min(100, 28 + _traffic_signal_score(metrics, rules) + (12 if content_issue else 6)),
                impact_level="high",
                effort_level="medium",
                rationale=_build_rationale(
                    metrics,
                    "URL matters in search but quality signals remain weak",
                    issue_labels=_top_issue_labels(record, limit=3),
                ),
            )
        )

    if (
        traffic_present
        and low_effort_issue
        and technical_issue_count > 0
        and technical_issue_count <= rules.low_hanging_max_issue_count
        and issue_weight_total <= rules.low_hanging_max_issue_weight
        and not critical_issue
    ):
        opportunities.append(
            _opportunity(
                "LOW_HANGING_FRUIT",
                opportunity_score=min(100, 32 + _traffic_signal_score(metrics, rules) + 10),
                impact_level="medium" if clicks < rules.important_clicks_threshold else "high",
                effort_level="low",
                rationale=_build_rationale(
                    metrics,
                    "URL has relatively low-effort fixes with meaningful search potential",
                    issue_labels=_top_issue_labels(record, limit=2),
                ),
            )
        )

    if traffic_present and critical_issue:
        opportunities.append(
            _opportunity(
                "HIGH_RISK_PAGES",
                opportunity_score=min(100, 50 + _traffic_signal_score(metrics, rules) + min(20, issue_weight_total)),
                impact_level="high",
                effort_level="high" if bool(record.get("non_indexable_like")) else "medium",
                rationale=_build_rationale(
                    metrics,
                    "URL already has visibility but is exposed to a high-risk indexability or canonical problem",
                    issue_labels=_top_issue_labels(record, limit=2),
                ),
            )
        )

    if underlinked and (important_traffic or mid_position or clicks > 0):
        opportunities.append(
            _opportunity(
                "UNDERLINKED_OPPORTUNITIES",
                opportunity_score=min(100, 30 + _traffic_signal_score(metrics, rules) + 12),
                impact_level="high" if important_traffic else "medium",
                effort_level="medium",
                rationale=_build_rationale(
                    metrics,
                    "URL shows demand but has weak internal linking support",
                    issue_labels=[
                        f"{int(record.get('incoming_internal_links') or 0)} internal links",
                        f"{int(record.get('incoming_internal_linking_pages') or 0)} linking pages",
                    ],
                ),
            )
        )

    opportunities.sort(
        key=lambda item: (
            int(item["opportunity_score"]),
            -rules.opportunity_order.index(item["type"]),
        ),
        reverse=True,
    )
    return opportunities


def _traffic_signal_score(metrics: dict[str, Any], rules: PriorityRules) -> int:
    impressions = int(metrics["impressions"])
    clicks = int(metrics["clicks"])
    score = 0
    if impressions >= rules.very_high_impressions_threshold:
        score += 30
    elif impressions >= rules.high_impressions_threshold:
        score += 20
    elif impressions >= rules.important_impressions_threshold:
        score += 12
    elif impressions >= rules.traffic_impressions_threshold:
        score += 6

    if clicks >= 50:
        score += 20
    elif clicks >= 20:
        score += 14
    elif clicks >= rules.important_clicks_threshold:
        score += 8
    elif clicks >= rules.traffic_clicks_threshold:
        score += 4
    return min(40, score)


def _opportunity(
    opportunity_type: OpportunityType,
    *,
    opportunity_score: int,
    impact_level: ImpactLevel,
    effort_level: EffortLevel,
    rationale: str,
) -> dict[str, Any]:
    return {
        "type": opportunity_type,
        "opportunity_score": int(opportunity_score),
        "impact_level": impact_level,
        "effort_level": effort_level,
        "rationale": rationale,
    }


def _build_rationale(metrics: dict[str, Any], lead: str, *, issue_labels: list[str]) -> str:
    traffic_parts = []
    if int(metrics["impressions"]) > 0:
        traffic_parts.append(f"{int(metrics['impressions'])} impressions")
    if int(metrics["clicks"]) > 0:
        traffic_parts.append(f"{int(metrics['clicks'])} clicks")
    if float(metrics["ctr"] or 0.0) > 0:
        traffic_parts.append(f"CTR {float(metrics['ctr']) * 100:.2f}%")
    if metrics["position"] is not None:
        traffic_parts.append(f"position {float(metrics['position']):.1f}")

    traffic_text = ", ".join(traffic_parts) if traffic_parts else "no meaningful traffic signal"
    issue_text = ", ".join(issue_labels) if issue_labels else "limited issue depth"
    return f"{lead}: {traffic_text}; issues: {issue_text}."


def _top_issue_labels(record: dict[str, Any], *, limit: int) -> list[str]:
    weighted_items = [
        (int(weight), ISSUE_EXPLANATIONS.get(key, key.replace("_", " ")))
        for key, weight in get_priority_rules().issue_weights.items()
        if bool(record.get(key))
    ]
    weighted_items.sort(key=lambda item: item[0], reverse=True)
    return [label for _, label in weighted_items[:limit]]


def _find_opportunity(record: dict[str, Any], opportunity_type: OpportunityType) -> dict[str, Any]:
    for item in record.get("opportunities") or []:
        if item["type"] == opportunity_type:
            return item
    raise KeyError(opportunity_type)


def _build_opportunity_page_preview(
    record: dict[str, Any],
    opportunity_type: OpportunityType | None,
    suffix: str,
) -> dict[str, Any]:
    opportunity = _find_opportunity(record, opportunity_type) if opportunity_type is not None else None
    return {
        "page_id": int(record["id"]),
        "url": record["url"],
        "priority_score": int(record.get("priority_score") or 0),
        "priority_level": record.get("priority_level") or "low",
        "priority_rationale": record.get("priority_rationale") or "",
        "primary_opportunity_type": record.get("primary_opportunity_type"),
        "opportunity_count": int(record.get("opportunity_count") or 0),
        "opportunity_types": list(record.get("opportunity_types") or []),
        "clicks": int(record.get(f"clicks_{suffix}") or 0),
        "impressions": int(record.get(f"impressions_{suffix}") or 0),
        "ctr": float(record.get(f"ctr_{suffix}") or 0.0),
        "position": float(record.get(f"position_{suffix}")) if record.get(f"position_{suffix}") is not None else None,
        "incoming_internal_links": int(record.get("incoming_internal_links") or 0),
        "incoming_internal_linking_pages": int(record.get("incoming_internal_linking_pages") or 0),
        "opportunities": list(record.get("opportunities") or []) if opportunity_type is None else [opportunity],
        "opportunity_score": int(opportunity["opportunity_score"]) if opportunity is not None else None,
        "impact_level": opportunity["impact_level"] if opportunity is not None else None,
        "effort_level": opportunity["effort_level"] if opportunity is not None else None,
        "rationale": opportunity["rationale"] if opportunity is not None else record.get("priority_rationale") or "",
    }
