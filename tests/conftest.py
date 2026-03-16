"""Shared test fixtures for dreamhubcli."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from dreamhubcli.config import DreamhubConfig, save_config


@pytest.fixture()
def temp_config_dir(tmp_path: Path) -> Path:
    """Redirect config storage to a temp directory."""
    config_dir = tmp_path / ".dreamhub"
    config_dir.mkdir()
    with (
        patch("dreamhubcli.config.CONFIG_DIR", config_dir),
        patch("dreamhubcli.config.CONFIG_FILE", config_dir / "config.toml"),
    ):
        yield config_dir


@pytest.fixture()
def authenticated_config(temp_config_dir: Path) -> DreamhubConfig:
    """Set up a config with a valid token and tenant ID."""
    config = DreamhubConfig(
        token="pat_test_token_12345678",
        tenant_id="test-tenant-id",
        api_url="https://crm.dreamhub.ai/api/v1",
    )
    save_config(config)
    return config
