"""Unit tests for dreamhubcli.errors module."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import typer

from dreamhubcli.errors import handle_response, require_auth

# ---------------------------------------------------------------------------
# handle_response — success (no-op for 2xx)
# ---------------------------------------------------------------------------


class TestHandleResponseSuccess:
    def test_200_returns_normally(self) -> None:
        response = httpx.Response(200)
        handle_response(response)  # should not raise

    def test_201_returns_normally(self) -> None:
        response = httpx.Response(201)
        handle_response(response)

    def test_204_returns_normally(self) -> None:
        response = httpx.Response(204)
        handle_response(response)

    def test_301_returns_normally(self) -> None:
        response = httpx.Response(301)
        handle_response(response)


# ---------------------------------------------------------------------------
# handle_response — known status codes
# ---------------------------------------------------------------------------


class TestHandleResponseKnownCodes:
    def test_401_prints_session_expired_and_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(401, request=httpx.Request("GET", "http://test"))
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert "Session expired" in captured.err
        assert "dh auth login" in captured.err

    def test_403_prints_permission_denied_and_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(403, request=httpx.Request("GET", "http://test"))
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert "permission" in captured.err.lower()

    def test_404_prints_not_found_and_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(404, request=httpx.Request("GET", "http://test"))
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert "Not found" in captured.err

    def test_404_with_entity_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(404, request=httpx.Request("GET", "http://test"))
        with pytest.raises(typer.Exit):
            handle_response(response, entity_name="Company 'Acme'")
        captured = capsys.readouterr()
        assert "Company 'Acme' not found" in captured.err

    def test_409_prints_conflict_and_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(409, request=httpx.Request("GET", "http://test"))
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert "Conflict" in captured.err

    def test_500_prints_server_error_and_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(500, request=httpx.Request("GET", "http://test"))
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert "Something went wrong" in captured.err

    def test_503_prints_unavailable_and_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(503, request=httpx.Request("GET", "http://test"))
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert "Service unavailable" in captured.err


# ---------------------------------------------------------------------------
# handle_response — 422 validation errors
# ---------------------------------------------------------------------------


class TestHandleResponse422:
    def test_422_with_errors_array(self, capsys: pytest.CaptureFixture[str]) -> None:
        body = {"errors": [{"field": "email", "message": "is required"}, {"field": "name", "message": "too short"}]}
        response = httpx.Response(
            422,
            json=body,
            request=httpx.Request("POST", "http://test"),
        )
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert "email" in captured.err
        assert "is required" in captured.err

    def test_422_with_non_json_body(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(
            422,
            text="bad request",
            request=httpx.Request("POST", "http://test"),
        )
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert "Validation failed" in captured.err


# ---------------------------------------------------------------------------
# handle_response — unknown status codes / fallback
# ---------------------------------------------------------------------------


class TestHandleResponseUnknown:
    def test_unknown_code_extracts_message_field(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(
            429,
            json={"message": "Rate limit exceeded"},
            request=httpx.Request("GET", "http://test"),
        )
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert "Rate limit exceeded" in captured.err

    def test_unknown_code_extracts_error_field(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(
            429,
            json={"error": "Too many requests"},
            request=httpx.Request("GET", "http://test"),
        )
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert "Too many requests" in captured.err

    def test_unknown_code_no_message_field(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(
            418,
            json={"detail": "I'm a teapot"},
            request=httpx.Request("GET", "http://test"),
        )
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert "Unexpected error (HTTP 418)" in captured.err


# ---------------------------------------------------------------------------
# handle_response — verbose mode
# ---------------------------------------------------------------------------


class TestHandleResponseVerbose:
    def test_verbose_prints_raw_details(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(
            500,
            json={"detail": "traceback info"},
            request=httpx.Request("GET", "http://test/api/v1/things"),
        )
        with pytest.raises(typer.Exit):
            handle_response(response, verbose=True)
        captured = capsys.readouterr()
        assert "500" in captured.err
        assert "http://test/api/v1/things" in captured.err


# ---------------------------------------------------------------------------
# handle_response — stderr routing
# ---------------------------------------------------------------------------


class TestHandleResponseStderr:
    def test_error_output_goes_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        response = httpx.Response(500, request=httpx.Request("GET", "http://test"))
        with pytest.raises(typer.Exit):
            handle_response(response)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err != ""


# ---------------------------------------------------------------------------
# require_auth
# ---------------------------------------------------------------------------


class TestRequireAuth:
    def test_exits_when_not_authenticated(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("dreamhubcli.errors.is_authenticated", return_value=False):
            with pytest.raises(typer.Exit):
                require_auth()
        captured = capsys.readouterr()
        assert "Not logged in" in captured.err
        assert "dh auth login" in captured.err

    def test_returns_none_when_authenticated(self) -> None:
        with patch("dreamhubcli.errors.is_authenticated", return_value=True):
            result = require_auth()
        assert result is None
