from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.text_processing import collapse_whitespace, normalize_text_for_hash
from app.db.models import EditorDocumentBlock


MOCK_EDITOR_REVIEW_ENGINE_VERSION = "ai_review_editor_mock_rules_v1"
MOCK_EDITOR_REVIEW_MODEL_NAME = "ai_review_editor_mock_rules_v1"
MOCK_EDITOR_REVIEW_PROMPT_VERSION = "ai_review_editor_prompt_v1"
MOCK_EDITOR_REVIEW_SCHEMA_VERSION = "ai_review_editor_review_v1"

_GENERIC_HEADING_PHRASES = {
    "intro",
    "introduction",
    "overview",
    "summary",
    "conclusion",
    "wstep",
    "wprowadzenie",
    "podsumowanie",
}
_PLACEHOLDER_PATTERN = re.compile(
    r"\b(lorem\s+ipsum|ipsum\s+dolor|placeholder(?:\s+text)?|dummy\s+text|sample\s+text)\b",
    re.IGNORECASE,
)
_TODO_PATTERN = re.compile(r"\b(todo|fixme|tbd)\b|\[todo\]", re.IGNORECASE)
_HEADING_THRESHOLDS: dict[str, tuple[int, int]] = {
    "light": (1, 8),
    "standard": (1, 12),
    "strict": (2, 18),
}
_PARAGRAPH_THRESHOLDS: dict[str, tuple[int, int]] = {
    "light": (4, 24),
    "standard": (6, 40),
    "strict": (8, 56),
}


@dataclass(frozen=True, slots=True)
class EditorReviewIssueDraft:
    block_key: str
    issue_type: str
    severity: str
    confidence: float
    message: str
    reason: str | None = None
    replacement_instruction: str | None = None
    replacement_candidate_text: str | None = None


def generate_review_issues(
    blocks: list[EditorDocumentBlock],
    *,
    review_mode: str,
) -> list[EditorReviewIssueDraft]:
    normalized_mode = _normalize_review_mode(review_mode)
    issue_drafts: list[EditorReviewIssueDraft] = []

    for block in blocks:
        block_text = collapse_whitespace(block.text_content)
        if not block_text:
            continue

        if block.block_type == "heading":
            issue_drafts.extend(_review_heading(block.block_key, block_text, normalized_mode))
            continue

        if block.block_type not in {"paragraph", "list_item"}:
            continue

        issue_drafts.extend(_review_body_text(block.block_key, block_text, normalized_mode))

    return issue_drafts


def review_document_blocks(
    blocks: list[EditorDocumentBlock],
    *,
    review_mode: str,
) -> list[EditorReviewIssueDraft]:
    return generate_review_issues(blocks, review_mode=review_mode)


def _review_heading(block_key: str, text: str, review_mode: str) -> list[EditorReviewIssueDraft]:
    normalized_text = normalize_text_for_hash(text)
    tokens = normalized_text.split()
    word_count = len(tokens)
    char_count = len(collapse_whitespace(text))
    max_words, max_chars = _HEADING_THRESHOLDS[review_mode]
    drafts: list[EditorReviewIssueDraft] = []

    if _is_generic_heading(normalized_text, tokens):
        drafts.append(
            EditorReviewIssueDraft(
                block_key=block_key,
                issue_type="generic_heading",
                severity="medium",
                confidence=0.84,
                message="Heading is too generic and could be more specific.",
                reason=f"Heading text {text!r} uses a generic section label such as intro or summary.",
                replacement_instruction="Replace the heading with a more specific section title.",
                replacement_candidate_text=text.strip(),
            )
        )

    if word_count <= max_words and char_count <= max_chars:
        severity = "medium" if word_count == 1 and char_count <= 8 else "low"
        drafts.append(
            EditorReviewIssueDraft(
                block_key=block_key,
                issue_type="weak_heading",
                severity=severity,
                confidence=0.68 if severity == "low" else 0.76,
                message="Heading is likely too weak to guide the reader.",
                reason=f"Heading has only {word_count} word(s) and {char_count} character(s) after normalization.",
                replacement_instruction="Expand the heading so it describes the section more clearly.",
                replacement_candidate_text=text.strip(),
            )
        )

    return drafts


def _review_body_text(block_key: str, text: str, review_mode: str) -> list[EditorReviewIssueDraft]:
    normalized_text = normalize_text_for_hash(text)
    tokens = normalized_text.split()
    word_count = len(tokens)
    char_count = len(collapse_whitespace(text))
    max_words, max_chars = _PARAGRAPH_THRESHOLDS[review_mode]

    drafts: list[EditorReviewIssueDraft] = []
    if _TODO_PATTERN.search(text):
        drafts.append(
            EditorReviewIssueDraft(
                block_key=block_key,
                issue_type="todo_marker",
                severity="high",
                confidence=0.98,
                message="Paragraph contains a TODO marker that should not ship.",
                reason="Matched a TODO-style placeholder marker such as TODO, FIXME, or TBD.",
                replacement_instruction="Replace the TODO marker with final copy or remove the unfinished placeholder.",
                replacement_candidate_text=text.strip(),
            )
        )

    if _PLACEHOLDER_PATTERN.search(text):
        drafts.append(
            EditorReviewIssueDraft(
                block_key=block_key,
                issue_type="placeholder_text",
                severity="high",
                confidence=0.99,
                message="Paragraph looks like placeholder copy.",
                reason="Matched placeholder wording such as lorem ipsum or dummy text.",
                replacement_instruction="Replace the placeholder copy with final content.",
                replacement_candidate_text=text.strip(),
            )
        )

    if not drafts and word_count <= max_words and char_count <= max_chars:
        severity = "medium" if word_count <= 2 or char_count <= 15 else "low"
        drafts.append(
            EditorReviewIssueDraft(
                block_key=block_key,
                issue_type="short_paragraph",
                severity=severity,
                confidence=0.74 if severity == "low" else 0.82,
                message="Paragraph is too short to carry useful meaning.",
                reason=f"Paragraph has only {word_count} word(s) and {char_count} character(s) after normalization.",
                replacement_instruction="Expand the paragraph so it adds context or evidence.",
                replacement_candidate_text=text.strip(),
            )
        )

    return drafts


def _is_generic_heading(normalized_text: str, tokens: list[str]) -> bool:
    if normalized_text in _GENERIC_HEADING_PHRASES:
        return True
    return len(tokens) <= 2 and any(token in _GENERIC_HEADING_PHRASES for token in tokens)


def _normalize_review_mode(review_mode: str | None) -> str:
    normalized_mode = (review_mode or "standard").strip().lower()
    if normalized_mode not in _HEADING_THRESHOLDS:
        return "standard"
    return normalized_mode
