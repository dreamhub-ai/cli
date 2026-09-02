"""Unit tests for the MCP server tool functions."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
import respx

import dreamhubcli.mcp_server as mcp_server_mod
from dreamhubcli.config import DreamhubConfig, load_config, save_config

API_URL = "https://crm.dreamhub.ai/api/v1"


def _auth(temp_config_dir: Path) -> None:
    save_config(DreamhubConfig(token="pat_test", tenant_id="t-1"))


def _reset_stage_cache() -> None:
    import dreamhubcli.mcp_server as mod

    mod._stage_cache = None


def _get_tool_fn(name: str) -> Any:
    """Get a registered MCP tool function by name."""
    from dreamhubcli.mcp_server import mcp

    component = mcp._local_provider._components.get(f"tool:{name}@")
    assert component is not None, f"Tool '{name}' not registered"
    return component.fn


class TestHelpers:
    def test_ok_success(self) -> None:
        from dreamhubcli.mcp_server import _ok

        response = httpx.Response(200, json={"id": "CO-1"})
        assert _ok(response) == {"id": "CO-1"}

    def test_ok_error(self) -> None:
        from dreamhubcli.mcp_server import _ok

        response = httpx.Response(404, text="Not found")
        result = _ok(response)
        assert result["error"] is True
        assert result["status"] == 404

    def test_ok_401_instructs_login_tool(self) -> None:
        """A 401 that survives the client's own retry must tell the model to call login."""
        from dreamhubcli.mcp_server import _ok

        response = httpx.Response(401, text="Unauthorized")
        result = _ok(response)
        assert result["error"] is True
        assert result["status"] == 401
        assert "login" in result["detail"].lower()
        assert "check_auth_status" in result["detail"]

    def test_enrich_labels(self) -> None:
        from dreamhubcli.mcp_server import _enrich_labels

        record = {"status": 1, "name": "Acme"}
        labels = {"status": {1: "Prospect", 2: "Customer"}}
        result = _enrich_labels(record, labels)
        assert result["statusName"] == "Prospect"
        assert result["status"] == 1

    def test_enrich_labels_unknown_value(self) -> None:
        from dreamhubcli.mcp_server import _enrich_labels

        record = {"status": 99}
        labels = {"status": {1: "Active"}}
        result = _enrich_labels(record, labels)
        assert "statusName" not in result

    def test_enrich_labels_missing_field(self) -> None:
        from dreamhubcli.mcp_server import _enrich_labels

        record = {"name": "Acme"}
        labels = {"status": {1: "Active"}}
        result = _enrich_labels(record, labels)
        assert "statusName" not in result

    def test_enrich_response(self) -> None:
        from dreamhubcli.mcp_server import _enrich_response

        data = {
            "companies": [
                {"id": "CO-1", "status": 1},
                {"id": "CO-2", "status": 2},
            ],
            "total": 2,
        }
        labels = {"status": {1: "Prospect", 2: "Customer"}}
        result = _enrich_response(data, "companies", labels)
        assert result["companies"][0]["statusName"] == "Prospect"
        assert result["companies"][1]["statusName"] == "Customer"

    def test_enrich_response_error_passthrough(self) -> None:
        from dreamhubcli.mcp_server import _enrich_response

        data = {"error": True, "status": 500}
        result = _enrich_response(data, "companies", {"status": {1: "Active"}})
        assert result == data

    def test_enrich_response_no_labels(self) -> None:
        from dreamhubcli.mcp_server import _enrich_response

        data = {"companies": [{"id": "CO-1", "status": 1}]}
        result = _enrich_response(data, "companies", {})
        assert "statusName" not in result["companies"][0]

    def test_enrich_activity(self) -> None:
        from dreamhubcli.mcp_server import _enrich_activity

        activity = {"id": "ACT-1", "type": 9}
        result = _enrich_activity(activity)
        assert result["typeName"] == "Note"

    def test_enrich_activity_unknown_type(self) -> None:
        from dreamhubcli.mcp_server import _enrich_activity

        activity = {"id": "ACT-1", "type": 99}
        result = _enrich_activity(activity)
        assert "typeName" not in result


