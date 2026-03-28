"""semstorm brief execution v1

Revision ID: 0027_semstorm_brief_exec_v1
Revises: 0026_semstorm_brief_ai_v1
Create Date: 2026-03-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0027_semstorm_brief_exec_v1"
down_revision = "0026_semstorm_brief_ai_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "site_semstorm_brief_items",
        sa.Column("assignee", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "site_semstorm_brief_items",
        sa.Column("execution_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "site_semstorm_brief_items",
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "site_semstorm_brief_items",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "site_semstorm_brief_items",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "site_semstorm_brief_items",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_site_semstorm_brief_items_site_id_assignee",
        "site_semstorm_brief_items",
        ["site_id", "assignee"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_semstorm_brief_items_site_id_assignee",
        table_name="site_semstorm_brief_items",
    )
    op.drop_column("site_semstorm_brief_items", "archived_at")
    op.drop_column("site_semstorm_brief_items", "completed_at")
    op.drop_column("site_semstorm_brief_items", "started_at")
    op.drop_column("site_semstorm_brief_items", "ready_at")
    op.drop_column("site_semstorm_brief_items", "execution_note")
    op.drop_column("site_semstorm_brief_items", "assignee")
