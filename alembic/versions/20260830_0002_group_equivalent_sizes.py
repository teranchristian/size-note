"""Store multiple confirmed size representations on one fit record.

Revision ID: 20260830_0002
Revises: 20260829_0001
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0002"
down_revision: str | None = "20260829_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "size_records",
        sa.Column(
            "equivalents",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.create_index(
        "ix_size_records_current_fit",
        "size_records",
        ["person_id", "item_key", "brand_key", "model_key", "is_current"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_size_records_current_fit", table_name="size_records")
    op.drop_column("size_records", "equivalents")
