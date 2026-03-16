"""Tests for dreamhubcli.auth_callback module — OAuth PKCE browser flow."""

from __future__ import annotations

import base64
import hashlib
import socket
import threading
import time
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx
import typer

from dreamhubcli.auth_callback import (
    CALLBACK_PORT,
    _build_auth_url,
    _CallbackHandler,
    _exchange_code,
    _generate_pkce,
    run_browser_flow,
)
from dreamhubcli.config import DEFAULT_CLIENT_ID

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simulate_callback(port: int, code: str, state: str, delay: float = 0.3) -> None:
    """Fire a fake GET callback to the running server after a short delay."""

    def _fire() -> None:
        time.sleep(delay)
        try:
            httpx.get(
                f"http://127.0.0.1:{port}/callback?code={code}&state={state}",
                timeout=5.0,
            )
        except httpx.ConnectError:
            pass

    thread = threading.Thread(target=_fire, daemon=True)
    thread.start()


# ---------------------------------------------------------------------------
# PKCE generation
# ---------------------------------------------------------------------------


class TestPKCEGeneration:
    def test_pkce_generation(self) -> None:
        verifier, challenge = _generate_pkce()
        assert len(verifier) >= 43
        # Verifier is URL-safe base64 characters
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        assert all(char in allowed for char in verifier)
        # Challenge is non-empty base64url without padding
        assert len(challenge) > 0
        assert "=" not in challenge

    def test_pkce_challenge_matches_rfc7636(self) -> None:
        verifier, challenge = _generate_pkce()
        # Independently compute SHA-256 base64url of verifier
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert challenge == expected_challenge


# ---------------------------------------------------------------------------
# Auth URL construction
# ---------------------------------------------------------------------------


class TestBuildAuthUrl:
    def test_build_auth_url(self, temp_config_dir: Path) -> None:
        url = _build_auth_url("test_challenge_abc", "test_state_xyz")
        assert "response_type=code" in url
        assert f"client_id={DEFAULT_CLIENT_ID}" in url
        assert "redirect_uri=" in url
        assert str(CALLBACK_PORT) in url
        assert "state=test_state_xyz" in url
        assert "code_challenge=test_challenge_abc" in url
        assert "code_challenge_method=S256" in url


# ---------------------------------------------------------------------------
# Callback handler
# ---------------------------------------------------------------------------


class TestCallbackHandler:
    def test_callback_handler_extracts_code(self) -> None:
        """Handler extracts ?code= and ?state= from query string."""
        received = threading.Event()
        with HTTPServer(("127.0.0.1", 0), _CallbackHandler) as httpd:
            httpd.timeout = 2.0
            httpd.auth_code = None  # type: ignore[attr-defined]
            httpd.returned_state = None  # type: ignore[attr-defined]
            httpd.received_event = received  # type: ignore[attr-defined]
            port = httpd.server_address[1]

            def _send_request() -> None:
                time.sleep(0.1)
                httpx.get(f"http://127.0.0.1:{port}/callback?code=abc123&state=xyz789", timeout=5.0)

            thread = threading.Thread(target=_send_request, daemon=True)
            thread.start()
            httpd.handle_request()

            assert httpd.auth_code == "abc123"  # type: ignore[attr-defined]
            assert httpd.returned_state == "xyz789"  # type: ignore[attr-defined]
            assert received.is_set()

    def test_callback_handler_returns_html(self) -> None:
        """Handler responds with 200 and HTML body containing 'Login complete'."""
        received = threading.Event()
        with HTTPServer(("127.0.0.1", 0), _CallbackHandler) as httpd:
            httpd.timeout = 2.0
            httpd.auth_code = None  # type: ignore[attr-defined]
            httpd.returned_state = None  # type: ignore[attr-defined]
            httpd.received_event = received  # type: ignore[attr-defined]
            port = httpd.server_address[1]

            response_holder: list[httpx.Response] = []

            def _send_request() -> None:
                time.sleep(0.1)
                response = httpx.get(f"http://127.0.0.1:{port}/callback?code=c&state=s", timeout=5.0)
                response_holder.append(response)

            thread = threading.Thread(target=_send_request, daemon=True)
            thread.start()
            httpd.handle_request()
            thread.join(timeout=3.0)

            assert len(response_holder) == 1
            assert response_holder[0].status_code == 200
            assert "Logged In to Dreamhub CLI" in response_holder[0].text

    def test_callback_handler_ignores_non_callback_path(self) -> None:
        """GET to a path other than /callback returns 404."""
        received = threading.Event()
        with HTTPServer(("127.0.0.1", 0), _CallbackHandler) as httpd:
            httpd.timeout = 2.0
            httpd.auth_code = None  # type: ignore[attr-defined]
            httpd.returned_state = None  # type: ignore[attr-defined]
            httpd.received_event = received  # type: ignore[attr-defined]
            port = httpd.server_address[1]

            response_holder: list[httpx.Response] = []

            def _send_request() -> None:
                time.sleep(0.1)
                response = httpx.get(f"http://127.0.0.1:{port}/other-path", timeout=5.0)
                response_holder.append(response)

            thread = threading.Thread(target=_send_request, daemon=True)
            thread.start()
            httpd.handle_request()
            thread.join(timeout=3.0)

            assert len(response_holder) == 1
            assert response_holder[0].status_code == 404
            assert not received.is_set()


