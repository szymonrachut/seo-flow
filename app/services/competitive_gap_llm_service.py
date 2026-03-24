from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.text_processing import dedupe_preserve_order
from app.core.config import get_settings
from app.integrations.openai.client import OpenAiConfigurationError, OpenAiIntegrationError, OpenAiLlmClient
from app.schemas.competitive_gap import NormalizedCompetitiveGapStrategy
from app.services.competitive_gap_language_service import output_language_instruction


STRATEGY_NORMALIZATION_PROMPT_VERSION = "competitive-gap-strategy-normalization-v1"
GAP_EXPLANATION_PROMPT_VERSION = "competitive-gap-explanation-v1"
STRATEGY_NORMALIZATION_COMPLETION_LIMITS = (900, 1600)
GAP_EXPLANATION_COMPLETION_LIMITS = (700, 1200)


@dataclass(slots=True)
class StrategyNormalizationAttempt:
    normalized_strategy_json: dict[str, Any] | None
    normalization_status: str
    llm_provider: str | None
    llm_model: str | None
    prompt_version: str | None
    attempted_at: datetime | None
    fallback_used: bool
    debug_code: str | None
    debug_message: str | None
    normalized_at: datetime | None


@dataclass(slots=True)
class GapExplanationResult:
    explanation: str
    bullets: list[str]
    used_llm: bool
    fallback_used: bool
    fallback_reason: str | None
    llm_provider: str | None
    llm_model: str | None
    prompt_version: str


class CompetitiveGapExplanationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(min_length=1, max_length=320)
    bullets: list[str] = Field(min_length=2, max_length=3)


def normalize_strategy_from_raw_input(
    raw_user_input: str,
    *,
    client: OpenAiLlmClient | None = None,
    output_language: str = "en",
) -> StrategyNormalizationAttempt:
    settings = get_settings()
    llm_model = settings.openai_model_competitor_extraction
    resolved_client = client or OpenAiLlmClient()
    attempt_time = datetime.now(timezone.utc)
    if not raw_user_input.strip():
        return StrategyNormalizationAttempt(
            normalized_strategy_json=None,
            normalization_status="not_started",
            llm_provider=None,
            llm_model=None,
            prompt_version=None,
            attempted_at=None,
            fallback_used=False,
            debug_code="empty_input",
            debug_message="Strategy notes are empty, so normalization did not run.",
            normalized_at=None,
        )
    if not resolved_client.is_available():
        debug_code, debug_message = _resolve_unavailable_strategy_debug_message()
        return StrategyNormalizationAttempt(
            normalized_strategy_json=None,
            normalization_status="not_processed",
            llm_provider=None,
            llm_model=None,
            prompt_version=None,
            attempted_at=attempt_time,
            fallback_used=True,
            debug_code=debug_code,
            debug_message=debug_message,
            normalized_at=None,
        )

    parsed = None
    last_error: OpenAiIntegrationError | None = None
    try:
        for completion_limit in STRATEGY_NORMALIZATION_COMPLETION_LIMITS:
            try:
                parsed = resolved_client.parse_chat_completion(
                    model=llm_model,
                    system_prompt=_strategy_normalization_system_prompt(output_language=output_language),
                    user_prompt=_strategy_normalization_user_prompt(raw_user_input, output_language=output_language),
                    response_format=NormalizedCompetitiveGapStrategy,
                    max_completion_tokens=completion_limit,
                    reasoning_effort="minimal",
                )
                break
            except OpenAiIntegrationError as exc:
                last_error = exc
                if exc.code == "length_limit" and completion_limit != STRATEGY_NORMALIZATION_COMPLETION_LIMITS[-1]:
                    continue
                raise
    except OpenAiConfigurationError as exc:
        return StrategyNormalizationAttempt(
            normalized_strategy_json=None,
            normalization_status="not_processed",
            llm_provider=None,
            llm_model=None,
            prompt_version=None,
            attempted_at=attempt_time,
            fallback_used=True,
            debug_code=exc.code,
            debug_message=str(exc),
            normalized_at=None,
        )
    except OpenAiIntegrationError as exc:
        return StrategyNormalizationAttempt(
            normalized_strategy_json=None,
            normalization_status="failed",
            llm_provider=resolved_client.provider_name,
            llm_model=llm_model,
            prompt_version=STRATEGY_NORMALIZATION_PROMPT_VERSION,
            attempted_at=attempt_time,
            fallback_used=True,
            debug_code=exc.code,
            debug_message=str(exc),
            normalized_at=None,
        )

    if parsed is None:
        fallback_exc = last_error or OpenAiIntegrationError(
            "OpenAI normalization returned no structured output.",
            code="structured_output_missing",
        )
        return StrategyNormalizationAttempt(
            normalized_strategy_json=None,
            normalization_status="failed",
            llm_provider=resolved_client.provider_name,
            llm_model=llm_model,
            prompt_version=STRATEGY_NORMALIZATION_PROMPT_VERSION,
            attempted_at=attempt_time,
            fallback_used=True,
            debug_code=fallback_exc.code,
            debug_message=str(fallback_exc),
            normalized_at=None,
        )

    normalized = _clean_normalized_strategy(parsed)
    return StrategyNormalizationAttempt(
        normalized_strategy_json=normalized.model_dump(mode="json"),
        normalization_status="ready",
        llm_provider=resolved_client.provider_name,
        llm_model=llm_model,
        prompt_version=STRATEGY_NORMALIZATION_PROMPT_VERSION,
        attempted_at=attempt_time,
        fallback_used=False,
        debug_code=None,
        debug_message="Strategy normalized successfully.",
        normalized_at=attempt_time,
    )


