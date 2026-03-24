"""Add ETAP 4 page metrics and hashes.

Revision ID: 0004_stage4_page_metrics
Revises: 0003_add_stopped_status
Create Date: 2026-03-13 22:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_stage4_page_metrics"
down_revision: str | None = "0003_add_stopped_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("title_length", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("meta_description_length", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("h1_count", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("h2_count", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("word_count", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("content_text_hash", sa.String(length=64), nullable=True))
    op.add_column("pages", sa.Column("images_count", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("images_missing_alt_count", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("html_size_bytes", sa.Integer(), nullable=True))
    op.create_index("ix_pages_content_text_hash", "pages", ["content_text_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pages_content_text_hash", table_name="pages")
    op.drop_column("pages", "html_size_bytes")
    op.drop_column("pages", "images_missing_alt_count")
    op.drop_column("pages", "images_count")
    op.drop_column("pages", "content_text_hash")
    op.drop_column("pages", "word_count")
    op.drop_column("pages", "h2_count")
    op.drop_column("pages", "h1_count")
    op.drop_column("pages", "meta_description_length")
    op.drop_column("pages", "title_length")
