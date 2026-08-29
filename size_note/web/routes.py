from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from size_note.database import get_session
from size_note.exceptions import DomainError
from size_note.schemas import PersonCreate, SizeCreate
from size_note.services.people import (
    add_alias,
    create_person,
    get_person,
    list_people,
    resolve_person,
)
from size_note.services.sizes import list_reviews, list_sizes, save_size, verify_size

router = APIRouter(include_in_schema=False)
SessionDependency = Annotated[Session, Depends(get_session)]


def render(request: Request, name: str, context: dict, *, status_code: int = 200) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request=request,
        name=name,
        context=context,
        status_code=status_code,
    )


@router.get("/", response_class=HTMLResponse, name="home")
def home(request: Request, session: SessionDependency) -> HTMLResponse:
    people = list_people(session)
    reviews = list_reviews(session)
    attention_count = sum(review.status != "current" for review in reviews)
    return render(
        request,
        "home.html",
        {"people": people, "attention_count": attention_count},
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
    growth_stage: Annotated[str, Form()] = "adult",
    aliases: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
) -> HTMLResponse | RedirectResponse:
    values = {
        "name": name,
        "growth_stage": growth_stage,
        "aliases": aliases,
        "notes": notes,
    }
    try:
        person = create_person(
            session,
            PersonCreate(
                name=name,
                growth_stage=growth_stage,
                aliases=[alias.strip() for alias in aliases.split(",") if alias.strip()],
                notes=notes or None,
            ),
        )
    except (DomainError, ValueError) as exc:
        message = exc.message if isinstance(exc, DomainError) else "Please check the form."
        return render(
            request,
            "new_person.html",
            {"values": values, "error": message},
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
            "current_sizes": [record for record in records if record.is_current],
            "history": [record for record in records if not record.is_current],
            "reviews": reviews,
        },
    )


@router.post("/people/{person_id}/aliases", name="confirm_alias_web")
def confirm_alias_web(
    request: Request,
    person_id: str,
    session: SessionDependency,
    alias: Annotated[str, Form(min_length=1, max_length=160)],
) -> RedirectResponse:
    add_alias(session, person_id, alias)
    return RedirectResponse(
        request.url_for("person_detail", person_id=person_id), status_code=303
    )


@router.get(
    "/people/{person_id}/sizes/new", response_class=HTMLResponse, name="new_size"
)
def new_size(request: Request, person_id: str, session: SessionDependency) -> HTMLResponse:
    person = get_person(session, person_id)
    return render(
        request,
        "new_size.html",
        {"person": person, "values": {}, "error": None},
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
                brand=brand or None,
                model=model or None,
                fit_notes=fit_notes or None,
                notes=notes or None,
                measured_on=date.fromisoformat(measured_on) if measured_on else None,
            ),
        )
    except (DomainError, ValueError) as exc:
        message = exc.message if isinstance(exc, DomainError) else "Please check the form."
        return render(
            request,
            "new_size.html",
            {"person": person, "values": values, "error": message},
            status_code=400,
        )
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
