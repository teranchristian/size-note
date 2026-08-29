def test_resolves_exact_names_and_confirmed_aliases(client, create_person):
    person = create_person("Alexandra", notes="Prefers relaxed fits")

    exact = client.post("/api/v1/people/resolve", json={"name": "  ALEXANDRA  "})
    assert exact.status_code == 200
    assert exact.json()["status"] == "exact_match"
    assert exact.json()["candidates"][0]["id"] == person["id"]

    suggestion = client.post("/api/v1/people/resolve", json={"name": "Alex"})
    assert suggestion.status_code == 200
    assert suggestion.json()["status"] == "confirmation_required"
    assert suggestion.json()["candidates"][0]["name"] == "Alexandra"

    people_before_confirmation = client.get("/api/v1/people").json()
    assert people_before_confirmation[0]["aliases"] == []

    confirmed = client.post(
        f"/api/v1/people/{person['id']}/aliases", json={"alias": "Alex"}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["aliases"] == ["Alex"]

    alias = client.post("/api/v1/people/resolve", json={"name": "alex"})
    assert alias.json()["status"] == "alias_match"
    assert alias.json()["candidates"][0]["id"] == person["id"]


def test_short_or_unknown_names_are_not_guessed(client, create_person):
    create_person("Alexandra")

    short = client.post("/api/v1/people/resolve", json={"name": "Al"}).json()
    unknown = client.post("/api/v1/people/resolve", json={"name": "Morgan"}).json()

    assert short == {"status": "not_found", "query": "Al", "candidates": []}
    assert unknown["status"] == "not_found"


def test_names_and_aliases_cannot_point_to_different_people(client, create_person):
    create_person("Alexandra", aliases=["Alex"])
    response = client.post(
        "/api/v1/people",
        json={"name": "Alex", "growth_stage": "adult", "aliases": []},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "person_identifier_conflict"


def test_person_context_remains_free_form_notes(client, create_person):
    person = create_person("Sam", growth_stage="child", notes="Prefers soft fabrics")

    assert person["growth_stage"] == "child"
    assert person["notes"] == "Prefers soft fabrics"
    assert "relationship" not in person
