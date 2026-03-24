from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any
import warnings

from app.core.text_processing import dedupe_preserve_order, normalize_text_for_hash
from app.db.models import SiteCompetitorPage
from app.integrations.openai.client import OpenAiConfigurationError, OpenAiIntegrationError, OpenAiLlmClient
from app.schemas.competitive_gap import CompetitiveGapCompetitorExtractionOutput
from app.core.config import get_settings
from app.services.competitive_gap_language_service import output_language_instruction
from app.services.competitive_gap_page_diagnostics import (
    get_page_schema_types,
    get_page_visible_text_chars,
    get_page_visible_text_truncated,
    get_page_word_count,
)
from app.services.competitive_gap_semantic_card_service import (
    COMPETITOR_EXTRACTION_PROMPT_VERSION,
    COMPETITOR_EXTRACTION_SYNTHESIS_PROMPT_VERSION,
    SEMANTIC_CARD_VERSION,
    build_primary_topic_key,
    build_semantic_card,
    normalize_semantic_card,
)


COMPETITOR_EXTRACTION_COMPLETION_LIMITS = (900, 1400)
COMPETITOR_EXTRACTION_SCALAR_COMPATIBILITY_SHIM_REMOVAL_PHASE = "stage-12a4 stabilization phase 1"


class CompetitiveGapExtractionServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "extraction_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class CompetitorExtractionResult:
    llm_provider: str
    llm_model: str
    prompt_version: str
    schema_version: str
    topic_label: str
    topic_key: str
    search_intent: str
    content_format: str
    page_role: str
    evidence_snippets_json: list[str]
    confidence: float
    semantic_version: str = SEMANTIC_CARD_VERSION
    semantic_input_hash: str = ""
    semantic_card_json: dict[str, Any] = field(default_factory=dict)
    chunk_summary_json: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.semantic_card_json:
            normalized_card = normalize_semantic_card(self.semantic_card_json)
            self.semantic_card_json = normalized_card
            self.semantic_version = str(normalized_card.get("semantic_version") or self.semantic_version)
            self.semantic_input_hash = str(normalized_card.get("semantic_input_hash") or self.semantic_input_hash)
            return

        # TODO(stage-12a4-stabilization-1): remove this scalar compatibility shim
        # once all call sites pass semantic_card_json explicitly.
        warnings.warn(
            "CompetitorExtractionResult without semantic_card_json is deprecated and will be removed after "
            f"{COMPETITOR_EXTRACTION_SCALAR_COMPATIBILITY_SHIM_REMOVAL_PHASE}. "
            "Pass semantic_card_json explicitly.",
            DeprecationWarning,
            stacklevel=2,
        )
        semantic_card = build_semantic_card(
            primary_topic=self.topic_label,
            topic_labels=[self.topic_label],
            core_problem=self.topic_label,
            dominant_intent=self.search_intent,
            secondary_intents=[],
            page_role=self.page_role,
            content_format=self.content_format,
            target_audience=None,
            entities=[],
            geo_scope=None,
            supporting_subtopics=[],
            what_this_page_is_about=self.topic_label,
            what_this_page_is_not_about="Not another topic.",
            commerciality="high" if self.search_intent == "commercial" else "low",
            evidence_snippets=self.evidence_snippets_json,
            confidence=self.confidence,
            semantic_version=self.semantic_version,
        )
        self.semantic_card_json = semantic_card
        self.semantic_version = str(semantic_card.get("semantic_version") or self.semantic_version)
        self.semantic_input_hash = str(semantic_card.get("semantic_input_hash") or self.semantic_input_hash)


