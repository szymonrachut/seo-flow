"""merge content generator and semstorm heads

Revision ID: 0029_merge_content_gen_semstorm
Revises: 0022_content_gen_assets, 0028_semstorm_brief_impl_v1
Create Date: 2026-03-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "0029_merge_content_gen_semstorm"
down_revision: tuple[str, str] = ("0022_content_gen_assets", "0028_semstorm_brief_impl_v1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
