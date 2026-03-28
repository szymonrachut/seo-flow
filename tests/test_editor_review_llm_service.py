from __future__ import annotations

import json

import pytest

from app.db.models import EditorDocument, EditorDocumentBlock
from app.schemas.ai_review_editor import EditorReviewLlmOutput
from app.services import editor_review_llm_service


class _RecordingReviewClient:
    provider_name = "openai-test"

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.user_payloads: list[dict] = []

    def is_available(self) -> bool:
        return True

    def parse_chat_completion(
        self,
        *,
        user_prompt: str,
        response_format,
        **_: object,
    ):
        self.user_payloads.append(json.loads(user_prompt))
        return response_format.model_validate(self.payload)


def _make_document() -> EditorDocument:
    return EditorDocument(
        id=11,
        site_id=7,
        title="Local SEO Service Page",
        document_type="money_page",
        source_format="html",
        source_content="<h1>Local SEO</h1><p>Example draft.</p>",
        normalized_content="Local SEO\n\nExample draft.",
        topic_brief_json={"primary_topic": "local SEO services", "brand": "Example"},
        facts_context_json={"brand": "Example", "services": ["Local SEO", "SEO Audit"]},
        status="parsed",
    )


def _make_blocks() -> list[EditorDocumentBlock]:
    return [
        EditorDocumentBlock(
            id=1,
            document_id=11,
            block_key="H1-001",
            block_type="heading",
            block_level=1,
            parent_block_key=None,
            position_index=1,
            text_content="Overview",
            html_content="<h1>Overview</h1>",
            context_path="Overview",
            content_hash="hash-h1",
            is_active=True,
        ),
        EditorDocumentBlock(
            id=2,
            document_id=11,
            block_key="P-002",
            block_type="paragraph",
            block_level=None,
            parent_block_key="H1-001",
            position_index=2,
            text_content="Our platform includes Example Analytics Pro for every local SEO plan.",
            html_content="<p>Our platform includes Example Analytics Pro for every local SEO plan.</p>",
            context_path="Overview",
            content_hash="hash-p2",
            is_active=True,
        ),
    ]


def test_normalize_review_output_filters_invalid_rows_and_keeps_valid_issue() -> None:
    parsed = EditorReviewLlmOutput.model_validate(
        {
            "document_issues": [],
            "block_issues": [
                {
                    "block_key": "P-002",
                    "issue_type": "product_hallucination",
                    "severity": "high",
                    "confidence": "0.91",
                    "message": "Product is not supported by the provided facts context.",
                    "reason": "Facts context names services but does not mention Example Analytics Pro.",
                    "replacement_instruction": "Replace the product mention with a supported service description.",
                },
                {
                    "block_key": "P-999",
                    "issue_type": "unsupported_claim",
                    "severity": "medium",
                    "message": "Unknown block key should be rejected.",
                },
                {
                    "block_key": "P-002",
                    "issue_type": "invented_issue",
                    "severity": "medium",
                    "message": "Unknown issue type should be filtered out.",
                },
                {
                    "block_key": "P-002",
                    "issue_type": "unsupported_claim",
                    "severity": "medium",
                    "message": "   ",
                },
                {
                    "block_key": "P-002",
                    "issue_type": "product_hallucination",
                    "severity": "high",
                    "message": "Product is not supported by the provided facts context.",
                },
            ],
        }
    )

    normalized = editor_review_llm_service.normalize_review_output(parsed, _make_blocks())

    assert normalized.raw_block_issue_count == 5
    assert normalized.rejected_issue_count == 4
    assert len(normalized.issue_drafts) == 1
    assert normalized.issue_drafts[0].block_key == "P-002"
    assert normalized.issue_drafts[0].issue_type == "product_hallucination"
    assert normalized.issue_drafts[0].severity == "high"
    assert normalized.issue_drafts[0].confidence == 0.91


def test_review_document_builds_prompt_from_brief_facts_and_active_blocks() -> None:
    fake_client = _RecordingReviewClient(
        {
            "document_issues": [],
            "block_issues": [
                {
                    "block_key": "H1-001",
                    "issue_type": "weak_heading",
                    "severity": "medium",
                    "confidence": 0.82,
                    "message": "Heading is too generic for the section.",
                    "reason": "The heading does not express the actual topic from the brief.",
                    "replacement_instruction": "Use a heading that names the local SEO service focus directly.",
                }
            ],
        }
    )

    result = editor_review_llm_service.review_document(
        _make_document(),
        _make_blocks(),
        review_mode="strict",
        client=fake_client,
    )

    assert result.llm_provider == "openai-test"
    assert result.llm_model == editor_review_llm_service.get_llm_model_name()
    assert len(result.issue_drafts) == 1

    prompt_payload = fake_client.user_payloads[0]
    assert prompt_payload["review_mode"] == "strict"
    assert prompt_payload["topic_brief_json"] == {"primary_topic": "local SEO services", "brand": "Example"}
    assert prompt_payload["facts_context_json"] == {
        "brand": "Example",
        "services": ["Local SEO", "SEO Audit"],
    }
    assert prompt_payload["blocks"] == [
        {
            "block_key": "H1-001",
            "block_level": 1,
            "block_type": "heading",
            "context_path": "Overview",
            "text_content": "Overview",
        },
        {
            "block_key": "P-002",
            "block_level": None,
            "block_type": "paragraph",
            "context_path": "Overview",
            "text_content": "Our platform includes Example Analytics Pro for every local SEO plan.",
        },
    ]


def test_review_document_fails_when_all_returned_block_issues_are_invalid() -> None:
    fake_client = _RecordingReviewClient(
        {
            "document_issues": [],
            "block_issues": [
                {
                    "block_key": "P-999",
                    "issue_type": "unsupported_claim",
                    "severity": "medium",
                    "message": "This block does not exist.",
                }
            ],
        }
    )

    with pytest.raises(editor_review_llm_service.EditorReviewLlmServiceError) as exc_info:
        editor_review_llm_service.review_document(
            _make_document(),
            _make_blocks(),
            review_mode="standard",
            client=fake_client,
        )

    assert exc_info.value.code == "review_output_invalid"
