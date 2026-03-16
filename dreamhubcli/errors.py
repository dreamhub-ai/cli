"""Centralized error handling and auth gate for Dreamhub CLI.

Provides ``handle_response`` (HTTP error mapping) and ``require_auth``
(authentication guard).  All error output goes to stderr via
``print_error`` / ``print_warning`` from :mod:`dreamhubcli.output`.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import typer

from dreamhubcli.auth import is_authenticated
from dreamhubcli.output import error_console, print_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status-code -> user-friendly message map
# ---------------------------------------------------------------------------

_STATUS_MESSAGES: dict[int, str] = {
    401: "Session expired. Run: dh auth login to re-authenticate.",
    403: "You don't have permission to perform this action.",
    404: "Not found.",
    409: "Conflict: the resource already exists or is in a conflicting state.",
    500: "Something went wrong on our end. If this persists, contact support.",
    503: "Service unavailable. Try again shortly.",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def handle_response(
    response: httpx.Response,
    *,
    verbose: bool = False,
    entity_name: str | None = None,
) -> None:
    """Check *response* for HTTP errors and exit with a friendly message.

    Returns normally for any status < 400 with a JSON content type.
    For errors it prints a human-readable message to stderr and raises
    ``typer.Exit(code=1)``.
    """
    if response.status_code < 400:
        content_type = response.headers.get("content-type", "").lower()
        if "json" not in content_type and response.text.strip():
            if verbose:
                _print_verbose(response)
            print_error("API returned an unexpected response (not JSON). The endpoint may not exist.")
            raise typer.Exit(code=1)
        return

    if verbose:
        _print_verbose(response)

    status = response.status_code

    # 422 — validation errors get special treatment
    if status == 422:
        _handle_validation_error(response)
        raise typer.Exit(code=1)

    # 404 — enrich with entity_name when provided
    if status == 404 and entity_name:
        print_error(f"{entity_name} not found.")
        raise typer.Exit(code=1)

    # Known status codes
    if status in _STATUS_MESSAGES:
        print_error(_STATUS_MESSAGES[status])
        raise typer.Exit(code=1)

    # Unknown — try to extract a message from the body
    api_message = _extract_api_message(response)
    if api_message:
        print_error(api_message)
    else:
        print_error(f"Unexpected error (HTTP {status}).")

    raise typer.Exit(code=1)


def require_auth() -> None:
    """Exit with a friendly message if the user is not authenticated."""
    if not is_authenticated():
        print_error("Not logged in. Run: dh auth login")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _handle_validation_error(response: httpx.Response) -> None:
    """Parse 422 response body and print structured validation errors."""
    try:
        body: dict[str, Any] = response.json()
    except Exception:
        print_error("Validation failed: invalid request.")
        return

    errors = body.get("errors")
    if isinstance(errors, list) and errors:
        print_error("Validation failed:")
        for err in errors:
            if not isinstance(err, dict):
                error_console.print(f"  - {err}")
                continue
            field = err.get("field", "unknown")
            message = err.get("message", "invalid")
            error_console.print(f"  - [bold]{field}:[/bold] {message}")
        return

    message = body.get("message") or body.get("detail")
    if message:
        print_error(f"Validation failed: {message}")
        return

    print_error("Validation failed: invalid request.")


def _extract_api_message(response: httpx.Response) -> str | None:
    """Try to pull a ``message`` or ``error`` field from the JSON body."""
    try:
        body = response.json()
    except Exception:
        return None

    if isinstance(body, dict):
        return body.get("message") or body.get("error")

    return None


def _print_verbose(response: httpx.Response) -> None:
    """Print raw HTTP details to stderr for debugging."""
    error_console.print("\n[dim]--- HTTP Debug ---[/dim]")
    error_console.print(f"[dim]Status:[/dim] {response.status_code}")
    error_console.print(f"[dim]URL:[/dim] {response.request.url}")
    try:
        error_console.print(f"[dim]Body:[/dim] {response.text}")
    except Exception:
        error_console.print("[dim]Body:[/dim] (unreadable)")
    error_console.print("[dim]-----------------[/dim]\n")
