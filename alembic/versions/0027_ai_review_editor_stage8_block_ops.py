"""ai review editor stage 8 block operations

Revision ID: 0027_ai_review_editor_stage8_block_ops
Revises: 0026_ai_review_editor_stage7
Create Date: 2026-03-27 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0027_ai_review_editor_stage8"
down_revision: str | None = "0026_ai_review_editor_stage7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("editor_document_versions") as batch_op:
        batch_op.drop_constraint("ck_editor_document_versions_source_of_change", type_="check")
        batch_op.create_check_constraint(
            "ck_editor_document_versions_source_of_change",
            "source_of_change IN ('document_parse', 'document_update', 'manual_block_edit', 'block_insert', 'block_delete', 'rewrite_apply', 'rollback')",
        )


def downgrade() -> None:
    with op.batch_alter_table("editor_document_versions") as batch_op:
        batch_op.drop_constraint("ck_editor_document_versions_source_of_change", type_="check")
        batch_op.create_check_constraint(
            "ck_editor_document_versions_source_of_change",
            "source_of_change IN ('document_parse', 'document_update', 'manual_block_edit', 'rewrite_apply', 'rollback')",
        )
