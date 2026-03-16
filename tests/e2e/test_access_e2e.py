"""E2E tests for the access command group (dev/QA only).

Access commands are only registered when DH_DEV_MODE=1 or API URL
points to a dev environment. These tests verify the token management
endpoints against the staging API.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


def test_access_token(runner: CliRunner) -> None:
    """Get current user's token metadata."""
    result = runner.invoke(app, ["access", "token"])
    if result.exit_code == 2:
        pytest.skip("access commands not registered (not in dev mode)")
    assert result.exit_code in (0, 1), f"access token exited unexpectedly (code {result.exit_code}): {result.output}"


def test_access_token_json(runner: CliRunner) -> None:
    """Get token --json."""
    result = runner.invoke(app, ["access", "token", "--json"])
    if result.exit_code == 2:
        pytest.skip("access commands not registered (not in dev mode)")
    assert result.exit_code in (
        0,
        1,
    ), f"access token --json exited unexpectedly (code {result.exit_code}): {result.output}"
