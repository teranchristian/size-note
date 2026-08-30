def test_web_copy_routes_identity_phrases_to_aliases(client, create_person):
    person = create_person("Riley", aliases=["my son"], notes="Prefers soft fabrics")
    person_url = f"/people/{person['id']}"

    detail = client.get(person_url)
    assert detail.status_code == 200
    assert "Add preferences or other person-level context." not in detail.text
    assert "Prefers soft fabrics" in detail.text
    assert "my son" in detail.text

    edit = client.get(f"{person_url}/edit")
    assert edit.status_code == 200
    assert "Use aliases below for names or phrases that identify this person" in edit.text
    assert "Preferences or other person-level context" in edit.text

    new_person = client.get("/people/new")
    assert new_person.status_code == 200
    assert "Alternative names or identifying phrases for this person" in new_person.text
    assert "Use notes for facts about the person" in new_person.text
