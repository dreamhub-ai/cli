"""Tests for CLI-managed PAT fallback (auth.py + client.py integration)."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import httpx
import respx

from dreamhubcli.auth import (
    create_cli_pat,
    delete_cli_pat,
    logout,
    rotate_cli_pat_if_needed,
)
from dreamhubcli.config import DEFAULT_API_URL, DreamhubConfig, load_config, save_config


def _make_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.sig"


PAT_ENDPOINT = f"{DEFAULT_API_URL}/accessenabler/tokens/"


class TestCreateCliPat:
    @respx.mock
    def test_creates_pat_after_browser_login(self, temp_config_dir: Path) -> None:
        jwt = _make_jwt({"exp": int(time.time()) + 3600, "sub": "user1"})
        config = DreamhubConfig(token=jwt, tenant_id="t-1")
        save_config(config)

        respx.post(PAT_ENDPOINT).mock(
            return_value=httpx.Response(201, json={"id": "pat-id-1", "token": "pat_new_token"})
        )
        create_cli_pat(config)

        assert config.cli_pat == "pat_new_token"
        assert config.cli_pat_id == "pat-id-1"
        assert config.cli_pat_created_at is not None

        persisted = load_config()
        assert persisted.cli_pat == "pat_new_token"

    def test_skips_when_token_is_already_pat(self, temp_config_dir: Path) -> None:
        config = DreamhubConfig(token="pat_existing", tenant_id="t-1")
        save_config(config)
        create_cli_pat(config)
        assert config.cli_pat is None

    def test_skips_when_no_token(self, temp_config_dir: Path) -> None:
        config = DreamhubConfig()
        create_cli_pat(config)
        assert config.cli_pat is None

    @respx.mock
    def test_non_fatal_on_api_failure(self, temp_config_dir: Path) -> None:
        jwt = _make_jwt({"exp": int(time.time()) + 3600})
        config = DreamhubConfig(token=jwt, tenant_id="t-1")
        save_config(config)

        respx.post(PAT_ENDPOINT).mock(return_value=httpx.Response(500))
        create_cli_pat(config)
        assert config.cli_pat is None

    @respx.mock
    def test_non_fatal_on_network_error(self, temp_config_dir: Path) -> None:
        jwt = _make_jwt({"exp": int(time.time()) + 3600})
        config = DreamhubConfig(token=jwt, tenant_id="t-1")
        save_config(config)

        respx.post(PAT_ENDPOINT).mock(side_effect=httpx.ConnectError("fail"))
        create_cli_pat(config)
        assert config.cli_pat is None

    @respx.mock
    def test_sends_tenant_header(self, temp_config_dir: Path) -> None:
        jwt = _make_jwt({"exp": int(time.time()) + 3600})
        config = DreamhubConfig(token=jwt, tenant_id="my-tenant")
        save_config(config)

        route = respx.post(PAT_ENDPOINT).mock(return_value=httpx.Response(201, json={"id": "p1", "token": "pat_t"}))
        create_cli_pat(config)
        assert route.calls[0].request.headers["x-tenant-id"] == "my-tenant"


class TestDeleteCliPat:
    @respx.mock
    def test_deletes_pat(self, temp_config_dir: Path) -> None:
        config = DreamhubConfig(
            token="pat_current",
            tenant_id="t-1",
            cli_pat="pat_to_delete",
            cli_pat_id="pat-id-1",
            cli_pat_created_at="2026-01-01T00:00:00Z",
        )
        save_config(config)

        route = respx.delete(f"{PAT_ENDPOINT}pat-id-1").mock(return_value=httpx.Response(204))
        delete_cli_pat(config)

        assert route.called
        assert config.cli_pat is None
        assert config.cli_pat_id is None
        assert config.cli_pat_created_at is None

    def test_noop_when_no_pat_id(self, temp_config_dir: Path) -> None:
        config = DreamhubConfig(token="pat_current")
        save_config(config)
        delete_cli_pat(config)
        # Should not raise

    @respx.mock
    def test_non_fatal_on_delete_failure(self, temp_config_dir: Path) -> None:
        config = DreamhubConfig(
            token="pat_current",
            cli_pat="pat_old",
            cli_pat_id="pat-id-1",
            cli_pat_created_at="2026-01-01T00:00:00Z",
        )
        save_config(config)

        respx.delete(f"{PAT_ENDPOINT}pat-id-1").mock(side_effect=httpx.ConnectError("fail"))
        delete_cli_pat(config)
        # Fields should still be cleared locally
        assert config.cli_pat is None


class TestRotateCliPat:
    @respx.mock
    def test_rotates_when_old(self, temp_config_dir: Path) -> None:
        old_time = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(time.time() - 13 * 86400),
        )
        config = DreamhubConfig(
            token="pat_old_primary",
            tenant_id="t-1",
            cli_pat="pat_old_primary",
            cli_pat_id="old-id",
            cli_pat_created_at=old_time,
        )
        save_config(config)

        respx.post(PAT_ENDPOINT).mock(
            return_value=httpx.Response(201, json={"id": "new-id", "token": "pat_new_rotated"})
        )
        respx.delete(f"{PAT_ENDPOINT}old-id").mock(return_value=httpx.Response(204))

        rotate_cli_pat_if_needed(config)

        assert config.cli_pat == "pat_new_rotated"
        assert config.cli_pat_id == "new-id"
        # Primary token should also be updated since it was the old PAT
        assert config.token == "pat_new_rotated"

    def test_skips_when_recent(self, temp_config_dir: Path) -> None:
        config = DreamhubConfig(
            token="pat_current",
            cli_pat="pat_current",
            cli_pat_id="current-id",
            cli_pat_created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        save_config(config)
        rotate_cli_pat_if_needed(config)
        assert config.cli_pat_id == "current-id"  # unchanged

    def test_skips_when_no_pat(self, temp_config_dir: Path) -> None:
        config = DreamhubConfig(token="some_jwt")
        rotate_cli_pat_if_needed(config)
        # no-op, should not raise


class TestLogoutClearsPatFields:
    def test_logout_clears_pat(self, temp_config_dir: Path) -> None:
        save_config(
            DreamhubConfig(
                token="pat_test",
                refresh_token="refresh_abc",
                tenant_id="t-1",
                cli_pat="pat_backup",
                cli_pat_id="pat-id-1",
                cli_pat_created_at="2026-01-01T00:00:00Z",
            )
        )
        config = logout()
        assert config.cli_pat is None
        assert config.cli_pat_id is None
        assert config.cli_pat_created_at is None


class TestClientPatFallback:
    """Test that DreamhubClient falls back to CLI PAT when JWT refresh fails."""

    @respx.mock
    def test_proactive_refresh_promotes_pat_on_jwt_failure(self, temp_config_dir: Path) -> None:
        expired_jwt = _make_jwt({"exp": int(time.time()) - 60})
        save_config(
            DreamhubConfig(
                token=expired_jwt,
                refresh_token="bad_refresh",
                tenant_id="t-1",
                cli_pat="pat_fallback",
                cli_pat_id="pat-id-1",
                cli_pat_created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
        )

        # JWT refresh will fail
        respx.post(url__regex=r".*/oauth/token$").mock(return_value=httpx.Response(401, text="invalid refresh token"))
        # API call with PAT succeeds
        respx.get(f"{DEFAULT_API_URL}/companies").mock(return_value=httpx.Response(200, json={"companies": []}))

        from dreamhubcli.client import DreamhubClient

        client = DreamhubClient()
        response = client.get("companies")

        assert response.status_code == 200
        config = load_config()
        assert config.token == "pat_fallback"
        assert config.refresh_token is None

    @respx.mock
    def test_401_handler_promotes_pat_when_refresh_fails(self, temp_config_dir: Path) -> None:
        save_config(
            DreamhubConfig(
                token="pat_not_a_jwt",
                tenant_id="t-1",
                cli_pat="pat_backup_token",
                cli_pat_id="pat-id-2",
                cli_pat_created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
        )

        # First request returns 401, second (with PAT) succeeds
        respx.get(f"{DEFAULT_API_URL}/companies").mock(
            side_effect=[
                httpx.Response(401, text="Unauthorized"),
                httpx.Response(200, json={"companies": []}),
            ]
        )

        from dreamhubcli.client import DreamhubClient

        client = DreamhubClient()
        response = client.get("companies")

        assert response.status_code == 200
        config = load_config()
        assert config.token == "pat_backup_token"

    @respx.mock
    def test_401_handler_no_double_promote(self, temp_config_dir: Path) -> None:
        """If token already IS the PAT, don't re-promote on 401."""
        save_config(
            DreamhubConfig(
                token="pat_same_token",
                tenant_id="t-1",
                cli_pat="pat_same_token",
                cli_pat_id="pat-id-3",
            )
        )

        respx.get(f"{DEFAULT_API_URL}/companies").mock(return_value=httpx.Response(401, text="Unauthorized"))

        from dreamhubcli.client import DreamhubClient

        client = DreamhubClient()
        response = client.get("companies")

        # Should NOT retry — token is already the PAT
        assert response.status_code == 401
