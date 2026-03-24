"""Add operational sync runs for competitive gap competitor sync.

Revision ID: 0013_comp_gap_sync_runs
Revises: 0012_comp_gap_hardening
Create Date: 2026-03-17 09:15:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0013_comp_gap_sync_runs"
down_revision: str | None = "0012_comp_gap_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_competitor_sync_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("competitor_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("trigger_source", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message_safe", sa.Text(), nullable=True),
        sa.Column(
            "summary_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("retry_of_run_id", sa.Integer(), nullable=True),
        sa.Column("processed_urls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("url_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_extraction_pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_extractable_pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["competitor_id"], ["site_competitors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("competitor_id", "run_id", name="uq_site_competitor_sync_runs_competitor_id_run_id"),
    )
    op.create_index(
        "ix_site_competitor_sync_runs_site_id",
        "site_competitor_sync_runs",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_sync_runs_competitor_id",
        "site_competitor_sync_runs",
        ["competitor_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_sync_runs_status",
        "site_competitor_sync_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_sync_runs_lease_expires_at",
        "site_competitor_sync_runs",
        ["lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_sync_runs_competitor_id_created_at",
        "site_competitor_sync_runs",
        ["competitor_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_site_competitor_sync_runs_competitor_id_created_at", table_name="site_competitor_sync_runs")
    op.drop_index("ix_site_competitor_sync_runs_lease_expires_at", table_name="site_competitor_sync_runs")
    op.drop_index("ix_site_competitor_sync_runs_status", table_name="site_competitor_sync_runs")
    op.drop_index("ix_site_competitor_sync_runs_competitor_id", table_name="site_competitor_sync_runs")
    op.drop_index("ix_site_competitor_sync_runs_site_id", table_name="site_competitor_sync_runs")
    op.drop_table("site_competitor_sync_runs")
