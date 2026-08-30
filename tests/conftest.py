import pytest
from fastapi.testclient import TestClient

from size_note.main import create_app


@pytest.fixture
def client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = create_app(database_url=database_url, auto_create_schema=True)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def create_person(client):
    def factory(
        name: str = "Alexandra",
        *,
        growth_stage: str | None = "adult",
        birth_year: int | None = None,
        birth_month: int | None = None,
        birth_day: int | None = None,
        aliases: list[str] | None = None,
        notes: str | None = None,
    ) -> dict:
        response = client.post(
            "/api/people",
            json={
                "name": name,
                "growth_stage": growth_stage,
                "birth_year": birth_year,
                "birth_month": birth_month,
                "birth_day": birth_day,
                "aliases": aliases or [],
                "notes": notes,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    return factory
