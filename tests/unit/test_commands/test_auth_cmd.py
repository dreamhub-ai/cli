"""Tests for dh auth commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import respx
import typer
from typer.testing import CliRunner

from dreamhubcli.config import DreamhubConfig, load_config, save_config
from dreamhubcli.main import app

runner = CliRunner()

API_URL = "https://crm.dreamhub.ai/api/v1"


class TestAuthLogin:
    def test_login_with_token(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["auth", "login", "--token", "pat_abc123"])
        assert result.exit_code == 0
        assert "Logged in" in result.output
        config = load_config()
        assert config.token == "pat_abc123"

    def test_login_with_token_and_tenant(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["auth", "login", "--token", "pat_abc123", "--tenant-id", "t-1"])
        assert result.exit_code == 0
        config = load_config()
        assert config.token == "pat_abc123"
        assert config.tenant_id == "t-1"

    def test_login_browser_flow_success(self, temp_config_dir: Path) -> None:
        with patch(
            "dreamhubcli.auth_callback.run_browser_flow",
            return_value=("fake_access_token", "fake_tenant"),
        ):
            result = runner.invoke(app, ["auth", "login"])
        assert result.exit_code == 0
        assert "Logged in successfully" in result.output
        config = load_config()
        assert config.token == "fake_access_token"
        assert config.tenant_id == "fake_tenant"

    def test_login_browser_flow_failure(self, temp_config_dir: Path) -> None:
        with patch(
            "dreamhubcli.auth_callback.run_browser_flow",
            side_effect=typer.Exit(code=1),
        ):
            result = runner.invoke(app, ["auth", "login"])
        assert result.exit_code == 1


class TestAuthStatus:
    @respx.mock
    def test_status_logged_in(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_longtoken12345678", tenant_id="t-1"))
        respx.get(f"{API_URL}/me").mock(
            return_value=httpx.Response(200, json={"email": "user@acme.com", "tenantName": "Acme"})
        )
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "user@acme.com" in result.output
        assert "Acme" in result.output
        assert "Authenticated" in result.output

    @respx.mock
    def test_status_token_expired(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_expired", tenant_id="t-1"))
        respx.get(f"{API_URL}/me").mock(return_value=httpx.Response(401, json={"message": "Unauthorized"}))
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 1
        assert "Token expired" in result.output
        # Token should be auto-cleared
        config = load_config()
        assert config.token is None

    def test_status_not_logged_in(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 1
        assert "Not logged in" in result.output

    @respx.mock
    def test_status_network_error(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.get(f"{API_URL}/me").mock(side_effect=httpx.ConnectError("connection refused"))
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 1
        assert "Cannot connect" in result.output


class TestAuthLogout:
    def test_logout_clears_credentials(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_abc", tenant_id="t-1"))
        result = runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0
        assert "Logged out" in result.output
        config = load_config()
        assert config.token is None
        assert config.tenant_id is None



