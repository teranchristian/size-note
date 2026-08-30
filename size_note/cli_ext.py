from typing import Annotated, Any

import typer

from size_note.cli import _base_url, _emit, _request, _resolved_person_id, app
from size_note.normalization import normalize


def _aliases_for_person(base_url: str, person_id: str) -> list[dict[str, str]]:
    return _request("GET", f"{base_url}/api/people/{person_id}/aliases")


def _find_alias(aliases: list[dict[str, str]], raw_alias: str) -> dict[str, str] | None:
    alias_key = normalize(raw_alias)
    return next((entry for entry in aliases if normalize(entry["alias"]) == alias_key), None)


def _emit_alias_not_found(raw_alias: str, *, json_output: bool) -> None:
    payload = {
        "status": "not_found",
        "detail": f'Alias "{raw_alias}" was not found for that person.',
    }
    _emit(
        payload,
        json_output=json_output,
        human=f'Alias "{raw_alias}" was not found. Nothing was changed.',
    )


@app.command("person-alias-list")
def person_alias_list(
    person: Annotated[str, typer.Option("--person", help="Name or alias")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """List aliases for one exactly resolved person."""
    base_url = _base_url(url)
    person_id = _resolved_person_id(
        base_url, person, json_output=json_output, operation="listed"
    )
    if person_id is None:
        return
    aliases = _aliases_for_person(base_url, person_id)
    payload: dict[str, Any] = {"person_id": person_id, "aliases": aliases}
    _emit(
        payload,
        json_output=json_output,
        human=f"Found {len(aliases)} alias{'es' if len(aliases) != 1 else ''}.",
    )


@app.command("person-alias-add")
def person_alias_add(
    person: Annotated[str, typer.Option("--person", help="Name or alias")],
    alias: Annotated[str, typer.Option("--alias", help="Alias to add")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """Add an alias to one exactly resolved person."""
    base_url = _base_url(url)
    person_id = _resolved_person_id(
        base_url, person, json_output=json_output, operation="updated"
    )
    if person_id is None:
        return
    payload = _request(
        "POST",
        f"{base_url}/api/people/{person_id}/aliases",
        json={"alias": alias},
    )
    _emit(payload, json_output=json_output, human=f'Alias "{alias}" is saved.')


@app.command("person-alias-update")
def person_alias_update(
    person: Annotated[str, typer.Option("--person", help="Name or alias")],
    alias: Annotated[str, typer.Option("--alias", help="Existing alias")],
    new_alias: Annotated[str, typer.Option("--new-alias", help="Replacement alias")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """Rename one alias for an exactly resolved person."""
    base_url = _base_url(url)
    person_id = _resolved_person_id(
        base_url, person, json_output=json_output, operation="updated"
    )
    if person_id is None:
        return
    entry = _find_alias(_aliases_for_person(base_url, person_id), alias)
    if entry is None:
        _emit_alias_not_found(alias, json_output=json_output)
        return
    payload = _request(
        "PATCH",
        f"{base_url}/api/people/{person_id}/aliases/{entry['id']}",
        json={"alias": new_alias},
    )
    _emit(
        payload,
        json_output=json_output,
        human=f'Updated alias "{alias}" to "{new_alias}".',
    )


@app.command("person-alias-delete")
def person_alias_delete(
    person: Annotated[str, typer.Option("--person", help="Name or alias")],
    alias: Annotated[str, typer.Option("--alias", help="Alias to delete")],
    confirm: Annotated[bool, typer.Option("--confirm")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    url: Annotated[str | None, typer.Option("--url", envvar="SIZE_NOTE_URL")] = None,
) -> None:
    """Delete one alias after explicit confirmation."""
    if not confirm:
        _emit(
            {
                "status": "confirmation_required",
                "detail": (
                    f'Deleting alias "{alias}" stops that phrase from identifying the person. '
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
    entry = _find_alias(_aliases_for_person(base_url, person_id), alias)
    if entry is None:
        _emit_alias_not_found(alias, json_output=json_output)
        return
    payload = _request(
        "DELETE",
        f"{base_url}/api/people/{person_id}/aliases/{entry['id']}",
    )
    _emit(payload, json_output=json_output, human=f'Deleted alias "{alias}".')
