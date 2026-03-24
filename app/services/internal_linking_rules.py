from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal


InternalLinkingIssueType = Literal[
    "ORPHAN_LIKE",
    "WEAKLY_LINKED_IMPORTANT",
    "LOW_ANCHOR_DIVERSITY",
    "EXACT_MATCH_ANCHOR_CONCENTRATION",
    "BOILERPLATE_DOMINATED",
    "LOW_LINK_EQUITY",
]

INTERNAL_LINKING_ISSUE_TYPES: tuple[InternalLinkingIssueType, ...] = (
    "ORPHAN_LIKE",
    "WEAKLY_LINKED_IMPORTANT",
    "LOW_ANCHOR_DIVERSITY",
    "EXACT_MATCH_ANCHOR_CONCENTRATION",
    "BOILERPLATE_DOMINATED",
    "LOW_LINK_EQUITY",
)


@dataclass(frozen=True, slots=True)
class InternalLinkingRules:
    issue_order: tuple[InternalLinkingIssueType, ...] = INTERNAL_LINKING_ISSUE_TYPES
    issue_weights: dict[InternalLinkingIssueType, int] = field(
        default_factory=lambda: {
            "ORPHAN_LIKE": 40,
            "WEAKLY_LINKED_IMPORTANT": 28,
            "LOW_LINK_EQUITY": 22,
            "BOILERPLATE_DOMINATED": 16,
            "EXACT_MATCH_ANCHOR_CONCENTRATION": 14,
            "LOW_ANCHOR_DIVERSITY": 10,
        }
    )
    orphan_like_max_follow_linking_pages: int = 0
    orphan_like_excluded_depth: int = 0

    weakly_linked_max_follow_links: int = 2
    weakly_linked_max_follow_linking_pages: int = 1
    important_priority_score_threshold: int = 45

    anchor_diversity_min_anchor_links: int = 4
    anchor_diversity_score_threshold: float = 35.0
    anchor_diversity_dominant_anchor_ratio_threshold: float = 0.7
    anchor_diversity_max_unique_anchors: int = 2

    exact_match_min_anchor_links: int = 4
    exact_match_min_count: int = 3
    exact_match_ratio_threshold: float = 0.6
    exact_match_min_words: int = 2

    boilerplate_min_linking_pages: int = 4
    boilerplate_anchor_share_threshold: float = 0.6
    boilerplate_min_links: int = 3
    boilerplate_dominated_ratio_threshold: float = 0.65
    boilerplate_body_like_max_linking_pages: int = 1

    link_equity_iterations: int = 8
    link_equity_damping: float = 0.15
    body_like_edge_weight: float = 1.0
    boilerplate_like_edge_weight: float = 0.35
    low_link_equity_score_threshold: float = 40.0

    anchor_preview_limit: int = 3
    generic_anchor_terms: set[str] = field(
        default_factory=lambda: {
            "",
            "click here",
            "read more",
            "learn more",
            "more",
            "here",
            "this page",
            "website",
            "home",
            "start",
        }
    )


@lru_cache(maxsize=1)
def get_internal_linking_rules() -> InternalLinkingRules:
    return InternalLinkingRules()
