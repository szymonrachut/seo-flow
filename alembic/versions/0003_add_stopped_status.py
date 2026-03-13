"""Add stopped status to crawl job enum.

Revision ID: 0003_add_stopped_status
Revises: 0002_page_seo_fields
Create Date: 2026-03-12 21:00:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_add_stopped_status"
down_revision: str | None = "0002_page_seo_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE crawl_job_status ADD VALUE IF NOT EXISTS 'stopped'")


def downgrade() -> None:
    # Downgrade for enum value removal in PostgreSQL would require type recreation.
    # Left as no-op to keep downgrade predictable and avoid destructive rewrites.
    return None
