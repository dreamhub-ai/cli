"""Unit tests for dh activities commands."""

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


def _auth(temp_config_dir: Path) -> None:
    save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))


class TestListActivities:
    @respx.mock
    def test_list_activities_table(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/deals/D-AB-1/activities/fetch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "ACT-1",
                            "type": 9,
                            "notes": {"date": "2026-03-16", "summary": "Follow-up"},
                            "createdAt": "2026-03-16T10:00:00Z",
                        }
                    ],
                    "total": 1,
                    "countPerType": {"9": 1},
                },
            )
        )
        result = runner.invoke(app, ["activities", "list", "deals", "D-AB-1"])
        assert result.exit_code == 0
        assert "ACT-1" in result.output
        assert "Note" in result.output

    @respx.mock
    def test_list_activities_json(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/deals/D-AB-1/activities/fetch").mock(
            return_value=httpx.Response(200, json={"activities": [], "total": 0})
        )
        result = runner.invoke(app, ["activities", "list", "deals", "D-AB-1", "--json"])
        assert result.exit_code == 0
        assert '"total"' in result.output

    @respx.mock
    def test_list_with_type_filter(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        route = respx.post(f"{API_URL}/deals/D-AB-1/activities/fetch").mock(
            return_value=httpx.Response(200, json={"activities": [], "total": 0})
        )
        result = runner.invoke(app, ["activities", "list", "deals", "D-AB-1", "--type", "email"])
        assert result.exit_code == 0
        assert route.called
        payload = json.loads(route.calls[0].request.content)
        assert payload["activityTypes"] == [2]

    @respx.mock
    def test_list_with_date_range(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        route = respx.post(f"{API_URL}/companies/CO-AB-1/activities/fetch").mock(
            return_value=httpx.Response(200, json={"activities": [], "total": 0})
        )
        result = runner.invoke(
            app, ["activities", "list", "companies", "CO-AB-1", "--from", "2026-01-01", "--to", "2026-03-01"]
        )
        assert result.exit_code == 0
        payload = json.loads(route.calls[0].request.content)
        assert payload["fromDatetime"] == "2026-01-01"
        assert payload["toDatetime"] == "2026-03-01"

    def test_list_invalid_entity_type(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        result = runner.invoke(app, ["activities", "list", "widgets", "W-1"])
        assert result.exit_code == 1
        assert "Unknown entity type" in result.output


class TestCreateActivity:
    @respx.mock
    def test_create_note(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/deals/D-AB-1/activities").mock(
            return_value=httpx.Response(201, json={"id": "ACT-NEW"})
        )
        result = runner.invoke(
            app,
            [
                "activities", "create", "deals", "D-AB-1", "note",
                '{"date": "2026-03-16", "summary": "Test"}',
                "--company", "CO-AB-1",
            ],
        )
        assert result.exit_code == 0
        assert "Created" in result.output

    @respx.mock
    def test_create_with_people_and_tags(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        route = respx.post(f"{API_URL}/leads/L-AB-1/activities").mock(
            return_value=httpx.Response(201, json={"id": "ACT-NEW"})
        )
        result = runner.invoke(
            app,
            [
                "activities", "create", "leads", "L-AB-1", "call",
                '{"date": "2026-03-16", "subject": "Discovery"}',
                "--people", "P-AB-1", "--people", "P-AB-2",
                "--company", "CO-AB-1", "--tag", "ato-4e5a1118",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(route.calls[0].request.content)
        assert payload["type"] == 1
        assert payload["peopleIds"] == ["P-AB-1", "P-AB-2"]
        assert payload["tags"] == ["ato-4e5a1118"]

    def test_create_invalid_json(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        result = runner.invoke(app, ["activities", "create", "deals", "D-AB-1", "note", "not-json"])
        assert result.exit_code == 1
        assert "Invalid JSON" in result.output

    def test_create_invalid_activity_type(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        result = runner.invoke(
            app, ["activities", "create", "deals", "D-AB-1", "teleport", '{"date": "2026-03-16"}']
        )
        assert result.exit_code == 1
        assert "Unknown activity type" in result.output


class TestUpdateActivity:
    @respx.mock
    def test_update_activity(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.put(f"{API_URL}/deals/D-AB-1/activities/ACT-1").mock(
            return_value=httpx.Response(200, json={"id": "ACT-1", "type": 9})
        )
        result = runner.invoke(
            app, ["activities", "update", "deals", "D-AB-1", "ACT-1", '{"notes": {"summary": "Updated"}}']
        )
        assert result.exit_code == 0
        assert "Updated" in result.output

    def test_update_invalid_json(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        result = runner.invoke(app, ["activities", "update", "deals", "D-AB-1", "ACT-1", "{bad}"])
        assert result.exit_code == 1


class TestDeleteActivity:
    @respx.mock
    def test_delete_activity_with_force(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.delete(f"{API_URL}/deals/D-AB-1/activities/ACT-1").mock(
            return_value=httpx.Response(204)
        )
        result = runner.invoke(app, ["activities", "delete", "deals", "D-AB-1", "ACT-1", "--force"])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_delete_activity_abort(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        result = runner.invoke(app, ["activities", "delete", "deals", "D-AB-1", "ACT-1"], input="n\n")
        assert result.exit_code != 0


class TestListTypes:
    def test_list_activity_types(self) -> None:
        result = runner.invoke(app, ["activities", "types"])
        assert result.exit_code == 0
        assert "Call" in result.output
        assert "Email" in result.output
        assert "Note" in result.output
