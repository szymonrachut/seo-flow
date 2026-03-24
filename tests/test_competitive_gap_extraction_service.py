from __future__ import annotations

import pytest

from app.db.models import SiteCompetitorPage
from app.integrations.openai.client import OpenAiIntegrationError
from app.schemas.competitive_gap import CompetitiveGapCompetitorExtractionOutput
from app.services import competitive_gap_extraction_service
from app.services.competitive_gap_page_diagnostics import build_fetch_diagnostics_payload


class FakeOpenAiClient:
    provider_name = "openai"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def is_available(self) -> bool:
        return True

    def parse_chat_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_format: type[CompetitiveGapCompetitorExtractionOutput],
        max_completion_tokens: int,
        reasoning_effort: str | None = None,
        verbosity: str = "low",
    ) -> CompetitiveGapCompetitorExtractionOutput:
        self.calls.append(
            {
                "model": model,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_format": response_format,
                "max_completion_tokens": max_completion_tokens,
                "reasoning_effort": reasoning_effort,
                "verbosity": verbosity,
            }
        )
        if max_completion_tokens == 900:
            raise OpenAiIntegrationError(
                "OpenAI response hit a length limit.",
                code="length_limit",
            )
        return CompetitiveGapCompetitorExtractionOutput(
            primary_topic="Orthopedic prosthetics",
            topic_labels=["Orthopedic prosthetics", "Prosthetics services"],
            core_problem="Orthopedic prosthetics services and fitting support.",
            dominant_intent="commercial",
            secondary_intents=["informational"],
            content_format="service_page",
            page_role="money_page",
            target_audience="Patients needing prosthetic support",
            entities=["amputation", "prosthesis"],
            geo_scope="Poland",
            supporting_subtopics=["prosthetics", "orthotics"],
            what_this_page_is_about="Orthopedic prosthetics services and fitting support.",
            what_this_page_is_not_about="Not a blog-only educational article.",
            commerciality="high",
            evidence_snippets=["Orthopedic prosthetics services and fitting support."],
            confidence=0.84,
        )


def test_extract_competitor_page_retries_after_length_limit_without_sending_body_excerpt() -> None:
    client = FakeOpenAiClient()
    page = SiteCompetitorPage(
        site_id=1,
        competitor_id=1,
        url="https://example-competitor.com/prosthetics",
        normalized_url="https://example-competitor.com/prosthetics",
        final_url="https://example-competitor.com/prosthetics",
        status_code=200,
        title="Orthopedic prosthetics",
        meta_description="Orthopedic prosthetics services.",
        h1="Orthopedic prosthetics",
        canonical_url="https://example-competitor.com/prosthetics",
        content_type="text/html; charset=utf-8",
        visible_text=("Orthopedic prosthetics services and fitting support. " * 200),
        fetch_diagnostics_json=build_fetch_diagnostics_payload(
            schema_count=1,
            schema_types=["MedicalBusiness"],
            visible_text_truncated=False,
        ),
        page_type="service",
        page_bucket="commercial",
        page_type_confidence=0.93,
    )

    result = competitive_gap_extraction_service.extract_competitor_page(page, client=client)

    assert result.topic_key == "orthopedic-prosthetics"
    assert result.semantic_card_json["primary_topic"] == "Orthopedic prosthetics"
    assert result.semantic_version == "competitive-gap-semantic-card-v1"
    assert [call["max_completion_tokens"] for call in client.calls[:2]] == [900, 1400]
    assert len(client.calls) == 2
    assert all(call["reasoning_effort"] == "minimal" for call in client.calls)
    assert all(call["verbosity"] == "low" for call in client.calls)
    prompt = str(client.calls[0]["user_prompt"])
    assert "visible_text_chars" in prompt
    assert len(prompt) < len(page.visible_text or "")


def test_competitor_extraction_result_scalar_compatibility_shim_is_deprecated() -> None:
    with pytest.warns(DeprecationWarning, match="semantic_card_json"):
        result = competitive_gap_extraction_service.CompetitorExtractionResult(
            llm_provider="openai",
            llm_model="gpt-5-mini",
            prompt_version="competitive-gap-competitor-extraction-v2",
            schema_version="competitive_gap_competitor_extraction_v2",
            topic_label="SEO Audit",
            topic_key="seo-audit",
            search_intent="commercial",
            content_format="service_page",
            page_role="money_page",
            evidence_snippets_json=["SEO Audit"],
            confidence=0.81,
        )

    assert result.semantic_card_json["primary_topic"] == "SEO Audit"


def test_extract_competitor_page_respects_requested_output_language() -> None:
    client = FakeOpenAiClient()
    page = SiteCompetitorPage(
        site_id=1,
        competitor_id=1,
        url="https://example-competitor.com/prosthetics",
        normalized_url="https://example-competitor.com/prosthetics",
        final_url="https://example-competitor.com/prosthetics",
        status_code=200,
        title="Orthopedic prosthetics",
        meta_description="Orthopedic prosthetics services.",
        h1="Orthopedic prosthetics",
        canonical_url="https://example-competitor.com/prosthetics",
        content_type="text/html; charset=utf-8",
        visible_text="Orthopedic prosthetics services and fitting support.",
        fetch_diagnostics_json=build_fetch_diagnostics_payload(schema_count=1, schema_types=["MedicalBusiness"]),
        page_type="service",
        page_bucket="commercial",
        page_type_confidence=0.93,
    )

    competitive_gap_extraction_service.extract_competitor_page(page, client=client, output_language="pl")

    assert "Polish" in str(client.calls[-1]["system_prompt"])