class TestEntityTypeValidation:
    def test_resolve_valid_entity_type(self) -> None:
        from dreamhubcli.mcp_server import _resolve_entity_resource

        assert _resolve_entity_resource("deals") == "deals"
        assert _resolve_entity_resource("person") == "people"
        assert _resolve_entity_resource("COMPANIES") == "companies"

    def test_resolve_invalid_entity_type(self) -> None:
        from dreamhubcli.mcp_server import _resolve_entity_resource

        with pytest.raises(ValueError, match="Unknown entity type"):
            _resolve_entity_resource("invalid")


class TestAuthError:
    def test_client_raises_when_not_authenticated(self, temp_config_dir: Path) -> None:
        from dreamhubcli.mcp_server import _client

        with pytest.raises(RuntimeError, match="Not logged in"):
            _client()


class TestDynamicStages:
    @respx.mock
    def test_fetch_stage_map(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        _reset_stage_cache()
        respx.get(f"{API_URL}/deals/stages").mock(
            return_value=httpx.Response(
                200,
                json={"stages": [{"id": 1, "name": "Prospecting"}, {"id": 2, "name": "Demo"}]},
            )
        )
        from dreamhubcli.mcp_server import _fetch_stage_map

        result = _fetch_stage_map()
        assert result == {1: "Prospecting", 2: "Demo"}
        _reset_stage_cache()

    @respx.mock
    def test_fetch_stage_map_caches(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        _reset_stage_cache()
        route = respx.get(f"{API_URL}/deals/stages").mock(
            return_value=httpx.Response(200, json={"stages": [{"id": 1, "name": "Prospecting"}]})
        )
        from dreamhubcli.mcp_server import _fetch_stage_map

        _fetch_stage_map()
        _fetch_stage_map()
        assert route.call_count == 1
        _reset_stage_cache()

    @respx.mock
    def test_fetch_stage_map_api_error(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        _reset_stage_cache()
        respx.get(f"{API_URL}/deals/stages").mock(return_value=httpx.Response(500, text="Server error"))
        from dreamhubcli.mcp_server import _fetch_stage_map

        result = _fetch_stage_map()
        assert result == {}
        _reset_stage_cache()

    @respx.mock
    def test_get_effective_labels_with_stages(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        _reset_stage_cache()
        respx.get(f"{API_URL}/deals/stages").mock(
            return_value=httpx.Response(200, json={"stages": [{"id": 1, "name": "Prospecting"}]})
        )
        from dreamhubcli.mcp_server import CRUD_ENTITIES, _get_effective_labels

        labels = _get_effective_labels(CRUD_ENTITIES["deals"])
        assert "stage" in labels
        assert labels["stage"][1] == "Prospecting"
        assert "status" in labels
        _reset_stage_cache()

    def test_get_effective_labels_static_only(self) -> None:
        from dreamhubcli.mcp_server import CRUD_ENTITIES, _get_effective_labels

        labels = _get_effective_labels(CRUD_ENTITIES["companies"])
        assert "status" in labels
        assert labels["status"][1] == "Prospect"


class TestCrudTools:
    @respx.mock
    def test_list_companies_enriched(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/companies/filter").mock(
            return_value=httpx.Response(
                200,
                json={"companies": [{"id": "CO-1", "name": "Acme", "status": 2}], "total": 1},
            )
        )
        result = _get_tool_fn("list_companies")(page=1, page_size=20)
        assert result["companies"][0]["statusName"] == "Customer"

    @respx.mock
    def test_get_company_enriched(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.get(f"{API_URL}/companies/CO-1").mock(
            return_value=httpx.Response(200, json={"id": "CO-1", "name": "Acme", "status": 1})
        )
        result = _get_tool_fn("get_company")(entity_id="CO-1")
        assert result["statusName"] == "Prospect"

    @respx.mock
    def test_filter_leads_enriched(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/leads/filter").mock(
            return_value=httpx.Response(
                200,
                json={"leads": [{"id": "L-1", "status": 5}], "total": 1},
            )
        )
        result = _get_tool_fn("filter_leads")(filters={"status": {"eq": 5}})
        assert result["leads"][0]["statusName"] == "New"

    @respx.mock
    def test_filter_404_returns_empty(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/leads/filter").mock(return_value=httpx.Response(404))
        result = _get_tool_fn("filter_leads")(filters={"status": {"eq": 99}})
        assert result["leads"] == []
        assert result["total"] == 0

    @respx.mock
    def test_delete_company(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.delete(f"{API_URL}/companies/CO-1").mock(return_value=httpx.Response(204))
        result = _get_tool_fn("delete_company")(entity_id="CO-1")
        assert result["deleted"] is True

    @respx.mock
    def test_create_company_enriched(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/companies").mock(return_value=httpx.Response(201, json={"id": "CO-NEW", "status": 1}))
        result = _get_tool_fn("create_company")(data={"name": "New Corp"})
        assert result["statusName"] == "Prospect"

    @respx.mock
    def test_update_task_enriched(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.put(f"{API_URL}/tasks/T-1").mock(
            return_value=httpx.Response(200, json={"id": "T-1", "isCompleted": 1, "isHighPriority": 0})
        )
        result = _get_tool_fn("update_task")(entity_id="T-1", data={"isCompleted": 1})
        assert result["isCompletedName"] == "Completed"
        assert result["isHighPriorityName"] == "Normal"

    @respx.mock
    def test_list_deals_with_dynamic_stages(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        _reset_stage_cache()
        respx.get(f"{API_URL}/deals/stages").mock(
            return_value=httpx.Response(200, json={"stages": [{"id": 3, "name": "Custom Stage"}]})
        )
        respx.post(f"{API_URL}/deals/filter").mock(
            return_value=httpx.Response(
                200,
                json={"deals": [{"id": "D-1", "stage": 3, "status": 1}], "total": 1},
            )
        )
        result = _get_tool_fn("list_deals")(page=1, page_size=20)
        assert result["deals"][0]["stageName"] == "Custom Stage"
        assert result["deals"][0]["statusName"] == "In Progress"
        _reset_stage_cache()


class TestActivityTools:
    @respx.mock
    def test_list_activities_enriched(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/deals/D-1/activities/fetch").mock(
            return_value=httpx.Response(
                200,
                json={"activities": [{"id": "ACT-1", "type": 9}], "total": 1},
            )
        )
        from dreamhubcli.mcp_server import list_activities

        result = list_activities(entity_type="deals", entity_id="D-1")
        assert result["activities"][0]["typeName"] == "Note"

    @respx.mock
    def test_list_activities_with_filters(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        import json

        route = respx.post(f"{API_URL}/deals/D-1/activities/fetch").mock(
            return_value=httpx.Response(200, json={"activities": [], "total": 0})
        )
        from dreamhubcli.mcp_server import list_activities

        list_activities(
            entity_type="deals",
            entity_id="D-1",
            activity_types=[1, 2],
            from_datetime="2026-01-01",
            to_datetime="2026-03-01",
            direction="inbound",
            people_ids=["P-1"],
            tags=["t-1"],
            size=50,
        )
        payload = json.loads(route.calls[0].request.content)
        assert payload["activityTypes"] == [1, 2]
        assert payload["fromDatetime"] == "2026-01-01"
        assert payload["toDatetime"] == "2026-03-01"
        assert payload["direction"] == "inbound"
        assert payload["peopleIds"] == ["P-1"]
        assert payload["activitiesTags"] == ["t-1"]
        assert payload["size"] == 50

    @respx.mock
    def test_get_activity_enriched(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/deals/D-1/activities/fetch").mock(
            return_value=httpx.Response(
                200,
                json={"activities": [{"id": "ACT-1", "type": 1}], "total": 1},
            )
        )
        from dreamhubcli.mcp_server import get_activity

        result = get_activity(entity_type="deals", entity_id="D-1", activity_id="ACT-1")
        assert result["typeName"] == "Call"

    @respx.mock
    def test_get_activity_not_found(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/deals/D-1/activities/fetch").mock(
            return_value=httpx.Response(200, json={"activities": [], "total": 0})
        )
        from dreamhubcli.mcp_server import get_activity

        result = get_activity(entity_type="deals", entity_id="D-1", activity_id="ACT-MISSING")
        assert result["error"] is True

    @respx.mock
    def test_get_activity_api_error(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/deals/D-1/activities/fetch").mock(return_value=httpx.Response(500, text="Server error"))
        from dreamhubcli.mcp_server import get_activity

        result = get_activity(entity_type="deals", entity_id="D-1", activity_id="ACT-1")
        assert result["error"] is True

    @respx.mock
    def test_create_activity(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        import json

        route = respx.post(f"{API_URL}/deals/D-1/activities").mock(
            return_value=httpx.Response(201, json={"id": "ACT-NEW"})
        )
        from dreamhubcli.mcp_server import create_activity

        result = create_activity(
            entity_type="deals",
            entity_id="D-1",
            activity_type=9,
            notes={"summary": "Test"},
            company_id="CO-1",
            deal_id="D-1",
            lead_id="L-1",
            tag_ids=["t-1"],
        )
        assert result["id"] == "ACT-NEW"
        payload = json.loads(route.calls[0].request.content)
        assert payload["companyId"] == "CO-1"
        assert payload["dealId"] == "D-1"
        assert payload["leadId"] == "L-1"
        assert payload["tags"] == ["t-1"]

    def test_list_activity_types(self) -> None:
        from dreamhubcli.mcp_server import list_activity_types

        result = list_activity_types()
        assert len(result) == 9
        names = {r["name"] for r in result}
        assert "Call" in names
        assert "Note" in names


class TestSearchTool:
    @respx.mock
    def test_search(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/search/global").mock(
            return_value=httpx.Response(200, json={"results": [{"id": "CO-1"}], "total": 1})
        )
        from dreamhubcli.mcp_server import search

        result = search(query="Acme", entity_type="companies", filter_by="name", sort_by="name")
        assert result["total"] == 1

    @respx.mock
    def test_search_minimal(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.post(f"{API_URL}/search/global").mock(return_value=httpx.Response(200, json={"results": [], "total": 0}))
        from dreamhubcli.mcp_server import search

        result = search(query="nothing")
        assert result["total"] == 0


class TestHistoryTool:
    @respx.mock
    def test_get_history(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.get(f"{API_URL}/history").mock(return_value=httpx.Response(200, json={"history": [], "total": 0}))
        from dreamhubcli.mcp_server import get_history

        result = get_history(entity_type="company", entity_id="CO-1")
        assert result["total"] == 0

    @respx.mock
    def test_get_history_no_filters(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.get(f"{API_URL}/history").mock(return_value=httpx.Response(200, json={"history": [], "total": 0}))
        from dreamhubcli.mcp_server import get_history

        result = get_history()
        assert result["total"] == 0


class TestReportingTool:
    @respx.mock
    def test_get_report(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.get(f"{API_URL}/reports/kpis").mock(return_value=httpx.Response(200, json={"kpis": {}}))
        from dreamhubcli.mcp_server import get_report

        result = get_report(report_type="kpis")
        assert "kpis" in result

    def test_get_report_invalid_type(self) -> None:
        from dreamhubcli.mcp_server import get_report

        result = get_report(report_type="nonexistent")
        assert result["error"] is True


class TestSettingsTools:
    @respx.mock
    def test_list_settings(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.get(f"{API_URL}/settings/account/").mock(
            return_value=httpx.Response(200, json=[{"key": "currency", "value": "USD"}])
        )
        from dreamhubcli.mcp_server import list_settings

        result = list_settings()
        assert result[0]["key"] == "currency"

    @respx.mock
    def test_get_setting(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.get(f"{API_URL}/settings/account/currency").mock(
            return_value=httpx.Response(200, json={"key": "currency", "value": "USD"})
        )
        from dreamhubcli.mcp_server import get_setting

        result = get_setting(key="currency")
        assert result["value"] == "USD"

    @respx.mock
    def test_set_setting(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.put(f"{API_URL}/settings/account/currency").mock(
            return_value=httpx.Response(200, json={"key": "currency", "value": "EUR"})
        )
        from dreamhubcli.mcp_server import set_setting

        result = set_setting(key="currency", value="EUR")
        assert result["value"] == "EUR"


class TestDealStagesTool:
    @respx.mock
    def test_list_deal_stages(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        respx.get(f"{API_URL}/deals/stages").mock(
            return_value=httpx.Response(
                200,
                json={"stages": [{"id": 1, "name": "Prospecting", "stage_order": 1}]},
            )
        )
        from dreamhubcli.mcp_server import list_deal_stages

        result = list_deal_stages()
        assert result["stages"][0]["name"] == "Prospecting"

    @respx.mock
    def test_list_deal_stages_with_additional_info(self, temp_config_dir: Path) -> None:
        _auth(temp_config_dir)
        route = respx.get(f"{API_URL}/deals/stages").mock(
            return_value=httpx.Response(
                200,
                json={"stages": [{"id": 1, "name": "Prospecting", "deals_count": 5}]},
            )
        )
        from dreamhubcli.mcp_server import list_deal_stages

        result = list_deal_stages(include_additional_info=True)
        assert result["stages"][0]["deals_count"] == 5
        assert "include_additional_info" in str(route.calls[0].request.url)


class TestToolRegistration:
    def test_crud_tools_registered(self) -> None:
        from dreamhubcli.mcp_server import SINGULAR_NAMES, mcp

        components = mcp._local_provider._components
        for entity, singular in SINGULAR_NAMES.items():
            assert f"tool:list_{entity}@" in components, f"list_{entity} not registered"
            assert f"tool:get_{singular}@" in components, f"get_{singular} not registered"
            assert f"tool:create_{singular}@" in components, f"create_{singular} not registered"
            assert f"tool:update_{singular}@" in components, f"update_{singular} not registered"
            assert f"tool:delete_{singular}@" in components, f"delete_{singular} not registered"
            assert f"tool:filter_{entity}@" in components, f"filter_{entity} not registered"

    def test_custom_tools_registered(self) -> None:
        from dreamhubcli.mcp_server import mcp

        components = mcp._local_provider._components
        expected = [
            "list_activities",
            "get_activity",
            "create_activity",
            "list_activity_types",
            "list_deal_stages",
            "search",
            "get_history",
            "get_report",
            "list_settings",
            "get_setting",
            "set_setting",
        ]
        for name in expected:
            assert f"tool:{name}@" in components, f"{name} not registered"

    def test_total_tool_count(self) -> None:
        from dreamhubcli.mcp_server import mcp

        components = mcp._local_provider._components
        tool_keys = [k for k in components if k.startswith("tool:")]
        # 7 entities * 6 CRUD ops = 42 + 11 custom tools + 3 auth tools (check_auth_status, login, update_cli) = 56
        assert len(tool_keys) == 56


class TestUpdateCli:
    def test_success_path(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import shutil
        import subprocess

        monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/pipx" if "pipx" in name else None)
        result = subprocess.CompletedProcess(args=[], returncode=0, stdout="upgraded package dreamhubcli", stderr="")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)

        fn = _get_tool_fn("update_cli")
        response = fn()
        assert response["updated"] is True
        assert "restart" in response["message"]

    def test_already_up_to_date(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import shutil
        import subprocess

        monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/pipx" if "pipx" in name else None)
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="dreamhubcli is already up-to-date", stderr=""
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)

        fn = _get_tool_fn("update_cli")
        response = fn()
        assert response["updated"] is False
        assert "up to date" in response["message"]

    def test_nonzero_exit_returns_failure(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import shutil
        import subprocess

        monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/pipx" if "pipx" in name else None)
        result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="pip error: could not find package"
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)

        fn = _get_tool_fn("update_cli")
        response = fn()
        assert response["updated"] is False
        assert "Update failed" in response["message"]
        assert "pip error" in response["message"]

    def test_timeout_returns_failure(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import shutil
        import subprocess

        monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/pipx" if "pipx" in name else None)

        def _raise_timeout(*a: object, **kw: object) -> None:
            raise subprocess.TimeoutExpired(cmd="pipx", timeout=60)

        monkeypatch.setattr(subprocess, "run", _raise_timeout)

        fn = _get_tool_fn("update_cli")
        response = fn()
        assert response["updated"] is False
        assert "timed out" in response["message"]

    def test_pipx_not_found(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import os
        import shutil

        monkeypatch.setattr(shutil, "which", lambda name: None)
        monkeypatch.setattr(os.path, "isfile", lambda path: False)

        fn = _get_tool_fn("update_cli")
        response = fn()
        assert response["updated"] is False
        assert "pipx not found" in response["message"]


class TestClientCliPatFallback:
    def test_promotes_cli_pat_when_jwt_expired_and_refresh_fails(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        expired_token = jwt.encode({"exp": int(time.time()) - 3600}, "secret", algorithm="HS256")
        cli_pat = "pat_test_cli"
        save_config(
            DreamhubConfig(
                token=expired_token,
                refresh_token="refresh_xyz",
                cli_pat=cli_pat,
                tenant_id="t-1",
            )
        )

        with respx.mock:
            respx.post("https://auth.dreamhub.ai/oauth/token").mock(return_value=httpx.Response(401))
            mcp_server_mod._refresh_token_or_promote_pat()

        config = load_config()
        assert config.token == cli_pat
        assert config.refresh_token is None

    def test_client_raises_when_no_valid_token(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        save_config(DreamhubConfig(token=None, tenant_id="t-1"))

        from dreamhubcli.mcp_server import _client

        with pytest.raises(RuntimeError, match="Not logged in"):
            _client()

    def test_lazy_pat_creation_when_jwt_valid_and_pat_missing(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mcp_server_mod, "_cli_pat_creation_attempted", False)
        valid_token = jwt.encode({"exp": int(time.time()) + 3600}, "secret", algorithm="HS256")
        save_config(DreamhubConfig(token=valid_token, refresh_token="refresh_xyz", tenant_id="t-1"))

        calls: list[DreamhubConfig] = []

        def fake_create(config: DreamhubConfig) -> None:
            calls.append(config)
            cfg = load_config()
            cfg.cli_pat = "pat_lazy_created"
            cfg.cli_pat_id = "pat-lazy-1"
            save_config(cfg)

        monkeypatch.setattr(mcp_server_mod, "create_cli_pat", fake_create)
        mcp_server_mod._refresh_token_or_promote_pat()

        config = load_config()
        assert len(calls) == 1
        assert config.cli_pat == "pat_lazy_created"
        assert config.token == valid_token

    def test_lazy_pat_creation_skipped_when_pat_already_present(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mcp_server_mod, "_cli_pat_creation_attempted", False)
        valid_token = jwt.encode({"exp": int(time.time()) + 3600}, "secret", algorithm="HS256")
        save_config(
            DreamhubConfig(token=valid_token, refresh_token="refresh_xyz", cli_pat="pat_existing", tenant_id="t-1")
        )

        calls: list[object] = []
        monkeypatch.setattr(mcp_server_mod, "create_cli_pat", lambda c: calls.append(c))
        mcp_server_mod._refresh_token_or_promote_pat()

        assert calls == []

    def test_lazy_pat_creation_attempted_at_most_once_on_failure(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mcp_server_mod, "_cli_pat_creation_attempted", False)
        valid_token = jwt.encode({"exp": int(time.time()) + 3600}, "secret", algorithm="HS256")
        save_config(DreamhubConfig(token=valid_token, refresh_token="refresh_xyz", tenant_id="t-1"))

        calls: list[DreamhubConfig] = []
        monkeypatch.setattr(mcp_server_mod, "create_cli_pat", lambda c: calls.append(c))

        # Simulate two back-to-back tool calls; create_cli_pat swallows the error
        # and doesn't write cli_pat, so it stays None — but the flag prevents retry.
        mcp_server_mod._refresh_token_or_promote_pat()
        mcp_server_mod._refresh_token_or_promote_pat()

        assert len(calls) == 1, "create_cli_pat must not be retried after a failed attempt"


class TestToolAnnotations:
    """Risk hints are what let a client skip prompting on reads; an unannotated
    tool prompts identically to a delete, so the prompt stops carrying signal."""

    def _tools(self) -> dict[str, Any]:
        from dreamhubcli.mcp_server import mcp

        return {
            key.removeprefix("tool:").removesuffix("@"): component
            for key, component in mcp._local_provider._components.items()
            if key.startswith("tool:")
        }

    def test_every_registered_tool_advertises_risk_hints(self) -> None:
        unannotated = sorted(name for name, tool in self._tools().items() if tool.annotations is None)

        assert unannotated == []

    def test_reads_are_read_only_and_deletes_are_destructive(self) -> None:
        tools = self._tools()

        assert tools["list_contracts"].annotations.readOnlyHint is True
        assert tools["get_contract"].annotations.readOnlyHint is True
        assert tools["create_contract"].annotations.readOnlyHint is False
        assert tools["create_contract"].annotations.idempotentHint is False
        assert tools["update_contract"].annotations.idempotentHint is True
        assert tools["delete_contract"].annotations.destructiveHint is True

    def test_every_crud_entity_has_a_singular_name(self) -> None:
        """_register_crud_tools indexes SINGULAR_NAMES directly — a gap is an import-time KeyError."""
        assert set(mcp_server_mod.CRUD_ENTITIES) <= set(mcp_server_mod.SINGULAR_NAMES)

    def test_filter_docstring_lists_every_supported_operator(self) -> None:
        description = self._tools()["filter_contracts"].description

        assert "not_in" in description
        assert "between_or_null" in description
