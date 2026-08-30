def test_resolves_exact_names_and_confirmed_aliases(client, create_person):
    person = create_person("Alexandra", notes="Prefers relaxed fits")

    exact = client.post("/api/people/resolve", json={"name": "  ALEXANDRA  "})
    assert exact.status_code == 200
    assert exact.json()["status"] == "exact_match"
    assert exact.json()["candidates"][0]["id"] == person["id"]

    suggestion = client.post("/api/people/resolve", json={"name": "Alex"})
    assert suggestion.status_code == 200
    assert suggestion.json()["status"] == "confirmation_required"
    assert suggestion.json()["candidates"][0]["name"] == "Alexandra"

    people_before_confirmation = client.get("/api/people").json()
    assert people_before_confirmation[0]["aliases"] == []

    confirmed = client.post(
        f"/api/people/{person['id']}/aliases", json={"alias": "Alex"}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["aliases"] == ["Alex"]

    alias = client.post("/api/people/resolve", json={"name": "alex"})
    assert alias.json()["status"] == "alias_match"
    assert alias.json()["candidates"][0]["id"] == person["id"]


def test_short_or_unknown_names_are_not_guessed(client, create_person):
    create_person("Alexandra")

    short = client.post("/api/people/resolve", json={"name": "Al"}).json()
    unknown = client.post("/api/people/resolve", json={"name": "Morgan"}).json()

    assert short == {"status": "not_found", "query": "Al", "candidates": []}
    assert unknown["status"] == "not_found"


def test_names_and_aliases_cannot_point_to_different_people(client, create_person):
    create_person("Alexandra", aliases=["Alex"])
    response = client.post(
        "/api/people",
        json={"name": "Alex", "growth_stage": "adult", "aliases": []},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "person_identifier_conflict"


def test_person_creation_requires_stage_or_birth_information(client):
    response = client.post(
        "/api/people",
        json={"name": "Morgan", "aliases": [], "notes": None},
    )

    assert response.status_code == 422
    assert "Choose child or adult" in response.text


def test_birth_year_can_infer_child_without_fabricating_month_or_day(client):
    response = client.post(
        "/api/people",
        json={
            "name": "Haru",
            "birth_year": 2024,
            "aliases": [],
            "notes": "My son",
        },
    )

    assert response.status_code == 201
    person = response.json()
    assert person["growth_stage"] == "child"
    assert person["birth_year"] == 2024
    assert person["birth_month"] is None
    assert person["birth_day"] is None
    assert person["notes"] == "My son"


def test_person_context_remains_free_form_notes(client, create_person):
    person = create_person("Sam", growth_stage="child", notes="Prefers soft fabrics")

    assert person["growth_stage"] == "child"
    assert person["notes"] == "Prefers soft fabrics"
    assert "relationship" not in person


def test_person_notes_can_be_updated_and_cleared(client, create_person):
    person = create_person("Haru", growth_stage="child")

    updated = client.patch(
        f"/api/people/{person['id']}",
        json={"notes": "My son"},
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "My son"
    assert updated.json()["growth_stage"] == "child"

    cleared = client.patch(f"/api/people/{person['id']}", json={"notes": "   "})
    assert cleared.status_code == 200
    assert cleared.json()["notes"] is None


def test_partial_birth_information_can_be_updated_and_cleared(client, create_person):
    person = create_person("Haru", growth_stage="child")

    updated = client.patch(
        f"/api/people/{person['id']}",
        json={"birth_year": 2024, "birth_month": 5, "birth_day": None},
    )
    assert updated.status_code == 200
    assert updated.json()["birth_year"] == 2024
    assert updated.json()["birth_month"] == 5
    assert updated.json()["birth_day"] is None

    cleared = client.patch(
        f"/api/people/{person['id']}",
        json={"birth_year": None, "birth_month": None, "birth_day": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["birth_year"] is None
    assert cleared.json()["birth_month"] is None
    assert cleared.json()["birth_day"] is None


def test_person_name_and_growth_stage_can_be_corrected(client, create_person):
    person = create_person("Haru T", growth_stage="adult")

    updated = client.patch(
        f"/api/people/{person['id']}",
        json={"name": "Haru", "growth_stage": "child"},
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Haru"
    assert updated.json()["growth_stage"] == "child"
    resolution = client.post("/api/people/resolve", json={"name": "Haru"}).json()
    assert resolution["status"] == "exact_match"
    assert resolution["candidates"][0]["id"] == person["id"]


def test_deleting_person_removes_aliases_and_size_history(client, create_person):
    person = create_person("Haru", growth_stage="child", aliases=["H"])
    saved = client.post(
        "/api/sizes",
        json={"person_id": person["id"], "item": "T-shirt", "size": "90"},
    ).json()["record"]

    deleted = client.delete(f"/api/people/{person['id']}")

    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    assert client.get(f"/api/people/{person['id']}").status_code == 404
    assert client.get("/api/people").json() == []
    assert client.patch(
        f"/api/people/{person['id']}/sizes/{saved['id']}", json={"size": "95"}
    ).status_code == 404
