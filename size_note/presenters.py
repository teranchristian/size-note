from datetime import UTC, datetime

from size_note.models import Person, SizeRecord
from size_note.schemas import PersonCandidate, PersonRead, ReviewRead, SizeRead
from size_note.services.people import Candidate
from size_note.services.sizes import Review


def person_read(person: Person) -> PersonRead:
    return PersonRead(
        id=person.id,
        name=person.name,
        growth_stage=person.growth_stage,
        notes=person.notes,
        aliases=[entry.alias for entry in sorted(person.aliases, key=lambda item: item.alias)],
        created_at=_utc(person.created_at),
        updated_at=_utc(person.updated_at),
    )


def candidate_read(candidate: Candidate) -> PersonCandidate:
    return PersonCandidate(
        id=candidate.person.id,
        name=candidate.person.name,
        growth_stage=candidate.person.growth_stage,
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
