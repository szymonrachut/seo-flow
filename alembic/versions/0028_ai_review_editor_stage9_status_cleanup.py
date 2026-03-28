"""ai review editor stage 9 status cleanup

Revision ID: 0028_ai_review_editor_stage9
Revises: 0027_ai_review_editor_stage8
Create Date: 2026-03-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0028_ai_review_editor_stage9"
down_revision: str | None = "0027_ai_review_editor_stage8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("editor_review_issues") as batch_op:
        batch_op.drop_constraint("ck_editor_review_issues_status", type_="check")
        batch_op.create_check_constraint(
            "ck_editor_review_issues_status",
            "status IN ('open', 'dismissed', 'rewrite_requested', 'rewrite_ready', 'applied', 'resolved_manual')",
        )


def downgrade() -> None:
    with op.batch_alter_table("editor_review_issues") as batch_op:
        batch_op.drop_constraint("ck_editor_review_issues_status", type_="check")
        batch_op.create_check_constraint(
            "ck_editor_review_issues_status",
            "status IN ('open', 'dismissed', 'rewrite_requested', 'rewrite_ready', 'applied', 'resolved_manual', 'resolved')",
        )
