import json
import os
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
import typer

from size_note.birth import parse_birth

app = typer.Typer(
    name="size-note",
    help="Remember and retrieve clothing, footwear, and wearable sizes.",
    no_args_is_help=True,
)


def _base_url(value: str | None) -> str:
    return (value or os.getenv("SIZE_NOTE_URL") or "http://127.0.0.1:3010").rstrip("/")


def _request(method: str, url: str, **kwargs: Any) -> Any:
    try:
        # Size Note is normally local. Ignoring ambient proxy settings prevents
        # localhost requests from being routed through a host-wide HTTP/SOCKS proxy.
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            response = client.request(method, url, **kwargs)
        response.raise_for_status()
    except httpx.RequestError:
        typer.echo(
            json.dumps(
                {
                    "status": "unavailable",
                    "detail": "Size Note is not reachable. Check that the container is running.",
                }
            )
        )
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json()
        except ValueError:
            detail = {"detail": exc.response.text}
        typer.echo(json.dumps({"status": "error", **detail}))
        raise typer.Exit(code=1) from None
    return response.json()


def _resolve(base_url: str, person: str) -> dict[str, Any]:
    return _request("POST", f"{base_url}/api/people/resolve", json={"name": person})


def _emit(payload: Any, *, json_output: bool, human: str | None = None) -> None:
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    elif human:
        typer.echo(human)
    else:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _parse_equivalent_options(values: list[str] | None) -> list[dict[str, str | None]]:
    result: list[dict[str, str | None]] = []
    for raw in values or []:
        if ":" not in raw:
            raise typer.BadParameter(
                "equivalent sizes must use SYSTEM:SIZE, for example --equivalent EU:40"
            )
        system, size = (part.strip() for part in raw.split(":", 1))
        if not size:
            raise typer.BadParameter("equivalent sizes must include a size value")
        result.append({"system": system or None, "size": size})
    return result


def _parse_birth_option(value: str) -> dict[str, int | None]:
    try:
        birth = parse_birth(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    return {
        "birth_year": birth.year,
        "birth_month": birth.month,
        "birth_day": birth.day,
    }


def _format_birth(person: dict[str, Any]) -> str | None:
    year = person.get("birth_year")
    if year is None:
        return None
    month = person.get("birth_month")
    day = person.get("birth_day")
    if month is None:
        return f"{year:04d}"
    if day is None:
        return f"{year:04d}-{month:02d}"
    return f"{year:04d}-{month:02d}-{day:02d}"


def _months_since(value: str) -> int:
    checked = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=UTC)
    days = max(0, (datetime.now(UTC) - checked.astimezone(UTC)).days)
    return days // 30


def _resolved_person_id(
    base_url: str, person: str, *, json_output: bool, operation: str
) -> str | None:
    resolution = _resolve(base_url, person)
    if resolution["status"] in {"exact_match", "alias_match"}:
        return resolution["candidates"][0]["id"]
    _emit(
        resolution,
        json_output=json_output,
        human=f"The person could not be resolved safely. Nothing was {operation}.",
    )
    return None


