from typer.testing import CliRunner

from size_note import cli_ext

runner = CliRunner()


def test_person_alias_add_resolves_then_posts(monkeypatch):
    calls = []
    monkeypatch.setattr(cli_ext, "_resolved_person_id", lambda *args, **kwargs: "person-1")

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {"id": "person-1", "name": "Riley", "aliases": ["my son"]}

    monkeypatch.setattr(cli_ext, "_request", fake_request)
    result = runner.invoke(
        cli_ext.app,
        [
            "person-alias-add",
            "--person",
            "Riley",
            "--alias",
            "my son",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        (
            "POST",
            "http://127.0.0.1:3010/api/people/person-1/aliases",
            {"json": {"alias": "my son"}},
        )
    ]


def test_person_alias_update_finds_alias_then_patches(monkeypatch):
    calls = []
    monkeypatch.setattr(cli_ext, "_resolved_person_id", lambda *args, **kwargs: "person-1")

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "GET":
            return [{"id": "alias-1", "alias": "My Kid"}]
        return {"id": "person-1", "name": "Riley", "aliases": ["my son"]}

    monkeypatch.setattr(cli_ext, "_request", fake_request)
    result = runner.invoke(
        cli_ext.app,
        [
            "person-alias-update",
            "--person",
            "Riley",
            "--alias",
            "my kid",
            "--new-alias",
            "my son",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        ("GET", "http://127.0.0.1:3010/api/people/person-1/aliases", {}),
        (
            "PATCH",
            "http://127.0.0.1:3010/api/people/person-1/aliases/alias-1",
            {"json": {"alias": "my son"}},
        ),
    ]


def test_person_alias_update_stops_when_alias_is_missing(monkeypatch):
    calls = []
    monkeypatch.setattr(cli_ext, "_resolved_person_id", lambda *args, **kwargs: "person-1")

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return []

    monkeypatch.setattr(cli_ext, "_request", fake_request)
    result = runner.invoke(
        cli_ext.app,
        [
            "person-alias-update",
            "--person",
            "Riley",
            "--alias",
            "my kid",
            "--new-alias",
            "my son",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert '"status": "not_found"' in result.stdout
    assert calls == [("GET", "http://127.0.0.1:3010/api/people/person-1/aliases", {})]


def test_person_alias_delete_requires_confirmation_before_resolution(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli_ext,
        "_resolved_person_id",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    result = runner.invoke(
        cli_ext.app,
        [
            "person-alias-delete",
            "--person",
            "Riley",
            "--alias",
            "my son",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert '"status": "confirmation_required"' in result.stdout
    assert calls == []


def test_person_alias_delete_finds_alias_then_deletes(monkeypatch):
    calls = []
    monkeypatch.setattr(cli_ext, "_resolved_person_id", lambda *args, **kwargs: "person-1")

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "GET":
            return [{"id": "alias-1", "alias": "my son"}]
        return {"id": "person-1", "name": "Riley", "aliases": []}

    monkeypatch.setattr(cli_ext, "_request", fake_request)
    result = runner.invoke(
        cli_ext.app,
        [
            "person-alias-delete",
            "--person",
            "Riley",
            "--alias",
            "my son",
            "--confirm",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        ("GET", "http://127.0.0.1:3010/api/people/person-1/aliases", {}),
        ("DELETE", "http://127.0.0.1:3010/api/people/person-1/aliases/alias-1", {}),
    ]
