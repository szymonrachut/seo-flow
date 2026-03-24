"""Add competitor sync diagnostics summary.

Revision ID: 0012_comp_gap_hardening
Revises: 0011_comp_gap_sync_progress
Create Date: 2026-03-17 00:45:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0012_comp_gap_hardening"
down_revision: str | None = "0011_comp_gap_sync_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "site_competitors",
        sa.Column("last_sync_error_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "site_competitors",
        sa.Column(
            "last_sync_summary_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )

    op.execute(
        sa.text(
            "UPDATE site_competitors "
            "SET last_sync_summary_json = '{}' "
            "WHERE last_sync_summary_json IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("site_competitors", "last_sync_summary_json")
    op.drop_column("site_competitors", "last_sync_error_code")
