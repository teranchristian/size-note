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
