from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from app.core.config import get_settings
from app.core.text_processing import collapse_whitespace
from app.db.models import EditorDocument, EditorDocumentBlock, EditorReviewIssue
from app.integrations.openai.client import OpenAiConfigurationError, OpenAiIntegrationError, OpenAiLlmClient
from app.schemas.ai_review_editor import (
    EditorReviewBlockInput,
    EditorRewriteLlmOutput,
    EditorRewriteNeighborBlockInput,
    EditorRewritePromptInput,
)
import app.services.editor_document_version_service as editor_document_version_service


EDITOR_REWRITE_LLM_PROMPT_VERSION = "ai_review_editor_rewrite_llm_v1"
EDITOR_REWRITE_LLM_SCHEMA_VERSION = "ai_review_editor_rewrite_output_v1"
EDITOR_REWRITE_LLM_COMPLETION_LIMITS = (700, 1100)


class EditorRewriteLlmServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "editor_rewrite_llm_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class EditorRewriteLlmExecutionResult:
    block_key: str
    rewritten_text: str
    llm_provider: str | None
    llm_model: str
    prompt_version: str
    schema_version: str


def rewrite_issue_block(
    document: EditorDocument,
    blocks: list[EditorDocumentBlock],
    target_block: EditorDocumentBlock,
    issue: EditorReviewIssue,
    *,
    client: OpenAiLlmClient | Any | None = None,
) -> EditorRewriteLlmExecutionResult:
    resolved_client = client or OpenAiLlmClient()
    llm_model = get_llm_model_name()
    if not resolved_client.is_available():
        raise EditorRewriteLlmServiceError(_resolve_unavailable_message(), code=_resolve_unavailable_code())

    parsed = None
    last_error: OpenAiIntegrationError | None = None
    try:
        for completion_limit in EDITOR_REWRITE_LLM_COMPLETION_LIMITS:
            try:
                parsed = resolved_client.parse_chat_completion(
                    model=llm_model,
                    system_prompt=_build_rewrite_system_prompt(),
                    user_prompt=_build_rewrite_user_prompt(document, blocks, target_block, issue),
                    response_format=EditorRewriteLlmOutput,
                    max_completion_tokens=completion_limit,
                    reasoning_effort="minimal",
                    verbosity="low",
                )
                break
            except OpenAiIntegrationError as exc:
                last_error = exc
                if exc.code == "length_limit" and completion_limit != EDITOR_REWRITE_LLM_COMPLETION_LIMITS[-1]:
                    continue
                raise
    except OpenAiConfigurationError as exc:
        raise EditorRewriteLlmServiceError(str(exc), code=exc.code) from exc
    except OpenAiIntegrationError as exc:
        raise EditorRewriteLlmServiceError(str(exc), code=exc.code) from exc

    if parsed is None:
        fallback_exc = last_error or OpenAiIntegrationError(
            "Editor rewrite model returned no structured output.",
            code="structured_output_missing",
        )
        raise EditorRewriteLlmServiceError(str(fallback_exc), code=fallback_exc.code)

    normalized = normalize_rewrite_output(parsed, target_block=target_block)
    return EditorRewriteLlmExecutionResult(
        block_key=normalized["block_key"],
        rewritten_text=normalized["rewritten_text"],
        llm_provider=getattr(resolved_client, "provider_name", "openai"),
        llm_model=llm_model,
        prompt_version=EDITOR_REWRITE_LLM_PROMPT_VERSION,
        schema_version=EDITOR_REWRITE_LLM_SCHEMA_VERSION,
    )


def normalize_rewrite_output(
    parsed: EditorRewriteLlmOutput,
    *,
    target_block: EditorDocumentBlock,
) -> dict[str, str]:
    block_key = collapse_whitespace(parsed.block_key or "")
    if not block_key:
        raise EditorRewriteLlmServiceError("Rewrite output is missing block_key.", code="rewrite_output_missing_block_key")
    if block_key != target_block.block_key:
        raise EditorRewriteLlmServiceError(
            "Rewrite output block_key does not match the requested block.",
            code="rewrite_block_key_mismatch",
        )

    rewritten_text = collapse_whitespace(parsed.rewritten_text or "")
    if not rewritten_text:
        raise EditorRewriteLlmServiceError(
            "Rewrite output is missing rewritten_text.",
            code="rewrite_output_empty",
        )
    if rewritten_text == collapse_whitespace(target_block.text_content):
        raise EditorRewriteLlmServiceError(
            "Rewrite output did not change the original block text.",
            code="rewrite_no_change",
        )

    return {
        "block_key": block_key,
        "rewritten_text": rewritten_text[:12000],
    }


