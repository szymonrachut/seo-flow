from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SiteContentStrategy
from app.services import competitive_gap_llm_service, crawl_job_service


class SiteContentStrategyServiceError(RuntimeError):
    pass


def get_site_content_strategy(session: Session, site_id: int) -> dict[str, Any] | None:
    _get_site_or_raise(session, site_id)
    strategy = session.scalar(select(SiteContentStrategy).where(SiteContentStrategy.site_id == site_id))
    if strategy is None:
        return None
    return _serialize_strategy(strategy)


def upsert_site_content_strategy(
    session: Session,
    site_id: int,
    *,
    raw_user_input: str,
    normalized_strategy_json: Any | None,
    output_language: str = "en",
) -> dict[str, Any]:
    _get_site_or_raise(session, site_id)
    strategy = session.scalar(select(SiteContentStrategy).where(SiteContentStrategy.site_id == site_id))
    if strategy is None:
        strategy = SiteContentStrategy(site_id=site_id, raw_user_input="")
        session.add(strategy)

    strategy.raw_user_input = raw_user_input.strip()
    if normalized_strategy_json is not None:
        try:
            validated_json = competitive_gap_llm_service.normalize_manual_strategy_json(normalized_strategy_json)
        except ValueError as exc:
            raise SiteContentStrategyServiceError(str(exc)) from exc
        strategy.normalized_strategy_json = validated_json
        strategy.llm_provider = None
        strategy.llm_model = None
        strategy.prompt_version = None
        strategy.normalization_status = "ready"
        strategy.last_normalization_attempt_at = datetime.now(timezone.utc)
        strategy.normalization_fallback_used = False
        strategy.normalization_debug_code = "manual_override"
        strategy.normalization_debug_message = "Normalized strategy was provided manually."
        strategy.normalized_at = strategy.last_normalization_attempt_at
    else:
        normalization_attempt = competitive_gap_llm_service.normalize_strategy_from_raw_input(
            strategy.raw_user_input,
            output_language=output_language,
        )
        strategy.normalized_strategy_json = normalization_attempt.normalized_strategy_json
        strategy.llm_provider = normalization_attempt.llm_provider
        strategy.llm_model = normalization_attempt.llm_model
        strategy.prompt_version = normalization_attempt.prompt_version
        strategy.normalization_status = normalization_attempt.normalization_status
        strategy.last_normalization_attempt_at = normalization_attempt.attempted_at
        strategy.normalization_fallback_used = normalization_attempt.fallback_used
        strategy.normalization_debug_code = normalization_attempt.debug_code
        strategy.normalization_debug_message = normalization_attempt.debug_message
        strategy.normalized_at = normalization_attempt.normalized_at

    session.flush()
    session.refresh(strategy)
    return _serialize_strategy(strategy)


def delete_site_content_strategy(session: Session, site_id: int) -> None:
    _get_site_or_raise(session, site_id)
    strategy = session.scalar(select(SiteContentStrategy).where(SiteContentStrategy.site_id == site_id))
    if strategy is None:
        raise SiteContentStrategyServiceError(f"Strategy for site {site_id} not found.")
    session.delete(strategy)
    session.flush()


def _get_site_or_raise(session: Session, site_id: int) -> None:
    site = crawl_job_service.get_site(session, site_id)
    if site is None:
        raise SiteContentStrategyServiceError(f"Site {site_id} not found.")


def _serialize_strategy(strategy: SiteContentStrategy) -> dict[str, Any]:
    return {
        "id": strategy.id,
        "site_id": strategy.site_id,
        "raw_user_input": strategy.raw_user_input,
        "normalized_strategy_json": _coerce_normalized_strategy(strategy.normalized_strategy_json),
        "llm_provider": strategy.llm_provider,
        "llm_model": strategy.llm_model,
        "prompt_version": strategy.prompt_version,
        "normalization_status": strategy.normalization_status,
        "last_normalization_attempt_at": strategy.last_normalization_attempt_at,
        "normalization_fallback_used": strategy.normalization_fallback_used,
        "normalization_debug_code": strategy.normalization_debug_code,
        "normalization_debug_message": strategy.normalization_debug_message,
        "normalized_at": strategy.normalized_at,
        "created_at": strategy.created_at,
        "updated_at": strategy.updated_at,
    }


def _coerce_normalized_strategy(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        return competitive_gap_llm_service.normalize_manual_strategy_json(value)
    except ValueError:
        return None
