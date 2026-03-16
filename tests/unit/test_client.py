"""Tests for dreamhubcli.client module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx
import typer

from dreamhubcli.client import DreamhubClient
from dreamhubcli.config import DEFAULT_API_URL, DreamhubConfig, save_config


class TestDreamhubClient:
    def test_uses_default_base_url(self, temp_config_dir: Path) -> None:
        client = DreamhubClient()
        assert client.base_url == DEFAULT_API_URL

    def test_override_base_url(self, temp_config_dir: Path) -> None:
        client = DreamhubClient(api_url="https://override.api/v2")
        assert client.base_url == "https://override.api/v2"

    def test_strips_trailing_slash(self, temp_config_dir: Path) -> None:
        client = DreamhubClient(api_url="https://api.com/v1/")
        assert client.base_url == "https://api.com/v1"

    @respx.mock
    def test_get_request(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        route = respx.get("https://api.test/v1/companies").mock(
            return_value=httpx.Response(200, json={"companies": []})
        )
        client = DreamhubClient(api_url="https://api.test/v1")
        response = client.get("companies")
        assert response.status_code == 200
        assert response.json() == {"companies": []}
        assert route.called
        request = route.calls[0].request
        assert request.headers["authorization"] == "Bearer pat_test"
        assert request.headers["x-tenant-id"] == "t-1"

    @respx.mock
    def test_post_request_with_payload(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        route = respx.post("https://api.test/v1/companies").mock(
            return_value=httpx.Response(201, json={"id": "CO-AB-1"})
        )
        client = DreamhubClient(api_url="https://api.test/v1")
        response = client.post("companies", json_payload={"name": "Acme"})
        assert response.status_code == 201
        assert route.called

    @respx.mock
    def test_patch_request(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        route = respx.patch("https://api.test/v1/companies/CO-AB-1").mock(
            return_value=httpx.Response(200, json={"id": "CO-AB-1", "name": "Updated"})
        )
        client = DreamhubClient(api_url="https://api.test/v1")
        response = client.patch("companies/CO-AB-1", json_payload={"name": "Updated"})
        assert response.status_code == 200
        assert route.called

    @respx.mock
    def test_delete_request(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        route = respx.delete("https://api.test/v1/companies/CO-AB-1").mock(return_value=httpx.Response(204))
        client = DreamhubClient(api_url="https://api.test/v1")
        response = client.delete("companies/CO-AB-1")
        assert response.status_code == 204
        assert route.called

    @respx.mock
    def test_get_with_params(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        route = respx.get("https://api.test/v1/companies", params={"page": "1", "pageSize": "20"}).mock(
            return_value=httpx.Response(200, json={"companies": [], "total": 0})
        )
        client = DreamhubClient(api_url="https://api.test/v1")
        response = client.get("companies", params={"page": "1", "pageSize": "20"})
        assert response.status_code == 200
        assert route.called


class TestClientNetworkErrors:
    """Network error handling produces friendly messages and exit code 1."""

    @respx.mock
    def test_timeout_produces_friendly_message(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        respx.get("https://api.test/v1/companies").mock(side_effect=httpx.ReadTimeout("timed out"))
        client = DreamhubClient(api_url="https://api.test/v1")
        with pytest.raises(typer.Exit) as exc_info:
            client.get("companies")
        assert exc_info.value.exit_code == 1

    @respx.mock
    def test_connect_error_produces_friendly_message(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        respx.get("https://api.test/v1/companies").mock(side_effect=httpx.ConnectError("connection refused"))
        client = DreamhubClient(api_url="https://api.test/v1")
        with pytest.raises(typer.Exit) as exc_info:
            client.get("companies")
        assert exc_info.value.exit_code == 1

    @respx.mock
    def test_generic_request_error_produces_friendly_message(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        respx.get("https://api.test/v1/companies").mock(side_effect=httpx.RequestError("something broke"))
        client = DreamhubClient(api_url="https://api.test/v1")
        with pytest.raises(typer.Exit) as exc_info:
            client.get("companies")
        assert exc_info.value.exit_code == 1


class TestClient429Retry:
    """429 responses trigger automatic retry with backoff."""

    @respx.mock
    @patch("dreamhubcli.client.time.sleep")
    def test_429_retries_and_succeeds(self, mock_sleep, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        respx.get("https://api.test/v1/companies").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "1"}),
                httpx.Response(200, json={"companies": []}),
            ]
        )
        client = DreamhubClient(api_url="https://api.test/v1")
        response = client.get("companies")
        assert response.status_code == 200
        mock_sleep.assert_called_once_with(1)

    @respx.mock
    @patch("dreamhubcli.client.time.sleep")
    def test_429_exhausts_retries(self, mock_sleep, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        respx.get("https://api.test/v1/companies").mock(return_value=httpx.Response(429, headers={"Retry-After": "1"}))
        client = DreamhubClient(api_url="https://api.test/v1")
        response = client.get("companies")
        # After 3 retries, returns the 429 response
        assert response.status_code == 429
        assert mock_sleep.call_count == 3

    @respx.mock
    @patch("dreamhubcli.client.time.sleep")
    def test_429_uses_retry_after_header(self, mock_sleep, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        respx.get("https://api.test/v1/companies").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "5"}),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        client = DreamhubClient(api_url="https://api.test/v1")
        response = client.get("companies")
        assert response.status_code == 200
        mock_sleep.assert_called_once_with(5)

    @respx.mock
    @patch("dreamhubcli.client.time.sleep")
    def test_429_defaults_retry_after_to_2(self, mock_sleep, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test"))
        respx.get("https://api.test/v1/companies").mock(
            side_effect=[
                httpx.Response(429),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        client = DreamhubClient(api_url="https://api.test/v1")
        response = client.get("companies")
        assert response.status_code == 200
        mock_sleep.assert_called_once_with(2)
