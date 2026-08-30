from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from size_note.birth import effective_growth_stage, validate_birth_parts
from size_note.exceptions import ConflictError, DomainError, NotFoundError
from size_note.models import Person, PersonAlias
from size_note.normalization import clean_text, normalize, optional_text
from size_note.schemas import PersonCreate, PersonUpdate


@dataclass(frozen=True)
class Candidate:
    person: Person
    matched_value: str
    match_type: str
    score: float


@dataclass(frozen=True)
class Resolution:
    status: str
    query: str
    candidates: list[Candidate]


def get_person(session: Session, person_id: str) -> Person:
    person = session.scalar(
        select(Person)
        .where(Person.id == person_id)
        .options(selectinload(Person.aliases))
    )
    if person is None:
        raise NotFoundError("Person was not found.", code="person_not_found")
    return person


def list_people(session: Session) -> list[Person]:
    return list(
        session.scalars(
            select(Person).options(selectinload(Person.aliases)).order_by(Person.name)
        ).all()
    )


def create_person(session: Session, data: PersonCreate) -> Person:
    normalized_name = normalize(data.name)
    _ensure_identifier_available(session, normalized_name)

    growth_stage = data.growth_stage or effective_growth_stage(
        "adult", data.birth_year, data.birth_month, data.birth_day
    )
    person = Person(
        name=clean_text(data.name),
        normalized_name=normalized_name,
        growth_stage=growth_stage,
        birth_year=data.birth_year,
        birth_month=data.birth_month,
        birth_day=data.birth_day,
        notes=optional_text(data.notes),
    )
    session.add(person)
    session.flush()

    seen = {normalized_name}
    for raw_alias in data.aliases:
        alias_key = normalize(raw_alias)
        if not alias_key or alias_key in seen:
            continue
        _ensure_identifier_available(session, alias_key)
        person.aliases.append(
            PersonAlias(alias=clean_text(raw_alias), normalized_alias=alias_key)
        )
        seen.add(alias_key)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "That name or alias is already used by another person.",
            code="person_identifier_conflict",
        ) from exc
    return get_person(session, person.id)


def update_person(session: Session, person_id: str, data: PersonUpdate) -> Person:
    person = get_person(session, person_id)

    if "name" in data.model_fields_set and data.name is not None:
        normalized_name = normalize(data.name)
        _ensure_identifier_available(session, normalized_name, person_id=person_id)
        person.name = clean_text(data.name)
        person.normalized_name = normalized_name

    if "growth_stage" in data.model_fields_set and data.growth_stage is not None:
        person.growth_stage = data.growth_stage

    birth_fields = {"birth_year", "birth_month", "birth_day"}
    if data.model_fields_set & birth_fields:
        year = data.birth_year if "birth_year" in data.model_fields_set else person.birth_year
        month = (
            data.birth_month if "birth_month" in data.model_fields_set else person.birth_month
        )
        day = data.birth_day if "birth_day" in data.model_fields_set else person.birth_day
        try:
            validate_birth_parts(year, month, day)
        except ValueError as exc:
            raise DomainError(str(exc), code="invalid_birth") from exc
        person.birth_year = year
        person.birth_month = month
        person.birth_day = day

    if "notes" in data.model_fields_set:
        person.notes = optional_text(data.notes)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "That name or alias is already used by another person.",
            code="person_identifier_conflict",
        ) from exc
    return get_person(session, person_id)


def delete_person(session: Session, person_id: str) -> str:
    person = get_person(session, person_id)
    name = person.name
    session.delete(person)
    session.commit()
    return name


def add_alias(session: Session, person_id: str, raw_alias: str) -> Person:
    person = get_person(session, person_id)
    alias = clean_text(raw_alias)
    alias_key = normalize(alias)

    if alias_key == person.normalized_name:
        return person
    existing_for_person = next(
        (entry for entry in person.aliases if entry.normalized_alias == alias_key), None
    )
    if existing_for_person:
        return person

    _ensure_identifier_available(session, alias_key, person_id=person_id)
    person.aliases.append(PersonAlias(alias=alias, normalized_alias=alias_key))
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "That alias is already used by another person.",
            code="person_identifier_conflict",
        ) from exc
    return get_person(session, person_id)


