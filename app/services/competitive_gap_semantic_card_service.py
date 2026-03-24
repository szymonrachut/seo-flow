from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from app.core.text_processing import collapse_whitespace, dedupe_preserve_order, normalize_text_for_hash, tokenize_topic_text


SEMANTIC_CARD_VERSION = "competitive-gap-semantic-card-v1"
OWN_PAGE_SEMANTIC_PROFILE_VERSION = "competitive-gap-own-page-profile-v1"
COMPETITOR_EXTRACTION_PROMPT_VERSION = "competitive-gap-competitor-semantic-card-v1"
COMPETITOR_EXTRACTION_SYNTHESIS_PROMPT_VERSION = "competitive-gap-competitor-semantic-synthesis-v1"
OWN_PAGE_PROFILE_PROMPT_VERSION = "competitive-gap-own-page-semantic-profile-v1"
CLUSTER_VERSION = "competitive-gap-cluster-v1"
COVERAGE_VERSION = "competitive-gap-coverage-v1"

_EMPTY_CARD = {
    "primary_topic": "",
    "topic_labels": [],
    "core_problem": "",
    "dominant_intent": "other",
    "secondary_intents": [],
    "page_role": "other",
    "content_format": "other",
    "target_audience": None,
    "entities": [],
    "geo_scope": None,
    "supporting_subtopics": [],
    "what_this_page_is_about": "",
    "what_this_page_is_not_about": "",
    "commerciality": "neutral",
    "evidence_snippets": [],
    "confidence": 0.0,
    "semantic_version": SEMANTIC_CARD_VERSION,
    "semantic_input_hash": "",
}


def build_semantic_card(
    *,
    primary_topic: Any,
    topic_labels: Iterable[Any] | None = None,
    core_problem: Any = None,
    dominant_intent: Any = None,
    secondary_intents: Iterable[Any] | None = None,
    page_role: Any = None,
    content_format: Any = None,
    target_audience: Any = None,
    entities: Iterable[Any] | None = None,
    geo_scope: Any = None,
    supporting_subtopics: Iterable[Any] | None = None,
    what_this_page_is_about: Any = None,
    what_this_page_is_not_about: Any = None,
    commerciality: Any = None,
    evidence_snippets: Iterable[Any] | None = None,
    confidence: Any = None,
    semantic_version: str = SEMANTIC_CARD_VERSION,
) -> dict[str, Any]:
    card = {
        "primary_topic": _clean_text(primary_topic),
        "topic_labels": _clean_list(topic_labels, limit=8),
        "core_problem": _clean_text(core_problem),
        "dominant_intent": _clean_enum(dominant_intent, default="other"),
        "secondary_intents": _clean_list(secondary_intents, limit=4),
        "page_role": _clean_enum(page_role, default="other"),
        "content_format": _clean_enum(content_format, default="other"),
        "target_audience": _clean_text(target_audience),
        "entities": _clean_list(entities, limit=10),
        "geo_scope": _clean_text(geo_scope),
        "supporting_subtopics": _clean_list(supporting_subtopics, limit=8),
        "what_this_page_is_about": _clean_text(what_this_page_is_about),
        "what_this_page_is_not_about": _clean_text(what_this_page_is_not_about),
        "commerciality": _clean_enum(commerciality, default="neutral"),
        "evidence_snippets": _clean_list(evidence_snippets, limit=4),
        "confidence": _clean_confidence(confidence),
        "semantic_version": semantic_version or SEMANTIC_CARD_VERSION,
    }
    card = _backfill_card_fields(card)
    card["semantic_input_hash"] = build_semantic_card_hash(card)
    return card


