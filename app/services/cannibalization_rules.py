from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal


CannibalizationSeverity = Literal["low", "medium", "high", "critical"]
CannibalizationRecommendationType = Literal[
    "MERGE_CANDIDATE",
    "SPLIT_INTENT_CANDIDATE",
    "REINFORCE_PRIMARY_URL",
    "QUERY_CLUSTER_WITHOUT_CLEAR_PRIMARY",
    "LOW_VALUE_OVERLAP",
    "HIGH_IMPACT_CANNIBALIZATION",
]

CANNIBALIZATION_RECOMMENDATION_TYPES: tuple[CannibalizationRecommendationType, ...] = (
    "MERGE_CANDIDATE",
    "SPLIT_INTENT_CANDIDATE",
    "REINFORCE_PRIMARY_URL",
    "QUERY_CLUSTER_WITHOUT_CLEAR_PRIMARY",
    "LOW_VALUE_OVERLAP",
    "HIGH_IMPACT_CANNIBALIZATION",
)


@dataclass(frozen=True, slots=True)
class CannibalizationRules:
    min_query_impressions: int = 10
    min_query_clicks: int = 1

    min_shared_queries: int = 1
    min_pair_shared_impressions: int = 20
    min_pair_shared_clicks: int = 1
    min_weighted_overlap_by_impressions: float = 0.12
    min_weighted_overlap_by_clicks: float = 0.08
    min_pair_overlap_score: float = 0.18

    overlap_impressions_weight: float = 0.45
    overlap_clicks_weight: float = 0.35
    overlap_query_ratio_weight: float = 0.20

    dominance_click_weight: float = 0.45
    dominance_impressions_weight: float = 0.35
    dominance_position_weight: float = 0.20
    dominance_min_score: float = 0.45
    dominance_min_margin: float = 0.10
    clear_primary_confidence_threshold: float = 0.62
    split_intent_confidence_ceiling: float = 0.60

    merge_candidate_min_overlap: float = 0.55
    merge_candidate_secondary_click_share_max: float = 0.15
    merge_candidate_secondary_impression_share_max: float = 0.20
    merge_candidate_max_exclusive_queries: int = 1

    reinforce_primary_min_overlap: float = 0.32
    reinforce_primary_secondary_click_share_max: float = 0.30

    split_intent_min_overlap: float = 0.22
    split_intent_min_exclusive_queries: int = 2
    split_intent_min_urls_with_exclusive_queries: int = 2

    low_value_max_shared_impressions: int = 80
    low_value_max_shared_clicks: int = 3
    high_impact_min_shared_impressions: int = 300
    high_impact_min_shared_clicks: int = 20
    medium_impact_min_shared_impressions: int = 120
    medium_impact_min_shared_clicks: int = 6

    severity_thresholds: dict[CannibalizationSeverity, int] = field(
        default_factory=lambda: {
            "critical": 75,
            "high": 55,
            "medium": 30,
            "low": 0,
        }
    )
    severity_recommendation_bonus: dict[CannibalizationRecommendationType, int] = field(
        default_factory=lambda: {
            "MERGE_CANDIDATE": 6,
            "SPLIT_INTENT_CANDIDATE": 8,
            "REINFORCE_PRIMARY_URL": 10,
            "QUERY_CLUSTER_WITHOUT_CLEAR_PRIMARY": 14,
            "LOW_VALUE_OVERLAP": -10,
            "HIGH_IMPACT_CANNIBALIZATION": 18,
        }
    )
    severity_priority_weight: float = 0.18

    cluster_sample_queries_limit: int = 5
    per_url_sample_queries_limit: int = 5


@lru_cache(maxsize=1)
def get_cannibalization_rules() -> CannibalizationRules:
    return CannibalizationRules()
