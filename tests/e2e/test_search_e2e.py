"""E2E tests for the search command."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


def test_search_query(runner: CliRunner) -> None:
    """Search for a term across all entities."""
    result = runner.invoke(app, ["search", "test"])
    assert result.exit_code in (0, 1), f"search exited unexpectedly (code {result.exit_code}): {result.output}"


def test_search_query_json(runner: CliRunner) -> None:
    """Search with --json output."""
    result = runner.invoke(app, ["search", "test", "--json"])
    assert result.exit_code in (0, 1), f"search --json exited unexpectedly (code {result.exit_code}): {result.output}"


def test_search_with_type_filter(runner: CliRunner) -> None:
    """Search filtered to a specific entity type."""
    result = runner.invoke(app, ["search", "test", "--type", "companies"])
    assert result.exit_code in (0, 1), f"search --type exited unexpectedly (code {result.exit_code}): {result.output}"
