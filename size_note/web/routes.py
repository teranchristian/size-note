from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from size_note.birth import birth_parts, effective_growth_stage, parse_birth
from size_note.database import get_session
from size_note.exceptions import DomainError
from size_note.schemas import PersonCreate, PersonUpdate, SizeCreate, SizeUpdate
from size_note.services.people import (
    add_alias,
    create_person,
    delete_alias,
    delete_person,
    get_person,
    list_people,
    resolve_person,
    update_alias,
    update_person,
)
from size_note.services.sizes import (
    delete_size,
    get_size,
    list_reviews,
    list_sizes,
    save_size,
    update_size,
    verify_size,
)

router = APIRouter(include_in_schema=False)
SessionDependency = Annotated[Session, Depends(get_session)]


def render(request: Request, name: str, context: dict, *, status_code: int = 200) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request=request,
        name=name,
        context=context,
        status_code=status_code,
    )


def _format_equivalents(record) -> str:
    return "\n".join(
        f"{entry.get('system') or 'Other'}: {entry['size']}"
        for entry in (record.equivalents or [])
    )


def _parse_equivalents(value: str) -> list[dict[str, str | None]]:
    result: list[dict[str, str | None]] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError("Equivalent sizes must use SYSTEM: SIZE, one per line.")
        system, size = (part.strip() for part in line.split(":", 1))
        if not size:
            raise ValueError("Equivalent sizes must include a size value.")
        result.append({"system": system or None, "size": size})
    return result


def _parse_birth_form(value: str) -> dict[str, int | None]:
    if not value.strip():
        return {"birth_year": None, "birth_month": None, "birth_day": None}
    birth = parse_birth(value)
    return {
        "birth_year": birth.year,
        "birth_month": birth.month,
        "birth_day": birth.day,
    }


def _birth_text(person) -> str:
    birth = birth_parts(person.birth_year, person.birth_month, person.birth_day)
    return birth.display() if birth else ""


def _person_stage(person) -> str:
    return effective_growth_stage(
        person.growth_stage,
        person.birth_year,
        person.birth_month,
        person.birth_day,
    )


def _person_values(person) -> dict[str, str]:
    return {
        "name": person.name,
        "growth_stage": _person_stage(person),
        "birth": _birth_text(person),
        "notes": person.notes or "",
    }


def _edit_person_context(
    person,
    *,
    values: dict[str, str] | None = None,
    error: str | None = None,
    alias_error: str | None = None,
) -> dict:
    return {
        "person": person,
        "values": values or _person_values(person),
        "error": error,
        "alias_error": alias_error,
    }


def _size_form_error(exc: DomainError | ValueError) -> str:
    if isinstance(exc, DomainError):
        return exc.message
    return str(exc) or "Please check the form."


def _size_values(record) -> dict[str, str]:
    return {
        "item": record.item,
        "size": record.size_value,
        "system": record.size_system or "",
        "equivalents": _format_equivalents(record),
        "brand": record.brand or "",
        "model": record.model or "",
        "fit_notes": record.fit_notes or "",
        "notes": record.notes or "",
        "measured_on": record.measured_on.isoformat() if record.measured_on else "",
    }


@router.get("/", response_class=HTMLResponse, name="home")
def home(request: Request, session: SessionDependency) -> HTMLResponse:
    people = list_people(session)
    reviews = list_reviews(session)
    attention_count = sum(review.status != "current" for review in reviews)
    return render(
        request,
        "home.html",
        {
            "people": people,
            "growth_stages": {person.id: _person_stage(person) for person in people},
            "attention_count": attention_count,
        },
    )


@router.get(
    "/find", response_class=HTMLResponse, response_model=None, name="find_person"
)
def find_person(
    request: Request,
    session: SessionDependency,
    name: Annotated[str, Query(min_length=1, max_length=160)],
) -> HTMLResponse | RedirectResponse:
    resolution = resolve_person(session, name)
    if resolution.status in {"exact_match", "alias_match"}:
        person_id = resolution.candidates[0].person.id
        return RedirectResponse(
            request.url_for("person_detail", person_id=person_id), status_code=303
        )
    return render(request, "resolve.html", {"resolution": resolution})


