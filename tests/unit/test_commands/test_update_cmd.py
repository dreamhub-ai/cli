"""Tests for dh update command and version check."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import respx
from typer.testing import CliRunner

from dreamhubcli.commands.update import (
    GITHUB_RELEASES_URL,
    _parse_version,
    check_for_update_notice,
)
from dreamhubcli.config import DreamhubConfig, load_config, save_config
from dreamhubcli.main import app

runner = CliRunner()


class TestParseVersion:
    def test_simple_version(self) -> None:
        assert _parse_version("1.2.0") == (1, 2, 0)

    def test_strips_v_prefix(self) -> None:
        assert _parse_version("v1.3.0") == (1, 3, 0)

    def test_comparison(self) -> None:
        assert _parse_version("1.3.0") > _parse_version("1.2.0")
        assert _parse_version("2.0.0") > _parse_version("1.9.9")
        assert _parse_version("1.2.1") > _parse_version("1.2.0")


class TestCheckForUpdateNotice:
    @respx.mock
    def test_prints_notice_when_newer_version_available(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig())
        respx.get(GITHUB_RELEASES_URL).mock(return_value=httpx.Response(200, json={"tag_name": "v99.0.0"}))
        with patch("dreamhubcli.commands.update.print_warning") as mock_warn:
            check_for_update_notice()
        mock_warn.assert_called_once()
        assert "99.0.0" in mock_warn.call_args[0][0]

    @respx.mock
    def test_no_notice_when_same_version(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig())
        from dreamhubcli import __version__

        respx.get(GITHUB_RELEASES_URL).mock(return_value=httpx.Response(200, json={"tag_name": f"v{__version__}"}))
        with patch("dreamhubcli.commands.update.print_warning") as mock_warn:
            check_for_update_notice()
        mock_warn.assert_not_called()

    @respx.mock
    def test_skips_check_within_24h(self, temp_config_dir: Path) -> None:
        import time

        save_config(
            DreamhubConfig(
                last_version_check=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                latest_known_version="1.2.0",
            )
        )
        route = respx.get(GITHUB_RELEASES_URL).mock(return_value=httpx.Response(200, json={"tag_name": "v99.0.0"}))
        check_for_update_notice()
        assert not route.called

    @respx.mock
    def test_shows_cached_notice_within_24h(self, temp_config_dir: Path) -> None:
        import time

        save_config(
            DreamhubConfig(
                last_version_check=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                latest_known_version="99.0.0",
            )
        )
        with patch("dreamhubcli.commands.update.print_warning") as mock_warn:
            check_for_update_notice()
        mock_warn.assert_called_once()
        assert "99.0.0" in mock_warn.call_args[0][0]

    @respx.mock
    def test_saves_check_timestamp(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig())
        from dreamhubcli import __version__

        respx.get(GITHUB_RELEASES_URL).mock(return_value=httpx.Response(200, json={"tag_name": f"v{__version__}"}))
        check_for_update_notice()
        config = load_config()
        assert config.last_version_check is not None
        assert config.latest_known_version == __version__

    @respx.mock
    def test_silent_on_network_error(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig())
        respx.get(GITHUB_RELEASES_URL).mock(side_effect=httpx.ConnectError("fail"))
        with patch("dreamhubcli.commands.update.print_warning") as mock_warn:
            check_for_update_notice()
        mock_warn.assert_not_called()

    @respx.mock
    def test_silent_on_non_200(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig())
        respx.get(GITHUB_RELEASES_URL).mock(return_value=httpx.Response(404))
        with patch("dreamhubcli.commands.update.print_warning") as mock_warn:
            check_for_update_notice()
        mock_warn.assert_not_called()


class TestUpdateCommand:
    @patch("dreamhubcli.commands.update.check_for_update_notice")
    @patch("dreamhubcli.commands.update._is_pipx_install", return_value=True)
    @patch("dreamhubcli.commands.update.subprocess.run")
    @patch("dreamhubcli.commands.update.shutil.which", return_value="/usr/local/bin/pipx")
    def test_pipx_upgrade_success(self, mock_which, mock_run, mock_pipx, mock_check, temp_config_dir: Path) -> None:
        mock_run.return_value = type("Result", (), {"returncode": 0, "stdout": "upgraded dreamhubcli", "stderr": ""})()
        result = runner.invoke(app, ["update"])
        assert result.exit_code == 0
        assert "Update complete" in result.output

    @patch("dreamhubcli.commands.update.check_for_update_notice")
    @patch("dreamhubcli.commands.update._is_pipx_install", return_value=False)
    @patch("dreamhubcli.commands.update.subprocess.run")
    @patch("dreamhubcli.commands.update.shutil.which", return_value="/usr/bin/pip")
    def test_pip_upgrade_success(self, mock_which, mock_run, mock_pipx, mock_check, temp_config_dir: Path) -> None:
        mock_run.return_value = type("Result", (), {"returncode": 0, "stdout": "installed", "stderr": ""})()
        result = runner.invoke(app, ["update"])
        assert result.exit_code == 0
        assert "Update complete" in result.output

    @patch("dreamhubcli.commands.update.check_for_update_notice")
    @patch("dreamhubcli.commands.update._is_pipx_install", return_value=True)
    @patch("dreamhubcli.commands.update.subprocess.run")
    @patch("dreamhubcli.commands.update.shutil.which", return_value="/usr/local/bin/pipx")
    def test_pipx_upgrade_failure(self, mock_which, mock_run, mock_pipx, mock_check, temp_config_dir: Path) -> None:
        mock_run.return_value = type("Result", (), {"returncode": 1, "stdout": "", "stderr": "error"})()
        result = runner.invoke(app, ["update"])
        assert result.exit_code == 1