# ---------------------------------------------------------------------------
# run_browser_flow error paths
# ---------------------------------------------------------------------------


class TestRunBrowserFlowErrors:
    def test_state_mismatch(self, temp_config_dir: Path) -> None:
        """State mismatch raises typer.Exit(code=1) and prints 'state mismatch'."""
        with (
            patch("dreamhubcli.auth_callback.webbrowser.open"),
            patch("dreamhubcli.auth_callback._exchange_code", return_value=("token", "tenant")),
            patch("dreamhubcli.auth_callback.secrets.token_urlsafe", return_value="expected_state"),
            patch("dreamhubcli.auth_callback._run_callback_server", return_value=("auth_code_123", "wrong_state")),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                run_browser_flow()
            assert exc_info.value.exit_code == 1

    def test_timeout(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no callback arrives within the timeout, run_browser_flow exits with code 1."""
        monkeypatch.setattr("dreamhubcli.auth_callback.LOGIN_TIMEOUT_SECONDS", 1)
        with (
            patch("dreamhubcli.auth_callback.webbrowser.open"),
            patch("dreamhubcli.auth_callback._port_is_free", return_value=True),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                run_browser_flow()
            assert exc_info.value.exit_code == 1

    def test_ctrl_c(self, temp_config_dir: Path) -> None:
        """When KeyboardInterrupt is raised during the wait, exits with code 1."""
        with (
            patch("dreamhubcli.auth_callback.webbrowser.open"),
            patch("dreamhubcli.auth_callback._run_callback_server", side_effect=KeyboardInterrupt),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                run_browser_flow()
            assert exc_info.value.exit_code == 1

    def test_port_occupied(self, temp_config_dir: Path) -> None:
        """When port 8391 is already in use, exits with code 1 and prints 'Port 8391'."""
        # Bind a socket to the port to occupy it
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            blocker.bind(("127.0.0.1", CALLBACK_PORT))
            blocker.listen(1)

            with pytest.raises(typer.Exit) as exc_info:
                run_browser_flow()
            assert exc_info.value.exit_code == 1
        finally:
            blocker.close()


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


class TestExchangeCode:
    @respx.mock
    def test_exchange_code_success(self, temp_config_dir: Path) -> None:
        """POSTs to token endpoint and returns (access_token, tenant_id)."""
        token_url_pattern = respx.post(url__regex=r".*/oauth/token$").respond(
            200,
            json={
                "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test",
                "token_type": "Bearer",
                "tenantId": "tenant-abc-123",
            },
        )
        access_token, tenant_id = _exchange_code("auth_code_xyz", "verifier_abc")
        assert access_token == "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test"
        assert tenant_id == "tenant-abc-123"
        assert token_url_pattern.called

    @respx.mock
    def test_exchange_code_failure(self, temp_config_dir: Path) -> None:
        """Non-200 response raises typer.Exit(code=1)."""
        respx.post(url__regex=r".*/oauth/token$").respond(400, json={"error": "invalid_grant"})
        with pytest.raises(typer.Exit) as exc_info:
            _exchange_code("bad_code", "bad_verifier")
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# Full flow (end-to-end with mocks)
# ---------------------------------------------------------------------------


class TestRunBrowserFlowSuccess:
    def test_run_browser_flow_success(self, temp_config_dir: Path) -> None:
        """Full flow with mocked browser, simulated callback, and mocked exchange."""
        fake_token = "eyJhbGciOiJSUzI1NiJ9.test_access_token"
        fake_tenant = "tenant-xyz-789"

        # We need to capture the state that run_browser_flow generates
        # so we can simulate a correct callback with matching state.
        original_token_urlsafe = __import__("secrets").token_urlsafe
        captured_state = []

        def _capture_state(nbytes: int = 32) -> str:
            value = original_token_urlsafe(nbytes)
            captured_state.append(value)
            return value

        with (
            patch("dreamhubcli.auth_callback.webbrowser.open") as mock_browser,
            patch("dreamhubcli.auth_callback._exchange_code", return_value=(fake_token, fake_tenant)),
            patch("dreamhubcli.auth_callback.secrets.token_urlsafe", side_effect=_capture_state),
        ):
            # The first call to token_urlsafe is for the PKCE verifier (32 bytes),
            # the second is for the state (16 bytes).
            # We need to simulate the callback after the server starts.
            def _delayed_callback() -> None:
                time.sleep(0.5)
                # captured_state[1] is the state token
                while len(captured_state) < 2:
                    time.sleep(0.05)
                state = captured_state[1]
                try:
                    httpx.get(
                        f"http://127.0.0.1:{CALLBACK_PORT}/callback?code=test_auth_code&state={state}",
                        timeout=5.0,
                    )
                except httpx.ConnectError:
                    pass

            callback_thread = threading.Thread(target=_delayed_callback, daemon=True)
            callback_thread.start()

            access_token, tenant_id = run_browser_flow()

            assert access_token == fake_token
            assert tenant_id == fake_tenant
            mock_browser.assert_called_once()
