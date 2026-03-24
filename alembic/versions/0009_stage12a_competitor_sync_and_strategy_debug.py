"""Add ETAP 12A.2 competitor sync and strategy debug fields.

Revision ID: 0009_comp_gap_sync_debug
Revises: 0008_stage12a_gap_core
Create Date: 2026-03-16 22:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0009_comp_gap_sync_debug"
down_revision: str | None = "0008_stage12a_gap_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dialect_name = op.get_bind().dialect.name

    op.add_column(
        "site_content_strategies",
        sa.Column("last_normalization_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "site_content_strategies",
        sa.Column("normalization_fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "site_content_strategies",
        sa.Column("normalization_debug_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "site_content_strategies",
        sa.Column("normalization_debug_message", sa.Text(), nullable=True),
    )

    op.execute(
        sa.text(
            "UPDATE site_competitors "
            "SET last_sync_status = 'idle' "
            "WHERE last_sync_status IS NULL OR last_sync_status = 'not_started'"
        )
    )
    if dialect_name != "sqlite":
        op.alter_column(
            "site_competitors",
            "last_sync_status",
            existing_type=sa.String(length=32),
            server_default="idle",
        )


def downgrade() -> None:
    dialect_name = op.get_bind().dialect.name

    if dialect_name != "sqlite":
        op.alter_column(
            "site_competitors",
            "last_sync_status",
            existing_type=sa.String(length=32),
            server_default="not_started",
        )
    op.execute(
        sa.text(
            "UPDATE site_competitors "
            "SET last_sync_status = 'not_started' "
            "WHERE last_sync_status = 'idle'"
        )
    )

    op.drop_column("site_content_strategies", "normalization_debug_message")
    op.drop_column("site_content_strategies", "normalization_debug_code")
    op.drop_column("site_content_strategies", "normalization_fallback_used")
    op.drop_column("site_content_strategies", "last_normalization_attempt_at")
