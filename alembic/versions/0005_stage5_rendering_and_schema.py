"""Add ETAP 5 rendering, robots and schema fields.

Revision ID: 0005_stage5_rendering_and_schema
Revises: 0004_stage4_page_metrics
Create Date: 2026-03-13 23:05:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_stage5_rendering_and_schema"
down_revision: str | None = "0004_stage4_page_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("x_robots_tag", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("was_rendered", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("pages", sa.Column("render_attempted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("pages", sa.Column("fetch_mode_used", sa.String(length=32), nullable=True))
    op.add_column("pages", sa.Column("js_heavy_like", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("pages", sa.Column("render_reason", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("render_error_message", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("schema_present", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("pages", sa.Column("schema_count", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("schema_types_json", sa.JSON(), nullable=True))

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column("pages", "was_rendered", server_default=None)
        op.alter_column("pages", "render_attempted", server_default=None)
        op.alter_column("pages", "js_heavy_like", server_default=None)
        op.alter_column("pages", "schema_present", server_default=None)


def downgrade() -> None:
    op.drop_column("pages", "schema_types_json")
    op.drop_column("pages", "schema_count")
    op.drop_column("pages", "schema_present")
    op.drop_column("pages", "render_error_message")
    op.drop_column("pages", "render_reason")
    op.drop_column("pages", "js_heavy_like")
    op.drop_column("pages", "fetch_mode_used")
    op.drop_column("pages", "render_attempted")
    op.drop_column("pages", "was_rendered")
    op.drop_column("pages", "x_robots_tag")
