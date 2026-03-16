"""E2E test configuration and shared fixtures.

E2E tests require staging credentials via environment variables:
  DH_E2E_TOKEN     — Personal Access Token for the staging API
  DH_E2E_TENANT_ID — Tenant ID for the x-tenant-id header
  DH_E2E_API_URL   — (optional) Override the API base URL

Run with:
  DH_E2E_TOKEN=xxx DH_E2E_TENANT_ID=yyy poetry run pytest -m e2e -v
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
import tomli_w
from typer.testing import CliRunner

from dreamhubcli.config import DEFAULT_API_URL, DreamhubConfig


def pytest_configure(config: pytest.Config) -> None:
    """Register the e2e marker to avoid PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "e2e: end-to-end tests against the staging API (requires DH_E2E_TOKEN and DH_E2E_TENANT_ID)",
    )


@pytest.fixture(scope="session")
def e2e_credentials() -> tuple[str, str | None]:
    """Read staging credentials from environment variables.

    Skips the entire E2E suite if DH_E2E_TOKEN is not set.

    Returns:
        (token, tenant_id) tuple — tenant_id may be None if not provided.
    """
    token = os.environ.get("DH_E2E_TOKEN")
    if not token:
        pytest.skip(
            "DH_E2E_TOKEN is not set -- skipping E2E suite. "
            "Set DH_E2E_TOKEN and DH_E2E_TENANT_ID to run against staging."
        )
    tenant_id = os.environ.get("DH_E2E_TENANT_ID")
    return token, tenant_id


@pytest.fixture(scope="session", autouse=True)
def e2e_config(tmp_path_factory: pytest.TempPathFactory, e2e_credentials: tuple[str, str | None]) -> None:
    """Set up an isolated config file pointing to staging credentials.

    Creates a temp config dir, writes a config.toml with the staging
    credentials, and patches CONFIG_DIR / CONFIG_FILE for the whole session.

    Supports optional DH_E2E_API_URL env var to override the API base URL.
    """
    token, tenant_id = e2e_credentials
    api_url = os.environ.get("DH_E2E_API_URL", DEFAULT_API_URL)

    config_dir = tmp_path_factory.mktemp("e2e_config")
    config_file = config_dir / "config.toml"

    cfg = DreamhubConfig(token=token, tenant_id=tenant_id, api_url=api_url)
    with open(config_file, "wb") as f:
        tomli_w.dump(cfg.model_dump(exclude_none=True), f)

    with (
        patch("dreamhubcli.config.CONFIG_DIR", config_dir),
        patch("dreamhubcli.config.CONFIG_FILE", config_file),
    ):
        yield


@pytest.fixture(scope="session")
def runner() -> CliRunner:
    """Return a CliRunner with stderr separated from stdout."""
    return CliRunner(mix_stderr=False)
