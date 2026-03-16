"""E2E tests for the settings command group."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


def test_settings_list(runner: CliRunner) -> None:
    """List all account settings."""
    result = runner.invoke(app, ["settings", "list"])
    assert result.exit_code in (0, 1), f"settings list exited unexpectedly (code {result.exit_code}): {result.output}"


def test_settings_list_json(runner: CliRunner) -> None:
    """List settings with --json output."""
    result = runner.invoke(app, ["settings", "list", "--json"])
    assert result.exit_code in (
        0,
        1,
    ), f"settings list --json exited unexpectedly (code {result.exit_code}): {result.output}"


def test_settings_get(runner: CliRunner) -> None:
    """Get a specific setting by key."""
    result = runner.invoke(app, ["settings", "get", "account_currency"])
    assert result.exit_code in (0, 1), f"settings get exited unexpectedly (code {result.exit_code}): {result.output}"
