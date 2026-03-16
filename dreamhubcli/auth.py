"""Authentication helpers for Dreamhub CLI.

Supports PAT token login and browser-based Frontegg OAuth flow.
Manages x-tenant-id header alongside authorization.
"""

from __future__ import annotations

import logging

from dreamhubcli.config import DreamhubConfig, load_config, save_config

logger = logging.getLogger(__name__)


def login_with_token(token: str, tenant_id: str | None = None) -> DreamhubConfig:
    """Store a PAT token (and optional tenant ID) in config."""
    config = load_config()
    config.token = token
    if tenant_id is not None:
        config.tenant_id = tenant_id
    save_config(config)
    return config


def login_with_browser() -> DreamhubConfig:
    """Run the full browser OAuth PKCE flow and save the resulting token."""
    # Local import to avoid circular dependency (auth_callback imports from config/output, not auth)
    from dreamhubcli.auth_callback import run_browser_flow

    access_token, tenant_id = run_browser_flow()
    return login_with_token(access_token, tenant_id)


def logout() -> DreamhubConfig:
    """Clear stored credentials."""
    config = load_config()
    config.token = None
    config.tenant_id = None
    save_config(config)
    return config


def get_auth_headers() -> dict[str, str]:
    """Build authentication headers from stored config.

    Returns a dict with Authorization and x-tenant-id headers if available.
    """
    config = load_config()
    headers: dict[str, str] = {}
    if config.token:
        headers["Authorization"] = f"Bearer {config.token}"
    if config.tenant_id:
        headers["x-tenant-id"] = config.tenant_id
    return headers


def is_authenticated() -> bool:
    config = load_config()
    return config.token is not None
