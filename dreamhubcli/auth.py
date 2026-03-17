"""Authentication helpers for Dreamhub CLI.

Supports PAT token login and browser-based Frontegg OAuth flow.
Manages x-tenant-id header alongside authorization.
"""

from __future__ import annotations

import base64
import json
import logging
import time

import httpx

from dreamhubcli.config import DreamhubConfig, load_config, save_config

logger = logging.getLogger(__name__)


def login_with_token(
    token: str,
    tenant_id: str | None = None,
    refresh_token: str | None = None,
) -> DreamhubConfig:
    """Store a token (and optional tenant ID / refresh token) in config."""
    config = load_config()
    config.token = token
    if tenant_id is not None:
        config.tenant_id = tenant_id
    config.refresh_token = refresh_token
    save_config(config)
    return config


def login_with_browser() -> DreamhubConfig:
    """Run the full browser OAuth PKCE flow and save the resulting token."""
    from dreamhubcli.auth_callback import run_browser_flow

    access_token, refresh_token, tenant_id = run_browser_flow()
    return login_with_token(access_token, tenant_id, refresh_token=refresh_token)


def logout() -> DreamhubConfig:
    """Clear stored credentials."""
    config = load_config()
    config.token = None
    config.refresh_token = None
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


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

_TOKEN_PATH = "/oauth/token"
_EXPIRY_BUFFER_SECONDS = 30


def _decode_jwt_exp(token: str) -> int | None:
    """Extract the exp claim from a JWT without verification."""
    try:
        payload_b64 = token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        return int(exp) if exp is not None else None
    except Exception:
        return None


def is_token_expired(token: str) -> bool:
    """Return True if the JWT access token is expired or about to expire."""
    exp = _decode_jwt_exp(token)
    if exp is None:
        return False
    return time.time() >= (exp - _EXPIRY_BUFFER_SECONDS)


def refresh_access_token() -> bool:
    """Use the stored refresh token to obtain a new access token.

    Returns True if the token was refreshed, False if refresh is not possible
    (no refresh token, PAT auth, or refresh failed).
    """
    from dreamhubcli.config import DEFAULT_AUTH_URL, DEFAULT_CLIENT_ID

    config = load_config()
    if not config.refresh_token:
        return False

    base = DEFAULT_AUTH_URL.rstrip("/")
    token_endpoint = f"{base}{_TOKEN_PATH}"

    try:
        response = httpx.post(
            token_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": config.refresh_token,
                "client_id": DEFAULT_CLIENT_ID,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
    except httpx.RequestError:
        logger.debug("Token refresh request failed", exc_info=True)
        return False

    if response.status_code != 200:
        logger.debug("Token refresh returned %d", response.status_code)
        return False

    body = response.json()
    new_access_token = body.get("access_token")
    if not new_access_token:
        return False

    config.token = new_access_token
    new_refresh_token = body.get("refresh_token")
    if new_refresh_token:
        config.refresh_token = new_refresh_token
    save_config(config)
    logger.debug("Access token refreshed successfully")
    return True
