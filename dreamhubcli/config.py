"""Configuration management for Dreamhub CLI.

Stores credentials in ~/.dreamhub/config.toml.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import tomli
import tomli_w
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".dreamhub"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_API_URL = "https://crm.dreamhub.ai/api/v1"
DEFAULT_AUTH_URL = "https://auth.dreamhub.ai"
DEFAULT_CLIENT_ID = "bc32f08d-8c43-4360-bd68-fa1f320c0560"


class DreamhubConfig(BaseModel):
    """Persistent CLI configuration (credentials only)."""

    model_config = ConfigDict(extra="ignore")

    token: str | None = Field(default=None)
    refresh_token: str | None = Field(default=None)
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
    """Return True when DH_DEV_MODE=1 is set."""
    return os.environ.get("DH_DEV_MODE") == "1"
