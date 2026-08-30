def test_web_can_create_child_from_birth_year_without_stage(client):
    created = client.post(
        "/people",
        data={
            "name": "Haru",
            "growth_stage": "",
            "birth": "2024",
            "aliases": "",
            "notes": "My son",
        },
        follow_redirects=False,
    )

    assert created.status_code == 303
    person_url = created.headers["location"]
    stored = client.get(f"/api{person_url}").json() if person_url.startswith("/people/") else None
    if stored is None:
        person_id = person_url.rsplit("/", 1)[-1]
        stored = client.get(f"/api/people/{person_id}").json()
    assert stored["growth_stage"] == "child"
    assert stored["birth_year"] == 2024
    assert stored["birth_month"] is None

    detail = client.get(person_url)
    assert "Born 2024" in detail.text


def test_web_requires_stage_when_birth_is_missing(client):
    response = client.post(
        "/people",
        data={
            "name": "Morgan",
            "growth_stage": "",
            "birth": "",
            "aliases": "",
            "notes": "",
        },
    )

    assert response.status_code == 400
    assert "Choose child or adult" in response.text


def test_web_can_refine_partial_birth_information(client, create_person):
    person = create_person("Haru", growth_stage="child", birth_year=2024)
    edit_url = f"/people/{person['id']}/edit"

    page = client.get(edit_url)
    assert page.status_code == 200
    assert 'value="2024"' in page.text

    changed = client.post(
        edit_url,
        data={
            "name": "Haru",
            "growth_stage": "child",
            "birth": "2024-05",
            "notes": "My son",
        },
        follow_redirects=False,
    )

    assert changed.status_code == 303
    stored = client.get(f"/api/people/{person['id']}").json()
    assert stored["birth_year"] == 2024
    assert stored["birth_month"] == 5
    assert stored["birth_day"] is None
