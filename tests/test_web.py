import re


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
            "equivalents": "JP: L",
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
    assert "L JP" in updated_detail.text
    assert "A little loose" in updated_detail.text
    assert "Bought in Tokyo" in updated_detail.text
    assert "Edit" in updated_detail.text


def test_web_groups_multiple_shoe_systems_on_one_card(client, create_person):
    person = create_person("Christian")
    person_url = f"/people/{person['id']}"

    saved = client.post(
        f"{person_url}/sizes",
        data={
            "item": "Shoes",
            "size": "25.25",
            "system": "CM",
            "equivalents": "EU: 40\nUS: 7",
            "brand": "ASICS",
            "model": "1011B004",
            "fit_notes": "Fits well",
            "notes": "",
            "measured_on": "",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303

    detail = client.get(person_url)
    assert detail.status_code == 200
    assert "25.25" in detail.text
    assert "40 EU" in detail.text
    assert "7 US" in detail.text
    assert "ASICS" in detail.text
    assert "1011B004" in detail.text

    records = client.get(
        f"/api/people/{person['id']}/sizes", params={"history": "false"}
    ).json()
    assert len(records) == 1
    assert records[0]["equivalents"] == [
        {"size": "40", "system": "EU"},
        {"size": "7", "system": "US"},
    ]


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
    assert "Save person" in page.text

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


def test_aliases_are_visible_editable_and_removable_from_web(client, create_person):
    person = create_person("Christian", aliases=["me"])
    person_url = f"/people/{person['id']}"
    edit_url = f"{person_url}/edit"

    detail = client.get(person_url)
    assert detail.status_code == 200
    assert '<span class="alias-chip">me</span>' in detail.text
    assert "Alternative names or phrases" in detail.text
    assert "Add alias" not in detail.text
    assert ">Manage<" not in detail.text
    assert "Also known as" not in detail.text
    assert "nickname" not in detail.text.lower()

    edit = client.get(edit_url)
    assert edit.status_code == 200
    assert 'value="me"' in edit.text
    assert "Alternative names or phrases" in edit.text
    assert "Update alias" in edit.text
    assert "Delete alias" in edit.text
    assert "Add alias" in edit.text
    assert "Save person" in edit.text
    assert "Save changes" not in edit.text
    assert "nicknames" not in edit.text.lower()
    alias_match = re.search(r"/aliases/([^/]+)/edit", edit.text)
    assert alias_match is not None
    alias_id = alias_match.group(1)

    renamed = client.post(
        f"{person_url}/aliases/{alias_id}/edit",
        data={"alias": "myself"},
        follow_redirects=False,
    )
    assert renamed.status_code == 303
    assert renamed.headers["location"].endswith("/edit")
    assert client.get(f"/api/people/{person['id']}").json()["aliases"] == ["myself"]

    conflict = client.post(
        f"{person_url}/aliases/{alias_id}/edit",
        data={"alias": "Christian"},
    )
    assert conflict.status_code == 400
    assert "must be different from" in conflict.text

    removed = client.post(
        f"{person_url}/aliases/{alias_id}/delete",
        follow_redirects=False,
    )
    assert removed.status_code == 303
    assert client.get(f"/api/people/{person['id']}").json()["aliases"] == []

    added = client.post(
        f"{person_url}/aliases",
        data={"alias": "me", "return_to": "edit"},
        follow_redirects=False,
    )
    assert added.status_code == 303
    assert added.headers["location"].endswith("/edit")
    assert client.get(f"/api/people/{person['id']}").json()["aliases"] == ["me"]


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
            "equivalents": "US: 3T",
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
    assert "3T US" in detail.text
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
