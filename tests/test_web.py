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
    assert "Edit person" in detail.text

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
    assert "Edit" in updated_detail.text


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


def test_person_can_be_edited_from_web(client, create_person):
    person = create_person("Haru T", growth_stage="adult", notes="Old note")
    edit_url = f"/people/{person['id']}/edit"

    page = client.get(edit_url)
    assert page.status_code == 200
    assert "Edit person" in page.text
    assert "Old note" in page.text

    changed = client.post(
        edit_url,
        data={
            "name": "Haru",
            "growth_stage": "child",
            "notes": "My son; born in 2024",
        },
        follow_redirects=False,
    )

    assert changed.status_code == 303
    stored = client.get(f"/api/people/{person['id']}").json()
    assert stored["name"] == "Haru"
    assert stored["growth_stage"] == "child"
    assert stored["notes"] == "My son; born in 2024"


def test_size_can_be_edited_and_deleted_from_web(client, create_person):
    person = create_person("Haru", growth_stage="child")
    person_url = f"/people/{person['id']}"
    saved = client.post(
        "/api/sizes",
        json={
            "person_id": person["id"],
            "item": "T-shirt",
            "size": "90",
            "system": "Japan",
            "notes": "Wrong note",
        },
    ).json()["record"]

    edit_url = f"{person_url}/sizes/{saved['id']}/edit"
    edit_page = client.get(edit_url)
    assert edit_page.status_code == 200
    assert "Correct this size" in edit_page.text
    assert "Delete size" in edit_page.text

    changed = client.post(
        edit_url,
        data={
            "item": "T-shirt",
            "size": "95",
            "system": "Japan",
            "brand": "Uniqlo",
            "model": "",
            "fit_notes": "Fits well",
            "notes": "",
            "measured_on": "",
        },
        follow_redirects=False,
    )
    assert changed.status_code == 303
    detail = client.get(person_url)
    assert "95" in detail.text
    assert "Uniqlo" in detail.text
    assert "Fits well" in detail.text
    assert "Wrong note" not in detail.text

    confirm = client.get(f"{person_url}/sizes/{saved['id']}/delete")
    assert confirm.status_code == 200
    assert "Delete T-shirt 95?" in confirm.text

    deleted = client.post(
        f"{person_url}/sizes/{saved['id']}/delete", follow_redirects=False
    )
    assert deleted.status_code == 303
    assert client.get(person_url).status_code == 200
    assert client.get(f"/api/people/{person['id']}/sizes").json() == []


def test_person_delete_has_confirmation_page_and_removes_person(client, create_person):
    person = create_person("Mistake")
    client.post(
        "/api/sizes",
        json={"person_id": person["id"], "item": "Shoes", "size": "10"},
    )

    confirm = client.get(f"/people/{person['id']}/delete")
    assert confirm.status_code == 200
    assert "Delete Mistake?" in confirm.text
    assert "1 saved size record" in confirm.text

    deleted = client.post(
        f"/people/{person['id']}/delete", follow_redirects=False
    )
    assert deleted.status_code == 303
    assert client.get(f"/api/people/{person['id']}").status_code == 404


def test_web_lookup_requires_confirmation_before_aliasing(client, create_person):
    person = create_person("Alexandra")

    result = client.get("/find", params={"name": "Alex"})
    assert result.status_code == 200
    assert "Who did you mean?" in result.text
    assert "Yes, use this person" in result.text

    unchanged = client.get(f"/api/people/{person['id']}").json()
    assert unchanged["aliases"] == []
