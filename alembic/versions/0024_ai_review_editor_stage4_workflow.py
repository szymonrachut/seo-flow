"""ai review editor stage 4 workflow

Revision ID: 0024_ai_review_editor_stage4
Revises: 0023_ai_review_editor_stage1
Create Date: 2026-03-27 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0024_ai_review_editor_stage4"
down_revision: str | None = "0023_ai_review_editor_stage1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("editor_review_issues") as batch_op:
        batch_op.add_column(sa.Column("resolution_note", sa.Text(), nullable=True))
        batch_op.drop_constraint("ck_editor_review_issues_status", type_="check")
        batch_op.create_check_constraint(
            "ck_editor_review_issues_status",
            "status IN ('open', 'dismissed', 'rewrite_requested', 'rewrite_ready', 'applied', 'resolved_manual', 'resolved')",
        )

    with op.batch_alter_table("editor_rewrite_runs") as batch_op:
        batch_op.add_column(sa.Column("schema_version", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        batch_op.drop_constraint("ck_editor_rewrite_runs_status", type_="check")
        batch_op.create_check_constraint(
            "ck_editor_rewrite_runs_status",
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'applied')",
        )


def downgrade() -> None:
    with op.batch_alter_table("editor_rewrite_runs") as batch_op:
        batch_op.drop_constraint("ck_editor_rewrite_runs_status", type_="check")
        batch_op.create_check_constraint(
            "ck_editor_rewrite_runs_status",
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
        )
        batch_op.drop_column("error_message")
        batch_op.drop_column("applied_at")
        batch_op.drop_column("schema_version")

    with op.batch_alter_table("editor_review_issues") as batch_op:
        batch_op.drop_constraint("ck_editor_review_issues_status", type_="check")
        batch_op.create_check_constraint(
            "ck_editor_review_issues_status",
            "status IN ('open', 'dismissed', 'resolved')",
        )
        batch_op.drop_column("resolution_note")
