import json
from pathlib import Path

CONTRACT_PATH = Path(__file__).with_name("api_contract.json")
NON_CONTRACT_KEYS = {"description", "operationId", "summary", "tags", "title"}


def _without_documentation(value):
    if isinstance(value, dict):
        return {
            key: _without_documentation(item)
            for key, item in sorted(value.items())
            if key not in NON_CONTRACT_KEYS
        }
    if isinstance(value, list):
        return [_without_documentation(item) for item in value]
    return value


def test_public_api_matches_committed_contract(client):
    """Make every public API change deliberate, including unversioned route changes."""
    openapi = client.get("/openapi.json").json()
    current_contract = _without_documentation(
        {
            "paths": {
                path: definition
                for path, definition in openapi["paths"].items()
                if path == "/health" or path.startswith("/api/")
            },
            "schemas": openapi["components"]["schemas"],
        }
    )
    committed_contract = json.loads(CONTRACT_PATH.read_text())

    assert current_contract == committed_contract, (
        "The public API contract changed. If the change is intentional, review it "
        "for CLI and Hermes compatibility and update tests/api_contract.json."
    )


def test_old_versioned_routes_are_not_exposed(client):
    assert client.get("/api/v1/people").status_code == 404
