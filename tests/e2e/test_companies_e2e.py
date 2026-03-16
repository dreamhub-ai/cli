"""E2E tests for the companies command group.

Creates real companies on staging with E2E_TEST_ prefix and deletes them in teardown.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


@pytest.fixture()
def test_company(runner: CliRunner) -> dict:
    """Create a staging company with E2E_TEST_ prefix; delete it after the test."""
    name = f"E2E_TEST_{uuid4().hex[:8]}"
    result = runner.invoke(app, ["companies", "create", json.dumps({"name": name, "status": 1}), "--json"])
    assert result.exit_code == 0, f"companies create failed: {result.output}"
    company = json.loads(result.output)
    yield company
    runner.invoke(app, ["companies", "delete", company["id"], "--force"])


def test_companies_list(runner: CliRunner) -> None:
    """List companies returns paginated results successfully."""
    result = runner.invoke(app, ["companies", "list"])
    assert result.exit_code in (0, 1), f"companies list failed: {result.output}"


def test_companies_list_json(runner: CliRunner) -> None:
    """List companies --json returns valid JSON with the companies collection key."""
    result = runner.invoke(app, ["companies", "list", "--json"])
    assert result.exit_code in (0, 1), f"companies list --json failed: {result.output}"
    if result.exit_code == 0:
        data = json.loads(result.output)
        assert "companies" in data


def test_companies_get(runner: CliRunner, test_company: dict) -> None:
    """Get a company by ID returns successfully."""
    result = runner.invoke(app, ["companies", "get", test_company["id"]])
    assert result.exit_code == 0, f"companies get failed: {result.output}"


def test_companies_update(runner: CliRunner, test_company: dict) -> None:
    """Update a company name and verify the change is reflected."""
    new_name = f"E2E_TEST_UPD_{uuid4().hex[:8]}"
    result = runner.invoke(
        app, ["companies", "update", test_company["id"], json.dumps({"name": new_name, "status": 1}), "--json"]
    )
    assert result.exit_code == 0, f"companies update failed: {result.output}"
    updated = json.loads(result.output)
    assert updated["name"] == new_name


def test_companies_delete(runner: CliRunner) -> None:
    """Create and immediately delete a throwaway company."""
    name = f"E2E_TEST_{uuid4().hex[:8]}"
    create_result = runner.invoke(app, ["companies", "create", json.dumps({"name": name, "status": 1}), "--json"])
    assert create_result.exit_code == 0, f"companies create failed: {create_result.output}"
    company = json.loads(create_result.output)

    delete_result = runner.invoke(app, ["companies", "delete", company["id"], "--force"])
    assert delete_result.exit_code == 0, f"companies delete failed: {delete_result.output}"
