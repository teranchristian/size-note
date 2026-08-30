from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from size_note.database import get_session
from size_note.presenters import candidate_read, person_read, review_read, size_read
from size_note.schemas import (
    AliasCreate,
    PersonCreate,
    PersonRead,
    PersonResolveRequest,
    PersonResolveResponse,
    PersonUpdate,
    ReviewRead,
    SizeCreate,
    SizeRead,
    SizeSaveResponse,
    SizeUpdate,
)
from size_note.services.people import (
    add_alias,
    create_person,
    delete_person,
    get_person,
    list_people,
    resolve_person,
    update_person,
)
from size_note.services.sizes import (
    delete_size,
    list_reviews,
    list_sizes,
    save_size,
    update_size,
    verify_size,
)

router = APIRouter(prefix="/api")
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/people/resolve", response_model=PersonResolveResponse)
def resolve_person_endpoint(
    payload: PersonResolveRequest, session: SessionDependency
) -> PersonResolveResponse:
    result = resolve_person(session, payload.name)
    return PersonResolveResponse(
        status=result.status,
        query=result.query,
        candidates=[candidate_read(candidate) for candidate in result.candidates],
    )


@router.post("/people", response_model=PersonRead, status_code=status.HTTP_201_CREATED)
def create_person_endpoint(payload: PersonCreate, session: SessionDependency) -> PersonRead:
    return person_read(create_person(session, payload))


@router.get("/people", response_model=list[PersonRead])
def list_people_endpoint(session: SessionDependency) -> list[PersonRead]:
    return [person_read(person) for person in list_people(session)]


@router.get("/people/{person_id}", response_model=PersonRead)
def get_person_endpoint(person_id: str, session: SessionDependency) -> PersonRead:
    return person_read(get_person(session, person_id))


@router.patch("/people/{person_id}", response_model=PersonRead)
def update_person_endpoint(
    person_id: str, payload: PersonUpdate, session: SessionDependency
) -> PersonRead:
    return person_read(update_person(session, person_id, payload))


@router.delete("/people/{person_id}", include_in_schema=False)
def delete_person_endpoint(person_id: str, session: SessionDependency) -> dict[str, str]:
    name = delete_person(session, person_id)
    return {"status": "deleted", "id": person_id, "name": name}


@router.post("/people/{person_id}/aliases", response_model=PersonRead)
def add_alias_endpoint(
    person_id: str, payload: AliasCreate, session: SessionDependency
) -> PersonRead:
    return person_read(add_alias(session, person_id, payload.alias))


@router.post("/sizes", response_model=SizeSaveResponse)
def save_size_endpoint(payload: SizeCreate, session: SessionDependency) -> SizeSaveResponse:
    result = save_size(session, payload)
    return SizeSaveResponse(action=result.action, record=size_read(result.record))


@router.get("/people/{person_id}/sizes", response_model=list[SizeRead])
def list_sizes_endpoint(
    person_id: str,
    session: SessionDependency,
    history: Annotated[bool, Query(description="Include previous sizes")] = True,
) -> list[SizeRead]:
    return [
        size_read(record)
        for record in list_sizes(session, person_id, include_history=history)
    ]


@router.patch(
    "/people/{person_id}/sizes/{size_id}",
    response_model=SizeRead,
    include_in_schema=False,
)
def update_size_endpoint(
    person_id: str,
    size_id: str,
    payload: SizeUpdate,
    session: SessionDependency,
) -> SizeRead:
    return size_read(
        update_size(session, size_id, payload, expected_person_id=person_id)
    )


@router.delete("/people/{person_id}/sizes/{size_id}", include_in_schema=False)
def delete_size_endpoint(
    person_id: str, size_id: str, session: SessionDependency
) -> dict[str, str]:
    record = delete_size(session, size_id, expected_person_id=person_id)
    return {
        "status": "deleted",
        "id": size_id,
        "person_id": person_id,
        "item": record.item,
        "size": record.size_value,
    }


@router.post("/sizes/{size_id}/verify", response_model=SizeSaveResponse)
def verify_size_endpoint(size_id: str, session: SessionDependency) -> SizeSaveResponse:
    return SizeSaveResponse(action="verified", record=size_read(verify_size(session, size_id)))


@router.get("/reviews", response_model=list[ReviewRead])
def list_reviews_endpoint(session: SessionDependency) -> list[ReviewRead]:
    return [review_read(review) for review in list_reviews(session)]
