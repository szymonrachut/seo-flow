"""Add ETAP 2 SEO page fields.

Revision ID: 0002_page_seo_fields
Revises: 0001_initial
Create Date: 2026-03-12 00:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_page_seo_fields"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("canonical_url", sa.String(length=2048), nullable=True))
    op.add_column("pages", sa.Column("robots_meta", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("content_type", sa.String(length=255), nullable=True))
    op.add_column("pages", sa.Column("response_time_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("pages", "response_time_ms")
    op.drop_column("pages", "content_type")
    op.drop_column("pages", "robots_meta")
    op.drop_column("pages", "canonical_url")
