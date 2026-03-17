"""Tests for dreamhubcli.auth module."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx
import typer

from dreamhubcli.auth import (
    _decode_jwt_exp,
    get_auth_headers,
    is_authenticated,
    is_token_expired,
    login_with_browser,
    login_with_token,
    logout,
    refresh_access_token,
)
from dreamhubcli.config import DreamhubConfig, load_config, save_config


def _make_jwt(payload: dict) -> str:
    """Build a fake unsigned JWT with the given payload."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.sig"


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

    def test_clears_refresh_token_when_not_provided(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="old", refresh_token="old_refresh"))
        config = login_with_token("pat_new")
        assert config.token == "pat_new"
        assert config.refresh_token is None


class TestLogout:
    def test_clears_credentials(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_abc", refresh_token="refresh_abc", tenant_id="t-1"))
        config = logout()
        assert config.token is None
        assert config.refresh_token is None
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
        with patch(
            "dreamhubcli.auth_callback.run_browser_flow", return_value=("access_tok", "refresh_tok", "tenant-1")
        ):
            login_with_browser()

    def test_saves_token(self, temp_config_dir: Path) -> None:
        with patch("dreamhubcli.auth_callback.run_browser_flow", return_value=("browser_token_123", None, None)):
            login_with_browser()
        config = load_config()
        assert config.token == "browser_token_123"

    def test_saves_tenant(self, temp_config_dir: Path) -> None:
        with patch("dreamhubcli.auth_callback.run_browser_flow", return_value=("tok", None, "tenant-abc")):
            login_with_browser()
        config = load_config()
        assert config.tenant_id == "tenant-abc"

    def test_saves_refresh_token(self, temp_config_dir: Path) -> None:
        with patch("dreamhubcli.auth_callback.run_browser_flow", return_value=("tok", "refresh_xyz", "tenant-abc")):
            login_with_browser()
        config = load_config()
        assert config.refresh_token == "refresh_xyz"

    def test_propagates_exit(self, temp_config_dir: Path) -> None:
        with (
            patch("dreamhubcli.auth_callback.run_browser_flow", side_effect=typer.Exit(code=1)),
            pytest.raises(typer.Exit) as exc_info,
        ):
            login_with_browser()
        assert exc_info.value.exit_code == 1
        config = load_config()
        assert config.token is None


class TestTokenExpiry:
    def test_decode_jwt_exp(self) -> None:
        token = _make_jwt({"exp": 1700000000, "sub": "user1"})
        assert _decode_jwt_exp(token) == 1700000000

    def test_decode_jwt_exp_missing(self) -> None:
        token = _make_jwt({"sub": "user1"})
        assert _decode_jwt_exp(token) is None

    def test_decode_jwt_exp_invalid_token(self) -> None:
        assert _decode_jwt_exp("not-a-jwt") is None

    def test_is_token_expired_true(self) -> None:
        token = _make_jwt({"exp": int(time.time()) - 60})
        assert is_token_expired(token) is True

    def test_is_token_expired_false(self) -> None:
        token = _make_jwt({"exp": int(time.time()) + 300})
        assert is_token_expired(token) is False

    def test_is_token_expired_within_buffer(self) -> None:
        token = _make_jwt({"exp": int(time.time()) + 10})
        assert is_token_expired(token) is True

    def test_is_token_expired_no_exp_returns_false(self) -> None:
        token = _make_jwt({"sub": "user1"})
        assert is_token_expired(token) is False

    def test_pat_token_not_expired(self) -> None:
        assert is_token_expired("pat_abc123") is False


class TestRefreshAccessToken:
    @respx.mock
    def test_refresh_success(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="old_token", refresh_token="refresh_abc", tenant_id="t-1"))
        respx.post(url__regex=r".*/oauth/token$").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "new_token", "refresh_token": "new_refresh"},
            )
        )
        assert refresh_access_token() is True
        config = load_config()
        assert config.token == "new_token"
        assert config.refresh_token == "new_refresh"

    @respx.mock
    def test_refresh_updates_only_access_token_when_no_new_refresh(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="old_token", refresh_token="refresh_abc", tenant_id="t-1"))
        respx.post(url__regex=r".*/oauth/token$").mock(
            return_value=httpx.Response(200, json={"access_token": "new_token"})
        )
        assert refresh_access_token() is True
        config = load_config()
        assert config.token == "new_token"
        assert config.refresh_token == "refresh_abc"

    def test_refresh_no_refresh_token(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_token"))
        assert refresh_access_token() is False

    @respx.mock
    def test_refresh_api_failure(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="old_token", refresh_token="refresh_abc"))
        respx.post(url__regex=r".*/oauth/token$").mock(return_value=httpx.Response(401, text="invalid"))
        assert refresh_access_token() is False
        config = load_config()
        assert config.token == "old_token"

    @respx.mock
    def test_refresh_network_error(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="old_token", refresh_token="refresh_abc"))
        respx.post(url__regex=r".*/oauth/token$").mock(side_effect=httpx.ConnectError("fail"))
        assert refresh_access_token() is False
        config = load_config()
        assert config.token == "old_token"
