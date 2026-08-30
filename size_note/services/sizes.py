from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from size_note.birth import review_interval_days, youngest_possible_age
from size_note.exceptions import ConflictError, NotFoundError
from size_note.models import Person, SizeRecord, utc_now
from size_note.normalization import clean_text, normalize, optional_text
from size_note.schemas import SizeCreate, SizeUpdate
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
    age_years: int | None
    age_approximate: bool
    interval_days: int


SHOE_KEYS = {"shoe", "shoes", "footwear", "sneaker", "sneakers", "boot", "boots"}


def get_size(
    session: Session, size_id: str, *, expected_person_id: str | None = None
) -> SizeRecord:
    record = session.get(SizeRecord, size_id)
    if record is None or (
        expected_person_id is not None and record.person_id != expected_person_id
    ):
        raise NotFoundError("Size record was not found.", code="size_not_found")
    return record


def save_size(session: Session, data: SizeCreate) -> SaveResult:
    get_person(session, data.person_id)
    now = _as_utc(data.verified_at or utc_now())
    item = clean_text(data.item)
    size_value = clean_text(data.size)
    system = optional_text(data.system)
    brand = optional_text(data.brand)
    model = optional_text(data.model)
    equivalents = _clean_equivalents(
        data.equivalents, primary_size=size_value, primary_system=system
    )

    identity = {
        "person_id": data.person_id,
        "item_key": normalize(item),
        "brand_key": normalize(brand),
        "model_key": normalize(model),
    }
    current = list(
        session.scalars(
            select(SizeRecord).where(
                SizeRecord.person_id == identity["person_id"],
                SizeRecord.item_key == identity["item_key"],
                SizeRecord.brand_key == identity["brand_key"],
                SizeRecord.model_key == identity["model_key"],
                SizeRecord.is_current.is_(True),
            )
        ).all()
    )

    incoming_keys = _representation_keys(size_value, system, equivalents)
    same = next(
        (record for record in current if _record_representation_keys(record) & incoming_keys),
        None,
    )
    if same is not None:
        same.verified_at = now
        same.equivalents = _merge_equivalents(
            same,
            incoming_size=size_value,
            incoming_system=system,
            incoming_equivalents=equivalents,
        )
        if data.measured_on is not None:
            same.measured_on = data.measured_on
        if data.fit_notes is not None:
            same.fit_notes = optional_text(data.fit_notes)
        if data.notes is not None:
            same.notes = optional_text(data.notes)
        for record in current:
            if record.id != same.id:
                record.is_current = False
                record.superseded_at = now
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
        system_key=normalize(system),
        equivalents=equivalents,
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


def update_size(
    session: Session,
    size_id: str,
    data: SizeUpdate,
    *,
    expected_person_id: str | None = None,
) -> SizeRecord:
    record = get_size(session, size_id, expected_person_id=expected_person_id)

    if "item" in data.model_fields_set and data.item is not None:
        record.item = clean_text(data.item)
    if "size" in data.model_fields_set and data.size is not None:
        record.size_value = clean_text(data.size)
    if "system" in data.model_fields_set:
        record.size_system = optional_text(data.system)
    if "brand" in data.model_fields_set:
        record.brand = optional_text(data.brand)
    if "model" in data.model_fields_set:
        record.model = optional_text(data.model)
    if "fit_notes" in data.model_fields_set:
        record.fit_notes = optional_text(data.fit_notes)
    if "notes" in data.model_fields_set:
        record.notes = optional_text(data.notes)
    if "measured_on" in data.model_fields_set:
        record.measured_on = data.measured_on
    if "equivalents" in data.model_fields_set:
        record.equivalents = _clean_equivalents(
            data.equivalents or [],
            primary_size=record.size_value,
            primary_system=record.size_system,
        )
    else:
        record.equivalents = _clean_equivalents(
            record.equivalents or [],
            primary_size=record.size_value,
            primary_system=record.size_system,
        )

    record.item_key = normalize(record.item)
    record.size_key = normalize(record.size_value)
    record.system_key = normalize(record.size_system)
    record.brand_key = normalize(record.brand)
    record.model_key = normalize(record.model)

    if record.is_current:
        conflict = session.scalar(
            select(SizeRecord).where(
                SizeRecord.id != record.id,
                SizeRecord.person_id == record.person_id,
                SizeRecord.item_key == record.item_key,
                SizeRecord.brand_key == record.brand_key,
                SizeRecord.model_key == record.model_key,
                SizeRecord.is_current.is_(True),
            )
        )
        if conflict is not None:
            session.rollback()
            raise ConflictError(
                "Another current size already uses that item, brand, and model.",
                code="size_identity_conflict",
            )

    session.commit()
    session.refresh(record)
    return record


