from typer.testing import CliRunner

from size_note import cli

runner = CliRunner()


def test_person_add_accepts_partial_birth_without_growth_stage(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {
            "id": "person-1",
            "name": "Haru",
            "growth_stage": "child",
            "birth_year": 2024,
            "birth_month": None,
            "birth_day": None,
            "aliases": [],
            "notes": "My son",
        }

    monkeypatch.setattr(cli, "_request", fake_request)
    result = runner.invoke(
        cli.app,
        ["person-add", "Haru", "--birth", "2024", "--notes", "My son", "--json"],
    )

    assert result.exit_code == 0
    assert calls == [
        (
            "POST",
            "http://127.0.0.1:3010/api/people",
            {
                "json": {
                    "name": "Haru",
                    "growth_stage": None,
                    "aliases": [],
                    "notes": "My son",
                    "birth_year": 2024,
                    "birth_month": None,
                    "birth_day": None,
                }
            },
        )
    ]


def test_person_add_requires_stage_or_birth_before_api_call(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_request", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = runner.invoke(cli.app, ["person-add", "Morgan", "--json"])

    assert result.exit_code != 0
    assert calls == []


def test_person_update_can_replace_or_clear_birth(monkeypatch):
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
            "birth_year": 2024,
            "birth_month": 5,
            "birth_day": None,
            "aliases": [],
            "notes": None,
        }

    monkeypatch.setattr(cli, "_request", fake_request)

    changed = runner.invoke(
        cli.app,
        ["person-update", "--person", "Haru", "--birth", "2024-05", "--json"],
    )
    assert changed.exit_code == 0
    assert calls[-1][2]["json"] == {
        "birth_year": 2024,
        "birth_month": 5,
        "birth_day": None,
    }

    cleared = runner.invoke(
        cli.app,
        ["person-update", "--person", "Haru", "--clear-birth", "--json"],
    )
    assert cleared.exit_code == 0
    assert calls[-1][2]["json"] == {
        "birth_year": None,
        "birth_month": None,
        "birth_day": None,
    }


def test_review_human_output_mentions_age_and_time_since_check(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_request",
        lambda *args, **kwargs: [
            {
                "person_id": "person-1",
                "person_name": "Haru",
                "person_age_years": 2,
                "person_age_approximate": True,
                "review_interval_days": 90,
                "size_id": "size-1",
                "item": "T-shirt",
                "size": "90",
                "system": "JP",
                "verified_at": "2026-01-01T00:00:00Z",
                "due_at": "2026-04-01T00:00:00Z",
                "status": "due",
            }
        ],
    )

    result = runner.invoke(cli.app, ["review"])

    assert result.exit_code == 0
    assert "about 2 years old" in result.stdout
    assert "checked" in result.stdout
    assert "months ago" in result.stdout
