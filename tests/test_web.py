def test_mobile_web_flow_creates_person_and_size(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "Remember what fits" in home.text

    created = client.post(
        "/people",
        data={
            "name": "Alexandra",
            "growth_stage": "adult",
            "aliases": "Alex",
            "notes": "Prefers relaxed fits",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    person_url = created.headers["location"]

    detail = client.get(person_url)
    assert detail.status_code == 200
    assert "Alexandra" in detail.text
    assert "Prefers relaxed fits" in detail.text
    assert "Edit note" in detail.text

    saved = client.post(
        f"{person_url}/sizes",
        data={
            "item": "T-shirt",
            "size": "M",
            "system": "Universal",
            "brand": "",
            "model": "",
            "fit_notes": "A little loose",
            "notes": "Bought in Tokyo",
            "measured_on": "",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    updated_detail = client.get(person_url)
    assert "T-shirt" in updated_detail.text
    assert "Universal" in updated_detail.text
    assert "A little loose" in updated_detail.text
    assert "Bought in Tokyo" in updated_detail.text


def test_person_notes_can_be_added_and_edited_from_detail_page(client, create_person):
    person = create_person("Haru", growth_stage="child")
    person_url = f"/people/{person['id']}"

    detail = client.get(person_url)
    assert "No notes yet" in detail.text
    assert "Add note" in detail.text

    updated = client.post(
        f"{person_url}/notes",
        data={"notes": "My son; born in 2024"},
        follow_redirects=False,
    )
    assert updated.status_code == 303

    detail = client.get(person_url)
    assert "My son; born in 2024" in detail.text
    assert "Edit note" in detail.text

    stored = client.get(f"/api/people/{person['id']}").json()
    assert stored["notes"] == "My son; born in 2024"


def test_web_lookup_requires_confirmation_before_aliasing(client, create_person):
    person = create_person("Alexandra")

    result = client.get("/find", params={"name": "Alex"})
    assert result.status_code == 200
    assert "Who did you mean?" in result.text
    assert "Yes, use this person" in result.text

    unchanged = client.get(f"/api/people/{person['id']}").json()
    assert unchanged["aliases"] == []
