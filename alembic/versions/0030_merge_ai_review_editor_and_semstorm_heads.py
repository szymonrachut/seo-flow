"""merge ai review editor and semstorm heads

Revision ID: 0030_merge_ai_review_semstorm
Revises: 0028_ai_review_editor_stage9, 0029_merge_content_gen_semstorm
Create Date: 2026-03-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "0030_merge_ai_review_semstorm"
down_revision: tuple[str, str] = ("0028_ai_review_editor_stage9", "0029_merge_content_gen_semstorm")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
