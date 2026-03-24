"""Add competitor sync progress and reset support.

Revision ID: 0011_comp_gap_sync_progress
Revises: 0010_reco_lifecycle_state
Create Date: 2026-03-16 23:59:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0011_comp_gap_sync_progress"
down_revision: str | None = "0010_reco_lifecycle_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "site_competitors",
        sa.Column("last_sync_run_id", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "site_competitors",
        sa.Column("last_sync_stage", sa.String(length=32), nullable=False, server_default="idle"),
    )
    op.add_column(
        "site_competitors",
        sa.Column("last_sync_processed_urls", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "site_competitors",
        sa.Column("last_sync_url_limit", sa.Integer(), nullable=False, server_default="400"),
    )
    op.add_column(
        "site_competitors",
        sa.Column("last_sync_processed_extraction_pages", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "site_competitors",
        sa.Column("last_sync_total_extractable_pages", sa.Integer(), nullable=False, server_default="0"),
    )

    op.execute(
        sa.text(
            "UPDATE site_competitors "
            "SET last_sync_stage = CASE "
            "WHEN last_sync_status IN ('queued', 'running', 'done', 'failed') THEN last_sync_status "
            "ELSE 'idle' "
            "END"
        )
    )


def downgrade() -> None:
    op.drop_column("site_competitors", "last_sync_total_extractable_pages")
    op.drop_column("site_competitors", "last_sync_processed_extraction_pages")
    op.drop_column("site_competitors", "last_sync_url_limit")
    op.drop_column("site_competitors", "last_sync_processed_urls")
    op.drop_column("site_competitors", "last_sync_stage")
    op.drop_column("site_competitors", "last_sync_run_id")
