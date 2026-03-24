from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services import competitive_gap_llm_service, competitive_gap_service
from app.services.competitive_gap_keys import build_competitive_gap_signature


class CompetitiveGapExplanationServiceError(RuntimeError):
    pass


def build_gap_explanation_response(
    session: Session,
    site_id: int,
    *,
    gap_key: str,
    active_crawl_id: int,
    gsc_date_range: str = "last_28_days",
    gap_signature: str | None = None,
    output_language: str = "en",
) -> dict[str, Any]:
    gap_row = competitive_gap_service.get_competitive_gap_row(
        session,
        site_id,
        gap_key=gap_key,
        active_crawl_id=active_crawl_id,
        gsc_date_range=gsc_date_range,
    )
    current_signature = build_competitive_gap_signature(gap_row)
    if gap_signature is not None and gap_signature != current_signature:
        raise CompetitiveGapExplanationServiceError(
            "Gap signature mismatch. Refresh the competitive gap list and try again."
        )

    explanation = competitive_gap_llm_service.build_gap_explanation(
        gap_row,
        gap_signature=current_signature,
        output_language=output_language,
    )
    return {
        "gap_key": gap_key,
        "gap_signature": current_signature,
        "semantic_cluster_key": gap_row.get("semantic_cluster_key"),
        "canonical_topic_label": gap_row.get("canonical_topic_label"),
        "merged_topic_count": gap_row.get("merged_topic_count"),
        "own_match_status": gap_row.get("own_match_status"),
        "own_match_source": gap_row.get("own_match_source"),
        "explanation": explanation.explanation,
        "bullets": explanation.bullets,
        "used_llm": explanation.used_llm,
        "fallback_used": explanation.fallback_used,
        "fallback_reason": explanation.fallback_reason,
        "llm_provider": explanation.llm_provider,
        "llm_model": explanation.llm_model,
        "prompt_version": explanation.prompt_version,
    }
