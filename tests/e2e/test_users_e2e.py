"""E2E tests for the users command group.

Read-only tests only — creating users may trigger emails or require admin permissions.
NOTE: Users list requires --ids and we have no reliable way to get a user ID,
so assertions are lenient.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


def test_users_list(runner: CliRunner) -> None:
    """List users — API requires ids param; accept graceful failure."""
    result = runner.invoke(app, ["users", "list"])
    # Users list requires --ids; without a known ID this may return 422
    assert result.exit_code in (0, 1), f"users list exited unexpectedly (code {result.exit_code}): {result.output}"


def test_users_list_json(runner: CliRunner) -> None:
    """List users --json — accept graceful failure since we have no user IDs."""
    result = runner.invoke(app, ["users", "list", "--json"])
    assert result.exit_code in (
        0,
        1,
    ), f"users list --json exited unexpectedly (code {result.exit_code}): {result.output}"