def normalize_semantic_card(card: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(card, dict):
        return dict(_EMPTY_CARD)
    normalized = build_semantic_card(
        primary_topic=card.get("primary_topic"),
        topic_labels=card.get("topic_labels"),
        core_problem=card.get("core_problem"),
        dominant_intent=card.get("dominant_intent"),
        secondary_intents=card.get("secondary_intents"),
        page_role=card.get("page_role"),
        content_format=card.get("content_format"),
        target_audience=card.get("target_audience"),
        entities=card.get("entities"),
        geo_scope=card.get("geo_scope"),
        supporting_subtopics=card.get("supporting_subtopics"),
        what_this_page_is_about=card.get("what_this_page_is_about"),
        what_this_page_is_not_about=card.get("what_this_page_is_not_about"),
        commerciality=card.get("commerciality"),
        evidence_snippets=card.get("evidence_snippets"),
        confidence=card.get("confidence"),
        semantic_version=str(card.get("semantic_version") or SEMANTIC_CARD_VERSION),
    )
    for key in ("topic_key", "topic_label", "search_intent"):
        if key in card and card.get(key) is not None:
            normalized[key] = card.get(key)
    return normalized


def build_semantic_card_hash(card: dict[str, Any]) -> str:
    payload = {
        "primary_topic": normalize_text_for_hash(card.get("primary_topic")),
        "topic_labels": sorted(
            normalize_text_for_hash(value)
            for value in (card.get("topic_labels") or [])
            if normalize_text_for_hash(value)
        ),
        "core_problem": normalize_text_for_hash(card.get("core_problem")),
        "dominant_intent": normalize_text_for_hash(card.get("dominant_intent")),
        "secondary_intents": sorted(
            normalize_text_for_hash(value)
            for value in (card.get("secondary_intents") or [])
            if normalize_text_for_hash(value)
        ),
        "page_role": normalize_text_for_hash(card.get("page_role")),
        "content_format": normalize_text_for_hash(card.get("content_format")),
        "target_audience": normalize_text_for_hash(card.get("target_audience")),
        "entities": sorted(
            normalize_text_for_hash(value)
            for value in (card.get("entities") or [])
            if normalize_text_for_hash(value)
        ),
        "geo_scope": normalize_text_for_hash(card.get("geo_scope")),
        "supporting_subtopics": sorted(
            normalize_text_for_hash(value)
            for value in (card.get("supporting_subtopics") or [])
            if normalize_text_for_hash(value)
        ),
        "what_this_page_is_about": normalize_text_for_hash(card.get("what_this_page_is_about")),
        "what_this_page_is_not_about": normalize_text_for_hash(card.get("what_this_page_is_not_about")),
        "commerciality": normalize_text_for_hash(card.get("commerciality")),
        "evidence_snippets": sorted(
            normalize_text_for_hash(value)
            for value in (card.get("evidence_snippets") or [])
            if normalize_text_for_hash(value)
        ),
        "semantic_version": normalize_text_for_hash(card.get("semantic_version")),
    }
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_semantic_match_terms(card: dict[str, Any] | None) -> list[str]:
    normalized = normalize_semantic_card(card)
    raw_values: list[str] = []
    raw_values.extend(_iter_text([normalized.get("primary_topic")]))
    raw_values.extend(_iter_text(normalized.get("topic_labels") or []))
    raw_values.extend(_iter_text([normalized.get("core_problem")]))
    raw_values.extend(_iter_text([normalized.get("what_this_page_is_about")]))
    raw_values.extend(_iter_text(normalized.get("supporting_subtopics") or []))
    raw_values.extend(_iter_text(normalized.get("entities") or []))
    raw_values.extend(_iter_text([normalized.get("target_audience")]))
    raw_values.extend(_iter_text([normalized.get("geo_scope")]))
    tokens: list[str] = []
    for value in raw_values:
        tokens.extend(tokenize_topic_text(value))
    return dedupe_preserve_order(token for token in tokens if token)[:24]


def build_primary_topic_key(card: dict[str, Any] | None) -> str:
    normalized = normalize_semantic_card(card)
    tokens = tokenize_topic_text(str(normalized.get("primary_topic") or ""))
    if tokens:
        return "-".join(tokens[:4])
    return normalize_text_for_hash(normalized.get("primary_topic") or "topic").replace(" ", "-") or "topic"


def semantic_card_similarity(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    left_card = normalize_semantic_card(left)
    right_card = normalize_semantic_card(right)
    left_terms = set(build_semantic_match_terms(left_card))
    right_terms = set(build_semantic_match_terms(right_card))
    shared_terms = left_terms & right_terms
    topic_overlap = _safe_ratio(len(shared_terms), len(left_terms | right_terms))
    primary_match = (
        normalize_text_for_hash(left_card.get("primary_topic"))
        and normalize_text_for_hash(left_card.get("primary_topic"))
        == normalize_text_for_hash(right_card.get("primary_topic"))
    )
    intent_match = normalize_text_for_hash(left_card.get("dominant_intent")) == normalize_text_for_hash(
        right_card.get("dominant_intent")
    )
    role_match = normalize_text_for_hash(left_card.get("page_role")) == normalize_text_for_hash(right_card.get("page_role"))
    format_match = normalize_text_for_hash(left_card.get("content_format")) == normalize_text_for_hash(
        right_card.get("content_format")
    )
    geo_match = normalize_text_for_hash(left_card.get("geo_scope")) == normalize_text_for_hash(right_card.get("geo_scope"))
    entity_overlap = _safe_ratio(
        len(set(_clean_list(left_card.get("entities"), limit=10)) & set(_clean_list(right_card.get("entities"), limit=10))),
        len(set(_clean_list(left_card.get("entities"), limit=10)) | set(_clean_list(right_card.get("entities"), limit=10))),
    )
    score = 0
    score += 40 if primary_match else 0
    score += int(round(topic_overlap * 28))
    score += 10 if intent_match else 0
    score += 6 if role_match else 0
    score += 4 if format_match else 0
    score += 4 if geo_match else 0
    score += int(round(entity_overlap * 8))
    score += min(10, int(round(((left_card.get("confidence") or 0.0) + (right_card.get("confidence") or 0.0)) * 5)))
    return {
        "score": max(0, min(100, score)),
        "primary_match": primary_match,
        "intent_match": intent_match,
        "role_match": role_match,
        "format_match": format_match,
        "geo_match": geo_match,
        "topic_overlap": round(topic_overlap, 2),
        "entity_overlap": round(entity_overlap, 2),
        "shared_terms": sorted(shared_terms),
    }


def build_topic_labels(card: dict[str, Any] | None) -> list[str]:
    normalized = normalize_semantic_card(card)
    values = [normalized.get("primary_topic")] + list(normalized.get("topic_labels") or [])
    return _clean_list(values, limit=8)


def _backfill_card_fields(card: dict[str, Any]) -> dict[str, Any]:
    if not card["primary_topic"]:
        labels = list(card.get("topic_labels") or [])
        if labels:
            card["primary_topic"] = labels[0]
    if not card["topic_labels"]:
        values = [card.get("primary_topic"), card.get("what_this_page_is_about")]
        card["topic_labels"] = _clean_list(values, limit=8)
    if not card["core_problem"]:
        card["core_problem"] = card.get("what_this_page_is_about") or card.get("primary_topic") or ""
    if not card["what_this_page_is_about"]:
        card["what_this_page_is_about"] = card.get("core_problem") or card.get("primary_topic") or ""
    if not card["what_this_page_is_not_about"]:
        card["what_this_page_is_not_about"] = "Unclear boundary."
    return card


def _clean_text(value: Any) -> str | None:
    cleaned = collapse_whitespace(value)
    return cleaned[:280] if cleaned else None


def _clean_list(values: Iterable[Any] | Any, *, limit: int) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        candidates = [values]
    else:
        try:
            candidates = list(values)
        except TypeError:
            candidates = [values]
    cleaned = [collapse_whitespace(value) for value in candidates]
    return [value[:280] for value in dedupe_preserve_order(value for value in cleaned if value)][:limit]


def _clean_confidence(value: Any) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        resolved = 0.0
    return round(max(0.0, min(1.0, resolved)), 2)


def _clean_enum(value: Any, *, default: str) -> str:
    cleaned = normalize_text_for_hash(value)
    return cleaned.replace(" ", "_") if cleaned else default


def _iter_text(values: Iterable[Any]) -> list[str]:
    return [collapse_whitespace(value) or "" for value in values if collapse_whitespace(value)]


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator
