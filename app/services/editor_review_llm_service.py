from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from app.core.config import get_settings
from app.core.text_processing import collapse_whitespace
from app.db.models import EditorDocument, EditorDocumentBlock
from app.integrations.openai.client import OpenAiConfigurationError, OpenAiIntegrationError, OpenAiLlmClient
from app.schemas.ai_review_editor import (
    EditorReviewBlockInput,
    EditorReviewLlmOutput,
    EditorReviewPromptInput,
)
from app.services.editor_review_engine_service import EditorReviewIssueDraft


EDITOR_REVIEW_LLM_PROMPT_VERSION = "ai_review_editor_review_llm_v1"
EDITOR_REVIEW_LLM_SCHEMA_VERSION = "ai_review_editor_review_output_v1"
EDITOR_REVIEW_LLM_COMPLETION_LIMITS = (1800, 2600)
EDITOR_REVIEW_LLM_ALLOWED_ISSUE_TYPES = (
    "brand_mismatch",
    "factuality",
    "irrelevant_entity",
    "off_topic",
    "product_hallucination",
    "terminology_inconsistency",
    "unclear",
    "unsupported_claim",
    "weak_heading",
)
EDITOR_REVIEW_LLM_ALLOWED_SEVERITIES = ("low", "medium", "high")


class EditorReviewLlmServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "editor_review_llm_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class EditorReviewNormalizationResult:
    issue_drafts: list[EditorReviewIssueDraft]
    raw_block_issue_count: int
    raw_document_issue_count: int
    rejected_issue_count: int


@dataclass(frozen=True, slots=True)
class EditorReviewLlmExecutionResult:
    issue_drafts: list[EditorReviewIssueDraft]
    llm_provider: str | None
    llm_model: str
    prompt_version: str
    schema_version: str
    raw_block_issue_count: int
    raw_document_issue_count: int
    rejected_issue_count: int


def review_document(
    document: EditorDocument,
    blocks: list[EditorDocumentBlock],
    *,
    review_mode: str,
    client: OpenAiLlmClient | Any | None = None,
) -> EditorReviewLlmExecutionResult:
    resolved_client = client or OpenAiLlmClient()
    llm_model = get_llm_model_name()
    if not resolved_client.is_available():
        raise EditorReviewLlmServiceError(_resolve_unavailable_message(), code=_resolve_unavailable_code())

    parsed = None
    last_error: OpenAiIntegrationError | None = None
    try:
        for completion_limit in EDITOR_REVIEW_LLM_COMPLETION_LIMITS:
            try:
                parsed = resolved_client.parse_chat_completion(
                    model=llm_model,
                    system_prompt=_build_review_system_prompt(),
                    user_prompt=_build_review_user_prompt(document, blocks, review_mode=review_mode),
                    response_format=EditorReviewLlmOutput,
                    max_completion_tokens=completion_limit,
                    reasoning_effort="low",
                    verbosity="low",
                )
                break
            except OpenAiIntegrationError as exc:
                last_error = exc
                if exc.code == "length_limit" and completion_limit != EDITOR_REVIEW_LLM_COMPLETION_LIMITS[-1]:
                    continue
                raise
    except OpenAiConfigurationError as exc:
        raise EditorReviewLlmServiceError(str(exc), code=exc.code) from exc
    except OpenAiIntegrationError as exc:
        raise EditorReviewLlmServiceError(str(exc), code=exc.code) from exc

    if parsed is None:
        fallback_exc = last_error or OpenAiIntegrationError(
            "Editor review model returned no structured output.",
            code="structured_output_missing",
        )
        raise EditorReviewLlmServiceError(str(fallback_exc), code=fallback_exc.code)

    normalized = normalize_review_output(parsed, blocks)
    if normalized.raw_block_issue_count > 0 and not normalized.issue_drafts:
        raise EditorReviewLlmServiceError(
            "Editor review output contained block issues, but none passed validation for this document.",
            code="review_output_invalid",
        )

    return EditorReviewLlmExecutionResult(
        issue_drafts=normalized.issue_drafts,
        llm_provider=getattr(resolved_client, "provider_name", "openai"),
        llm_model=llm_model,
        prompt_version=EDITOR_REVIEW_LLM_PROMPT_VERSION,
        schema_version=EDITOR_REVIEW_LLM_SCHEMA_VERSION,
        raw_block_issue_count=normalized.raw_block_issue_count,
        raw_document_issue_count=normalized.raw_document_issue_count,
        rejected_issue_count=normalized.rejected_issue_count,
    )


def normalize_review_output(
    parsed: EditorReviewLlmOutput,
    blocks: list[EditorDocumentBlock],
) -> EditorReviewNormalizationResult:
    block_keys = {collapse_whitespace(block.block_key): block for block in blocks}
    issue_drafts: list[EditorReviewIssueDraft] = []
    seen: set[tuple[str, str]] = set()
    rejected_issue_count = 0

    for raw_issue in parsed.block_issues:
        normalized_issue = _normalize_block_issue(raw_issue, block_keys=block_keys)
        if normalized_issue is None:
            rejected_issue_count += 1
            continue
        dedupe_key = (normalized_issue.block_key, normalized_issue.issue_type)
        if dedupe_key in seen:
            rejected_issue_count += 1
            continue
        seen.add(dedupe_key)
        issue_drafts.append(normalized_issue)

    return EditorReviewNormalizationResult(
        issue_drafts=issue_drafts,
        raw_block_issue_count=len(parsed.block_issues),
        raw_document_issue_count=len(parsed.document_issues),
        rejected_issue_count=rejected_issue_count,
    )


def build_review_prompt_input(
    document: EditorDocument,
    blocks: list[EditorDocumentBlock],
    *,
    review_mode: str,
) -> EditorReviewPromptInput:
    normalized_review_mode = _normalize_review_mode(review_mode)
    return EditorReviewPromptInput(
        prompt_version=EDITOR_REVIEW_LLM_PROMPT_VERSION,
        task="editor_document_review",
        review_mode=normalized_review_mode,
        allowed_issue_types=list(EDITOR_REVIEW_LLM_ALLOWED_ISSUE_TYPES),
        allowed_severities=list(EDITOR_REVIEW_LLM_ALLOWED_SEVERITIES),
        document={
            "document_id": int(document.id),
            "site_id": int(document.site_id),
            "title": document.title,
            "document_type": document.document_type,
            "source_format": document.source_format,
            "status": document.status,
        },
        topic_brief_json=document.topic_brief_json,
        facts_context_json=document.facts_context_json,
        blocks=[
            EditorReviewBlockInput(
                block_key=block.block_key,
                block_type=block.block_type,
                block_level=block.block_level,
                context_path=block.context_path,
                text_content=collapse_whitespace(block.text_content),
            )
            for block in blocks
            if collapse_whitespace(block.text_content)
        ],
    )


def build_engine_version(*, llm_model: str | None = None) -> str:
    model_name = llm_model or get_llm_model_name()
    return f"{EDITOR_REVIEW_LLM_PROMPT_VERSION}:{EDITOR_REVIEW_LLM_SCHEMA_VERSION}:{model_name}"


def get_llm_model_name() -> str:
    return get_settings().openai_model_editor_review


def llm_is_available(client: OpenAiLlmClient | Any | None = None) -> bool:
    resolved_client = client or OpenAiLlmClient()
    return bool(resolved_client.is_available())


def _normalize_block_issue(
    raw_issue: Any,
    *,
    block_keys: dict[str, EditorDocumentBlock],
) -> EditorReviewIssueDraft | None:
    block_key = collapse_whitespace(getattr(raw_issue, "block_key", None) or "")
    if not block_key or block_key not in block_keys:
        return None

    issue_type = collapse_whitespace(getattr(raw_issue, "issue_type", None) or "").lower()
    if issue_type not in EDITOR_REVIEW_LLM_ALLOWED_ISSUE_TYPES:
        return None

    severity = collapse_whitespace(getattr(raw_issue, "severity", None) or "").lower()
    if severity not in EDITOR_REVIEW_LLM_ALLOWED_SEVERITIES:
        return None

    message = _clean_required_text(getattr(raw_issue, "message", None), max_length=500)
    if not message:
        return None

    return EditorReviewIssueDraft(
        block_key=block_key,
        issue_type=issue_type,
        severity=severity,
        confidence=_parse_confidence(getattr(raw_issue, "confidence", None)),
        message=message,
        reason=_clean_optional_text(getattr(raw_issue, "reason", None), max_length=1200),
        replacement_instruction=_clean_optional_text(
            getattr(raw_issue, "replacement_instruction", None),
            max_length=500,
        ),
        replacement_candidate_text=None,
    )


def _clean_required_text(value: Any, *, max_length: int) -> str | None:
    cleaned = collapse_whitespace(str(value or ""))
    if not cleaned:
        return None
    return cleaned[:max_length]


def _clean_optional_text(value: Any, *, max_length: int) -> str | None:
    cleaned = collapse_whitespace(str(value or ""))
    if not cleaned:
        return None
    return cleaned[:max_length]


def _parse_confidence(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if confidence < 0.0 or confidence > 1.0:
        return None
    return round(confidence, 4)


def _build_review_system_prompt() -> str:
    return (
        "You are a strict structured review engine for editorial blocks. "
        "Use only the provided JSON payload. "
        "Do not use outside world knowledge, browsing, or unstated assumptions. "
        "Judge each block only against topic_brief_json, facts_context_json, and the supplied document blocks. "
        "Flag only problematic blocks. Omit clean blocks entirely. "
        "Never praise, summarize, or comment on every block. "
        "Prefer fewer, higher-confidence issues over broad coverage. "
        "Do not emit multiple variants of the same issue type for one block. "
        "Skip stylistic nits unless they create a clear editorial problem. "
        "When a claim, product, brand, entity, or terminology choice is not supported by the provided context, "
        "flag it conservatively instead of assuming it is true. "
        "Return only valid JSON matching the schema. "
        "replacement_instruction is optional and must stay a short edit instruction, not a rewrite."
    )


def _build_review_user_prompt(
    document: EditorDocument,
    blocks: list[EditorDocumentBlock],
    *,
    review_mode: str,
) -> str:
    payload = build_review_prompt_input(document, blocks, review_mode=review_mode).model_dump(mode="json")
    payload["review_mode_guidance"] = _review_mode_guidance(payload["review_mode"])
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _review_mode_guidance(review_mode: str) -> str:
    if review_mode == "light":
        return "Raise issues only when the problem is clear and well-supported by the provided context."
    if review_mode == "strict":
        return "Be stricter about unsupported claims, off-topic drift, weak headings, unclear language, and terminology mismatch."
    return "Use a balanced review threshold and report only meaningful problems."


def _normalize_review_mode(review_mode: str | None) -> str:
    normalized_mode = collapse_whitespace(review_mode or "standard").lower()
    if normalized_mode in {"light", "standard", "strict"}:
        return normalized_mode
    return "standard"


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
        return "OpenAI editor review is disabled in backend config."
    if code == "missing_api_key":
        return "OPENAI_API_KEY is not configured for editor review."
    return "OpenAI editor review is currently unavailable."