def extract_competitor_page(
    page: SiteCompetitorPage,
    *,
    client: OpenAiLlmClient | None = None,
    output_language: str = "en",
) -> CompetitorExtractionResult:
    settings = get_settings()
    resolved_client = client or OpenAiLlmClient()
    llm_model = settings.openai_model_competitor_extraction

    if not resolved_client.is_available():
        raise CompetitiveGapExtractionServiceError(_resolve_unavailable_message(), code=_resolve_unavailable_code())

    primary_card = _call_semantic_card_extraction(
        resolved_client=resolved_client,
        llm_model=llm_model,
        system_prompt=_competitor_extraction_system_prompt(output_language=output_language),
        user_prompt=_competitor_extraction_user_prompt(page),
        error_prefix="competitor_extraction",
    )
    cleaned_card = _clean_competitor_semantic_card(primary_card, page=page)

    chunk_summary_json: dict[str, Any] | None = None
    prompt_version = COMPETITOR_EXTRACTION_PROMPT_VERSION
    if _requires_synthesis_pass(page, cleaned_card):
        chunk_cards = _extract_chunk_cards(
                page,
                resolved_client=resolved_client,
                llm_model=llm_model,
                output_language=output_language,
            )
        if chunk_cards:
            synthesized = _synthesize_semantic_card(
                page,
                cleaned_card,
                chunk_cards,
                resolved_client=resolved_client,
                llm_model=llm_model,
                output_language=output_language,
            )
            cleaned_card = synthesized["semantic_card"]
            chunk_summary_json = synthesized["chunk_summary_json"]
            prompt_version = COMPETITOR_EXTRACTION_SYNTHESIS_PROMPT_VERSION

    topic_label = str(cleaned_card.get("primary_topic") or _fallback_topic_label(page))
    topic_key = build_primary_topic_key(cleaned_card)
    evidence_snippets = list(cleaned_card.get("evidence_snippets") or [])
    return CompetitorExtractionResult(
        llm_provider=resolved_client.provider_name,
        llm_model=llm_model,
        prompt_version=prompt_version,
        schema_version="competitive_gap_competitor_extraction_v2",
        semantic_version=str(cleaned_card.get("semantic_version") or SEMANTIC_CARD_VERSION),
        semantic_input_hash=str(cleaned_card.get("semantic_input_hash") or ""),
        topic_label=topic_label,
        topic_key=topic_key,
        search_intent=str(cleaned_card.get("dominant_intent") or "other"),
        content_format=str(cleaned_card.get("content_format") or "other"),
        page_role=str(cleaned_card.get("page_role") or "other"),
        evidence_snippets_json=evidence_snippets,
        confidence=float(cleaned_card.get("confidence") or 0.0),
        semantic_card_json=cleaned_card,
        chunk_summary_json=chunk_summary_json,
    )


def _call_semantic_card_extraction(
    *,
    resolved_client: OpenAiLlmClient,
    llm_model: str,
    system_prompt: str,
    user_prompt: str,
    error_prefix: str,
) -> CompetitiveGapCompetitorExtractionOutput:
    parsed = None
    last_error: OpenAiIntegrationError | None = None
    try:
        for completion_limit in COMPETITOR_EXTRACTION_COMPLETION_LIMITS:
            try:
                parsed = resolved_client.parse_chat_completion(
                    model=llm_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_format=CompetitiveGapCompetitorExtractionOutput,
                    max_completion_tokens=completion_limit,
                    reasoning_effort="minimal",
                    verbosity="low",
                )
                break
            except OpenAiIntegrationError as exc:
                last_error = exc
                if exc.code == "length_limit" and completion_limit != COMPETITOR_EXTRACTION_COMPLETION_LIMITS[-1]:
                    continue
                raise
    except OpenAiConfigurationError as exc:
        raise CompetitiveGapExtractionServiceError(str(exc), code=exc.code) from exc
    except OpenAiIntegrationError as exc:
        raise CompetitiveGapExtractionServiceError(str(exc), code=exc.code) from exc

    if parsed is None:
        fallback_exc = last_error or OpenAiIntegrationError(
            f"{error_prefix} returned no structured output.",
            code="structured_output_missing",
        )
        raise CompetitiveGapExtractionServiceError(str(fallback_exc), code=fallback_exc.code)
    return parsed


