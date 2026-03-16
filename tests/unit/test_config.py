"""Tests for dreamhubcli.config module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from dreamhubcli.config import DreamhubConfig, load_config, save_config


class TestDreamhubConfig:
    def test_defaults(self) -> None:
        config = DreamhubConfig()
        assert config.token is None
        assert config.tenant_id is None

    def test_custom_values(self) -> None:
        config = DreamhubConfig(token="pat_abc", tenant_id="tenant-123")
        assert config.token == "pat_abc"
        assert config.tenant_id == "tenant-123"

    def test_ignores_extra_fields(self) -> None:
        config = DreamhubConfig(token="pat_abc", api_url="https://stale.url", auth_url="https://old.auth")
        assert config.token == "pat_abc"


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        with patch("dreamhubcli.config.CONFIG_FILE", config_file):
            config = load_config()
        assert config.token is None

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

    def test_ignores_stale_keys_in_file(self, tmp_path: Path) -> None:
        """Old config files with api_url/auth_url/client_id are loaded without error."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('token = "pat_old"\napi_url = "https://stale"\nauth_url = "https://old"\n')
        with patch("dreamhubcli.config.CONFIG_FILE", config_file):
            config = load_config()
        assert config.token == "pat_old"


class TestSaveConfig:
    def test_creates_file(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".dreamhub"
        config_file = config_dir / "config.toml"
        with (
            patch("dreamhubcli.config.CONFIG_DIR", config_dir),
            patch("dreamhubcli.config.CONFIG_FILE", config_file),
        ):
            save_config(DreamhubConfig(token="pat_new"))
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
