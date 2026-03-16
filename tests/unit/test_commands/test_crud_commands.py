"""Tests for CRUD entity commands (companies, deals, leads, etc.)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from dreamhubcli.config import DreamhubConfig, save_config
from dreamhubcli.main import app

runner = CliRunner()

API_URL = "https://crm.dreamhub.ai/api/v1"


class TestCompaniesCommands:
    @respx.mock
    def test_list(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        route = respx.post(f"{API_URL}/companies/filter").mock(
            return_value=httpx.Response(
                200,
                json={
                    "companies": [
                        {"id": "CO-AB-1", "name": "Acme", "domain": "acme.com", "industry": "Tech", "status": 1}
                    ],
                    "total": 1,
                    "page": 1,
                    "pageSize": 20,
                },
            )
        )
        result = runner.invoke(app, ["companies", "list"])
        assert result.exit_code == 0
        assert "Acme" in result.output
        assert "Page 1" in result.output
        request = route.calls[0].request
        assert request.url.params["page"] == "1"
        assert request.url.params["size"] == "20"
        assert json.loads(request.content) == {"filters": {}}

    @respx.mock
    def test_list_json(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/companies/filter").mock(
            return_value=httpx.Response(
                200,
                json={
                    "companies": [{"id": "CO-AB-1", "name": "Acme"}],
                    "total": 1,
                    "page": 1,
                    "pageSize": 20,
                },
            )
        )
        result = runner.invoke(app, ["companies", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["companies"][0]["name"] == "Acme"

    @respx.mock
    def test_get(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.get(f"{API_URL}/companies/CO-AB-1").mock(
            return_value=httpx.Response(200, json={"id": "CO-AB-1", "name": "Acme"})
        )
        result = runner.invoke(app, ["companies", "get", "CO-AB-1"])
        assert result.exit_code == 0
        assert "Acme" in result.output

    @respx.mock
    def test_create(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/companies").mock(
            return_value=httpx.Response(201, json={"id": "CO-AB-2", "name": "NewCo"})
        )
        payload = json.dumps({"name": "NewCo"})
        result = runner.invoke(app, ["companies", "create", payload])
        assert result.exit_code == 0
        assert "Created" in result.output
        assert "Next: dh companies get" in result.output

    @respx.mock
    def test_update(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.put(f"{API_URL}/companies/CO-AB-1").mock(
            return_value=httpx.Response(200, json={"id": "CO-AB-1", "name": "Updated"})
        )
        payload = json.dumps({"name": "Updated"})
        result = runner.invoke(app, ["companies", "update", "CO-AB-1", payload])
        assert result.exit_code == 0
        assert "Updated" in result.output
        assert "Next: dh companies get" in result.output

    def test_list_help_shows_examples(self) -> None:
        result = runner.invoke(app, ["companies", "list", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output

    @respx.mock
    def test_delete(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.delete(f"{API_URL}/companies/CO-AB-1").mock(return_value=httpx.Response(204))
        result = runner.invoke(app, ["companies", "delete", "CO-AB-1", "--force"])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    @respx.mock
    def test_list_api_error(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/companies/filter").mock(return_value=httpx.Response(500, text="Internal Server Error"))
        result = runner.invoke(app, ["companies", "list"])
        assert result.exit_code == 1
        assert "Something went wrong" in result.output

    def test_create_invalid_json(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        result = runner.invoke(app, ["companies", "create", "not-json"])
        assert result.exit_code == 1
        assert "Invalid JSON" in result.output

    def test_list_requires_auth(self, temp_config_dir: Path) -> None:
        """CRUD commands require authentication."""
        result = runner.invoke(app, ["companies", "list"])
        assert result.exit_code == 1
        assert "Not logged in" in result.output

    def test_get_requires_auth(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["companies", "get", "CO-AB-1"])
        assert result.exit_code == 1
        assert "Not logged in" in result.output

    @respx.mock
    def test_get_404_shows_entity_name(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.get(f"{API_URL}/companies/CO-NOPE").mock(return_value=httpx.Response(404, json={"message": "not found"}))
        result = runner.invoke(app, ["companies", "get", "CO-NOPE"])
        assert result.exit_code == 1
        assert "company 'CO-NOPE' not found" in result.output

    @respx.mock
    def test_filter_inline(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/companies/filter").mock(
            return_value=httpx.Response(
                200,
                json={
                    "companies": [
                        {"id": "CO-AB-1", "name": "Acme", "domain": "acme.com", "industry": "Tech", "status": 1}
                    ],
                    "total": 1,
                    "page": 1,
                    "pageSize": 20,
                },
            )
        )
        result = runner.invoke(app, ["companies", "filter", "name", "contains_nocase", "Acme"])
        assert result.exit_code == 0
        assert "Acme" in result.output
        assert "Page 1" in result.output

    @respx.mock
    def test_filter_multiple_and(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        route = respx.post(f"{API_URL}/companies/filter").mock(
            return_value=httpx.Response(
                200,
                json={
                    "companies": [{"id": "CO-AB-1", "name": "Acme"}],
                    "total": 1,
                    "page": 1,
                    "pageSize": 20,
                },
            )
        )
        result = runner.invoke(
            app,
            ["companies", "filter", "name", "contains_nocase", "Acme", "and", "status", "eq", "1"],
        )
        assert result.exit_code == 0
        assert "Acme" in result.output
        request = route.calls[0].request
        assert json.loads(request.content) == {
            "filters": {
                "$and": [
                    {"name": {"contains_nocase": "Acme"}},
                    {"status": {"eq": 1}},
                ]
            }
        }

    @respx.mock
    def test_filter_no_args_returns_all(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/companies/filter").mock(
            return_value=httpx.Response(
                200,
                json={
                    "companies": [{"id": "CO-AB-1", "name": "Acme"}],
                    "total": 1,
                    "page": 1,
                    "pageSize": 20,
                },
            )
        )
        result = runner.invoke(app, ["companies", "filter"])
        assert result.exit_code == 0
        assert "Acme" in result.output

    @respx.mock
    def test_filter_json_output(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/companies/filter").mock(
            return_value=httpx.Response(
                200,
                json={
                    "companies": [{"id": "CO-AB-1", "name": "Acme"}],
                    "total": 1,
                    "page": 1,
                    "pageSize": 20,
                },
            )
        )
        result = runner.invoke(app, ["companies", "filter", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["companies"][0]["name"] == "Acme"

    @respx.mock
    def test_filter_from_file(self, temp_config_dir: Path, tmp_path: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/companies/filter").mock(
            return_value=httpx.Response(
                200,
                json={
                    "companies": [{"id": "CO-AB-1", "name": "Acme"}],
                    "total": 1,
                    "page": 1,
                    "pageSize": 20,
                },
            )
        )
        filter_file = tmp_path / "filter.json"
        filter_file.write_text(json.dumps({"filters": {"field": "name", "operator": "eq", "value": "Acme"}}))
        result = runner.invoke(app, ["companies", "filter", "--from", str(filter_file)])
        assert result.exit_code == 0
        assert "Acme" in result.output

    def test_filter_file_not_found(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        result = runner.invoke(app, ["companies", "filter", "--from", "nonexistent.json"])
        assert result.exit_code == 1
        assert "File not found" in result.output

    def test_filter_requires_auth(self, temp_config_dir: Path) -> None:
        result = runner.invoke(app, ["companies", "filter", "name", "eq", "test"])
        assert result.exit_code == 1
        assert "Not logged in" in result.output

    def test_filter_bad_operator(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        result = runner.invoke(app, ["companies", "filter", "name", "ilike", "Acme"])
        assert result.exit_code == 1
        assert "Unknown operator" in result.output

    def test_filter_help_shows_examples(self) -> None:
        result = runner.invoke(app, ["companies", "filter", "--help"])
        assert result.exit_code == 0
        assert "Examples:" in result.output


class TestDealsCommands:
    @respx.mock
    def test_list(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/deals/filter").mock(
            return_value=httpx.Response(
                200,
                json={
                    "deals": [{"id": "D-AB-1", "name": "Big Deal", "stage": 1}],
                    "total": 1,
                    "page": 1,
                    "pageSize": 20,
                },
            )
        )
        result = runner.invoke(app, ["deals", "list"])
        assert result.exit_code == 0
        assert "Big Deal" in result.output


class TestLeadsCommands:
    @respx.mock
    def test_list(self, temp_config_dir: Path) -> None:
        save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))
        respx.post(f"{API_URL}/leads/filter").mock(
            return_value=httpx.Response(
                200,
                json={
                    "leads": [{"id": "L-AB-1", "firstName": "John", "lastName": "Doe", "email": "john@test.com"}],
                    "total": 1,
                    "page": 1,
                    "pageSize": 20,
                },
            )
        )
        result = runner.invoke(app, ["leads", "list"])
        assert result.exit_code == 0
        assert "John" in result.output
