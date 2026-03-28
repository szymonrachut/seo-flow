"""ai review editor stage 6 versions

Revision ID: 0025_ai_review_editor_v6
Revises: 0024_ai_review_editor_stage4
Create Date: 2026-03-27 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0025_ai_review_editor_v6"
down_revision: str | None = "0024_ai_review_editor_stage4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("editor_document_blocks") as batch_op:
        batch_op.drop_constraint("uq_editor_document_blocks_document_id_block_key", type_="unique")
        batch_op.drop_constraint("uq_editor_document_blocks_document_id_position", type_="unique")

    op.create_index(
        "uq_editor_document_blocks_document_id_block_key_active",
        "editor_document_blocks",
        ["document_id", "block_key"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "uq_editor_document_blocks_document_id_position_active",
        "editor_document_blocks",
        ["document_id", "position_index"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active"),
    )

    with op.batch_alter_table("editor_rewrite_runs") as batch_op:
        batch_op.add_column(sa.Column("source_block_content_hash", sa.String(length=64), nullable=True))

    op.create_table(
        "editor_document_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("source_of_change", sa.String(length=32), nullable=False),
        sa.Column("version_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_of_change IN ('document_parse', 'document_update', 'rewrite_apply', 'rollback')",
            name="ck_editor_document_versions_source_of_change",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["editor_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_no", name="uq_editor_document_versions_document_id_version_no"),
    )
    op.create_index(
        "ix_editor_document_versions_document_id",
        "editor_document_versions",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_editor_document_versions_document_id_created_at",
        "editor_document_versions",
        ["document_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_editor_document_versions_document_id_source",
        "editor_document_versions",
        ["document_id", "source_of_change"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_editor_document_versions_document_id_source", table_name="editor_document_versions")
    op.drop_index("ix_editor_document_versions_document_id_created_at", table_name="editor_document_versions")
    op.drop_index("ix_editor_document_versions_document_id", table_name="editor_document_versions")
    op.drop_table("editor_document_versions")

    op.drop_index(
        "uq_editor_document_blocks_document_id_position_active",
        table_name="editor_document_blocks",
    )
    op.drop_index(
        "uq_editor_document_blocks_document_id_block_key_active",
        table_name="editor_document_blocks",
    )

    with op.batch_alter_table("editor_document_blocks") as batch_op:
        batch_op.create_unique_constraint(
            "uq_editor_document_blocks_document_id_position",
            ["document_id", "position_index"],
        )
        batch_op.create_unique_constraint(
            "uq_editor_document_blocks_document_id_block_key",
            ["document_id", "block_key"],
        )

    with op.batch_alter_table("editor_rewrite_runs") as batch_op:
        batch_op.drop_column("source_block_content_hash")
