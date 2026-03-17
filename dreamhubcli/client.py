"""HTTP client with automatic auth injection for Dreamhub APIs."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import typer

from dreamhubcli import __version__
from dreamhubcli.auth import get_auth_headers, is_token_expired, refresh_access_token
from dreamhubcli.output import print_error as _print_error
from dreamhubcli.output import print_warning as _print_warning

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
USER_AGENT = f"dreamhub-cli/{__version__}"
_MAX_RETRIES = 3


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
        """Refresh the access token if it's expired, before making a request."""
        from dreamhubcli.config import load_config

        config = load_config()
        if config.token and config.refresh_token and is_token_expired(config.token):
            refresh_access_token()

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

        # 401 — try refreshing the token once before giving up
        if response.status_code == 401 and refresh_access_token():
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
