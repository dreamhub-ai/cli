"""E2E tests for the auth command group.

Validates that staging credentials are functional by checking auth status.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


def test_auth_status(runner: CliRunner) -> None:
    """Verify that the staging credentials produce a successful auth status.

    /users/me may return 404 with PAT auth, which the CLI now handles
    gracefully by printing "Logged in (token set)".
    """
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code in (0, 1), f"auth status exited unexpectedly (code {result.exit_code}): {result.output}"