def normalize_manual_strategy_json(value: NormalizedCompetitiveGapStrategy | dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, NormalizedCompetitiveGapStrategy):
        model = value
    else:
        try:
            model = NormalizedCompetitiveGapStrategy.model_validate(value)
        except ValidationError as exc:
            raise ValueError("normalized_strategy_json does not match the required strategy schema.") from exc
    return _clean_normalized_strategy(model).model_dump(mode="json")


def build_gap_explanation(
    gap_row: dict[str, Any],
    *,
    gap_signature: str,
    client: OpenAiLlmClient | None = None,
    output_language: str = "en",
) -> GapExplanationResult:
    settings = get_settings()
    llm_model = settings.openai_model_competitor_explanation
    resolved_client = client or OpenAiLlmClient()
    fallback = _build_fallback_gap_explanation(gap_row)

    if not resolved_client.is_available():
        return GapExplanationResult(
            explanation=fallback["explanation"],
            bullets=fallback["bullets"],
            used_llm=False,
            fallback_used=True,
            fallback_reason="llm_unavailable",
            llm_provider=None,
            llm_model=None,
            prompt_version=GAP_EXPLANATION_PROMPT_VERSION,
        )

    parsed = None
    try:
        for completion_limit in GAP_EXPLANATION_COMPLETION_LIMITS:
            try:
                parsed = resolved_client.parse_chat_completion(
                    model=llm_model,
                    system_prompt=_gap_explanation_system_prompt(output_language=output_language),
                    user_prompt=_gap_explanation_user_prompt(
                        gap_row,
                        gap_signature,
                        output_language=output_language,
                    ),
                    response_format=CompetitiveGapExplanationOutput,
                    max_completion_tokens=completion_limit,
                    reasoning_effort="minimal",
                )
                break
            except OpenAiIntegrationError as exc:
                if exc.code == "length_limit" and completion_limit != GAP_EXPLANATION_COMPLETION_LIMITS[-1]:
                    continue
                raise
    except OpenAiIntegrationError:
        return GapExplanationResult(
            explanation=fallback["explanation"],
            bullets=fallback["bullets"],
            used_llm=False,
            fallback_used=True,
            fallback_reason="llm_request_failed",
            llm_provider=resolved_client.provider_name,
            llm_model=llm_model,
            prompt_version=GAP_EXPLANATION_PROMPT_VERSION,
        )

    if parsed is None:
        return GapExplanationResult(
            explanation=fallback["explanation"],
            bullets=fallback["bullets"],
            used_llm=False,
            fallback_used=True,
            fallback_reason="llm_request_failed",
            llm_provider=resolved_client.provider_name,
            llm_model=llm_model,
            prompt_version=GAP_EXPLANATION_PROMPT_VERSION,
        )

    return GapExplanationResult(
        explanation=parsed.explanation.strip(),
        bullets=[bullet.strip() for bullet in parsed.bullets if bullet.strip()][:3],
        used_llm=True,
        fallback_used=False,
        fallback_reason=None,
        llm_provider=resolved_client.provider_name,
        llm_model=llm_model,
        prompt_version=GAP_EXPLANATION_PROMPT_VERSION,
    )


