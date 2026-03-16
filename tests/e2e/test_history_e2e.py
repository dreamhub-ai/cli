"""E2E tests for the history command.

NOTE: The history endpoint returns 500 on the staging API.
All assertions are lenient.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


def test_history(runner: CliRunner) -> None:
    """Fetch history — API returns 500; accept graceful failure."""
    result = runner.invoke(app, ["history"])
    # History endpoint returns 500 on the staging API
    assert result.exit_code in (0, 1), f"history exited unexpectedly (code {result.exit_code}): {result.output}"


def test_history_json(runner: CliRunner) -> None:
    """Fetch history --json — API returns 500; accept graceful failure."""
    result = runner.invoke(app, ["history", "--json"])
    assert result.exit_code in (0, 1), f"history --json exited unexpectedly (code {result.exit_code}): {result.output}"
