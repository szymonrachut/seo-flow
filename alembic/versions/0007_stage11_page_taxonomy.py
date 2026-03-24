"""Add ETAP 11 page taxonomy fields.

Revision ID: 0007_stage11_page_taxonomy
Revises: 0006_stage6_gsc_integration
Create Date: 2026-03-16 12:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007_stage11_page_taxonomy"
down_revision: str | None = "0006_stage6_gsc_integration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pages",
        sa.Column("page_type", sa.String(length=64), nullable=False, server_default="other"),
    )
    op.add_column(
        "pages",
        sa.Column("page_bucket", sa.String(length=64), nullable=False, server_default="other"),
    )
    op.add_column(
        "pages",
        sa.Column("page_type_confidence", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pages",
        sa.Column("page_type_version", sa.String(length=64), nullable=False, server_default="unclassified"),
    )
    op.add_column(
        "pages",
        sa.Column("page_type_rationale", sa.Text(), nullable=True),
    )

    op.create_index("ix_pages_page_type", "pages", ["page_type"], unique=False)
    op.create_index("ix_pages_page_bucket", "pages", ["page_bucket"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pages_page_bucket", table_name="pages")
    op.drop_index("ix_pages_page_type", table_name="pages")

    op.drop_column("pages", "page_type_rationale")
    op.drop_column("pages", "page_type_version")
    op.drop_column("pages", "page_type_confidence")
    op.drop_column("pages", "page_bucket")
    op.drop_column("pages", "page_type")
