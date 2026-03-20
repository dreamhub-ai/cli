"""Authentication helpers for Dreamhub CLI.

Supports PAT token login and browser-based Frontegg OAuth flow.
Manages x-tenant-id header alongside authorization.
"""

from __future__ import annotations

import base64
import calendar
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
    config.cli_pat = None
    config.cli_pat_id = None
    config.cli_pat_created_at = None
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
    config.cli_pat = None
    config.cli_pat_id = None
    config.cli_pat_created_at = None
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


# ---------------------------------------------------------------------------
# CLI-managed PAT (transparent fallback)
# ---------------------------------------------------------------------------

_PAT_ENDPOINT = "/accessenabler/tokens/"
_PAT_EXPIRY_DAYS = 14
_PAT_ROTATION_THRESHOLD_DAYS = 12


def _api_base_url() -> str:
    from dreamhubcli.config import DEFAULT_API_URL

    return DEFAULT_API_URL.rstrip("/")


def create_cli_pat(config: DreamhubConfig) -> None:
    """Create a 14-day CLI-managed PAT after browser login.

    Non-fatal: failures are logged and swallowed.
    Skipped if the current token is already a PAT.
    """
    if config.token and config.token.startswith("pat_"):
        return
    if not config.token:
        return

    url = f"{_api_base_url()}{_PAT_ENDPOINT}"
    headers = {
        "Authorization": f"Bearer {config.token}",
        "Content-Type": "application/json",
    }
    if config.tenant_id:
        headers["x-tenant-id"] = config.tenant_id

    try:
        response = httpx.post(
            url,
            json={"name": "cli-session", "expiresInDays": _PAT_EXPIRY_DAYS},
            headers=headers,
            timeout=15.0,
        )
        if response.status_code not in (200, 201):
            logger.debug("Failed to create CLI PAT: %d", response.status_code)
            return
        body = response.json()
        config.cli_pat = body.get("token") or body.get("clientId")
        config.cli_pat_id = body.get("id")
        config.cli_pat_created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_config(config)
        logger.debug("CLI PAT created: %s", config.cli_pat_id)
    except Exception:
        logger.debug("CLI PAT creation failed", exc_info=True)


def delete_cli_pat(config: DreamhubConfig) -> None:
    """Delete the CLI-managed PAT. Best-effort, never raises."""
    if not config.cli_pat_id:
        return

    url = f"{_api_base_url()}{_PAT_ENDPOINT}{config.cli_pat_id}"
    token = config.cli_pat or config.token
    if not token:
        return
    headers = {"Authorization": f"Bearer {token}"}
    if config.tenant_id:
        headers["x-tenant-id"] = config.tenant_id

    try:
        response = httpx.delete(url, headers=headers, timeout=15.0)
        if response.status_code not in (200, 202, 204, 404):
            logger.debug("CLI PAT deletion returned %d", response.status_code)
    except Exception:
        logger.debug("CLI PAT deletion failed", exc_info=True)

    config.cli_pat = None
    config.cli_pat_id = None
    config.cli_pat_created_at = None
    save_config(config)


def rotate_cli_pat_if_needed(config: DreamhubConfig) -> None:
    """Rotate the CLI PAT if it's older than 12 days. Non-fatal."""
    if not config.cli_pat or not config.cli_pat_created_at:
        return

    try:
        created = calendar.timegm(time.strptime(config.cli_pat_created_at, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, OverflowError):
        return

    age_days = (time.time() - created) / 86400
    if age_days < _PAT_ROTATION_THRESHOLD_DAYS:
        return

    old_pat_id = config.cli_pat_id
    auth_token = config.cli_pat
    url = f"{_api_base_url()}{_PAT_ENDPOINT}"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }
    if config.tenant_id:
        headers["x-tenant-id"] = config.tenant_id

    try:
        response = httpx.post(
            url,
            json={"name": "cli-session", "expiresInDays": _PAT_EXPIRY_DAYS},
            headers=headers,
            timeout=15.0,
        )
        if response.status_code not in (200, 201):
            logger.debug("CLI PAT rotation failed: %d", response.status_code)
            return
        body = response.json()
        config.cli_pat = body.get("token") or body.get("clientId")
        config.cli_pat_id = body.get("id")
        config.cli_pat_created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        # If the primary token was the old PAT, promote the new one
        if config.token == auth_token:
            config.token = config.cli_pat
        save_config(config)
    except Exception:
        logger.debug("CLI PAT rotation failed", exc_info=True)
        return

    # Clean up old PAT
    if old_pat_id and config.cli_pat_id != old_pat_id:
        old_url = f"{_api_base_url()}{_PAT_ENDPOINT}{old_pat_id}"
        try:
            httpx.delete(
                old_url,
                headers={"Authorization": f"Bearer {config.cli_pat}", "x-tenant-id": config.tenant_id or ""},
                timeout=15.0,
            )
        except Exception:
            logger.debug("Old CLI PAT cleanup failed", exc_info=True)
        logger.debug("CLI PAT rotated: %s -> %s", old_pat_id, config.cli_pat_id)
