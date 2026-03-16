"""Tests for non-CRUD command modules (search, history, reporting, settings)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import respx
from typer.testing import CliRunner

from dreamhubcli.config import DreamhubConfig, save_config
from dreamhubcli.main import app

runner = CliRunner()

API_URL = "https://crm.dreamhub.ai/api/v1"


class TestSearchCommands:
    @respx.mock
    def test_search_query(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/search/global").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"entityType": "company", "id": "CO-AB-1", "name": "Acme"}],
                    "total": 1,
                    "page": 1,
                    "pageSize": 20,
                    "queryTimeMs": 12,
                },
            )
        )
        result = runner.invoke(app, ["search", "Acme"])
        assert result.exit_code == 0
        assert "Acme" in result.output
        assert "Page 1" in result.output

    @respx.mock
    def test_search_json(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/search/global").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"entityType": "company", "id": "CO-AB-1", "name": "Acme"}],
                    "total": 1,
                    "page": 1,
                    "pageSize": 20,
                    "queryTimeMs": 12,
                },
            )
        )
        result = runner.invoke(app, ["search", "Acme", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["results"][0]["name"] == "Acme"


class TestHistoryCommands:
    @respx.mock
    def test_list_history(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.get(f"{API_URL}/history").mock(
            return_value=httpx.Response(
                200,
                json={
                    "history": [
                        {
                            "id": "H-1",
                            "entityType": "company",
                            "entityId": "CO-AB-1",
                            "action": "update",
                            "userId": "U-1",
                            "createdAt": "2025-01-01",
                        }
                    ],
                    "total": 1,
                },
            )
        )
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        assert "update" in result.output


class TestReportingCommands:
    def test_list_reports(self) -> None:
        result = runner.invoke(app, ["reporting", "list"])
        assert result.exit_code == 0
        assert "kpis" in result.output
        assert "sales_pipeline_funnel" in result.output

    @respx.mock
    def test_get_report(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        route = respx.get(f"{API_URL}/reports/kpis").mock(
            return_value=httpx.Response(
                200,
                json={
                    "kpis": {"overallSalesYtd": [{"value": 24780.0}]},
                },
            )
        )
        result = runner.invoke(app, ["reporting", "get", "kpis"])
        assert result.exit_code == 0
        assert route.called

    def test_unknown_report_type(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        result = runner.invoke(app, ["reporting", "get", "nonexistent"])
        assert result.exit_code == 1
        assert "Unknown report type" in result.output


class TestSettingsCommands:
    @respx.mock
    def test_list_settings(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.get(f"{API_URL}/settings/account/").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "key": "fiscal_year_start",
                        "value": "2025-01-01",
                        "valueType": "date",
                        "category": "financial",
                        "description": "Start of fiscal year",
                    },
                    {
                        "key": "account_currency",
                        "value": "USD",
                        "valueType": "string",
                        "category": "financial",
                        "description": "Default currency",
                    },
                ],
            )
        )
        result = runner.invoke(app, ["settings", "list"])
        assert result.exit_code == 0
        assert "fiscal_year_start" in result.output
        assert "USD" in result.output

    @respx.mock
    def test_get_setting(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.get(f"{API_URL}/settings/account/account_currency").mock(
            return_value=httpx.Response(
                200,
                json={
                    "key": "account_currency",
                    "value": "USD",
                    "valueType": "string",
                    "category": "financial",
                    "description": "Default currency",
                },
            )
        )
        result = runner.invoke(app, ["settings", "get", "account_currency"])
        assert result.exit_code == 0
        assert "USD" in result.output

    @respx.mock
    def test_set_setting(self, temp_config_dir: Path) -> None:
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


class TestVersionFlag:
    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "Dreamhub CLI" in result.output

    def test_version_subcommand_removed(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code != 0


class TestCtrlCHandling:
    def test_pretty_exceptions_disabled(self) -> None:
        from dreamhubcli.main import app as main_app

        assert main_app.pretty_exceptions_enable is False


class TestShellCompletion:
    def test_install_completion_in_help(self) -> None:
        """Confirm shell completion is wired into the root --help output."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--install-completion" in result.output

    def test_show_completion_in_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--show-completion" in result.output

    def test_show_completion_zsh(self) -> None:
        """Verify --show-completion generates a zsh completion script."""
        with patch("typer.completion.shellingham.detect_shell", return_value=("zsh", "/bin/zsh")):
            result = runner.invoke(app, ["--show-completion"])
        assert result.exit_code == 0
        assert "compdef" in result.output or "_dh" in result.output

    def test_show_completion_bash(self) -> None:
        """Verify --show-completion generates a bash completion script."""
        with patch("typer.completion.shellingham.detect_shell", return_value=("bash", "/bin/bash")):
            result = runner.invoke(app, ["--show-completion"])
        assert result.exit_code == 0
        assert "complete" in result.output

    def test_show_completion_handles_detection_failure(self) -> None:
        """Verify --show-completion doesn't traceback when shell can't be detected."""
        from shellingham._core import ShellDetectionFailure

        with patch("typer.completion.shellingham.detect_shell", side_effect=ShellDetectionFailure()):
            result = runner.invoke(app, ["--show-completion"])
        # Should fail gracefully, not traceback
        assert result.exit_code != 0
        assert "Traceback" not in (result.output or "")
        if result.stderr_bytes:
            assert "Traceback" not in result.stderr_bytes.decode()


class TestCustomCommandHelpExamples:
    """Verify every custom command and auth subcommand shows usage examples in --help."""

    def test_search_help_examples(self) -> None:
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output

    def test_reporting_help_examples(self) -> None:
        result = runner.invoke(app, ["reporting", "get", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output

    def test_history_help_examples(self) -> None:
        result = runner.invoke(app, ["history", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output

    def test_settings_list_help_examples(self) -> None:
        result = runner.invoke(app, ["settings", "list", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output

    def test_settings_get_help_examples(self) -> None:
        result = runner.invoke(app, ["settings", "get", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output

    def test_settings_set_help_examples(self) -> None:
        result = runner.invoke(app, ["settings", "set", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output

    def test_auth_login_help_examples(self) -> None:
        result = runner.invoke(app, ["auth", "login", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output

    def test_auth_status_help_examples(self) -> None:
        result = runner.invoke(app, ["auth", "status", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output

    def test_auth_logout_help_examples(self) -> None:
        result = runner.invoke(app, ["auth", "logout", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output
