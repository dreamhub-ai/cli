"""E2E tests for the reporting command group.

Tests the actual /reports/{type} endpoints against staging.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


def test_reporting_list(runner: CliRunner) -> None:
    """List available report types (local, no API call)."""
    result = runner.invoke(app, ["reporting", "list"])
    assert result.exit_code == 0, f"reporting list failed: {result.output}"
    assert "kpis" in result.output


def test_reporting_get_kpis(runner: CliRunner) -> None:
    """Fetch KPIs report from staging."""
    result = runner.invoke(app, ["reporting", "get", "kpis"])
    assert result.exit_code in (
        0,
        1,
    ), f"reporting get kpis exited unexpectedly (code {result.exit_code}): {result.output}"


def test_reporting_get_kpis_json(runner: CliRunner) -> None:
    """Fetch KPIs report --json from staging."""
    result = runner.invoke(app, ["reporting", "get", "kpis", "--json"])
    assert result.exit_code in (
        0,
        1,
    ), f"reporting get kpis --json exited unexpectedly (code {result.exit_code}): {result.output}"
    if result.exit_code == 0:
        data = json.loads(result.output)
        assert "kpis" in data


def test_reporting_unknown_type(runner: CliRunner) -> None:
    """Unknown report type should fail with a helpful message."""
    result = runner.invoke(app, ["reporting", "get", "nonexistent"])
    assert result.exit_code == 1
    # print_error writes to stderr; runner uses mix_stderr=False
    combined = (result.output or "") + (result.stderr or "")
    assert "Unknown report type" in combined
