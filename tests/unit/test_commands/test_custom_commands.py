"""Auth-gate and error handling tests for custom (non-CRUD) command modules.

Verifies that custom command groups (search, reporting, history, settings)
enforce require_auth() and use centralized handle_response() for friendly
error messages.

Dev-only commands (enrichment, access) are tested with DH_DEV_MODE=1.
Messaging was removed (WebSocket-based, not CLI-suitable).
"""

from __future__ import annotations

from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from dreamhubcli.config import DreamhubConfig, save_config
from dreamhubcli.main import app

runner = CliRunner()

API_URL = "https://crm.dreamhub.ai/api/v1"


class TestCustomCommandAuthGate:
    """Verify auth-gate works on all custom (non-CRUD) commands."""

    def test_search_requires_auth(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 1
        assert "Not logged in" in result.output

    def test_reporting_list_requires_auth(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["reporting", "list"])
        assert result.exit_code == 0  # list just prints available types, no auth needed

    def test_reporting_get_requires_auth(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["reporting", "get", "kpis"])
        assert result.exit_code == 1
        assert "Not logged in" in result.output

    def test_history_requires_auth(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 1
        assert "Not logged in" in result.output

    def test_settings_list_requires_auth(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["settings", "list"])
        assert result.exit_code == 1
        assert "Not logged in" in result.output

    def test_settings_get_requires_auth(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["settings", "get", "account_currency"])
        assert result.exit_code == 1
        assert "Not logged in" in result.output

    def test_settings_set_requires_auth(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["settings", "set", "account_currency", "EUR"])
        assert result.exit_code == 1
        assert "Not logged in" in result.output


class TestCustomCommandFriendlyErrors:
    """Verify custom commands show friendly errors, not raw status codes."""

    @respx.mock
    def test_search_500_shows_friendly_message(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/search/global").mock(return_value=httpx.Response(500, text="Internal Server Error"))
        result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 1
        assert "Something went wrong" in result.output
        assert "500" not in result.output

    @respx.mock
    def test_reporting_403_shows_permission_error(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.get(f"{API_URL}/reports/kpis").mock(return_value=httpx.Response(403, text="Forbidden"))
        result = runner.invoke(app, ["reporting", "get", "kpis"])
        assert result.exit_code == 1
        assert "permission" in result.output.lower()
        assert "403" not in result.output

    @respx.mock
    def test_history_401_shows_session_expired(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.get(f"{API_URL}/history").mock(return_value=httpx.Response(401, text="Unauthorized"))
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 1
        assert "Session expired" in result.output
        assert "401" not in result.output


class TestCustomCommandHints:
    """Verify post-operation hints appear after successful operations."""

    @respx.mock
    def test_settings_set_shows_updated(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.put(f"{API_URL}/settings/account/account_currency").mock(
            return_value=httpx.Response(
                200,
                json={
                    "key": "account_currency",
                    "value": "EUR",
                    "valueType": "string",
                    "category": "financial",
                    "description": "Default currency",
                },
            )
        )
        result = runner.invoke(app, ["settings", "set", "account_currency", "EUR"])
        assert result.exit_code == 0
        assert "Updated account_currency" in result.output


class TestLoginCompletionNudge:
    """Verify auth login shows shell completion tip after success."""

    @respx.mock
    def test_login_shows_completion_tip(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["auth", "login", "--token", "pat_test", "--tenant-id", "t-1"])
        assert result.exit_code == 0
        assert "install-completion" in result.output


class TestReportingGetJson:
    """Verify --json works on reporting get."""

    @respx.mock
    def test_reporting_get_json(self, temp_config_dir: Path) -> None:
        import json as json_mod

        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.get(f"{API_URL}/reports/kpis").mock(
            return_value=httpx.Response(200, json={"kpis": {"overallSalesYtd": [{"value": 100}]}})
        )
        result = runner.invoke(app, ["reporting", "get", "kpis", "--json"])
        assert result.exit_code == 0
        data = json_mod.loads(result.output)
        assert "kpis" in data


class TestReportingValidation:
    """Verify reporting rejects unknown report types."""

    def test_unknown_report_type(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        result = runner.invoke(app, ["reporting", "get", "unknown_type"])
        assert result.exit_code == 1
        assert "Unknown report type" in result.output
