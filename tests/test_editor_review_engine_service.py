from __future__ import annotations

from app.db.models import EditorDocumentBlock
from app.services.editor_review_engine_service import generate_review_issues


def _make_block(
    *,
    block_key: str,
    block_type: str,
    position_index: int,
    text_content: str,
) -> EditorDocumentBlock:
    return EditorDocumentBlock(
        id=position_index,
        document_id=1,
        block_key=block_key,
        block_type=block_type,
        block_level=1 if block_type == "heading" else None,
        parent_block_key=None,
        position_index=position_index,
        text_content=text_content,
        html_content=None,
        context_path=None,
        content_hash=f"hash-{position_index}",
        is_active=True,
    )


def test_generate_review_issues_is_deterministic_and_skips_clean_blocks() -> None:
    blocks = [
        _make_block(block_key="H1-001", block_type="heading", position_index=1, text_content="Overview section"),
        _make_block(block_key="H2-002", block_type="heading", position_index=2, text_content="Plan"),
        _make_block(
            block_key="P-003",
            block_type="paragraph",
            position_index=3,
            text_content="TODO: Replace this draft with final copy after product review and approval.",
        ),
        _make_block(
            block_key="P-004",
            block_type="paragraph",
            position_index=4,
            text_content="Lorem ipsum dolor sit amet, placeholder text for the final example paragraph.",
        ),
        _make_block(block_key="P-005", block_type="paragraph", position_index=5, text_content="Too short."),
        _make_block(
            block_key="P-006",
            block_type="paragraph",
            position_index=6,
            text_content="This paragraph is descriptive enough to stay clean and should not create an issue.",
        ),
    ]

    first_run = generate_review_issues(blocks, review_mode="standard")
    second_run = generate_review_issues(blocks, review_mode="standard")

    assert first_run == second_run
    assert [(issue.block_key, issue.issue_type, issue.severity) for issue in first_run] == [
        ("H1-001", "generic_heading", "medium"),
        ("H2-002", "weak_heading", "medium"),
        ("P-003", "todo_marker", "high"),
        ("P-004", "placeholder_text", "high"),
        ("P-005", "short_paragraph", "medium"),
    ]
    assert all(issue.block_key != "P-006" for issue in first_run)


def test_generate_review_issues_respects_stricter_mode_thresholds() -> None:
    blocks = [
        _make_block(block_key="H2-001", block_type="heading", position_index=1, text_content="Best practices"),
        _make_block(
            block_key="P-002",
            block_type="paragraph",
            position_index=2,
            text_content="A concise paragraph that stays under the strict threshold only.",
        ),
    ]

    standard_issues = generate_review_issues(blocks, review_mode="standard")
    strict_issues = generate_review_issues(blocks, review_mode="strict")

    assert standard_issues == []
    assert [(issue.block_key, issue.issue_type) for issue in strict_issues] == [
        ("H2-001", "weak_heading"),
    ]