def _clean_competitor_semantic_card(
    model: CompetitiveGapCompetitorExtractionOutput,
    *,
    page: SiteCompetitorPage,
) -> dict[str, Any]:
    card = build_semantic_card(
        primary_topic=model.primary_topic or _fallback_topic_label(page),
        topic_labels=model.topic_labels,
        core_problem=model.core_problem or model.what_this_page_is_about or _fallback_topic_label(page),
        dominant_intent=model.dominant_intent,
        secondary_intents=model.secondary_intents,
        page_role=model.page_role,
        content_format=model.content_format,
        target_audience=model.target_audience,
        entities=model.entities,
        geo_scope=model.geo_scope,
        supporting_subtopics=model.supporting_subtopics,
        what_this_page_is_about=model.what_this_page_is_about or model.primary_topic,
        what_this_page_is_not_about=model.what_this_page_is_not_about or "Unclear boundary.",
        commerciality=model.commerciality,
        evidence_snippets=model.evidence_snippets,
        confidence=model.confidence,
        semantic_version=SEMANTIC_CARD_VERSION,
    )
    return normalize_semantic_card(card)


def _requires_synthesis_pass(page: SiteCompetitorPage, card: dict[str, Any]) -> bool:
    if get_page_visible_text_chars(page) >= 3_200:
        return True
    if get_page_word_count(page) >= 900:
        return True
    if float(card.get("confidence") or 0.0) <= 0.72:
        return True
    if len(card.get("topic_labels") or []) <= 1 and len(card.get("supporting_subtopics") or []) <= 1:
        return True
    return False


def _extract_chunk_cards(
    page: SiteCompetitorPage,
    *,
    resolved_client: OpenAiLlmClient,
    llm_model: str,
    output_language: str,
) -> list[dict[str, Any]]:
    chunk_prompts = _build_segment_payloads(page)
    chunk_cards: list[dict[str, Any]] = []
    for payload in chunk_prompts:
        try:
            parsed = _call_semantic_card_extraction(
                resolved_client=resolved_client,
                llm_model=llm_model,
                system_prompt=_competitor_extraction_system_prompt(output_language=output_language),
                user_prompt=json.dumps(payload, ensure_ascii=True, sort_keys=True),
                error_prefix="competitor_chunk_extraction",
            )
        except CompetitiveGapExtractionServiceError:
            continue
        chunk_cards.append(_clean_competitor_semantic_card(parsed, page=page))
    return chunk_cards


def _synthesize_semantic_card(
    page: SiteCompetitorPage,
    base_card: dict[str, Any],
    chunk_cards: list[dict[str, Any]],
    *,
    resolved_client: OpenAiLlmClient,
    llm_model: str,
    output_language: str,
) -> dict[str, Any]:
    chunk_summary_json = {
        "chunk_count": len(chunk_cards),
        "chunk_cards": chunk_cards,
    }
    try:
        parsed = _call_semantic_card_extraction(
            resolved_client=resolved_client,
            llm_model=llm_model,
            system_prompt=_competitor_synthesis_system_prompt(output_language=output_language),
            user_prompt=_competitor_synthesis_user_prompt(page, base_card=base_card, chunk_cards=chunk_cards),
            error_prefix="competitor_synthesis",
        )
    except CompetitiveGapExtractionServiceError:
        return {
            "semantic_card": _merge_chunk_cards(base_card, chunk_cards),
            "chunk_summary_json": chunk_summary_json,
        }
    return {
        "semantic_card": _clean_competitor_semantic_card(parsed, page=page),
        "chunk_summary_json": chunk_summary_json,
    }