@router.get("/people/new", response_class=HTMLResponse, name="new_person")
def new_person(request: Request) -> HTMLResponse:
    return render(request, "new_person.html", {"values": {}, "error": None})


@router.post("/people", response_model=None, name="create_person_web")
def create_person_web(
    request: Request,
    session: SessionDependency,
    name: Annotated[str, Form(min_length=1, max_length=160)],
    growth_stage: Annotated[str, Form()] = "",
    birth: Annotated[str, Form()] = "",
    aliases: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
) -> HTMLResponse | RedirectResponse:
    values = {
        "name": name,
        "growth_stage": growth_stage,
        "birth": birth,
        "aliases": aliases,
        "notes": notes,
    }
    if not growth_stage and not birth.strip():
        return render(
            request,
            "new_person.html",
            {
                "values": values,
                "error": "Choose child or adult, or enter birth information.",
            },
            status_code=400,
        )
    try:
        birth_data = _parse_birth_form(birth)
        person = create_person(
            session,
            PersonCreate(
                name=name,
                growth_stage=growth_stage or None,
                aliases=[alias.strip() for alias in aliases.split(",") if alias.strip()],
                notes=notes or None,
                **birth_data,
            ),
        )
    except (DomainError, ValueError) as exc:
        message = exc.message if isinstance(exc, DomainError) else str(exc)
        return render(
            request,
            "new_person.html",
            {"values": values, "error": message or "Please check the form."},
            status_code=400,
        )
    return RedirectResponse(
        request.url_for("person_detail", person_id=person.id), status_code=303
    )


@router.get("/people/{person_id}", response_class=HTMLResponse, name="person_detail")
def person_detail(
    request: Request, person_id: str, session: SessionDependency
) -> HTMLResponse:
    person = get_person(session, person_id)
    records = list_sizes(session, person_id)
    reviews = {
        review.record.id: review
        for review in list_reviews(session)
        if review.person.id == person_id
    }
    return render(
        request,
        "person_detail.html",
        {
            "person": person,
            "growth_stage": _person_stage(person),
            "birth_text": _birth_text(person),
            "current_sizes": [record for record in records if record.is_current],
            "history": [record for record in records if not record.is_current],
            "reviews": reviews,
        },
    )


@router.get("/people/{person_id}/edit", response_class=HTMLResponse, name="edit_person")
def edit_person(
    request: Request, person_id: str, session: SessionDependency
) -> HTMLResponse:
    person = get_person(session, person_id)
    return render(
        request,
        "edit_person.html",
        _edit_person_context(person),
    )


@router.post("/people/{person_id}/edit", response_model=None, name="edit_person_web")
def edit_person_web(
    request: Request,
    person_id: str,
    session: SessionDependency,
    name: Annotated[str, Form(min_length=1, max_length=160)],
    growth_stage: Annotated[str, Form()],
    birth: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
) -> HTMLResponse | RedirectResponse:
    person = get_person(session, person_id)
    values = {
        "name": name,
        "growth_stage": growth_stage,
        "birth": birth,
        "notes": notes,
    }
    try:
        birth_data = _parse_birth_form(birth)
        updated = update_person(
            session,
            person_id,
            PersonUpdate(
                name=name,
                growth_stage=growth_stage,
                notes=notes,
                **birth_data,
            ),
        )
    except (DomainError, ValueError) as exc:
        message = exc.message if isinstance(exc, DomainError) else str(exc)
        return render(
            request,
            "edit_person.html",
            _edit_person_context(
                person,
                values=values,
                error=message or "Please check the form.",
            ),
            status_code=400,
        )
    return RedirectResponse(
        request.url_for("person_detail", person_id=updated.id), status_code=303
    )


@router.get(
    "/people/{person_id}/delete", response_class=HTMLResponse, name="confirm_delete_person"
)
def confirm_delete_person(
    request: Request, person_id: str, session: SessionDependency
) -> HTMLResponse:
    person = get_person(session, person_id)
    records = list_sizes(session, person_id)
    return render(
        request,
        "confirm_delete_person.html",
        {"person": person, "size_count": len(records)},
    )


