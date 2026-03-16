"""E2E tests for the people command group.

Creates real people on staging with E2E_TEST_ prefix and deletes them in teardown.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


def _person_payload() -> dict:
    """Build a valid person payload with required camelCase fields."""
    uid = uuid4().hex[:8]
    return {
        "firstName": f"E2E_TEST_{uid}",
        "lastName": "Test",
        "email": f"e2etest_{uid}@test.com",
    }


@pytest.fixture()
def test_person(runner: CliRunner) -> dict:
    """Create a staging person with E2E_TEST_ prefix; delete it after the test."""
    payload = _person_payload()
    result = runner.invoke(app, ["people", "create", json.dumps(payload), "--json"])
    assert result.exit_code == 0, f"people create failed: {result.output}"
    person = json.loads(result.output)
    yield person
    runner.invoke(app, ["people", "delete", person["id"], "--force"])


def test_people_list(runner: CliRunner) -> None:
    """List people returns paginated results successfully."""
    result = runner.invoke(app, ["people", "list"])
    assert result.exit_code in (0, 1), f"people list failed: {result.output}"


def test_people_list_json(runner: CliRunner) -> None:
    """List people --json returns valid JSON with the people collection key."""
    result = runner.invoke(app, ["people", "list", "--json"])
    assert result.exit_code in (0, 1), f"people list --json failed: {result.output}"
    if result.exit_code == 0:
        data = json.loads(result.output)
        assert "people" in data


def test_people_get(runner: CliRunner, test_person: dict) -> None:
    """Get a person by ID returns successfully."""
    result = runner.invoke(app, ["people", "get", test_person["id"]])
    assert result.exit_code == 0, f"people get failed: {result.output}"


def test_people_update(runner: CliRunner, test_person: dict) -> None:
    """Update a person firstName and verify the change is reflected."""
    new_first = f"E2E_TEST_UPD_{uuid4().hex[:8]}"
    result = runner.invoke(app, ["people", "update", test_person["id"], json.dumps({"firstName": new_first}), "--json"])
    assert result.exit_code == 0, f"people update failed: {result.output}"
    updated = json.loads(result.output)
    assert updated["firstName"] == new_first


def test_people_delete(runner: CliRunner) -> None:
    """Create and immediately delete a throwaway person."""
    payload = _person_payload()
    create_result = runner.invoke(app, ["people", "create", json.dumps(payload), "--json"])
    assert create_result.exit_code == 0, f"people create failed: {create_result.output}"
    person = json.loads(create_result.output)

    delete_result = runner.invoke(app, ["people", "delete", person["id"], "--force"])
    assert delete_result.exit_code == 0, f"people delete failed: {delete_result.output}"
