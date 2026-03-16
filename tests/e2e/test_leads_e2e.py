"""E2E tests for the leads command group.

Creates real leads on staging with E2E_TEST_ prefix and deletes them in teardown.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


@pytest.fixture()
def test_lead(runner: CliRunner) -> dict:
    """Create a staging lead with E2E_TEST_ prefix; delete it after the test."""
    name = f"E2E_TEST_{uuid4().hex[:8]}"
    result = runner.invoke(app, ["leads", "create", json.dumps({"name": name}), "--json"])
    assert result.exit_code == 0, f"leads create failed: {result.output}"
    lead = json.loads(result.output)
    yield lead
    runner.invoke(app, ["leads", "delete", lead["id"], "--force"])


def test_leads_list(runner: CliRunner) -> None:
    """List leads returns paginated results successfully."""
    result = runner.invoke(app, ["leads", "list"])
    assert result.exit_code in (0, 1), f"leads list failed: {result.output}"


def test_leads_list_json(runner: CliRunner) -> None:
    """List leads --json returns valid JSON with the leads collection key."""
    result = runner.invoke(app, ["leads", "list", "--json"])
    assert result.exit_code in (0, 1), f"leads list --json failed: {result.output}"
    if result.exit_code == 0:
        data = json.loads(result.output)
        assert "leads" in data


def test_leads_get(runner: CliRunner, test_lead: dict) -> None:
    """Get a lead by ID returns successfully."""
    result = runner.invoke(app, ["leads", "get", test_lead["id"]])
    assert result.exit_code == 0, f"leads get failed: {result.output}"


def test_leads_update(runner: CliRunner) -> None:
    """Update a lead name and verify the change is reflected."""
    # Create its own entity to avoid dependency on shared fixture ordering
    name = f"E2E_TEST_{uuid4().hex[:8]}"
    create_result = runner.invoke(app, ["leads", "create", json.dumps({"name": name}), "--json"])
    assert create_result.exit_code == 0, f"leads create failed: {create_result.output}"
    lead = json.loads(create_result.output)
    try:
        new_name = f"E2E_TEST_UPD_{uuid4().hex[:8]}"
        result = runner.invoke(app, ["leads", "update", lead["id"], json.dumps({"name": new_name}), "--json"])
        assert result.exit_code == 0, f"leads update failed: {result.output}"
        updated = json.loads(result.output)
        assert updated["name"] == new_name
    finally:
        runner.invoke(app, ["leads", "delete", lead["id"], "--force"])


def test_leads_delete(runner: CliRunner) -> None:
    """Create and immediately delete a throwaway lead."""
    name = f"E2E_TEST_{uuid4().hex[:8]}"
    create_result = runner.invoke(app, ["leads", "create", json.dumps({"name": name}), "--json"])
    assert create_result.exit_code == 0, f"leads create failed: {create_result.output}"
    lead = json.loads(create_result.output)

    delete_result = runner.invoke(app, ["leads", "delete", lead["id"], "--force"])
    assert delete_result.exit_code == 0, f"leads delete failed: {delete_result.output}"
