from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from size_note.birth import validate_birth_parts
from size_note.normalization import clean_text, optional_text

GrowthStage = Literal["adult", "child"]
ResolutionStatus = Literal[
    "exact_match",
    "alias_match",
    "confirmation_required",
    "multiple_matches",
    "not_found",
]


class CleanModel(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return clean_text(value)
        return value


class PersonCreate(CleanModel):
    name: str = Field(min_length=1, max_length=160)
    growth_stage: GrowthStage | None = None
    birth_year: int | None = None
    birth_month: int | None = None
    birth_day: int | None = None
    aliases: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("notes", mode="after")
    @classmethod
    def blank_notes_to_none(cls, value: str | None) -> str | None:
        return optional_text(value)

    @model_validator(mode="after")
    def validate_person_context(self) -> "PersonCreate":
        validate_birth_parts(self.birth_year, self.birth_month, self.birth_day)
        if self.growth_stage is None and self.birth_year is None:
            raise ValueError("Choose child or adult, or provide birth information.")
        return self


class PersonUpdate(CleanModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    growth_stage: GrowthStage | None = None
    birth_year: int | None = None
    birth_month: int | None = None
    birth_day: int | None = None
    notes: str | None = None

    @field_validator("notes", mode="after")
    @classmethod
    def blank_notes_to_none(cls, value: str | None) -> str | None:
        return optional_text(value)

    @field_validator("birth_year")
    @classmethod
    def valid_birth_year(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("Birth year must be positive.")
        return value

    @field_validator("birth_month")
    @classmethod
    def valid_birth_month(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 12:
            raise ValueError("Birth month must be between 1 and 12.")
        return value

    @field_validator("birth_day")
    @classmethod
    def valid_birth_day(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 31:
            raise ValueError("Birth day must be between 1 and 31.")
        return value


class AliasCreate(CleanModel):
    alias: str = Field(min_length=1, max_length=160)


class PersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    growth_stage: GrowthStage
    birth_year: int | None
    birth_month: int | None
    birth_day: int | None
    notes: str | None
    aliases: list[str]
    created_at: datetime
    updated_at: datetime


class PersonCandidate(BaseModel):
    id: str
    name: str
    growth_stage: GrowthStage
    matched_value: str
    match_type: Literal["name", "alias", "similar"]
    score: float


class PersonResolveRequest(CleanModel):
    name: str = Field(min_length=1, max_length=160)


class PersonResolveResponse(BaseModel):
    status: ResolutionStatus
    query: str
    candidates: list[PersonCandidate] = Field(default_factory=list)


class SizeEquivalent(CleanModel):
    size: str = Field(min_length=1, max_length=120)
    system: str | None = Field(default=None, max_length=120)

    @field_validator("system", mode="after")
    @classmethod
    def blank_system_to_none(cls, value: str | None) -> str | None:
        return optional_text(value)


class SizeCreate(CleanModel):
    person_id: str
    item: str = Field(min_length=1, max_length=120)
    size: str = Field(min_length=1, max_length=120)
    system: str | None = Field(default=None, max_length=120)
    equivalents: list[SizeEquivalent] = Field(default_factory=list)
    brand: str | None = Field(default=None, max_length=160)
    model: str | None = Field(default=None, max_length=160)
    fit_notes: str | None = None
    notes: str | None = None
    measured_on: date | None = None
    verified_at: datetime | None = None

    @field_validator("system", "brand", "model", "fit_notes", "notes", mode="after")
    @classmethod
    def blanks_to_none(cls, value: str | None) -> str | None:
        return optional_text(value)


class SizeUpdate(CleanModel):
    item: str | None = Field(default=None, min_length=1, max_length=120)
    size: str | None = Field(default=None, min_length=1, max_length=120)
    system: str | None = Field(default=None, max_length=120)
    equivalents: list[SizeEquivalent] | None = None
    brand: str | None = Field(default=None, max_length=160)
    model: str | None = Field(default=None, max_length=160)
    fit_notes: str | None = None
    notes: str | None = None
    measured_on: date | None = None

    @field_validator("system", "brand", "model", "fit_notes", "notes", mode="after")
    @classmethod
    def blanks_to_none(cls, value: str | None) -> str | None:
        return optional_text(value)


class SizeRead(BaseModel):
    id: str
    person_id: str
    item: str
    size: str
    system: str | None
    equivalents: list[SizeEquivalent]
    brand: str | None
    model: str | None
    fit_notes: str | None
    notes: str | None
    measured_on: date | None
    verified_at: datetime
    is_current: bool
    superseded_at: datetime | None
    created_at: datetime


class SizeSaveResponse(BaseModel):
    action: Literal["created", "updated", "verified"]
    record: SizeRead


class ReviewRead(BaseModel):
    person_id: str
    person_name: str
    person_age_years: int | None
    person_age_approximate: bool
    review_interval_days: int
    size_id: str
    item: str
    size: str
    system: str | None
    verified_at: datetime
    due_at: datetime
    status: Literal["current", "review_soon", "due"]


class HealthRead(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
