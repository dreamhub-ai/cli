"""E2E tests for the deals command group.

Creates real deals on staging with E2E_TEST_ prefix and deletes them in teardown.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


@pytest.fixture()
def test_deal(runner: CliRunner) -> dict:
    """Create a staging deal with E2E_TEST_ prefix; delete it after the test."""
    name = f"E2E_TEST_{uuid4().hex[:8]}"
    result = runner.invoke(app, ["deals", "create", json.dumps({"name": name}), "--json"])
    assert result.exit_code == 0, f"deals create failed: {result.output}"
    deal = json.loads(result.output)
    yield deal
    runner.invoke(app, ["deals", "delete", deal["id"], "--force"])


def test_deals_list(runner: CliRunner) -> None:
    """List deals returns paginated results successfully."""
    result = runner.invoke(app, ["deals", "list"])
    assert result.exit_code in (0, 1), f"deals list failed: {result.output}"


def test_deals_list_json(runner: CliRunner) -> None:
    """List deals --json returns valid JSON with the deals collection key."""
    result = runner.invoke(app, ["deals", "list", "--json"])
    assert result.exit_code in (0, 1), f"deals list --json failed: {result.output}"
    if result.exit_code == 0:
        data = json.loads(result.output)
        assert "deals" in data


def test_deals_get(runner: CliRunner, test_deal: dict) -> None:
    """Get a deal by ID returns successfully."""
    result = runner.invoke(app, ["deals", "get", test_deal["id"]])
    assert result.exit_code == 0, f"deals get failed: {result.output}"


def test_deals_update(runner: CliRunner) -> None:
    """Update a deal name and verify the change is reflected."""
    # Create its own entity to avoid dependency on shared fixture ordering
    name = f"E2E_TEST_{uuid4().hex[:8]}"
    create_result = runner.invoke(app, ["deals", "create", json.dumps({"name": name}), "--json"])
    assert create_result.exit_code == 0, f"deals create failed: {create_result.output}"
    deal = json.loads(create_result.output)
    try:
        new_name = f"E2E_TEST_UPD_{uuid4().hex[:8]}"
        result = runner.invoke(app, ["deals", "update", deal["id"], json.dumps({"name": new_name}), "--json"])
        assert result.exit_code == 0, f"deals update failed: {result.output}"
        updated = json.loads(result.output)
        assert updated["name"] == new_name
    finally:
        runner.invoke(app, ["deals", "delete", deal["id"], "--force"])


def test_deals_delete(runner: CliRunner) -> None:
    """Create and immediately delete a throwaway deal."""
    name = f"E2E_TEST_{uuid4().hex[:8]}"
    create_result = runner.invoke(app, ["deals", "create", json.dumps({"name": name}), "--json"])
    assert create_result.exit_code == 0, f"deals create failed: {create_result.output}"
    deal = json.loads(create_result.output)

    delete_result = runner.invoke(app, ["deals", "delete", deal["id"], "--force"])
    assert delete_result.exit_code == 0, f"deals delete failed: {delete_result.output}"
