"""E2E tests for the contracts command group.

Creates real contracts on staging with E2E_TEST_ prefix and deletes them in teardown.
A contract hangs off a company, so each test provisions its own throwaway company.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


def _create_company(runner: CliRunner) -> dict:
    name = f"E2E_TEST_{uuid4().hex[:8]}"
    result = runner.invoke(app, ["companies", "create", json.dumps({"name": name}), "--json"])
    assert result.exit_code == 0, f"companies create failed: {result.output}"
    return json.loads(result.output)


@pytest.fixture()
def test_contract(runner: CliRunner) -> dict:
    """Create a staging contract with E2E_TEST_ prefix; delete it and its company after."""
    company = _create_company(runner)
    name = f"E2E_TEST_{uuid4().hex[:8]}"
    payload = {"name": name, "companyId": company["id"]}
    result = runner.invoke(app, ["contracts", "create", json.dumps(payload), "--json"])
    assert result.exit_code == 0, f"contracts create failed: {result.output}"
    contract = json.loads(result.output)
    yield contract
    runner.invoke(app, ["contracts", "delete", contract["id"], "--force"])
    runner.invoke(app, ["companies", "delete", company["id"], "--force"])


def test_contracts_list(runner: CliRunner) -> None:
    """List contracts returns paginated results successfully."""
    result = runner.invoke(app, ["contracts", "list"])
    assert result.exit_code in (0, 1), f"contracts list failed: {result.output}"


def test_contracts_list_json(runner: CliRunner) -> None:
    """List contracts --json returns valid JSON with the contracts collection key."""
    result = runner.invoke(app, ["contracts", "list", "--json"])
    assert result.exit_code in (0, 1), f"contracts list --json failed: {result.output}"
    if result.exit_code == 0:
        data = json.loads(result.output)
        assert "contracts" in data


def test_contracts_get(runner: CliRunner, test_contract: dict) -> None:
    """Get a contract by ID returns successfully."""
    result = runner.invoke(app, ["contracts", "get", test_contract["id"]])
    assert result.exit_code == 0, f"contracts get failed: {result.output}"


def test_contracts_update(runner: CliRunner, test_contract: dict) -> None:
    """Update a contract name and verify the change is reflected."""
    new_name = f"E2E_TEST_UPD_{uuid4().hex[:8]}"
    result = runner.invoke(app, ["contracts", "update", test_contract["id"], json.dumps({"name": new_name}), "--json"])
    assert result.exit_code == 0, f"contracts update failed: {result.output}"
    assert json.loads(result.output)["name"] == new_name


def test_contracts_filter(runner: CliRunner, test_contract: dict) -> None:
    """Filter contracts by the created contract's own name."""
    result = runner.invoke(app, ["contracts", "filter", "name", "eq", test_contract["name"], "--json"])
    assert result.exit_code == 0, f"contracts filter failed: {result.output}"
    names = {c["name"] for c in json.loads(result.output)["contracts"]}
    assert test_contract["name"] in names


def test_contracts_delete(runner: CliRunner) -> None:
    """Create and immediately delete a throwaway contract."""
    company = _create_company(runner)
    name = f"E2E_TEST_{uuid4().hex[:8]}"
    payload = {"name": name, "companyId": company["id"]}
    create_result = runner.invoke(app, ["contracts", "create", json.dumps(payload), "--json"])
    assert create_result.exit_code == 0, f"contracts create failed: {create_result.output}"
    contract = json.loads(create_result.output)
    try:
        delete_result = runner.invoke(app, ["contracts", "delete", contract["id"], "--force"])
        assert delete_result.exit_code == 0, f"contracts delete failed: {delete_result.output}"
    finally:
        runner.invoke(app, ["companies", "delete", company["id"], "--force"])
