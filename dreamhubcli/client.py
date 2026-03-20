"""HTTP client with automatic auth injection for Dreamhub APIs."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import typer

from dreamhubcli import __version__
from dreamhubcli.auth import (
    get_auth_headers,
    is_token_expired,
    refresh_access_token,
    rotate_cli_pat_if_needed,
)
from dreamhubcli.output import print_error as _print_error
from dreamhubcli.output import print_warning as _print_warning

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
USER_AGENT = f"dreamhub-cli/{__version__}"
_MAX_RETRIES = 3
_IDEMPOTENT_METHODS = {"GET", "HEAD", "OPTIONS", "PUT"}


class DreamhubClient:
    """Thin wrapper around httpx that injects auth headers and base URL."""

    def __init__(self, api_url: str | None = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        from dreamhubcli.config import DEFAULT_API_URL

        self.base_url = (api_url or DEFAULT_API_URL).rstrip("/")
        self.timeout = timeout

    def _build_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        headers = get_auth_headers()
        headers["Content-Type"] = "application/json"
        headers["User-Agent"] = USER_AGENT
        if extra_headers:
            headers.update(extra_headers)
        return headers

    @property
    def origin(self) -> str:
        """Return the scheme + host (no path) from the configured base URL."""
        if "://" not in self.base_url:
            return self.base_url
        scheme, remainder = self.base_url.split("://", 1)
        host = remainder.split("/", 1)[0]
        return f"{scheme}://{host}"

    def _build_url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _maybe_refresh_proactively(self) -> None:
        """Refresh the access token if it's expired, before making a request.

        For PAT-based auth, skips JWT refresh and checks PAT rotation instead.
        If JWT refresh fails and a CLI PAT exists, promotes the PAT to primary token.
        """
        from dreamhubcli.config import load_config, save_config

        config = load_config()
        if not config.token:
            return

        # PAT is the primary token — just check rotation
        if config.token.startswith("pat_"):
            rotate_cli_pat_if_needed(config)
            return

        # JWT not expired — nothing to do
        if not is_token_expired(config.token):
            return

        # Try JWT refresh first
        if config.refresh_token and refresh_access_token():
            return

        # JWT refresh failed or unavailable — fall back to CLI PAT
        if config.cli_pat:
            logger.debug("JWT refresh failed, promoting CLI PAT to primary token")
            config.token = config.cli_pat
            config.refresh_token = None
            save_config(config)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | list[Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Execute an HTTP request against the Dreamhub API."""
        self._maybe_refresh_proactively()

        url = self._build_url(path)
        headers = self._build_headers(extra_headers)

        request_kwargs: dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": headers,
            "params": params,
            "json": json_payload,
        }

        try:
            with httpx.Client(timeout=self.timeout) as http:
                response = http.request(**request_kwargs)
        except httpx.TimeoutException:
            _print_error("Request timed out. The API may be slow -- try again or check your connection.")
            raise typer.Exit(code=1)
        except httpx.ConnectError:
            _print_error("Cannot connect to API. Check your network connection.")
            raise typer.Exit(code=1)
        except httpx.RequestError as exc:
            _print_error(f"Network error: {exc}")
            raise typer.Exit(code=1)

        # 401 — retry once with a refreshed token, but only for idempotent methods
        # to avoid duplicating side effects on POST/PATCH/DELETE.
        _extra_header_names = {k.lower() for k in (extra_headers or {})}
        _is_idempotent = method.upper() in _IDEMPOTENT_METHODS or "idempotency-key" in _extra_header_names
        if response.status_code == 401 and _is_idempotent:
            refreshed = refresh_access_token()
            if not refreshed:
                # JWT refresh failed — try CLI PAT fallback
                from dreamhubcli.config import load_config, save_config

                config = load_config()
                if config.cli_pat and config.token != config.cli_pat:
                    logger.debug("401 handler: promoting CLI PAT to primary token")
                    config.token = config.cli_pat
                    config.refresh_token = None
                    save_config(config)
                    refreshed = True
            if refreshed:
                request_kwargs["headers"] = self._build_headers(extra_headers)
                try:
                    with httpx.Client(timeout=self.timeout) as http:
                        response = http.request(**request_kwargs)
                except httpx.RequestError:
                    pass

        # 429 retry with linear backoff (max 3 retries)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "2"))
            for attempt in range(_MAX_RETRIES):
                wait = retry_after * (attempt + 1)
                _print_warning(f"Rate limited. Waiting {wait}s before retrying...")
                time.sleep(wait)
                try:
                    with httpx.Client(timeout=self.timeout) as http:
                        response = http.request(**request_kwargs)
                except httpx.RequestError:
                    break
                if response.status_code != 429:
                    break

        if response.status_code >= 400:
            logger.debug("API error %s %s -> %d: %s", method, url, response.status_code, response.text[:500])

        return response

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        return self.request("GET", path, params=params)

    def post(self, path: str, *, json_payload: dict[str, Any] | list[Any] | None = None) -> httpx.Response:
        return self.request("POST", path, json_payload=json_payload)

    def put(self, path: str, *, json_payload: dict[str, Any] | None = None) -> httpx.Response:
        return self.request("PUT", path, json_payload=json_payload)

    def patch(self, path: str, *, json_payload: dict[str, Any] | None = None) -> httpx.Response:
        return self.request("PATCH", path, json_payload=json_payload)

    def delete(self, path: str) -> httpx.Response:
        return self.request("DELETE", path)
