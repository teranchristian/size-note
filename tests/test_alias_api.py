def test_internal_alias_routes_support_cli_management(client, create_person):
    person = create_person("Riley", aliases=["my kid"])
    base_url = f"/api/people/{person['id']}/aliases"

    aliases = client.get(base_url)
    assert aliases.status_code == 200
    assert len(aliases.json()) == 1
    alias_id = aliases.json()[0]["id"]
    assert aliases.json()[0]["alias"] == "my kid"

    renamed = client.patch(f"{base_url}/{alias_id}", json={"alias": "my son"})
    assert renamed.status_code == 200
    assert renamed.json()["aliases"] == ["my son"]

    removed = client.delete(f"{base_url}/{alias_id}")
    assert removed.status_code == 200
    assert removed.json()["aliases"] == []

    assert client.get(base_url).json() == []
