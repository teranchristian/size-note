from datetime import UTC, datetime

from size_note.birth import effective_growth_stage
from size_note.models import Person, SizeRecord
from size_note.schemas import PersonCandidate, PersonRead, ReviewRead, SizeRead
from size_note.services.people import Candidate
from size_note.services.sizes import Review


def person_read(person: Person) -> PersonRead:
    return PersonRead(
        id=person.id,
        name=person.name,
        growth_stage=effective_growth_stage(
            person.growth_stage,
            person.birth_year,
            person.birth_month,
            person.birth_day,
        ),
        birth_year=person.birth_year,
        birth_month=person.birth_month,
        birth_day=person.birth_day,
        notes=person.notes,
        aliases=[entry.alias for entry in sorted(person.aliases, key=lambda item: item.alias)],
        created_at=_utc(person.created_at),
        updated_at=_utc(person.updated_at),
    )


def candidate_read(candidate: Candidate) -> PersonCandidate:
    person = candidate.person
    return PersonCandidate(
        id=person.id,
        name=person.name,
        growth_stage=effective_growth_stage(
            person.growth_stage,
            person.birth_year,
            person.birth_month,
            person.birth_day,
        ),
        matched_value=candidate.matched_value,
        match_type=candidate.match_type,
        score=candidate.score,
    )


def size_read(record: SizeRecord) -> SizeRead:
    return SizeRead(
        id=record.id,
        person_id=record.person_id,
        item=record.item,
        size=record.size_value,
        system=record.size_system,
        equivalents=record.equivalents or [],
        brand=record.brand,
        model=record.model,
        fit_notes=record.fit_notes,
        notes=record.notes,
        measured_on=record.measured_on,
        verified_at=_utc(record.verified_at),
        is_current=record.is_current,
        superseded_at=_utc(record.superseded_at) if record.superseded_at else None,
        created_at=_utc(record.created_at),
    )


def review_read(review: Review) -> ReviewRead:
    return ReviewRead(
        person_id=review.person.id,
        person_name=review.person.name,
        person_age_years=review.age_years,
        person_age_approximate=review.age_approximate,
        review_interval_days=review.interval_days,
        size_id=review.record.id,
        item=review.record.item,
        size=review.record.size_value,
        system=review.record.size_system,
        verified_at=_utc(review.record.verified_at),
        due_at=review.due_at,
        status=review.status,
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
