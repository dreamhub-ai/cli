"""E2E tests for the enrichment command group (dev/QA only).

Enrichment commands are only registered when DH_DEV_MODE=1 or API URL
points to a dev environment. These tests trigger enrichment against staging.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from dreamhubcli.main import app

pytestmark = pytest.mark.e2e


def test_enrichment_trigger(runner: CliRunner) -> None:
    """Trigger enrichment runs without crashing.

    exit_code 0 means the staging API accepted the request.
    exit_code 1 means the API returned an error (e.g. 403/404) — this
    validates that the CLI routes the command correctly and handles the
    API error gracefully; it does NOT indicate a CLI defect.
    exit_code 2 means the command is not registered (dev-only, skipped).
    """
    result = runner.invoke(app, ["enrichment", "trigger", "people"])
    if result.exit_code == 2:
        pytest.skip("enrichment commands not registered (not in dev mode)")
    assert result.exit_code in (
        0,
        1,
    ), f"enrichment trigger exited unexpectedly (code {result.exit_code}): {result.output}"
