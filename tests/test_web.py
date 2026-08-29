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

    saved = client.post(
        f"{person_url}/sizes",
        data={
            "item": "T-shirt",
            "size": "M",
            "system": "Universal",
            "brand": "",
            "model": "",
            "fit_notes": "",
            "notes": "",
            "measured_on": "",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    updated_detail = client.get(person_url)
    assert "T-shirt" in updated_detail.text
    assert "Universal" in updated_detail.text


def test_web_lookup_requires_confirmation_before_aliasing(client, create_person):
    person = create_person("Alexandra")

    result = client.get("/find", params={"name": "Alex"})
    assert result.status_code == 200
    assert "Who did you mean?" in result.text
    assert "Yes, use this person" in result.text

    unchanged = client.get(f"/api/v1/people/{person['id']}").json()
    assert unchanged["aliases"] == []
