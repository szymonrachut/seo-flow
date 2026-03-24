from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from app.services.priority_rules import get_priority_rules


@dataclass(frozen=True, slots=True)
class TrendRules:
    issue_weights: dict[str, int] = field(default_factory=lambda: dict(get_priority_rules().issue_weights))
    issue_score_cap: int = 30
    internal_links_delta_threshold: int = 2
    internal_linking_pages_delta_threshold: int = 1
    word_count_delta_threshold: int = 50
    response_time_delta_threshold_ms: int = 200
    schema_count_delta_threshold: int = 1
    images_missing_alt_delta_threshold: int = 1
    priority_score_delta_threshold: int = 8
    summary_position_min_impressions: int = 1
    gsc_clicks_flat_threshold: int = 1
    gsc_impressions_flat_threshold: int = 5
    gsc_ctr_flat_threshold: float = 0.005
    gsc_position_flat_threshold: float = 0.3
    gsc_top_queries_flat_threshold: int = 1
    gsc_metric_weights: dict[str, int] = field(
        default_factory=lambda: {
            "clicks": 3,
            "impressions": 2,
            "ctr": 2,
            "position": 2,
            "top_queries_count": 1,
        }
    )


@lru_cache(maxsize=1)
def get_trend_rules() -> TrendRules:
    return TrendRules()
