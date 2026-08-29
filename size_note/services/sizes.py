from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from size_note.exceptions import ConflictError, NotFoundError
from size_note.models import Person, SizeRecord, utc_now
from size_note.normalization import clean_text, normalize, optional_text
from size_note.schemas import SizeCreate
from size_note.services.people import get_person


@dataclass(frozen=True)
class SaveResult:
    action: str
    record: SizeRecord


@dataclass(frozen=True)
class Review:
    person: Person
    record: SizeRecord
    due_at: datetime
    status: str


SHOE_KEYS = {"shoe", "shoes", "footwear", "sneaker", "sneakers", "boot", "boots"}


def save_size(session: Session, data: SizeCreate) -> SaveResult:
    get_person(session, data.person_id)
    now = _as_utc(data.verified_at or utc_now())
    item = clean_text(data.item)
    size_value = clean_text(data.size)
    system = optional_text(data.system)
    brand = optional_text(data.brand)
    model = optional_text(data.model)

    identity = {
        "person_id": data.person_id,
        "item_key": normalize(item),
        "system_key": normalize(system),
        "brand_key": normalize(brand),
        "model_key": normalize(model),
    }
    current = list(
        session.scalars(
            select(SizeRecord).where(
                SizeRecord.person_id == identity["person_id"],
                SizeRecord.item_key == identity["item_key"],
                SizeRecord.system_key == identity["system_key"],
                SizeRecord.brand_key == identity["brand_key"],
                SizeRecord.model_key == identity["model_key"],
                SizeRecord.is_current.is_(True),
            )
        ).all()
    )

    same = next((record for record in current if record.size_key == normalize(size_value)), None)
    if same is not None:
        same.verified_at = now
        if data.measured_on is not None:
            same.measured_on = data.measured_on
        if data.fit_notes is not None:
            same.fit_notes = optional_text(data.fit_notes)
        if data.notes is not None:
            same.notes = optional_text(data.notes)
        session.commit()
        session.refresh(same)
        return SaveResult(action="verified", record=same)

    action = "updated" if current else "created"
    for record in current:
        record.is_current = False
        record.superseded_at = now

    record = SizeRecord(
        **identity,
        item=item,
        size_value=size_value,
        size_key=normalize(size_value),
        size_system=system,
        brand=brand,
        model=model,
        fit_notes=optional_text(data.fit_notes),
        notes=optional_text(data.notes),
        measured_on=data.measured_on,
        verified_at=now,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return SaveResult(action=action, record=record)


def list_sizes(
    session: Session, person_id: str, *, include_history: bool = True
) -> list[SizeRecord]:
    get_person(session, person_id)
    query = select(SizeRecord).where(SizeRecord.person_id == person_id)
    if not include_history:
        query = query.where(SizeRecord.is_current.is_(True))
    query = query.order_by(SizeRecord.is_current.desc(), SizeRecord.verified_at.desc())
    return list(session.scalars(query).all())


def verify_size(
    session: Session, size_id: str, *, expected_person_id: str | None = None
) -> SizeRecord:
    record = session.get(SizeRecord, size_id)
    if record is None:
        raise NotFoundError("Size record was not found.", code="size_not_found")
    if expected_person_id is not None and record.person_id != expected_person_id:
        raise NotFoundError("Size record was not found.", code="size_not_found")
    if not record.is_current:
        raise ConflictError(
            "A previous size cannot become current through verification.",
            code="size_not_current",
        )
    record.verified_at = utc_now()
    session.commit()
    session.refresh(record)
    return record


def list_reviews(session: Session, *, now: datetime | None = None) -> list[Review]:
    comparison_time = _as_utc(now or utc_now())
    rows = session.execute(
        select(SizeRecord, Person)
        .join(Person, SizeRecord.person_id == Person.id)
        .where(SizeRecord.is_current.is_(True), Person.growth_stage == "child")
    ).all()

    reviews: list[Review] = []
    for record, person in rows:
        interval = timedelta(days=90 if record.item_key in SHOE_KEYS else 180)
        verified_at = _as_utc(record.verified_at)
        due_at = verified_at + interval
        if due_at <= comparison_time:
            status = "due"
        elif due_at <= comparison_time + timedelta(days=30):
            status = "review_soon"
        else:
            status = "current"
        reviews.append(Review(person=person, record=record, due_at=due_at, status=status))

    priority = {"due": 0, "review_soon": 1, "current": 2}
    reviews.sort(key=lambda review: (priority[review.status], review.due_at, review.person.name))
    return reviews


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
