"""E2E tests for the activities command group.

Creates activities on a staging deal with E2E_TEST_ prefix and cleans up after.
Activities are sub-resources — they need a parent entity to attach to.
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
    """Create a staging deal to attach activities to; delete after test."""
    name = f"E2E_TEST_ACT_{uuid4().hex[:8]}"
    result = runner.invoke(app, ["deals", "create", json.dumps({"name": name}), "--json"])
    assert result.exit_code == 0, f"deals create failed: {result.output}"
    deal = json.loads(result.output)
    yield deal
    runner.invoke(app, ["deals", "delete", deal["id"], "--force"])


def test_activities_list(runner: CliRunner, test_deal: dict) -> None:
    """List activities for a deal returns successfully."""
    result = runner.invoke(app, ["activities", "list", "deals", test_deal["id"]])
    assert result.exit_code == 0, f"activities list failed: {result.output}"


def test_activities_list_json(runner: CliRunner, test_deal: dict) -> None:
    """List activities --json returns valid JSON with activities key."""
    result = runner.invoke(app, ["activities", "list", "deals", test_deal["id"], "--json"])
    assert result.exit_code == 0, f"activities list --json failed: {result.output}"
    data = json.loads(result.output)
    assert "activities" in data
    assert "total" in data


def test_activities_list_with_type_filter(runner: CliRunner, test_deal: dict) -> None:
    """List activities filtered by type returns successfully."""
    result = runner.invoke(app, ["activities", "list", "deals", test_deal["id"], "--type", "note"])
    assert result.exit_code == 0, f"activities list --type note failed: {result.output}"


def test_activities_create_and_delete(runner: CliRunner, test_deal: dict) -> None:
    """Create a note activity and delete it."""
    notes = json.dumps({"date": "2026-03-16T10:00:00Z", "summary": "E2E test note"})
    create_result = runner.invoke(
        app,
        ["activities", "create", "deals", test_deal["id"], "note", notes, "--json"],
    )
    assert create_result.exit_code == 0, f"activities create failed: {create_result.output}"
    activity = json.loads(create_result.output)
    activity_id = activity.get("id")
    assert activity_id, f"No activity ID in response: {activity}"

    delete_result = runner.invoke(app, ["activities", "delete", "deals", test_deal["id"], activity_id, "--force"])
    assert delete_result.exit_code == 0, f"activities delete failed: {delete_result.output}"


def test_activities_create_and_update(runner: CliRunner, test_deal: dict) -> None:
    """Create a note activity, update it, verify the update."""
    notes = json.dumps({"date": "2026-03-16T10:00:00Z", "summary": "Original note"})
    create_result = runner.invoke(
        app,
        ["activities", "create", "deals", test_deal["id"], "note", notes, "--json"],
    )
    assert create_result.exit_code == 0, f"activities create failed: {create_result.output}"
    activity = json.loads(create_result.output)
    activity_id = activity.get("id")

    try:
        update_payload = json.dumps({"notes": {"date": "2026-03-16T10:00:00Z", "summary": "Updated note"}})
        update_result = runner.invoke(
            app,
            ["activities", "update", "deals", test_deal["id"], activity_id, update_payload, "--json"],
        )
        assert update_result.exit_code == 0, f"activities update failed: {update_result.output}"
    finally:
        runner.invoke(app, ["activities", "delete", "deals", test_deal["id"], activity_id, "--force"])


def test_activities_types(runner: CliRunner) -> None:
    """List activity types shows all expected types."""
    result = runner.invoke(app, ["activities", "types"])
    assert result.exit_code == 0
    assert "Call" in result.output
    assert "Email" in result.output
    assert "Note" in result.output
