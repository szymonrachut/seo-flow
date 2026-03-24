from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal


PriorityLevel = Literal["low", "medium", "high", "critical"]
ImpactLevel = Literal["low", "medium", "high"]
EffortLevel = Literal["low", "medium", "high"]
OpportunityType = Literal[
    "QUICK_WINS",
    "HIGH_IMPRESSIONS_LOW_CTR",
    "TRAFFIC_WITH_TECHNICAL_ISSUES",
    "IMPORTANT_BUT_WEAK",
    "LOW_HANGING_FRUIT",
    "HIGH_RISK_PAGES",
    "UNDERLINKED_OPPORTUNITIES",
]

OPPORTUNITY_TYPES: tuple[OpportunityType, ...] = (
    "QUICK_WINS",
    "HIGH_IMPRESSIONS_LOW_CTR",
    "TRAFFIC_WITH_TECHNICAL_ISSUES",
    "IMPORTANT_BUT_WEAK",
    "LOW_HANGING_FRUIT",
    "HIGH_RISK_PAGES",
    "UNDERLINKED_OPPORTUNITIES",
)


@dataclass(frozen=True, slots=True)
class PriorityRules:
    issue_weights: dict[str, int] = field(
        default_factory=lambda: {
            "title_missing": 10,
            "title_too_short": 4,
            "title_too_long": 4,
            "meta_description_missing": 8,
            "meta_description_too_short": 4,
            "meta_description_too_long": 4,
            "h1_missing": 8,
            "multiple_h1": 5,
            "missing_h2": 3,
            "canonical_missing": 6,
            "canonical_to_other_url": 12,
            "canonical_to_non_200": 14,
            "canonical_to_redirect": 10,
            "noindex_like": 16,
            "non_indexable_like": 18,
            "thin_content": 8,
            "duplicate_content": 7,
            "missing_alt_images": 3,
            "oversized": 3,
        }
    )
    issue_component_cap: int = 40
    opportunity_component_cap: int = 20
    internal_linking_component_cap: int = 10

    traffic_presence_impressions_threshold: int = 1
    traffic_presence_clicks_threshold: int = 1
    traffic_impressions_threshold: int = 50
    traffic_clicks_threshold: int = 5
    important_impressions_threshold: int = 150
    important_clicks_threshold: int = 10
    high_impressions_threshold: int = 200
    very_high_impressions_threshold: int = 1000
    low_ctr_threshold: float = 0.02
    very_low_ctr_threshold: float = 0.01
    quick_win_position_min: float = 4.0
    quick_win_position_max: float = 15.0
    low_hanging_max_issue_count: int = 3
    low_hanging_max_issue_weight: int = 12
    underlinked_impressions_threshold: int = 150
    underlinked_max_internal_links: int = 2
    underlinked_max_unique_linking_pages: int = 1
    moderate_underlinked_max_internal_links: int = 4
    moderate_underlinked_max_unique_linking_pages: int = 2
    top_queries_reference: int = 10

    priority_level_thresholds: dict[PriorityLevel, int] = field(
        default_factory=lambda: {
            "critical": 70,
            "high": 45,
            "medium": 25,
            "low": 0,
        }
    )
    opportunity_priority_bonuses: dict[OpportunityType, int] = field(
        default_factory=lambda: {
            "QUICK_WINS": 6,
            "HIGH_IMPRESSIONS_LOW_CTR": 6,
            "TRAFFIC_WITH_TECHNICAL_ISSUES": 5,
            "IMPORTANT_BUT_WEAK": 4,
            "LOW_HANGING_FRUIT": 5,
            "HIGH_RISK_PAGES": 8,
            "UNDERLINKED_OPPORTUNITIES": 4,
        }
    )
    opportunity_order: tuple[OpportunityType, ...] = OPPORTUNITY_TYPES


@lru_cache(maxsize=1)
def get_priority_rules() -> PriorityRules:
    return PriorityRules()
