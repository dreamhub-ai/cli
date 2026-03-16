"""OAuth 2.0 PKCE Authorization Code flow with localhost callback server.

Implements the full browser-based login flow for Frontegg:
1. Generate PKCE verifier + challenge
2. Open browser to authorize endpoint
3. Start a one-shot HTTP server on 127.0.0.1:8391 to capture the callback
4. Validate CSRF state
5. Exchange authorization code for tokens

Only ``run_browser_flow()`` is public.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import socket
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import typer

from dreamhubcli.output import console, print_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CALLBACK_HOST = "localhost"
CALLBACK_PORT = 8391
CALLBACK_PATH = "/callback"
REDIRECT_URI = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{CALLBACK_PATH}"
LOGIN_TIMEOUT_SECONDS = 120

_CALLBACK_HTML: bytes | None = None


def _load_callback_html() -> bytes:
    """Load the branded callback HTML page from the static directory."""
    global _CALLBACK_HTML  # noqa: PLW0603
    if _CALLBACK_HTML is None:
        try:
            _CALLBACK_HTML = resources.files("dreamhubcli.static").joinpath("login-callback.html").read_bytes()
        except Exception:
            _CALLBACK_HTML = b"<html><body><p>Login complete. You can close this tab.</p></body></html>"
    return _CALLBACK_HTML


# Frontegg endpoint paths (relative to auth_url from config)
_AUTHORIZE_PATH = "/oauth/authorize"
_TOKEN_PATH = "/oauth/token"


# ---------------------------------------------------------------------------
# PKCE generation (RFC 7636 S256)
# ---------------------------------------------------------------------------


def _generate_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) per RFC 7636 S256."""
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


# ---------------------------------------------------------------------------
# Auth URL construction
# ---------------------------------------------------------------------------


def _build_auth_url(challenge: str, state: str) -> str:
    """Build the full authorize URL with PKCE and state parameters."""
    from dreamhubcli.config import DEFAULT_AUTH_URL, DEFAULT_CLIENT_ID

    base = DEFAULT_AUTH_URL.rstrip("/")
    params = {
        "response_type": "code",
        "client_id": DEFAULT_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile email",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{base}{_AUTHORIZE_PATH}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Port availability check
# ---------------------------------------------------------------------------


def _port_is_free(port: int) -> bool:
    """Return True if the port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((CALLBACK_HOST, port)) != 0


# ---------------------------------------------------------------------------
# Callback handler
# ---------------------------------------------------------------------------


class _CallbackHandler(BaseHTTPRequestHandler):
    """Capture ?code= and ?state= from the Frontegg OAuth redirect."""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        self.server.auth_code = params.get("code", [None])[0]  # type: ignore[attr-defined]
        self.server.returned_state = params.get("state", [None])[0]  # type: ignore[attr-defined]
        self.server.received_event.set()  # type: ignore[attr-defined]

        body = _load_callback_html()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


# ---------------------------------------------------------------------------
# Callback server
# ---------------------------------------------------------------------------


def _run_callback_server(received: threading.Event) -> tuple[str | None, str | None]:
    """Start an HTTP server, wait for the callback, return (auth_code, returned_state)."""
    with HTTPServer((CALLBACK_HOST, CALLBACK_PORT), _CallbackHandler) as httpd:
        httpd.timeout = 1.0
        httpd.auth_code = None  # type: ignore[attr-defined]
        httpd.returned_state = None  # type: ignore[attr-defined]
        httpd.received_event = received  # type: ignore[attr-defined]

        deadline = time.monotonic() + LOGIN_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            httpd.handle_request()
            if received.is_set():
                break

        return httpd.auth_code, httpd.returned_state  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


def _exchange_code(auth_code: str, code_verifier: str) -> tuple[str, str | None]:
    """Exchange authorization code + PKCE verifier for access token."""
    from dreamhubcli.config import DEFAULT_AUTH_URL, DEFAULT_CLIENT_ID

    base = DEFAULT_AUTH_URL.rstrip("/")
    token_endpoint = f"{base}{_TOKEN_PATH}"

    response = httpx.post(
        token_endpoint,
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
            "client_id": DEFAULT_CLIENT_ID,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )

    if response.status_code != 200:
        print_error("Login failed: could not exchange authorization code.")
        raise typer.Exit(code=1)

    body = response.json()
    access_token = body["access_token"]

    # Extract tenantId from the JWT payload — the token response body
    # may return a different (wrong) tenant_id field.
    tenant_id = _extract_tenant_from_jwt(access_token)
    if not tenant_id:
        tenant_id = body.get("tenant_id") or body.get("tenantId")

    return access_token, tenant_id


def _extract_tenant_from_jwt(token: str) -> str | None:
    """Decode the JWT payload (without verification) to extract tenantId."""
    try:
        payload_b64 = token.split(".")[1]
        # Add padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("tenantId")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_browser_flow() -> tuple[str, str | None]:
    """Open browser for Frontegg OAuth login, wait for callback, return tokens.

    Returns (access_token, tenant_id_or_none) on success.
    Raises typer.Exit(code=1) with a printed error on failure.
    """
    if not _port_is_free(CALLBACK_PORT):
        print_error(f"Port {CALLBACK_PORT} is already in use. Close the other process and try again.")
        raise typer.Exit(code=1)

    verifier, challenge = _generate_pkce()
    state = secrets.token_urlsafe(16)
    auth_url = _build_auth_url(challenge, state)

    received = threading.Event()

    webbrowser.open(auth_url)

    try:
        with console.status("Waiting for browser login... (Ctrl-C to cancel)"):
            auth_code, returned_state = _run_callback_server(received)
    except KeyboardInterrupt:
        print_error("Login cancelled.")
        raise typer.Exit(code=1)

    if auth_code is None:
        print_error("Login timed out. Run: dh auth login to try again.")
        raise typer.Exit(code=1)

    if returned_state != state:
        print_error("Login failed: state mismatch (possible CSRF). Run: dh auth login to try again.")
        raise typer.Exit(code=1)

    return _exchange_code(auth_code, verifier)
