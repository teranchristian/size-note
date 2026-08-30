"""Add optional partial birth information for age-aware reviews.

Revision ID: 20260830_0003
Revises: 20260830_0002
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0003"
down_revision: str | None = "20260830_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("people", sa.Column("birth_year", sa.Integer(), nullable=True))
    op.add_column("people", sa.Column("birth_month", sa.Integer(), nullable=True))
    op.add_column("people", sa.Column("birth_day", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("people", "birth_day")
    op.drop_column("people", "birth_month")
    op.drop_column("people", "birth_year")
