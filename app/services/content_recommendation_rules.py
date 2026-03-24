from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from app.schemas.opportunities import EffortLevel, ImpactLevel


ContentRecommendationType = Literal[
    "MISSING_SUPPORTING_CONTENT",
    "THIN_CLUSTER",
    "EXPAND_EXISTING_PAGE",
    "MISSING_STRUCTURAL_PAGE_TYPE",
    "INTERNAL_LINKING_SUPPORT",
]
ContentRecommendationSegment = Literal[
    "create_new_page",
    "expand_existing_page",
    "strengthen_cluster",
    "improve_internal_support",
]

CONTENT_RECOMMENDATION_TYPES: tuple[ContentRecommendationType, ...] = (
    "MISSING_SUPPORTING_CONTENT",
    "THIN_CLUSTER",
    "EXPAND_EXISTING_PAGE",
    "MISSING_STRUCTURAL_PAGE_TYPE",
    "INTERNAL_LINKING_SUPPORT",
)

CONTENT_RECOMMENDATION_SEGMENTS: tuple[ContentRecommendationSegment, ...] = (
    "create_new_page",
    "expand_existing_page",
    "strengthen_cluster",
    "improve_internal_support",
)


@dataclass(frozen=True, slots=True)
class ContentRecommendationRules:
    cluster_eligible_page_types: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "category",
                "product",
                "service",
                "blog_article",
                "blog_index",
                "faq",
                "location",
                "other",
            }
        )
    )
    supporting_page_types: frozenset[str] = field(default_factory=lambda: frozenset({"blog_article", "faq"}))
    structural_hub_page_types: frozenset[str] = field(
        default_factory=lambda: frozenset({"category", "service", "blog_index", "location"})
    )
    commercial_page_types: frozenset[str] = field(
        default_factory=lambda: frozenset({"home", "category", "product", "service", "location"})
    )
    informational_page_types: frozenset[str] = field(
        default_factory=lambda: frozenset({"blog_article", "blog_index", "faq"})
    )
    expansion_candidate_page_types: frozenset[str] = field(
        default_factory=lambda: frozenset({"category", "product", "service", "blog_article", "blog_index", "faq", "location", "other"})
    )
    generic_topic_tokens: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "blog",
                "blogi",
                "article",
                "articles",
                "artykul",
                "artykuly",
                "category",
                "categories",
                "kategoria",
                "kategorie",
                "product",
                "products",
                "produkt",
                "produkty",
                "service",
                "services",
                "usluga",
                "uslugi",
                "offer",
                "oferta",
                "faq",
                "faqs",
                "contact",
                "kontakt",
                "about",
                "company",
                "about-us",
                "legal",
                "privacy",
                "policy",
                "cookie",
                "cookies",
                "terms",
                "utility",
                "page",
                "pages",
                "home",
                "main",
                "index",
                "default",
                "news",
                "aktualnosci",
                "guide",
                "guides",
                "poradnik",
                "poradniki",
                "tag",
                "tags",
                "author",
                "feed",
                "search",
                "login",
                "konto",
                "account",
            }
        )
    )
    stopwords: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "a",
                "an",
                "and",
                "are",
                "as",
                "at",
                "be",
                "by",
                "dla",
                "do",
                "for",
                "from",
                "how",
                "i",
                "if",
                "in",
                "is",
                "jak",
                "na",
                "nie",
                "o",
                "of",
                "on",
                "or",
                "oraz",
                "our",
                "po",
                "strona",
                "strony",
                "that",
                "the",
                "this",
                "to",
                "w",
                "with",
                "z",
            }
        )
    )
    path_primary_token_weight: float = 3.5
    path_secondary_token_weight: float = 2.0
    title_token_weight: float = 2.5
    h1_token_weight: float = 2.5
    query_token_weight: float = 1.8
    anchor_token_weight: float = 1.2
    stable_path_token_bonus: float = 1.2
    stable_path_token_min_pages: int = 2
    min_token_length: int = 3
    max_anchor_samples_per_page: int = 3
    max_query_rows_per_page: int = 6
    query_impression_bonus_divisor: float = 80.0
    query_click_bonus_divisor: float = 6.0
    query_token_max_bonus: float = 2.2
    label_secondary_token_min_share: float = 0.62
    label_max_tokens: int = 2

    thin_cluster_max_pages: int = 1
    thin_cluster_min_priority_score: int = 28
    thin_cluster_min_impressions: int = 20

    missing_support_min_pages: int = 2
    missing_support_min_priority_score: int = 35
    missing_support_min_impressions: int = 40
    missing_support_max_supporting_pages: int = 0

    expand_existing_min_priority_score: int = 35
    expand_existing_min_impressions: int = 30
    expand_existing_min_top_queries: int = 2
    expand_existing_max_word_count: int = 550
    expand_existing_low_linking_pages: int = 2
    expand_existing_min_issue_count: int = 2

    missing_structural_min_detail_pages: int = 2
    missing_structural_min_blog_articles: int = 2

    internal_support_min_cluster_pages: int = 2
    internal_support_min_priority_score: int = 30
    internal_support_max_linking_pages: int = 2
    internal_support_max_cluster_linking_pages: int = 2
    internal_support_low_cluster_links_per_page: float = 1.0

    helper_low_internal_support_score: int = 45
    helper_low_cluster_strength_score: int = 45
    helper_high_coverage_gap_score: int = 55
    helper_visibility_watch_min_impressions: int = 40
    helper_low_ctr_watch_min_impressions: int = 80
    helper_low_ctr_threshold: float = 0.03
    helper_low_position_threshold: float = 10.0
    helper_low_query_coverage_max_queries: int = 1
    helper_high_priority_attention_score: int = 60

    high_priority_recommendation_threshold: int = 70
    high_impact_priority_score: int = 60
    medium_impact_priority_score: int = 35
    high_impact_impressions: int = 300
    medium_impact_impressions: int = 80
    high_impact_clicks: int = 20
    medium_impact_clicks: int = 5

    confidence_base_by_type: dict[ContentRecommendationType, float] = field(
        default_factory=lambda: {
            "MISSING_SUPPORTING_CONTENT": 0.64,
            "THIN_CLUSTER": 0.6,
            "EXPAND_EXISTING_PAGE": 0.68,
            "MISSING_STRUCTURAL_PAGE_TYPE": 0.75,
            "INTERNAL_LINKING_SUPPORT": 0.72,
        }
    )
    default_effort_by_type: dict[ContentRecommendationType, EffortLevel] = field(
        default_factory=lambda: {
            "MISSING_SUPPORTING_CONTENT": "medium",
            "THIN_CLUSTER": "high",
            "EXPAND_EXISTING_PAGE": "medium",
            "MISSING_STRUCTURAL_PAGE_TYPE": "high",
            "INTERNAL_LINKING_SUPPORT": "low",
        }
    )
    recommendation_segment_by_type: dict[ContentRecommendationType, ContentRecommendationSegment] = field(
        default_factory=lambda: {
            "MISSING_SUPPORTING_CONTENT": "create_new_page",
            "THIN_CLUSTER": "strengthen_cluster",
            "EXPAND_EXISTING_PAGE": "expand_existing_page",
            "MISSING_STRUCTURAL_PAGE_TYPE": "create_new_page",
            "INTERNAL_LINKING_SUPPORT": "improve_internal_support",
        }
    )
    type_priority_bonus: dict[ContentRecommendationType, int] = field(
        default_factory=lambda: {
            "MISSING_SUPPORTING_CONTENT": 6,
            "THIN_CLUSTER": 4,
            "EXPAND_EXISTING_PAGE": 8,
            "MISSING_STRUCTURAL_PAGE_TYPE": 8,
            "INTERNAL_LINKING_SUPPORT": 5,
        }
    )
    effort_penalty: dict[EffortLevel, int] = field(
        default_factory=lambda: {
            "low": 0,
            "medium": 8,
            "high": 16,
        }
    )
    impact_base_score: dict[ImpactLevel, int] = field(
        default_factory=lambda: {
            "low": 35,
            "medium": 60,
            "high": 82,
        }
    )
    hub_page_type_weights: dict[str, float] = field(
        default_factory=lambda: {
            "category": 5.0,
            "service": 5.0,
            "blog_index": 4.5,
            "faq": 3.5,
            "location": 3.5,
            "product": 2.5,
            "blog_article": 2.0,
            "other": 1.5,
        }
    )
    internal_issue_priority_weights: dict[str, int] = field(
        default_factory=lambda: {
            "WEAKLY_LINKED_IMPORTANT": 14,
            "LOW_LINK_EQUITY": 12,
            "ORPHAN_LIKE": 10,
            "BOILERPLATE_DOMINATED": 6,
            "LOW_ANCHOR_DIVERSITY": 4,
            "EXACT_MATCH_ANCHOR_CONCENTRATION": 4,
        }
    )


@lru_cache(maxsize=1)
def get_content_recommendation_rules() -> ContentRecommendationRules:
    return ContentRecommendationRules()
