"""Tests for dreamhubcli.auth module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from dreamhubcli.auth import (
    get_auth_headers,
    is_authenticated,
    login_with_browser,
    login_with_token,
    logout,
)
from dreamhubcli.config import DreamhubConfig, load_config, save_config


class TestLoginWithToken:
    def test_stores_token(self, temp_config_dir: Path) -> None:
        config = login_with_token("pat_abc123")
        assert config.token == "pat_abc123"

    def test_stores_token_and_tenant(self, temp_config_dir: Path) -> None:
        config = login_with_token("pat_abc123", tenant_id="tenant-xyz")
        assert config.token == "pat_abc123"
        assert config.tenant_id == "tenant-xyz"

    def test_preserves_existing_tenant_when_not_provided(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="old", tenant_id="existing-tenant"))
        config = login_with_token("new_token")
        assert config.token == "new_token"
        assert config.tenant_id == "existing-tenant"


class TestLogout:
    def test_clears_credentials(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_abc", tenant_id="t-1"))
        config = logout()
        assert config.token is None
        assert config.tenant_id is None


class TestGetAuthHeaders:
    def test_returns_empty_when_not_authenticated(self, temp_config_dir: Path) -> None:
        headers = get_auth_headers()
        assert headers == {}

    def test_returns_bearer_token(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        headers = get_auth_headers()
        assert headers["Authorization"] == "Bearer pat_test"

    def test_returns_tenant_header(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="my-tenant"))
        headers = get_auth_headers()
        assert headers["x-tenant-id"] == "my-tenant"

    def test_omits_tenant_when_not_set(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        headers = get_auth_headers()
        assert "x-tenant-id" not in headers


class TestIsAuthenticated:
    def test_false_when_no_token(self, temp_config_dir: Path) -> None:
        assert is_authenticated() is False

    def test_true_when_token_exists(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        assert is_authenticated() is True


class TestLoginWithBrowser:
    def test_calls_run_browser_flow(self, temp_config_dir: Path) -> None:
        with patch("dreamhubcli.auth_callback.run_browser_flow", return_value=("access_tok", "tenant-1")):
            login_with_browser()

    def test_saves_token(self, temp_config_dir: Path) -> None:
        with patch("dreamhubcli.auth_callback.run_browser_flow", return_value=("browser_token_123", None)):
            login_with_browser()
        config = load_config()
        assert config.token == "browser_token_123"

    def test_saves_tenant(self, temp_config_dir: Path) -> None:
        with patch("dreamhubcli.auth_callback.run_browser_flow", return_value=("tok", "tenant-abc")):
            login_with_browser()
        config = load_config()
        assert config.tenant_id == "tenant-abc"

    def test_propagates_exit(self, temp_config_dir: Path) -> None:
        with (
            patch("dreamhubcli.auth_callback.run_browser_flow", side_effect=typer.Exit(code=1)),
            pytest.raises(typer.Exit) as exc_info,
        ):
            login_with_browser()
        assert exc_info.value.exit_code == 1
        config = load_config()
        assert config.token is None