def _merge_chunk_cards(base_card: dict[str, Any], chunk_cards: list[dict[str, Any]]) -> dict[str, Any]:
    merged = dict(base_card)
    merged["topic_labels"] = dedupe_preserve_order(
        [
            *(base_card.get("topic_labels") or []),
            *(
                label
                for chunk_card in chunk_cards
                for label in (chunk_card.get("topic_labels") or [])
            ),
        ]
    )[:8]
    merged["supporting_subtopics"] = dedupe_preserve_order(
        [
            *(base_card.get("supporting_subtopics") or []),
            *(
                label
                for chunk_card in chunk_cards
                for label in (chunk_card.get("supporting_subtopics") or [])
            ),
        ]
    )[:8]
    merged["entities"] = dedupe_preserve_order(
        [
            *(base_card.get("entities") or []),
            *(
                label
                for chunk_card in chunk_cards
                for label in (chunk_card.get("entities") or [])
            ),
        ]
    )[:10]
    merged["evidence_snippets"] = dedupe_preserve_order(
        [
            *(base_card.get("evidence_snippets") or []),
            *(
                label
                for chunk_card in chunk_cards
                for label in (chunk_card.get("evidence_snippets") or [])
            ),
        ]
    )[:4]
    merged["confidence"] = round(
        min(
            0.98,
            max(
                float(base_card.get("confidence") or 0.0),
                sum(float(card.get("confidence") or 0.0) for card in chunk_cards) / max(1, len(chunk_cards)),
            ),
        ),
        2,
    )
    return normalize_semantic_card(merged)


def _competitor_extraction_system_prompt(*, output_language: str) -> str:
    return (
        "You build a structured semantic card for a competitor page. "
        "Use only the provided metadata. "
        "Capture the real topic, intent, role, entities and evidence conservatively. "
        "Return only JSON and do not invent missing facts. "
        f"{output_language_instruction(output_language)}"
    )


def _competitor_extraction_user_prompt(page: SiteCompetitorPage) -> str:
    payload = {
        "prompt_version": COMPETITOR_EXTRACTION_PROMPT_VERSION,
        "task": "competitor_semantic_card",
        "url": page.url,
        "normalized_url": page.normalized_url,
        "title": page.title,
        "meta_description": page.meta_description,
        "h1": page.h1,
        "page_type": page.page_type,
        "page_bucket": page.page_bucket,
        "schema_types": get_page_schema_types(page),
        "word_count": get_page_word_count(page),
        "visible_text_chars": get_page_visible_text_chars(page),
        "visible_text_truncated": get_page_visible_text_truncated(page),
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _competitor_synthesis_system_prompt(*, output_language: str) -> str:
    return (
        "You synthesize one final semantic card for a competitor page from a base reading and chunk-level readings. "
        "Prefer the most specific, well-supported interpretation. "
        "Keep confidence conservative and return only JSON. "
        f"{output_language_instruction(output_language)}"
    )


def _competitor_synthesis_user_prompt(
    page: SiteCompetitorPage,
    *,
    base_card: dict[str, Any],
    chunk_cards: list[dict[str, Any]],
) -> str:
    payload = {
        "prompt_version": COMPETITOR_EXTRACTION_SYNTHESIS_PROMPT_VERSION,
        "task": "competitor_semantic_card_synthesis",
        "url": page.url,
        "normalized_url": page.normalized_url,
        "title": page.title,
        "h1": page.h1,
        "page_type": page.page_type,
        "page_bucket": page.page_bucket,
        "base_card": base_card,
        "chunk_cards": chunk_cards,
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _build_segment_payloads(_page: SiteCompetitorPage) -> list[dict[str, Any]]:
    # Segment-level extraction depends on raw visible text excerpts, which are
    # intentionally excluded from outbound LLM payloads.
    return []


def _fallback_topic_label(page: SiteCompetitorPage) -> str:
    candidate = page.h1 or page.title or page.normalized_url or page.url or f"competitor-page-{page.id}"
    cleaned = normalize_text_for_hash(candidate).replace("-", " ").strip()
    if cleaned:
        return cleaned.title()[:255]
    return f"Competitor Page {page.id}"


def _resolve_unavailable_code() -> str:
    settings = get_settings()
    if not settings.openai_llm_enabled:
        return "llm_disabled"
    if not settings.openai_api_key:
        return "missing_api_key"
    return "llm_unavailable"


def _resolve_unavailable_message() -> str:
    settings = get_settings()
    if not settings.openai_llm_enabled:
        return "OpenAI extraction is disabled in backend config."
    if not settings.openai_api_key:
        return "OPENAI_API_KEY is missing in backend config."
    return "OpenAI extraction is currently unavailable."