def update_alias(
    session: Session, person_id: str, alias_id: str, raw_alias: str
) -> Person:
    person = get_person(session, person_id)
    entry = _get_alias(session, person_id, alias_id)
    alias = clean_text(raw_alias)
    alias_key = normalize(alias)

    if alias_key == person.normalized_name:
        raise ConflictError(
            "An alias must be different from the person's name.",
            code="alias_matches_person_name",
        )

    existing = session.scalar(
        select(PersonAlias).where(PersonAlias.normalized_alias == alias_key)
    )
    if existing is not None and existing.id != alias_id:
        raise ConflictError(
            "That alias is already in use.", code="person_identifier_conflict"
        )

    _ensure_identifier_available(session, alias_key, person_id=person_id)
    entry.alias = alias
    entry.normalized_alias = alias_key
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "That alias is already in use.", code="person_identifier_conflict"
        ) from exc
    return get_person(session, person_id)


def delete_alias(session: Session, person_id: str, alias_id: str) -> Person:
    get_person(session, person_id)
    entry = _get_alias(session, person_id, alias_id)
    session.delete(entry)
    session.commit()
    return get_person(session, person_id)


def resolve_person(session: Session, raw_query: str) -> Resolution:
    query = clean_text(raw_query)
    query_key = normalize(query)

    person = session.scalar(
        select(Person)
        .where(Person.normalized_name == query_key)
        .options(selectinload(Person.aliases))
    )
    if person is not None:
        return Resolution(
            status="exact_match",
            query=query,
            candidates=[Candidate(person, person.name, "name", 1.0)],
        )

    alias = session.scalar(
        select(PersonAlias)
        .where(PersonAlias.normalized_alias == query_key)
        .options(selectinload(PersonAlias.person).selectinload(Person.aliases))
    )
    if alias is not None:
        return Resolution(
            status="alias_match",
            query=query,
            candidates=[Candidate(alias.person, alias.alias, "alias", 1.0)],
        )

    if len(query_key) < 3:
        return Resolution(status="not_found", query=query, candidates=[])

    people = list_people(session)
    candidates: list[Candidate] = []
    for possible in people:
        labels = [(possible.name, possible.normalized_name)] + [
            (entry.alias, entry.normalized_alias) for entry in possible.aliases
        ]
        best_value = possible.name
        best_score = 0.0
        for label, label_key in labels:
            score = _similarity(query_key, label_key)
            if score > best_score:
                best_value = label
                best_score = score
        if best_score >= 0.72:
            candidates.append(
                Candidate(possible, best_value, "similar", round(best_score, 3))
            )

    candidates.sort(key=lambda candidate: (-candidate.score, candidate.person.name.casefold()))
    if not candidates:
        status = "not_found"
    elif len(candidates) == 1:
        status = "confirmation_required"
    else:
        status = "multiple_matches"
    return Resolution(status=status, query=query, candidates=candidates[:5])


def _similarity(query: str, candidate: str) -> float:
    score = SequenceMatcher(None, query, candidate).ratio()
    shorter, longer = sorted((query, candidate), key=len)
    if len(shorter) >= 3 and longer.startswith(shorter):
        score = max(score, 0.82)
    return score


def _get_alias(session: Session, person_id: str, alias_id: str) -> PersonAlias:
    alias = session.scalar(
        select(PersonAlias).where(
            PersonAlias.id == alias_id, PersonAlias.person_id == person_id
        )
    )
    if alias is None:
        raise NotFoundError("Alias was not found.", code="alias_not_found")
    return alias


def _ensure_identifier_available(
    session: Session, identifier: str, *, person_id: str | None = None
) -> None:
    if not identifier:
        raise ConflictError("A name or alias cannot be blank.", code="blank_identifier")

    person = session.scalar(select(Person).where(Person.normalized_name == identifier))
    if person is not None and person.id != person_id:
        raise ConflictError(
            f'"{person.name}" already uses that name.', code="person_identifier_conflict"
        )

    alias = session.scalar(
        select(PersonAlias).where(PersonAlias.normalized_alias == identifier)
    )
    if alias is not None and alias.person_id != person_id:
        raise ConflictError(
            "That name is already used as another person's alias.",
            code="person_identifier_conflict",
        )