def delete_size(
    session: Session, size_id: str, *, expected_person_id: str | None = None
) -> SizeRecord:
    record = get_size(session, size_id, expected_person_id=expected_person_id)

    if record.is_current:
        previous = session.scalar(
            select(SizeRecord)
            .where(
                SizeRecord.id != record.id,
                SizeRecord.person_id == record.person_id,
                SizeRecord.item_key == record.item_key,
                SizeRecord.brand_key == record.brand_key,
                SizeRecord.model_key == record.model_key,
                SizeRecord.is_current.is_(False),
            )
            .order_by(SizeRecord.verified_at.desc())
        )
        if previous is not None:
            previous.is_current = True
            previous.superseded_at = None

    session.delete(record)
    session.commit()
    return record


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
    record = get_size(session, size_id, expected_person_id=expected_person_id)
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
    today = comparison_time.date()
    rows = session.execute(
        select(SizeRecord, Person)
        .join(Person, SizeRecord.person_id == Person.id)
        .where(SizeRecord.is_current.is_(True))
    ).all()

    reviews: list[Review] = []
    for record, person in rows:
        interval_days = review_interval_days(
            person.growth_stage,
            person.birth_year,
            person.birth_month,
            person.birth_day,
            item_key=record.item_key,
            shoe_keys=SHOE_KEYS,
            today=today,
        )
        if interval_days is None:
            continue

        age_years = None
        age_approximate = False
        if person.birth_year is not None:
            age_years = youngest_possible_age(
                person.birth_year,
                person.birth_month,
                person.birth_day,
                today=today,
            )
            age_approximate = person.birth_month is None or person.birth_day is None

        verified_at = _as_utc(record.verified_at)
        due_at = verified_at + timedelta(days=interval_days)
        if due_at <= comparison_time:
            status = "due"
        elif due_at <= comparison_time + timedelta(days=30):
            status = "review_soon"
        else:
            status = "current"
        reviews.append(
            Review(
                person=person,
                record=record,
                due_at=due_at,
                status=status,
                age_years=age_years,
                age_approximate=age_approximate,
                interval_days=interval_days,
            )
        )

    priority = {"due": 0, "review_soon": 1, "current": 2}
    reviews.sort(key=lambda review: (priority[review.status], review.due_at, review.person.name))
    return reviews


def _value(entry: Any, key: str) -> Any:
    if isinstance(entry, dict):
        return entry.get(key)
    return getattr(entry, key)


def _clean_equivalents(
    values: list[Any], *, primary_size: str, primary_system: str | None
) -> list[dict[str, str | None]]:
    primary_key = _representation_key(primary_size, primary_system)
    seen = {primary_key}
    result: list[dict[str, str | None]] = []
    for entry in values:
        size = clean_text(str(_value(entry, "size")))
        system = optional_text(_value(entry, "system"))
        key = _representation_key(size, system)
        if key in seen:
            continue
        seen.add(key)
        result.append({"size": size, "system": system})
    return result


def _representation_key(size: str, system: str | None) -> tuple[str, str]:
    return normalize(size), normalize(system)


def _representation_keys(
    size: str, system: str | None, equivalents: list[dict[str, str | None]]
) -> set[tuple[str, str]]:
    keys = {_representation_key(size, system)}
    keys.update(_representation_key(entry["size"], entry.get("system")) for entry in equivalents)
    return keys


def _record_representation_keys(record: SizeRecord) -> set[tuple[str, str]]:
    return _representation_keys(
        record.size_value, record.size_system, record.equivalents or []
    )


def _merge_equivalents(
    record: SizeRecord,
    *,
    incoming_size: str,
    incoming_system: str | None,
    incoming_equivalents: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    values: list[dict[str, str | None]] = list(record.equivalents or [])
    values.append({"size": incoming_size, "system": incoming_system})
    values.extend(incoming_equivalents)
    return _clean_equivalents(
        values, primary_size=record.size_value, primary_system=record.size_system
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
