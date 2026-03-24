from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from app.crawler.normalization.urls import normalize_url

_WHITESPACE_RE = re.compile(r"\s+")


def build_content_recommendation_key(recommendation: Mapping[str, Any]) -> str:
    identity = build_content_recommendation_identity(recommendation)
    serialized = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:24]
    recommendation_type = identity["recommendation_type"] or "recommendation"
    return f"{recommendation_type.lower()}:{digest}"


def build_content_recommendation_identity(recommendation: Mapping[str, Any]) -> dict[str, str | None]:
    recommendation_type = _normalize_token(recommendation.get("recommendation_type"))
    segment = _normalize_token(recommendation.get("segment"))
    cluster_key = _normalize_token(recommendation.get("cluster_key"))
    cluster_label = _normalize_text_fragment(recommendation.get("cluster_label"))
    suggested_page_type = _normalize_token(recommendation.get("suggested_page_type"))
    target_page_type = _normalize_token(recommendation.get("target_page_type") or recommendation.get("page_type"))
    normalized_target_url = _normalize_target_url(recommendation.get("normalized_target_url") or recommendation.get("target_url"))

    return {
        "recommendation_type": recommendation_type,
        "segment": segment,
        "normalized_target_url": normalized_target_url,
        "suggested_page_type": suggested_page_type if normalized_target_url is None else None,
        "target_page_type": target_page_type if normalized_target_url is None else None,
        "cluster_key": cluster_key,
        "cluster_label": cluster_label if cluster_key is None else None,
    }


def _normalize_target_url(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return normalize_url(text) or text.lower()


def _normalize_text_fragment(value: Any) -> str | None:
    if value is None:
        return None
    text = _WHITESPACE_RE.sub(" ", str(value).strip().lower())
    return text or None


def _normalize_token(value: Any) -> str | None:
    normalized = _normalize_text_fragment(value)
    if normalized is None:
        return None
    return normalized.replace(" ", "_")
