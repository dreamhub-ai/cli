"""Configuration management for Dreamhub CLI.

Stores settings in ~/.dreamhub/config.toml.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import tomli
import tomli_w
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".dreamhub"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_API_URL = "https://crm.dreamhub.ai/api/v1"
DEFAULT_AUTH_URL = "https://crm-auth.dreamhub.ai"
DEFAULT_CLIENT_ID = "bc32f08d-8c43-4360-bd68-fa1f320c0560"


class DreamhubConfig(BaseModel):
    """Persistent CLI configuration."""

    api_url: str = Field(default=DEFAULT_API_URL)
    auth_url: str = Field(default=DEFAULT_AUTH_URL)
    client_id: str = Field(default=DEFAULT_CLIENT_ID)
    token: str | None = Field(default=None)
    tenant_id: str | None = Field(default=None)


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> DreamhubConfig:
    """Load configuration from disk, returning defaults if file doesn't exist."""
    if not CONFIG_FILE.exists():
        return DreamhubConfig()
    try:
        with open(CONFIG_FILE, "rb") as file:
            data: dict[str, Any] = tomli.load(file)
        return DreamhubConfig(**data)
    except Exception:
        logger.exception("Failed to load config from %s", CONFIG_FILE)
        return DreamhubConfig()


def save_config(config: DreamhubConfig) -> None:
    """Persist configuration to disk."""
    ensure_config_dir()
    with open(CONFIG_FILE, "wb") as file:
        tomli_w.dump(config.model_dump(exclude_none=True), file)


def is_dev_environment() -> bool:
    """Return True if the configured API URL points to a dev/QA environment.

    Can be forced on via DH_DEV_MODE=1 environment variable (useful for testing).
    """
    if os.environ.get("DH_DEV_MODE") == "1":
        return True
    config = load_config()
    return any(tag in config.api_url for tag in ("-dev-", "-qa-", "-staging-", "localhost"))
