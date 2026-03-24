from __future__ import annotations

import hashlib
import json
from typing import Any


def build_competitive_gap_key(
    *,
    gap_type: str,
    topic_key: str,
    target_page_id: int | None,
    suggested_page_type: str | None,
) -> str:
    target_ref = str(target_page_id) if target_page_id is not None else "none"
    page_type_ref = suggested_page_type or "none"
    return f"{gap_type}:{topic_key}:{target_ref}:{page_type_ref}"


def build_competitive_gap_signature(gap_row: dict[str, Any]) -> str:
    payload = {
        "gap_key": gap_row.get("gap_key"),
        "semantic_cluster_key": gap_row.get("semantic_cluster_key"),
        "gap_type": gap_row.get("gap_type"),
        "segment": gap_row.get("segment"),
        "topic_key": gap_row.get("topic_key"),
        "topic_label": gap_row.get("topic_label"),
        "canonical_topic_label": gap_row.get("canonical_topic_label"),
        "merged_topic_count": gap_row.get("merged_topic_count"),
        "own_match_status": gap_row.get("own_match_status"),
        "own_match_source": gap_row.get("own_match_source"),
        "target_page_id": gap_row.get("target_page_id"),
        "target_url": gap_row.get("target_url"),
        "page_type": gap_row.get("page_type"),
        "target_page_type": gap_row.get("target_page_type"),
        "suggested_page_type": gap_row.get("suggested_page_type"),
        "competitor_ids": gap_row.get("competitor_ids"),
        "competitor_count": gap_row.get("competitor_count"),
        "competitor_urls": gap_row.get("competitor_urls"),
        "consensus_score": gap_row.get("consensus_score"),
        "competitor_coverage_score": gap_row.get("competitor_coverage_score"),
        "own_coverage_score": gap_row.get("own_coverage_score"),
        "strategy_alignment_score": gap_row.get("strategy_alignment_score"),
        "business_value_score": gap_row.get("business_value_score"),
        "priority_score": gap_row.get("priority_score"),
        "confidence": gap_row.get("confidence"),
        "rationale": gap_row.get("rationale"),
        "signals": gap_row.get("signals"),
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