def _clean_normalized_strategy(model: NormalizedCompetitiveGapStrategy) -> NormalizedCompetitiveGapStrategy:
    def clean_text_list(values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value and value.strip()]
        return dedupe_preserve_order(cleaned)[:8]

    return NormalizedCompetitiveGapStrategy(
        schema_version="competitive_gap_strategy_v1",
        business_summary=model.business_summary.strip(),
        target_audiences=clean_text_list(model.target_audiences),
        primary_goals=clean_text_list(model.primary_goals),
        priority_topics=clean_text_list(model.priority_topics),
        supporting_topics=clean_text_list(model.supporting_topics),
        priority_page_types=dedupe_preserve_order(list(model.priority_page_types))[:5],
        geographic_focus=clean_text_list(model.geographic_focus),
        constraints=clean_text_list(model.constraints),
        differentiation_points=clean_text_list(model.differentiation_points),
    )


def _strategy_normalization_system_prompt(*, output_language: str) -> str:
    return (
        "You normalize SEO strategy notes into a strict JSON contract for competitive gap analysis. "
        "Use only the user input. Do not invent products, markets or goals. "
        "Prefer short phrases. Keep arrays empty when the input is unclear. "
        f"{output_language_instruction(output_language)}"
    )


def _resolve_unavailable_strategy_debug_message() -> tuple[str, str]:
    settings = get_settings()
    if not settings.openai_llm_enabled:
        return ("llm_disabled", "OpenAI normalization is disabled in backend config.")
    if not settings.openai_api_key:
        return ("missing_api_key", "OPENAI_API_KEY is missing in backend config.")
    return ("llm_unavailable", "OpenAI normalization is currently unavailable.")


def _strategy_normalization_user_prompt(raw_user_input: str, *, output_language: str) -> str:
    return (
        f"Prompt version: {STRATEGY_NORMALIZATION_PROMPT_VERSION}\n"
        f"Output language: {output_language}\n"
        "Return only the structured strategy object.\n"
        f"User strategy input:\n{raw_user_input.strip()}"
    )


def _gap_explanation_system_prompt(*, output_language: str) -> str:
    return (
        "You explain a competitive content gap using only the provided deterministic JSON payload. "
        "Do not add facts, URLs or recommendations that are not present. "
        "Keep the explanation concise, stable and operational. "
        f"{output_language_instruction(output_language)}"
    )


def _gap_explanation_user_prompt(
    gap_row: dict[str, Any],
    gap_signature: str,
    *,
    output_language: str,
) -> str:
    return (
        f"Prompt version: {GAP_EXPLANATION_PROMPT_VERSION}\n"
        f"Output language: {output_language}\n"
        f"Gap signature: {gap_signature}\n"
        "Explain this gap row with one short paragraph and 2-3 short bullets.\n"
        f"{json.dumps(gap_row, sort_keys=True, ensure_ascii=True)}"
    )


def _build_fallback_gap_explanation(gap_row: dict[str, Any]) -> dict[str, Any]:
    explanation = (
        f"{gap_row['topic_label']} is a {gap_row['gap_type'].lower()} opportunity with priority "
        f"{gap_row['priority_score']}/100. Competitor consensus is {gap_row['consensus_score']}/100 and "
        f"current own coverage is {gap_row['own_coverage_score']}/100."
    )
    bullets = [
        f"Competitors covering topic: {gap_row['competitor_count']}",
        f"Suggested page type: {gap_row.get('suggested_page_type') or gap_row.get('target_page_type') or gap_row['page_type']}",
        f"Business value score: {gap_row['business_value_score']}/100",
    ]
    return {"explanation": explanation, "bullets": bullets}