def build_rewrite_prompt_input(
    document: EditorDocument,
    blocks: list[EditorDocumentBlock],
    target_block: EditorDocumentBlock,
    issue: EditorReviewIssue,
) -> EditorRewritePromptInput:
    return EditorRewritePromptInput(
        prompt_version=EDITOR_REWRITE_LLM_PROMPT_VERSION,
        task="editor_single_block_rewrite",
        document={
            "document_id": int(document.id),
            "site_id": int(document.site_id),
            "title": document.title,
            "document_type": document.document_type,
            "status": document.status,
        },
        issue={
            "issue_id": int(issue.id),
            "issue_type": issue.issue_type,
            "severity": issue.severity,
            "message": issue.message,
            "reason": issue.reason,
            "replacement_instruction": issue.replacement_instruction,
        },
        block=EditorReviewBlockInput(
            block_key=target_block.block_key,
            block_type=target_block.block_type,
            block_level=target_block.block_level,
            context_path=target_block.context_path,
            text_content=collapse_whitespace(target_block.text_content),
        ),
        neighbor_blocks=_build_neighbor_blocks(blocks, target_block=target_block),
        topic_brief_json=document.topic_brief_json,
        facts_context_json=document.facts_context_json,
    )


def build_input_hash(
    document: EditorDocument,
    blocks: list[EditorDocumentBlock],
    target_block: EditorDocumentBlock,
    issue: EditorReviewIssue,
) -> str:
    payload = build_rewrite_prompt_input(document, blocks, target_block, issue).model_dump(mode="json")
    payload["schema_version"] = EDITOR_REWRITE_LLM_SCHEMA_VERSION
    payload["llm_model"] = get_llm_model_name()
    payload["document_version_hash"] = editor_document_version_service.build_current_document_version_hash(
        document,
        active_blocks=blocks,
    )
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_llm_model_name() -> str:
    return get_settings().openai_model_editor_rewrite


def llm_is_available(client: OpenAiLlmClient | Any | None = None) -> bool:
    resolved_client = client or OpenAiLlmClient()
    return bool(resolved_client.is_available())


def _build_neighbor_blocks(
    blocks: list[EditorDocumentBlock],
    *,
    target_block: EditorDocumentBlock,
) -> list[EditorRewriteNeighborBlockInput]:
    ordered_blocks = sorted(blocks, key=lambda item: (item.position_index, item.id))
    target_index = next((index for index, block in enumerate(ordered_blocks) if block.id == target_block.id), None)
    if target_index is None:
        return []

    neighbor_blocks: list[EditorRewriteNeighborBlockInput] = []
    if target_index > 0:
        previous_block = ordered_blocks[target_index - 1]
        previous_text = collapse_whitespace(previous_block.text_content)
        if previous_text:
            neighbor_blocks.append(
                EditorRewriteNeighborBlockInput(
                    relation="previous",
                    block_key=previous_block.block_key,
                    block_type=previous_block.block_type,
                    block_level=previous_block.block_level,
                    text_content=previous_text[:2000],
                )
            )
    if target_index + 1 < len(ordered_blocks):
        next_block = ordered_blocks[target_index + 1]
        next_text = collapse_whitespace(next_block.text_content)
        if next_text:
            neighbor_blocks.append(
                EditorRewriteNeighborBlockInput(
                    relation="next",
                    block_key=next_block.block_key,
                    block_type=next_block.block_type,
                    block_level=next_block.block_level,
                    text_content=next_text[:2000],
                )
            )
    return neighbor_blocks


def _build_rewrite_system_prompt() -> str:
    return (
        "You rewrite exactly one editorial block. "
        "Use only the provided JSON payload. "
        "Do not change any other block, section, or document-level structure. "
        "Keep the rewrite conservative, factual, and aligned with topic_brief_json and facts_context_json. "
        "Preserve the block's role, approximate scope, and local continuity with neighbor blocks. "
        "Do not add new promises, sections, bullet markers, calls to action, or speculative detail. "
        "Do not invent products, brands, features, claims, numbers, or entities. "
        "Do not explain your work. Do not return variants. "
        "Return only valid JSON with the same block_key and one rewritten_text value."
    )


def _build_rewrite_user_prompt(
    document: EditorDocument,
    blocks: list[EditorDocumentBlock],
    target_block: EditorDocumentBlock,
    issue: EditorReviewIssue,
) -> str:
    payload = build_rewrite_prompt_input(document, blocks, target_block, issue).model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _resolve_unavailable_code() -> str:
    settings = get_settings()
    if not settings.openai_llm_enabled:
        return "llm_disabled"
    if not settings.openai_api_key:
        return "missing_api_key"
    return "llm_unavailable"


def _resolve_unavailable_message() -> str:
    code = _resolve_unavailable_code()
    if code == "llm_disabled":
        return "OpenAI editor rewrite is disabled in backend config."
    if code == "missing_api_key":
        return "OPENAI_API_KEY is not configured for editor rewrite."
    return "OpenAI editor rewrite is currently unavailable."
