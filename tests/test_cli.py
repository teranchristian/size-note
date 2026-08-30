from typer.testing import CliRunner

from size_note import cli

runner = CliRunner()


def test_remember_stops_at_similar_match(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "_resolve",
        lambda _url, _person: {
            "status": "confirmation_required",
            "query": "Alex",
            "candidates": [{"id": "person-1", "name": "Alexandra"}],
        },
    )
    monkeypatch.setattr(cli, "_request", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = runner.invoke(
        cli.app,
        [
            "remember",
            "--person",
            "Alex",
            "--item",
            "T-shirt",
            "--size",
            "M",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert '"status": "confirmation_required"' in result.stdout
    assert calls == []


def test_confirmed_match_can_store_alias_then_size(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith("/aliases"):
            return {"id": "person-1", "name": "Alexandra"}
        return {
            "action": "created",
            "record": {"item": "T-shirt", "size": "M", "system": None},
        }

    monkeypatch.setattr(cli, "_request", fake_request)
    result = runner.invoke(
        cli.app,
        [
            "remember",
            "--person",
            "Alex",
            "--confirm-person-id",
            "person-1",
            "--remember-alias",
            "--item",
            "T-shirt",
            "--size",
            "M",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert len(calls) == 2
    assert calls[0][1].endswith("/api/people/person-1/aliases")
    assert calls[1][1].endswith("/api/sizes")


def test_remember_groups_repeatable_equivalent_sizes(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "_resolve",
        lambda _url, _person: {
            "status": "exact_match",
            "query": "Christian",
            "candidates": [{"id": "person-1", "name": "Christian"}],
        },
    )

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {
            "action": "created",
            "record": {
                "item": "Shoes",
                "size": "25.25",
                "system": "CM",
                "equivalents": [
                    {"system": "EU", "size": "40"},
                    {"system": "US", "size": "7"},
                ],
            },
        }

    monkeypatch.setattr(cli, "_request", fake_request)
    result = runner.invoke(
        cli.app,
        [
            "remember",
            "--person",
            "Christian",
            "--item",
            "Shoes",
            "--size",
            "25.25",
            "--system",
            "CM",
            "--equivalent",
            "EU:40",
            "--equivalent",
            "US:7",
            "--brand",
            "ASICS",
            "--model",
            "1011B004",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        (
            "POST",
            "http://127.0.0.1:3010/api/sizes",
            {
                "json": {
                    "person_id": "person-1",
                    "item": "Shoes",
                    "size": "25.25",
                    "system": "CM",
                    "equivalents": [
                        {"system": "EU", "size": "40"},
                        {"system": "US", "size": "7"},
                    ],
                    "brand": "ASICS",
                    "model": "1011B004",
                    "fit_notes": None,
                    "notes": None,
                }
            },
        )
    ]


def test_person_update_resolves_exact_person_then_patches(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "_resolve",
        lambda _url, _person: {
            "status": "exact_match",
            "query": "Haru",
            "candidates": [{"id": "person-1", "name": "Haru"}],
        },
    )

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {
            "id": "person-1",
            "name": "Haru",
            "growth_stage": "child",
            "notes": "My son; born in 2024",
        }

    monkeypatch.setattr(cli, "_request", fake_request)
    result = runner.invoke(
        cli.app,
        [
            "person-update",
            "--person",
            "Haru",
            "--notes",
            "My son; born in 2024",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        (
            "PATCH",
            "http://127.0.0.1:3010/api/people/person-1",
            {"json": {"notes": "My son; born in 2024"}},
        )
    ]
    assert '"notes": "My son; born in 2024"' in result.stdout


def test_person_update_stops_at_similar_match(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "_resolve",
        lambda _url, _person: {
            "status": "confirmation_required",
            "query": "Har",
            "candidates": [{"id": "person-1", "name": "Haru"}],
        },
    )
    monkeypatch.setattr(cli, "_request", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = runner.invoke(
        cli.app,
        ["person-update", "--person", "Har", "--notes", "My son", "--json"],
    )

    assert result.exit_code == 0
    assert '"status": "confirmation_required"' in result.stdout
    assert calls == []


def test_person_delete_requires_explicit_confirm_before_resolution(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_resolve", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = runner.invoke(
        cli.app,
        ["person-delete", "--person", "Haru", "--json"],
    )

    assert result.exit_code == 0
    assert '"status": "confirmation_required"' in result.stdout
    assert calls == []


def test_person_delete_resolves_then_deletes_after_confirm(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "_resolve",
        lambda _url, _person: {
            "status": "exact_match",
            "query": "Haru",
            "candidates": [{"id": "person-1", "name": "Haru"}],
        },
    )

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {"status": "deleted", "id": "person-1", "name": "Haru"}

    monkeypatch.setattr(cli, "_request", fake_request)
    result = runner.invoke(
        cli.app,
        ["person-delete", "--person", "Haru", "--confirm", "--json"],
    )

    assert result.exit_code == 0
    assert calls == [
        ("DELETE", "http://127.0.0.1:3010/api/people/person-1", {})
    ]
    assert '"status": "deleted"' in result.stdout


def test_size_update_uses_exact_person_and_stable_size_id(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "_resolve",
        lambda _url, _person: {
            "status": "exact_match",
            "query": "Haru",
            "candidates": [{"id": "person-1", "name": "Haru"}],
        },
    )

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {
            "id": "size-1",
            "person_id": "person-1",
            "item": "T-shirt",
            "size": "95",
            "system": "Japan",
        }

    monkeypatch.setattr(cli, "_request", fake_request)
    result = runner.invoke(
        cli.app,
        [
            "size-update",
            "--person",
            "Haru",
            "--size-id",
            "size-1",
            "--size",
            "95",
            "--notes",
            "Corrected",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        (
            "PATCH",
            "http://127.0.0.1:3010/api/people/person-1/sizes/size-1",
            {"json": {"size": "95", "notes": "Corrected"}},
        )
    ]


def test_size_delete_requires_confirm(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_resolve", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = runner.invoke(
        cli.app,
        ["size-delete", "--person", "Haru", "--size-id", "size-1", "--json"],
    )

    assert result.exit_code == 0
    assert '"status": "confirmation_required"' in result.stdout
    assert calls == []