@router.post("/people/{person_id}/delete", name="delete_person_web")
def delete_person_web(
    request: Request, person_id: str, session: SessionDependency
) -> RedirectResponse:
    delete_person(session, person_id)
    return RedirectResponse(request.url_for("home"), status_code=303)


@router.post("/people/{person_id}/notes", name="update_person_notes_web")
def update_person_notes_web(
    request: Request,
    person_id: str,
    session: SessionDependency,
    notes: Annotated[str, Form()] = "",
) -> RedirectResponse:
    update_person(session, person_id, PersonUpdate(notes=notes))
    return RedirectResponse(
        request.url_for("person_detail", person_id=person_id), status_code=303
    )


@router.post(
    "/people/{person_id}/aliases", response_model=None, name="confirm_alias_web"
)
def confirm_alias_web(
    request: Request,
    person_id: str,
    session: SessionDependency,
    alias: Annotated[str, Form(min_length=1, max_length=160)],
    return_to: Annotated[str, Form()] = "detail",
) -> HTMLResponse | RedirectResponse:
    try:
        add_alias(session, person_id, alias)
    except DomainError as exc:
        if return_to != "edit":
            raise
        person = get_person(session, person_id)
        return render(
            request,
            "edit_person.html",
            _edit_person_context(person, alias_error=exc.message),
            status_code=400,
        )
    route_name = "edit_person" if return_to == "edit" else "person_detail"
    return RedirectResponse(
        request.url_for(route_name, person_id=person_id), status_code=303
    )


@router.post(
    "/people/{person_id}/aliases/{alias_id}/edit",
    response_model=None,
    name="update_alias_web",
)
def update_alias_web(
    request: Request,
    person_id: str,
    alias_id: str,
    session: SessionDependency,
    alias: Annotated[str, Form(min_length=1, max_length=160)],
) -> HTMLResponse | RedirectResponse:
    try:
        update_alias(session, person_id, alias_id, alias)
    except DomainError as exc:
        person = get_person(session, person_id)
        return render(
            request,
            "edit_person.html",
            _edit_person_context(person, alias_error=exc.message),
            status_code=400,
        )
    return RedirectResponse(
        request.url_for("edit_person", person_id=person_id), status_code=303
    )


@router.post(
    "/people/{person_id}/aliases/{alias_id}/delete", name="delete_alias_web"
)
def delete_alias_web(
    request: Request,
    person_id: str,
    alias_id: str,
    session: SessionDependency,
) -> RedirectResponse:
    delete_alias(session, person_id, alias_id)
    return RedirectResponse(
        request.url_for("edit_person", person_id=person_id), status_code=303
    )


@router.get(
    "/people/{person_id}/sizes/new", response_class=HTMLResponse, name="new_size"
)
def new_size(request: Request, person_id: str, session: SessionDependency) -> HTMLResponse:
    person = get_person(session, person_id)
    return render(
        request,
        "new_size.html",
        {
            "person": person,
            "record": None,
            "values": {},
            "error": None,
            "mode": "create",
        },
    )


@router.post(
    "/people/{person_id}/sizes", response_model=None, name="save_size_web"
)
def save_size_web(
    request: Request,
    person_id: str,
    session: SessionDependency,
    item: Annotated[str, Form(min_length=1, max_length=120)],
    size: Annotated[str, Form(min_length=1, max_length=120)],
    system: Annotated[str, Form()] = "",
    equivalents: Annotated[str, Form()] = "",
    brand: Annotated[str, Form()] = "",
    model: Annotated[str, Form()] = "",
    fit_notes: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    measured_on: Annotated[str, Form()] = "",
) -> HTMLResponse | RedirectResponse:
    person = get_person(session, person_id)
    values = {
        "item": item,
        "size": size,
        "system": system,
        "equivalents": equivalents,
        "brand": brand,
        "model": model,
        "fit_notes": fit_notes,
        "notes": notes,
        "measured_on": measured_on,
    }
    try:
        save_size(
            session,
            SizeCreate(
                person_id=person_id,
                item=item,
                size=size,
                system=system or None,
                equivalents=_parse_equivalents(equivalents),
                brand=brand or None,
                model=model or None,
                fit_notes=fit_notes or None,
                notes=notes or None,
                measured_on=date.fromisoformat(measured_on) if measured_on else None,
            ),
        )
    except (DomainError, ValueError) as exc:
        return render(
            request,
            "new_size.html",
            {
                "person": person,
                "record": None,
                "values": values,
                "error": _size_form_error(exc),
                "mode": "create",
            },
            status_code=400,
        )
    return RedirectResponse(
        request.url_for("person_detail", person_id=person_id), status_code=303
    )


