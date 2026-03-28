from __future__ import annotations

import json

import pytest

from app.db.models import EditorDocument, EditorDocumentBlock, EditorReviewIssue
from app.schemas.ai_review_editor import EditorRewriteLlmOutput
from app.services import editor_rewrite_llm_service


class _RecordingRewriteClient:
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
        id=21,
        site_id=5,
        title="Local SEO Landing Page",
        document_type="money_page",
        source_format="html",
        source_content="<h1>Overview</h1><p>Draft.</p>",
        normalized_content="Overview\n\nDraft.",
        topic_brief_json={"primary_topic": "local SEO services"},
        facts_context_json={"brand": "Example", "services": ["Local SEO", "SEO Audit"]},
        status="parsed",
    )


def _make_blocks() -> list[EditorDocumentBlock]:
    return [
        EditorDocumentBlock(
            id=1,
            document_id=21,
            block_key="H1-001",
            block_type="heading",
            block_level=1,
            parent_block_key=None,
            position_index=1,
            text_content="Overview",
            html_content="<h1>Overview</h1>",
            context_path="Overview",
            content_hash="hash-1",
            is_active=True,
        ),
        EditorDocumentBlock(
            id=2,
            document_id=21,
            block_key="P-002",
            block_type="paragraph",
            block_level=None,
            parent_block_key="H1-001",
            position_index=2,
            text_content="Example Analytics Pro is included in every package.",
            html_content="<p>Example Analytics Pro is included in every package.</p>",
            context_path="Overview",
            content_hash="hash-2",
            is_active=True,
        ),
        EditorDocumentBlock(
            id=3,
            document_id=21,
            block_key="P-003",
            block_type="paragraph",
            block_level=None,
            parent_block_key="H1-001",
            position_index=3,
            text_content="Contact us for a verified local SEO plan.",
            html_content="<p>Contact us for a verified local SEO plan.</p>",
            context_path="Overview",
            content_hash="hash-3",
            is_active=True,
        ),
    ]


def _make_issue() -> EditorReviewIssue:
    return EditorReviewIssue(
        id=8,
        review_run_id=3,
        document_id=21,
        block_key="P-002",
        issue_type="product_hallucination",
        severity="high",
        confidence=0.94,
        message="The paragraph introduces a product not grounded in facts_context_json.",
        reason="Facts context only lists services, not Example Analytics Pro.",
        replacement_instruction="Replace the product mention with a supported service description.",
        replacement_candidate_text=None,
        status="open",
    )


def test_rewrite_issue_block_builds_single_block_prompt_and_accepts_valid_output() -> None:
    fake_client = _RecordingRewriteClient(
        {
            "block_key": "P-002",
            "rewritten_text": "Every package includes support for local SEO services tailored to your business goals.",
        }
    )

    result = editor_rewrite_llm_service.rewrite_issue_block(
        _make_document(),
        _make_blocks(),
        _make_blocks()[1],
        _make_issue(),
        client=fake_client,
    )

    assert result.block_key == "P-002"
    assert result.rewritten_text.startswith("Every package includes support for local SEO services")
    prompt_payload = fake_client.user_payloads[0]
    assert prompt_payload["block"]["block_key"] == "P-002"
    assert prompt_payload["issue"]["issue_type"] == "product_hallucination"
    assert [item["relation"] for item in prompt_payload["neighbor_blocks"]] == ["previous", "next"]


def test_rewrite_output_rejects_wrong_block_key() -> None:
    with pytest.raises(editor_rewrite_llm_service.EditorRewriteLlmServiceError) as exc_info:
        editor_rewrite_llm_service.normalize_rewrite_output(
            EditorRewriteLlmOutput.model_validate(
                {
                    "block_key": "P-999",
                    "rewritten_text": "Supported text.",
                }
            ),
            target_block=_make_blocks()[1],
        )

    assert exc_info.value.code == "rewrite_block_key_mismatch"


def test_rewrite_output_rejects_missing_or_unchanged_text() -> None:
    target_block = _make_blocks()[1]

    with pytest.raises(editor_rewrite_llm_service.EditorRewriteLlmServiceError) as empty_exc:
        editor_rewrite_llm_service.normalize_rewrite_output(
            EditorRewriteLlmOutput.model_validate(
                {"block_key": "P-002", "rewritten_text": "   "}
            ),
            target_block=target_block,
        )
    assert empty_exc.value.code == "rewrite_output_empty"

    with pytest.raises(editor_rewrite_llm_service.EditorRewriteLlmServiceError) as same_exc:
        editor_rewrite_llm_service.normalize_rewrite_output(
            EditorRewriteLlmOutput.model_validate(
                {
                    "block_key": "P-002",
                    "rewritten_text": "Example Analytics Pro is included in every package.",
                }
            ),
            target_block=target_block,
        )
    assert same_exc.value.code == "rewrite_no_change"