@app.command("person-add")
def person_add(
    name: Annotated[str, typer.Argument(help="Canonical display name")],
    growth_stage: Annotated[
        str | None, typer.Option("--growth-stage", help="adult or child")
    ] = None,
    birth: Annotated[
        str | None,
        typer.Option("--birth", help="Known birth information: YYYY, YYYY-MM, or YYYY-MM-DD"),
    ] = None,
    alias: Annotated[
        list[str] | None, typer.Option("--alias", help="Repeat for multiple aliases")
    ] = None,
    notes: Annotated[str | None, typer.Option("--notes")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """Create a person explicitly."""
    if growth_stage is not None and growth_stage not in {"adult", "child"}:
        raise typer.BadParameter("growth stage must be adult or child")
    if growth_stage is None and birth is None:
        raise typer.BadParameter(
            "provide --growth-stage child/adult or --birth YYYY, YYYY-MM, or YYYY-MM-DD"
        )

    person_data: dict[str, Any] = {
        "name": name,
        "growth_stage": growth_stage,
        "aliases": alias or [],
        "notes": notes,
    }
    if birth is not None:
        person_data.update(_parse_birth_option(birth))

    payload = _request(
        "POST",
        f"{_base_url(url)}/api/people",
        json=person_data,
    )
    _emit(payload, json_output=json_output, human=f"Created {payload['name']}.")


@app.command("person-update")
def person_update(
    person: Annotated[str, typer.Option("--person", help="Name or alias")],
    name: Annotated[str | None, typer.Option("--name")] = None,
    notes: Annotated[str | None, typer.Option("--notes")] = None,
    growth_stage: Annotated[
        str | None, typer.Option("--growth-stage", help="adult or child")
    ] = None,
    birth: Annotated[
        str | None,
        typer.Option("--birth", help="Known birth information: YYYY, YYYY-MM, or YYYY-MM-DD"),
    ] = None,
    clear_birth: Annotated[bool, typer.Option("--clear-birth")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """Update an exactly resolved person's profile."""
    if all(value is None for value in (name, notes, growth_stage, birth)) and not clear_birth:
        raise typer.BadParameter(
            "provide --name, --notes, --growth-stage, --birth, and/or --clear-birth"
        )
    if growth_stage is not None and growth_stage not in {"adult", "child"}:
        raise typer.BadParameter("growth stage must be adult or child")
    if birth is not None and clear_birth:
        raise typer.BadParameter("use either --birth or --clear-birth")

    base_url = _base_url(url)
    person_id = _resolved_person_id(
        base_url, person, json_output=json_output, operation="updated"
    )
    if person_id is None:
        return

    changes: dict[str, Any] = {}
    if name is not None:
        changes["name"] = name
    if notes is not None:
        changes["notes"] = notes
    if growth_stage is not None:
        changes["growth_stage"] = growth_stage
    if birth is not None:
        changes.update(_parse_birth_option(birth))
    elif clear_birth:
        changes.update({"birth_year": None, "birth_month": None, "birth_day": None})

    payload = _request(
        "PATCH",
        f"{base_url}/api/people/{person_id}",
        json=changes,
    )
    _emit(payload, json_output=json_output, human=f"Updated {payload['name']}.")


@app.command("person-delete")
def person_delete(
    person: Annotated[str, typer.Option("--person", help="Name or alias")],
    confirm: Annotated[bool, typer.Option("--confirm")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """Delete a person and all of their size history after explicit confirmation."""
    if not confirm:
        _emit(
            {
                "status": "confirmation_required",
                "detail": (
                    "Deleting a person also deletes all of their sizes. "
                    "Pass --confirm only after explicit user confirmation."
                ),
            },
            json_output=json_output,
            human="Confirmation required. Nothing was deleted.",
        )
        return

    base_url = _base_url(url)
    person_id = _resolved_person_id(
        base_url, person, json_output=json_output, operation="deleted"
    )
    if person_id is None:
        return
    payload = _request("DELETE", f"{base_url}/api/people/{person_id}")
    _emit(payload, json_output=json_output, human=f"Deleted {payload['name']}.")


@app.command()
def remember(
    person: Annotated[str, typer.Option("--person", help="Name or alias")],
    item: Annotated[str, typer.Option("--item")],
    size: Annotated[str, typer.Option("--size")],
    system: Annotated[str | None, typer.Option("--system")] = None,
    equivalent: Annotated[
        list[str] | None,
        typer.Option(
            "--equivalent",
            help="Repeat confirmed alternate systems as SYSTEM:SIZE, e.g. EU:40",
        ),
    ] = None,
    brand: Annotated[str | None, typer.Option("--brand")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    fit_notes: Annotated[str | None, typer.Option("--fit-notes")] = None,
    notes: Annotated[str | None, typer.Option("--notes")] = None,
    confirm_person_id: Annotated[
        str | None,
        typer.Option(
            "--confirm-person-id",
            help="Stable ID selected by the user after a suggested match",
        ),
    ] = None,
    remember_alias: Annotated[
        bool,
        typer.Option(
            "--remember-alias",
            help="Save --person as an alias after explicit confirmation",
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """Save or verify a person's size without silently guessing their identity."""
    base_url = _base_url(url)
    person_id = confirm_person_id
    if person_id is None:
        resolution = _resolve(base_url, person)
        if resolution["status"] not in {"exact_match", "alias_match"}:
            candidate = resolution.get("candidates", [{}])[0]
            if resolution["status"] == "confirmation_required" and candidate:
                human = (
                    f"Did you mean {candidate['name']}? "
                    "Confirmation required; nothing was saved."
                )
            elif resolution["status"] == "multiple_matches":
                human = "Several people may match. Confirmation required; nothing was saved."
            else:
                human = f'No person matched "{person}". Create the person first.'
            _emit(resolution, json_output=json_output, human=human)
            return
        person_id = resolution["candidates"][0]["id"]
    elif remember_alias:
        _request(
            "POST",
            f"{base_url}/api/people/{person_id}/aliases",
            json={"alias": person},
        )

    result = _request(
        "POST",
        f"{base_url}/api/sizes",
        json={
            "person_id": person_id,
            "item": item,
            "size": size,
            "system": system,
            "equivalents": _parse_equivalent_options(equivalent),
            "brand": brand,
            "model": model,
            "fit_notes": fit_notes,
            "notes": notes,
        },
    )
    record = result["record"]
    system_text = f" {record['system']}" if record.get("system") else ""
    _emit(
        result,
        json_output=json_output,
        human=f"{result['action'].title()}: {record['item']} {record['size']}{system_text}.",
    )


@app.command("size-update")
def size_update(
    person: Annotated[str, typer.Option("--person", help="Name or alias")],
    size_id: Annotated[str, typer.Option("--size-id", help="Stable size record ID")],
    item: Annotated[str | None, typer.Option("--item")] = None,
    size: Annotated[str | None, typer.Option("--size")] = None,
    system: Annotated[str | None, typer.Option("--system")] = None,
    equivalent: Annotated[
        list[str] | None,
        typer.Option(
            "--equivalent",
            help="Replacement equivalent SYSTEM:SIZE; repeat as needed",
        ),
    ] = None,
    clear_equivalents: Annotated[bool, typer.Option("--clear-equivalents")] = False,
    brand: Annotated[str | None, typer.Option("--brand")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    fit_notes: Annotated[str | None, typer.Option("--fit-notes")] = None,
    notes: Annotated[str | None, typer.Option("--notes")] = None,
    measured_on: Annotated[str | None, typer.Option("--measured-on")] = None,
    clear_measured_on: Annotated[bool, typer.Option("--clear-measured-on")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """Correct one existing size record in place."""
    supplied = any(
        value is not None
        for value in (
            item,
            size,
            system,
            equivalent,
            brand,
            model,
            fit_notes,
            notes,
            measured_on,
        )
    ) or clear_measured_on or clear_equivalents
    if not supplied:
        raise typer.BadParameter("provide at least one field to update")
    if measured_on is not None and clear_measured_on:
        raise typer.BadParameter("use either --measured-on or --clear-measured-on")
    if equivalent is not None and clear_equivalents:
        raise typer.BadParameter("use either --equivalent or --clear-equivalents")

    base_url = _base_url(url)
    person_id = _resolved_person_id(
        base_url, person, json_output=json_output, operation="updated"
    )
    if person_id is None:
        return

    changes: dict[str, Any] = {}
    for key, value in {
        "item": item,
        "size": size,
        "system": system,
        "brand": brand,
        "model": model,
        "fit_notes": fit_notes,
        "notes": notes,
    }.items():
        if value is not None:
            changes[key] = value
    if equivalent is not None:
        changes["equivalents"] = _parse_equivalent_options(equivalent)
    elif clear_equivalents:
        changes["equivalents"] = []
    if measured_on is not None:
        changes["measured_on"] = measured_on
    elif clear_measured_on:
        changes["measured_on"] = None

    payload = _request(
        "PATCH",
        f"{base_url}/api/people/{person_id}/sizes/{size_id}",
        json=changes,
    )
    _emit(
        payload,
        json_output=json_output,
        human=f"Updated {payload['item']} {payload['size']}.",
    )


@app.command("size-delete")
def size_delete(
    person: Annotated[str, typer.Option("--person", help="Name or alias")],
    size_id: Annotated[str, typer.Option("--size-id", help="Stable size record ID")],
    confirm: Annotated[bool, typer.Option("--confirm")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """Delete one size record after explicit confirmation."""
    if not confirm:
        _emit(
            {
                "status": "confirmation_required",
                "detail": "Pass --confirm only after explicit user confirmation.",
            },
            json_output=json_output,
            human="Confirmation required. Nothing was deleted.",
        )
        return

    base_url = _base_url(url)
    person_id = _resolved_person_id(
        base_url, person, json_output=json_output, operation="deleted"
    )
    if person_id is None:
        return
    payload = _request(
        "DELETE", f"{base_url}/api/people/{person_id}/sizes/{size_id}"
    )
    _emit(
        payload,
        json_output=json_output,
        human=f"Deleted {payload['item']} {payload['size']}.",
    )


@app.command("get")
def get_sizes(
    person: Annotated[str, typer.Option("--person", help="Name or alias")],
    current_only: Annotated[bool, typer.Option("--current-only")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """Retrieve sizes for an exactly resolved person."""
    base_url = _base_url(url)
    resolution = _resolve(base_url, person)
    if resolution["status"] not in {"exact_match", "alias_match"}:
        _emit(
            resolution,
            json_output=json_output,
            human="The person could not be resolved safely. Nothing was retrieved.",
        )
        return

    candidate = resolution["candidates"][0]
    records = _request(
        "GET",
        f"{base_url}/api/people/{candidate['id']}/sizes",
        params={"history": str(not current_only).lower()},
    )
    all_reviews = _request("GET", f"{base_url}/api/reviews")
    reviews = [entry for entry in all_reviews if entry["person_id"] == candidate["id"]]
    review_status = {entry["size_id"]: entry["status"] for entry in reviews}
    payload = {
        "status": "ok",
        "person": candidate,
        "sizes": records,
        "reviews": reviews,
    }
    if not records:
        human = f"No sizes are saved for {candidate['name']}."
    else:
        lines = [f"{candidate['name']}:"]
        for record in records:
            marker = "" if record["is_current"] else " (previous)"
            system_text = f" {record['system']}" if record.get("system") else ""
            equivalents_text = ""
            if record.get("equivalents"):
                formatted = ", ".join(
                    (
                        f"{entry['size']} {entry['system']}"
                        if entry.get("system")
                        else entry["size"]
                    )
                    for entry in record["equivalents"]
                )
                equivalents_text = f" · also {formatted}"
            brand_text = f" · {record['brand']}" if record.get("brand") else ""
            review_text = (
                f" · {review_status[record['id']]}"
                if review_status.get(record["id"]) in {"due", "review_soon"}
                else ""
            )
            lines.append(
                f"- {record['item']}: "
                f"{record['size']}{system_text}{equivalents_text}{brand_text}{review_text}{marker}"
            )
        human = "\n".join(lines)
    _emit(payload, json_output=json_output, human=human)


@app.command()
def people(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """List people and their aliases."""
    payload = _request("GET", f"{_base_url(url)}/api/people")
    lines = []
    for person in payload:
        aliases = f" ({', '.join(person['aliases'])})" if person["aliases"] else ""
        birth = _format_birth(person)
        birth_text = f" · born {birth}" if birth else ""
        lines.append(f"- {person['name']}{aliases} · {person['growth_stage']}{birth_text}")
    human = "\n".join(lines) or "No people have been added."
    _emit(payload, json_output=json_output, human=human)


@app.command()
def review(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """List age-aware size review dates for children."""
    payload = _request("GET", f"{_base_url(url)}/api/reviews")
    attention = [entry for entry in payload if entry["status"] != "current"]
    lines = []
    for entry in attention:
        age = entry.get("person_age_years")
        if age is None:
            age_text = ""
        else:
            qualifier = "about " if entry.get("person_age_approximate") else ""
            age_text = f" · {qualifier}{age} years old"
        months = _months_since(entry["verified_at"])
        checked_text = f" · checked {months} month{'s' if months != 1 else ''} ago"
        lines.append(
            f"- {entry['person_name']} · {entry['item']} {entry['size']}: "
            f"{entry['status']}{age_text}{checked_text}"
        )
    human = "\n".join(lines) or "No sizes need review."
    _emit(payload, json_output=json_output, human=human)


@app.command()
def health(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """Check whether the Size Note service is reachable."""
    payload = _request("GET", f"{_base_url(url)}/health")
    _emit(payload, json_output=json_output, human=f"Size Note {payload['version']} is healthy.")


if __name__ == "__main__":
    app()
