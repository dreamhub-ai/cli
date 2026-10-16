"""Tests for the dev-only `dh access` token commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
import httpx
import respx
from click.testing import Result
from typer.testing import CliRunner

from dreamhubcli.commands import access
from dreamhubcli.config import DreamhubConfig, save_config

runner = CliRunner()

API_URL = "https://crm.dreamhub.ai/api/v1"
TOKENS_URL = f"{API_URL}/accessenabler/tokens/"


def _invoke(args: list[str]) -> Result:
    return runner.invoke(access.app, args, obj={"verbose": False})


def _token(**overrides: Any) -> dict[str, Any]:
    token = {"id": "tok-1", "name": "webapp-pat", "createdAt": "2026-10-01", "expiresAt": "2027-10-01"}
    return {**token, **overrides}


def _token_page(tokens: list[dict[str, Any]], page: int = 1, page_size: int = 20) -> dict[str, Any]:
    return {"tokens": tokens, "total": len(tokens), "page": page, "pageSize": page_size}


class TestAccessToken:
    @respx.mock
    def test_lists_every_token_from_the_list_endpoint(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        route = respx.get(TOKENS_URL).mock(
            return_value=httpx.Response(200, json=_token_page([_token(), _token(id="tok-2", name="nightly-export")]))
        )
        result = _invoke(["token"])
        assert result.exit_code == 0, result.output
        assert route.calls.last.request.url.params["page"] == "1"
        assert route.calls.last.request.url.params["pageSize"] == "20"
        assert "webapp-pat" in result.output
        assert "nightly-export" in result.output

    @respx.mock
    def test_passes_paging_through(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        route = respx.get(TOKENS_URL).mock(return_value=httpx.Response(200, json=_token_page([], page=2, page_size=5)))
        result = _invoke(["token", "--page", "2", "--page-size", "5", "--json"])
        assert result.exit_code == 0, result.output
        assert route.calls.last.request.url.params["page"] == "2"
        assert route.calls.last.request.url.params["pageSize"] == "5"
        assert json.loads(result.output)["total"] == 0

    def test_rejects_page_size_over_100(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        result = _invoke(["token", "--page-size", "101"])
        assert result.exit_code == 2
        assert "--page-size" in click.unstyle(result.output)

    def test_rejects_page_0(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        result = _invoke(["token", "--page", "0"])
        assert result.exit_code == 2
        assert "Invalid value for '--page'" in click.unstyle(result.output)


class TestAccessCreateToken:
    @respx.mock
    def test_sends_name_and_expiry(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        route = respx.post(TOKENS_URL).mock(
            return_value=httpx.Response(201, json=_token(id="tok-3", name="nightly-export", token="pat_new"))
        )
        result = _invoke(["create-token", "--name", "nightly-export", "--expires-days", "90"])
        assert result.exit_code == 0, result.output
        assert json.loads(route.calls.last.request.content) == {"name": "nightly-export", "expiresInDays": 90}
        assert "Personal access token created." in result.output
        assert "pat_new" in result.output

    @respx.mock
    def test_expiry_defaults_to_365(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        route = respx.post(TOKENS_URL).mock(
            return_value=httpx.Response(201, json=_token(id="tok-3", name="nightly-export", token="pat_new"))
        )
        result = _invoke(["create-token", "--name", "nightly-export"])
        assert result.exit_code == 0, result.output
        assert json.loads(route.calls.last.request.content)["expiresInDays"] == 365

    def test_name_is_required(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        result = _invoke(["create-token"])
        assert result.exit_code == 2
        assert "--name" in click.unstyle(result.output)

    def test_rejects_expiry_outside_1_to_365(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        for days in ("0", "366"):
            result = _invoke(["create-token", "--name", "x", "--expires-days", days])
            assert result.exit_code == 2
            assert "--expires-days" in click.unstyle(result.output)

    def test_rejects_name_outside_1_to_256_characters(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        for name in ("", "x" * 257):
            result = _invoke(["create-token", "--name", name])
            assert result.exit_code == 2
            assert "Invalid value for '--name'" in click.unstyle(result.output)
            assert "1-256 characters" in click.unstyle(result.output)

    @respx.mock
    def test_accepts_256_character_name(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        name = "x" * 256
        route = respx.post(TOKENS_URL).mock(return_value=httpx.Response(201, json=_token(name=name, token="pat_new")))
        result = _invoke(["create-token", "--name", name])
        assert result.exit_code == 0, result.output
        assert json.loads(route.calls.last.request.content)["name"] == name

    @respx.mock
    def test_server_422_exits_1(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(TOKENS_URL).mock(
            return_value=httpx.Response(422, json={"detail": "expiresInDays must be at most 365"})
        )
        result = _invoke(["create-token", "--name", "nightly-export"])
        assert result.exit_code == 1
        assert "Validation failed: expiresInDays must be at most 365" in result.output
        assert "Personal access token created." not in result.output