@router.get(
    "/people/{person_id}/sizes/{size_id}/edit",
    response_class=HTMLResponse,
    name="edit_size",
)
def edit_size(
    request: Request, person_id: str, size_id: str, session: SessionDependency
) -> HTMLResponse:
    person = get_person(session, person_id)
    record = get_size(session, size_id, expected_person_id=person_id)
    return render(
        request,
        "new_size.html",
        {
            "person": person,
            "record": record,
            "values": _size_values(record),
            "error": None,
            "mode": "edit",
        },
    )


@router.post(
    "/people/{person_id}/sizes/{size_id}/edit",
    response_model=None,
    name="edit_size_web",
)
def edit_size_web(
    request: Request,
    person_id: str,
    size_id: str,
    session: SessionDependency,
    item: Annotated[str, Form(min_length=1, max_length=120)],
    size: Annotated[str, Form(min_length=1, max_length=120)],
    system: Annotated[str, Form()] = "",
    equivalents: Annotated[str, Form()] = "",
    brand: Annotated[str, Form()] = "",
    model: Annotated[str, Form()] = "",
    fit_notes: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    measured_on: Annotated[str, Form()] = "",
) -> HTMLResponse | RedirectResponse:
    person = get_person(session, person_id)
    record = get_size(session, size_id, expected_person_id=person_id)
    values = {
        "item": item,
        "size": size,
        "system": system,
        "equivalents": equivalents,
        "brand": brand,
        "model": model,
        "fit_notes": fit_notes,
        "notes": notes,
        "measured_on": measured_on,
    }
    try:
        update_size(
            session,
            size_id,
            SizeUpdate(
                item=item,
                size=size,
                system=system or None,
                equivalents=_parse_equivalents(equivalents),
                brand=brand or None,
                model=model or None,
                fit_notes=fit_notes or None,
                notes=notes or None,
                measured_on=date.fromisoformat(measured_on) if measured_on else None,
            ),
            expected_person_id=person_id,
        )
    except (DomainError, ValueError) as exc:
        return render(
            request,
            "new_size.html",
            {
                "person": person,
                "record": record,
                "values": values,
                "error": _size_form_error(exc),
                "mode": "edit",
            },
            status_code=400,
        )
    return RedirectResponse(
        request.url_for("person_detail", person_id=person_id), status_code=303
    )


@router.get(
    "/people/{person_id}/sizes/{size_id}/delete",
    response_class=HTMLResponse,
    name="confirm_delete_size",
)
def confirm_delete_size(
    request: Request, person_id: str, size_id: str, session: SessionDependency
) -> HTMLResponse:
    person = get_person(session, person_id)
    record = get_size(session, size_id, expected_person_id=person_id)
    return render(
        request,
        "confirm_delete_size.html",
        {"person": person, "record": record},
    )


@router.post(
    "/people/{person_id}/sizes/{size_id}/delete", name="delete_size_web"
)
def delete_size_web(
    request: Request, person_id: str, size_id: str, session: SessionDependency
) -> RedirectResponse:
    delete_size(session, size_id, expected_person_id=person_id)
    return RedirectResponse(
        request.url_for("person_detail", person_id=person_id), status_code=303
    )


@router.post("/people/{person_id}/sizes/{size_id}/verify", name="verify_size_web")
def verify_size_web(
    request: Request, person_id: str, size_id: str, session: SessionDependency
) -> RedirectResponse:
    verify_size(session, size_id, expected_person_id=person_id)
    return RedirectResponse(
        request.url_for("person_detail", person_id=person_id), status_code=303
    )


@router.get("/reviews", response_class=HTMLResponse, name="reviews")
def reviews(request: Request, session: SessionDependency) -> HTMLResponse:
    return render(request, "reviews.html", {"reviews": list_reviews(session)})
