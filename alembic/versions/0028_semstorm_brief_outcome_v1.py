"""semstorm brief outcome v1

Revision ID: 0028_semstorm_brief_impl_v1
Revises: 0027_semstorm_brief_exec_v1
Create Date: 2026-03-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0028_semstorm_brief_impl_v1"
down_revision: str | None = "0027_semstorm_brief_exec_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "site_semstorm_brief_items",
        sa.Column("implementation_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "site_semstorm_brief_items",
        sa.Column("implemented_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "site_semstorm_brief_items",
        sa.Column("evaluation_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "site_semstorm_brief_items",
        sa.Column("last_outcome_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "site_semstorm_brief_items",
        sa.Column("implementation_url_override", sa.String(length=2048), nullable=True),
    )
    op.create_index(
        "ix_site_semstorm_brief_items_site_id_impl_status",
        "site_semstorm_brief_items",
        ["site_id", "implementation_status"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_brief_items_site_id_implemented_at",
        "site_semstorm_brief_items",
        ["site_id", "implemented_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_semstorm_brief_items_site_id_implemented_at",
        table_name="site_semstorm_brief_items",
    )
    op.drop_index(
        "ix_site_semstorm_brief_items_site_id_impl_status",
        table_name="site_semstorm_brief_items",
    )
    op.drop_column("site_semstorm_brief_items", "implementation_url_override")
    op.drop_column("site_semstorm_brief_items", "last_outcome_checked_at")
    op.drop_column("site_semstorm_brief_items", "evaluation_note")
    op.drop_column("site_semstorm_brief_items", "implemented_at")
    op.drop_column("site_semstorm_brief_items", "implementation_status")
