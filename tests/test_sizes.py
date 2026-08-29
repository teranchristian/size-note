def test_size_updates_preserve_history_and_same_value_only_verifies(client, create_person):
    person = create_person("Sam", growth_stage="child")
    base = {
        "person_id": person["id"],
        "item": "Shoes",
        "size": "15 cm",
        "system": "JP",
        "verified_at": "2025-01-01T00:00:00Z",
    }

    created = client.post("/api/sizes", json=base)
    assert created.status_code == 200
    assert created.json()["action"] == "created"
    assert created.json()["record"]["verified_at"].endswith("Z")

    verified = client.post(
        "/api/sizes",
        json={**base, "verified_at": "2025-02-01T00:00:00Z", "fit_notes": "Good fit"},
    )
    assert verified.json()["action"] == "verified"
    assert verified.json()["record"]["fit_notes"] == "Good fit"
    assert len(client.get(f"/api/people/{person['id']}/sizes").json()) == 1

    updated = client.post(
        "/api/sizes",
        json={**base, "size": "15.5 cm", "verified_at": "2025-03-01T00:00:00Z"},
    )
    assert updated.json()["action"] == "updated"

    records = client.get(f"/api/people/{person['id']}/sizes").json()
    assert [record["size"] for record in records] == ["15.5 cm", "15 cm"]
    assert records[0]["is_current"] is True
    assert records[1]["is_current"] is False
    assert records[1]["superseded_at"] is not None


def test_confirmed_sizes_in_different_systems_can_coexist(client, create_person):
    person = create_person("Sam", growth_stage="child")
    for size, system in [("15 cm", "JP"), ("8", "AU Kids")]:
        response = client.post(
            "/api/sizes",
            json={
                "person_id": person["id"],
                "item": "Shoes",
                "size": size,
                "system": system,
            },
        )
        assert response.json()["action"] == "created"

    current = client.get(
        f"/api/people/{person['id']}/sizes", params={"history": "false"}
    ).json()
    assert {(record["size"], record["system"]) for record in current} == {
        ("15 cm", "JP"),
        ("8", "AU Kids"),
    }


def test_child_review_rules_depend_on_item_not_relationship(client, create_person):
    person = create_person("Sam", growth_stage="child", notes="Prefers soft fabrics")
    for item in ["Shoes", "T-shirt"]:
        client.post(
            "/api/sizes",
            json={
                "person_id": person["id"],
                "item": item,
                "size": "M",
                "verified_at": "2020-01-01T00:00:00Z",
            },
        )

    reviews = client.get("/api/reviews").json()
    assert len(reviews) == 2
    assert all(review["status"] == "due" for review in reviews)
    due_dates = {review["item"]: review["due_at"] for review in reviews}
    assert due_dates["Shoes"].startswith("2020-03-31")
    assert due_dates["T-shirt"].startswith("2020-06-29")


def test_adult_sizes_do_not_get_automatic_review_deadlines(client, create_person):
    person = create_person("Alexandra", growth_stage="adult")
    client.post(
        "/api/sizes",
        json={
            "person_id": person["id"],
            "item": "T-shirt",
            "size": "M",
            "verified_at": "2020-01-01T00:00:00Z",
        },
    )

    assert client.get("/api/reviews").json() == []


def test_current_size_can_be_verified_without_new_history(client, create_person):
    person = create_person("Alexandra")
    saved = client.post(
        "/api/sizes",
        json={
            "person_id": person["id"],
            "item": "T-shirt",
            "size": "M",
            "verified_at": "2020-01-01T00:00:00Z",
        },
    ).json()

    verified = client.post(f"/api/sizes/{saved['record']['id']}/verify")

    assert verified.status_code == 200
    assert verified.json()["action"] == "verified"
    assert not verified.json()["record"]["verified_at"].startswith("2020-01-01")
    assert len(client.get(f"/api/people/{person['id']}/sizes").json()) == 1
