from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from size_note.database import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (
        CheckConstraint("growth_stage IN ('adult', 'child')", name="ck_people_growth_stage"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    growth_stage: Mapped[str] = mapped_column(String(16), nullable=False, default="adult")
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    birth_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    birth_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    aliases: Mapped[list["PersonAlias"]] = relationship(
        back_populates="person", cascade="all, delete-orphan", lazy="selectin"
    )
    sizes: Mapped[list["SizeRecord"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )


class PersonAlias(Base):
    __tablename__ = "person_aliases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    person: Mapped[Person] = relationship(back_populates="aliases")


class SizeRecord(Base):
    __tablename__ = "size_records"
    __table_args__ = (
        Index(
            "ix_size_records_current_lookup",
            "person_id",
            "item_key",
            "system_key",
            "brand_key",
            "model_key",
            "is_current",
        ),
        Index(
            "ix_size_records_current_fit",
            "person_id",
            "item_key",
            "brand_key",
            "model_key",
            "is_current",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item: Mapped[str] = mapped_column(String(120), nullable=False)
    item_key: Mapped[str] = mapped_column(String(120), nullable=False)
    size_value: Mapped[str] = mapped_column(String(120), nullable=False)
    size_key: Mapped[str] = mapped_column(String(120), nullable=False)
    size_system: Mapped[str | None] = mapped_column(String(120), nullable=True)
    system_key: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    equivalents: Mapped[list[dict[str, str | None]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    brand: Mapped[str | None] = mapped_column(String(160), nullable=True)
    brand_key: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    model_key: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    fit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    measured_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    person: Mapped[Person] = relationship(back_populates="sizes")
