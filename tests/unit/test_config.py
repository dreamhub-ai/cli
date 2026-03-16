"""Tests for dreamhubcli.config module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from dreamhubcli.config import DEFAULT_API_URL, DreamhubConfig, load_config, save_config


class TestDreamhubConfig:
    def test_defaults(self) -> None:
        config = DreamhubConfig()
        assert config.api_url == DEFAULT_API_URL
        assert config.token is None
        assert config.tenant_id is None

    def test_custom_values(self) -> None:
        config = DreamhubConfig(
            api_url="https://custom.api.com",
            token="pat_abc",
            tenant_id="tenant-123",
        )
        assert config.api_url == "https://custom.api.com"
        assert config.token == "pat_abc"
        assert config.tenant_id == "tenant-123"


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        with patch("dreamhubcli.config.CONFIG_FILE", config_file):
            config = load_config()
        assert config.token is None
        assert config.api_url == DEFAULT_API_URL

    def test_loads_from_file(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".dreamhub"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        with (
            patch("dreamhubcli.config.CONFIG_DIR", config_dir),
            patch("dreamhubcli.config.CONFIG_FILE", config_file),
        ):
            save_config(DreamhubConfig(token="pat_saved", tenant_id="t-1"))
            loaded = load_config()
        assert loaded.token == "pat_saved"
        assert loaded.tenant_id == "t-1"

    def test_returns_defaults_on_corrupt_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text("not valid toml {{{{")
        with patch("dreamhubcli.config.CONFIG_FILE", config_file):
            config = load_config()
        assert config.token is None


class TestSaveConfig:
    def test_creates_file(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".dreamhub"
        config_file = config_dir / "config.toml"
        with (
            patch("dreamhubcli.config.CONFIG_DIR", config_dir),
            patch("dreamhubcli.config.CONFIG_FILE", config_file),
        ):
            save_config(DreamhubConfig(token="pat_new", api_url="https://example.com"))
        assert config_file.exists()
        content = config_file.read_text()
        assert "pat_new" in content

    def test_excludes_none_values(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".dreamhub"
        config_file = config_dir / "config.toml"
        with (
            patch("dreamhubcli.config.CONFIG_DIR", config_dir),
            patch("dreamhubcli.config.CONFIG_FILE", config_file),
        ):
            save_config(DreamhubConfig(token=None))
        content = config_file.read_text()
        assert "token" not in content
