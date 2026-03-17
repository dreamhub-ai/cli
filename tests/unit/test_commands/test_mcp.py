"""Unit tests for dh mcp commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from dreamhubcli.main import app

runner = CliRunner()


class TestMcpInstall:
    def test_install_dry_run(self) -> None:
        result = runner.invoke(app, ["mcp", "install", "--dry-run"])
        assert result.exit_code == 0
        assert "mcpServers" in result.output
        assert "dreamhub" in result.output

    def test_install_creates_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        with patch("dreamhubcli.commands.mcp._claude_desktop_config_path", return_value=config_path):
            result = runner.invoke(app, ["mcp", "install"])
        assert result.exit_code == 0
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert "dreamhub" in data["mcpServers"]
        assert data["mcpServers"]["dreamhub"]["args"] == ["mcp", "serve"]
        assert "installed" in result.output.lower()

    def test_install_merges_existing_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        existing = {"mcpServers": {"other-tool": {"command": "other"}}, "someKey": "preserved"}
        config_path.write_text(json.dumps(existing))
        with patch("dreamhubcli.commands.mcp._claude_desktop_config_path", return_value=config_path):
            result = runner.invoke(app, ["mcp", "install"])
        assert result.exit_code == 0
        data = json.loads(config_path.read_text())
        assert "dreamhub" in data["mcpServers"]
        assert "other-tool" in data["mcpServers"]
        assert data["someKey"] == "preserved"

    def test_install_overwrites_existing_dreamhub(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        existing = {"mcpServers": {"dreamhub": {"command": "old-path"}}}
        config_path.write_text(json.dumps(existing))
        with patch("dreamhubcli.commands.mcp._claude_desktop_config_path", return_value=config_path):
            result = runner.invoke(app, ["mcp", "install"])
        assert result.exit_code == 0
        data = json.loads(config_path.read_text())
        assert data["mcpServers"]["dreamhub"]["command"] != "old-path"


class TestMcpUninstall:
    def test_uninstall_removes_dreamhub(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        existing = {"mcpServers": {"dreamhub": {"command": "dh"}, "other": {"command": "other"}}}
        config_path.write_text(json.dumps(existing))
        with patch("dreamhubcli.commands.mcp._claude_desktop_config_path", return_value=config_path):
            result = runner.invoke(app, ["mcp", "uninstall"])
        assert result.exit_code == 0
        data = json.loads(config_path.read_text())
        assert "dreamhub" not in data["mcpServers"]
        assert "other" in data["mcpServers"]
        assert "removed" in result.output.lower()

    def test_uninstall_not_found(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        existing = {"mcpServers": {"other": {"command": "other"}}}
        config_path.write_text(json.dumps(existing))
        with patch("dreamhubcli.commands.mcp._claude_desktop_config_path", return_value=config_path):
            result = runner.invoke(app, ["mcp", "uninstall"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_uninstall_no_config_file(self, tmp_path: Path) -> None:
        config_path = tmp_path / "nonexistent" / "claude_desktop_config.json"
        with patch("dreamhubcli.commands.mcp._claude_desktop_config_path", return_value=config_path):
            result = runner.invoke(app, ["mcp", "uninstall"])
        assert result.exit_code == 1


class TestMcpHelp:
    def test_mcp_help(self) -> None:
        result = runner.invoke(app, ["mcp", "--help"])
        assert result.exit_code == 0
        assert "serve" in result.output
        assert "install" in result.output
        assert "uninstall" in result.output

    def test_mcp_install_help_examples(self) -> None:
        result = runner.invoke(app, ["mcp", "install", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output

    def test_mcp_serve_help_examples(self) -> None:
        result = runner.invoke(app, ["mcp", "serve", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output

    def test_mcp_uninstall_help_examples(self) -> None:
        result = runner.invoke(app, ["mcp", "uninstall", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output
