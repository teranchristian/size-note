"""Create people, aliases, and size history.

Revision ID: 20260829_0001
Revises:
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260829_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("growth_stage", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "growth_stage IN ('adult', 'child')", name="ck_people_growth_stage"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name"),
    )
    op.create_table(
        "person_aliases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("person_id", sa.String(length=36), nullable=False),
        sa.Column("alias", sa.String(length=160), nullable=False),
        sa.Column("normalized_alias", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_alias"),
    )
    op.create_index(
        op.f("ix_person_aliases_person_id"), "person_aliases", ["person_id"], unique=False
    )
    op.create_table(
        "size_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("person_id", sa.String(length=36), nullable=False),
        sa.Column("item", sa.String(length=120), nullable=False),
        sa.Column("item_key", sa.String(length=120), nullable=False),
        sa.Column("size_value", sa.String(length=120), nullable=False),
        sa.Column("size_key", sa.String(length=120), nullable=False),
        sa.Column("size_system", sa.String(length=120), nullable=True),
        sa.Column("system_key", sa.String(length=120), nullable=False),
        sa.Column("brand", sa.String(length=160), nullable=True),
        sa.Column("brand_key", sa.String(length=160), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=True),
        sa.Column("model_key", sa.String(length=160), nullable=False),
        sa.Column("fit_notes", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("measured_on", sa.Date(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_size_records_current_lookup",
        "size_records",
        ["person_id", "item_key", "system_key", "brand_key", "model_key", "is_current"],
        unique=False,
    )
    op.create_index(
        op.f("ix_size_records_person_id"), "size_records", ["person_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_size_records_person_id"), table_name="size_records")
    op.drop_index("ix_size_records_current_lookup", table_name="size_records")
    op.drop_table("size_records")
    op.drop_index(op.f("ix_person_aliases_person_id"), table_name="person_aliases")
    op.drop_table("person_aliases")
    op.drop_table("people")
