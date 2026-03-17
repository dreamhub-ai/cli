"""MCP server exposing Dreamhub CLI commands as tools for Claude Desktop."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from dreamhubcli.client import DreamhubClient
from dreamhubcli.errors import require_auth

mcp = FastMCP("dreamhub", instructions="Dreamhub CRM tools. Requires `dh auth login` first.")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CRUD_ENTITIES = {
    "companies": {
        "path": "companies",
        "key": "companies",
        "labels": {"status": {1: "Prospect", 2: "Customer", 3: "Churned", 4: "On Hold", 5: "Disqualified"}},
    },
    "deals": {
        "path": "deals",
        "key": "deals",
        "labels": {
            "status": {1: "In Progress", 2: "Stuck", 4: "Won", 5: "Lost"},
            "stage": {
                1: "Prospecting",
                2: "Demo",
                3: "Demo to DMs",
                4: "Waiting Data POC",
                5: "POC",
                6: "Pilot",
                7: "Proposal",
                8: "Negotiation",
                9: "Closed Won",
                10: "Closed Lost",
            },
        },
    },
    "leads": {
        "path": "leads",
        "key": "leads",
        "labels": {
            "status": {1: "Disqualified", 2: "Qualified", 3: "Converted", 4: "Stuck", 5: "New", 6: "In Progress"},
        },
    },
    "people": {
        "path": "people",
        "key": "people",
        "labels": {
            "status": {
                1: "New",
                2: "Greenfield",
                3: "Engaged in Deal",
                4: "Engaged in Lead",
                5: "Engaged",
                6: "Active Customer",
                7: "Disqualified",
            },
        },
    },
    "users": {
        "path": "users",
        "key": "users",
        "labels": {"status": {1: "Active", 2: "Inactive", 3: "Pending", 4: "Expired"}},
    },
    "tasks": {
        "path": "tasks",
        "key": "tasks",
        "labels": {
            "isCompleted": {1: "Completed", 0: "Open"},
            "isHighPriority": {1: "High", 0: "Normal"},
        },
    },
}


def _client() -> DreamhubClient:
    require_auth()
    return DreamhubClient()


def _ok(response: Any) -> dict:
    """Return JSON from response, raising on HTTP errors."""
    if response.status_code >= 400:
        return {"error": True, "status": response.status_code, "detail": response.text[:500]}
    return response.json()


def _enrich_labels(record: dict, labels: dict[str, dict[int, str]]) -> dict:
    """Add human-readable *Name fields for integer-coded fields."""
    for field, mapping in labels.items():
        value = record.get(field)
        if isinstance(value, int) and value in mapping:
            record[f"{field}Name"] = mapping[value]
    return record


def _enrich_response(data: dict, collection_key: str, labels: dict[str, dict[int, str]]) -> dict:
    """Enrich a list response by resolving labels on each row."""
    if "error" in data or not labels:
        return data
    rows = data.get(collection_key, [])
    for row in rows:
        _enrich_labels(row, labels)
    return data


# ---------------------------------------------------------------------------
# CRUD tools (generated for each entity type)
# ---------------------------------------------------------------------------


def _register_crud_tools() -> None:
    for entity, cfg in CRUD_ENTITIES.items():
        path = cfg["path"]
        key = cfg["key"]
        labels = cfg.get("labels", {})
        singular = entity.rstrip("s") if not entity.endswith("ies") else entity[:-3] + "y"

        def _make_list(p: str = path, k: str = key, lbl: dict = labels) -> Any:
            def list_entities(page: int = 1, page_size: int = 20) -> dict:
                client = _client()
                response = client.request(
                    "POST", f"{p}/filter", params={"page": page, "size": page_size}, json_payload={"filters": {}}
                )
                data = _ok(response)
                return _enrich_response(data, k, lbl)

            return list_entities

        def _make_get(p: str = path, lbl: dict = labels) -> Any:
            def get_entity(entity_id: str) -> dict:
                client = _client()
                response = client.get(f"{p}/{entity_id}")
                data = _ok(response)
                if "error" not in data and lbl:
                    _enrich_labels(data, lbl)
                return data

            return get_entity

        def _make_create(p: str = path, lbl: dict = labels) -> Any:
            def create_entity(data: dict) -> dict:
                client = _client()
                response = client.post(p, json_payload=data)
                result = _ok(response)
                if "error" not in result and lbl:
                    _enrich_labels(result, lbl)
                return result

            return create_entity

        def _make_update(p: str = path, lbl: dict = labels) -> Any:
            def update_entity(entity_id: str, data: dict) -> dict:
                client = _client()
                response = client.put(f"{p}/{entity_id}", json_payload=data)
                result = _ok(response)
                if "error" not in result and lbl:
                    _enrich_labels(result, lbl)
                return result

            return update_entity

        def _make_delete(p: str = path) -> Any:
            def delete_entity(entity_id: str) -> dict:
                client = _client()
                response = client.delete(f"{p}/{entity_id}")
                if response.status_code == 204:
                    return {"deleted": True, "id": entity_id}
                return _ok(response)

            return delete_entity

        def _make_filter(p: str = path, k: str = key, lbl: dict = labels) -> Any:
            def filter_entities(filters: dict, page: int = 1, page_size: int = 20) -> dict:
                client = _client()
                response = client.request(
                    "POST", f"{p}/filter", params={"page": page, "size": page_size}, json_payload={"filters": filters}
                )
                if response.status_code == 404:
                    return {k: [], "total": 0, "page": page, "pageSize": page_size}
                data = _ok(response)
                return _enrich_response(data, k, lbl)

            return filter_entities

        list_fn = _make_list()
        list_fn.__name__ = f"list_{entity}"
        list_fn.__doc__ = f"List {entity} (paginated)."
        mcp.tool()(list_fn)

        get_fn = _make_get()
        get_fn.__name__ = f"get_{singular}"
        get_fn.__doc__ = f"Get a single {singular} by ID."
        mcp.tool()(get_fn)

        create_fn = _make_create()
        create_fn.__name__ = f"create_{singular}"
        create_fn.__doc__ = f"Create a new {singular}. Pass entity fields as data."
        mcp.tool()(create_fn)

        update_fn = _make_update()
        update_fn.__name__ = f"update_{singular}"
        update_fn.__doc__ = f"Update an existing {singular}. Pass changed fields as data."
        mcp.tool()(update_fn)

        delete_fn = _make_delete()
        delete_fn.__name__ = f"delete_{singular}"
        delete_fn.__doc__ = f"Delete a {singular} by ID."
        mcp.tool()(delete_fn)

        filter_fn = _make_filter()
        filter_fn.__name__ = f"filter_{entity}"
        filter_fn.__doc__ = (
            f"Filter {entity} by field conditions. "
            "Operators: eq, ne, gt, gte, lt, lte, in, nin, contains, contains_nocase, between, not_null."
        )
        mcp.tool()(filter_fn)


_register_crud_tools()


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

ACTIVITY_TYPES = {
    1: "Call",
    2: "Email",
    3: "Text",
    4: "In-Person Meeting",
    5: "Online Meeting",
    6: "Quote Sent",
    7: "NDA Sent",
    8: "NDA Completed",
    9: "Note",
}
ENTITY_TYPES = {
    "company": "companies",
    "companies": "companies",
    "deal": "deals",
    "deals": "deals",
    "lead": "leads",
    "leads": "leads",
    "person": "people",
    "people": "people",
    "task": "tasks",
    "tasks": "tasks",
}


@mcp.tool()
def list_activities(
    entity_type: str,
    entity_id: str,
    activity_types: list[int] | None = None,
    from_datetime: str | None = None,
    to_datetime: str | None = None,
    direction: str | None = None,
    people_ids: list[str] | None = None,
    tags: list[str] | None = None,
    size: int = 20,
) -> dict:
    """List activities for an entity (deal, company, lead, person, task)."""
    resource = ENTITY_TYPES.get(entity_type.lower().strip(), entity_type)
    client = _client()
    payload: dict[str, Any] = {"size": size}
    if activity_types:
        payload["activityTypes"] = activity_types
    if from_datetime:
        payload["fromDatetime"] = from_datetime
    if to_datetime:
        payload["toDatetime"] = to_datetime
    if direction:
        payload["direction"] = direction
    if people_ids:
        payload["peopleIds"] = people_ids
    if tags:
        payload["activitiesTags"] = tags
    response = client.post(f"{resource}/{entity_id}/activities/fetch", json_payload=payload)
    data = _ok(response)
    if "error" not in data:
        for activity in data.get("activities", []):
            _enrich_activity(activity)
    return data


def _enrich_activity(activity: dict) -> dict:
    """Add typeName to an activity record."""
    type_id = activity.get("type")
    if isinstance(type_id, int) and type_id in ACTIVITY_TYPES:
        activity["typeName"] = ACTIVITY_TYPES[type_id]
    return activity


@mcp.tool()
def get_activity(entity_type: str, entity_id: str, activity_id: str) -> dict:
    """Get a single activity by ID from an entity's activity list."""
    resource = ENTITY_TYPES.get(entity_type.lower().strip(), entity_type)
    client = _client()
    response = client.post(f"{resource}/{entity_id}/activities/fetch", json_payload={"size": 500})
    data = _ok(response)
    if "error" in data:
        return data
    for activity in data.get("activities", []):
        if activity.get("id") == activity_id:
            return _enrich_activity(activity)
    return {"error": True, "detail": f"Activity '{activity_id}' not found on {entity_id}."}


@mcp.tool()
def create_activity(
    entity_type: str,
    entity_id: str,
    activity_type: int,
    notes: dict,
    people_ids: list[str] | None = None,
    company_id: str | None = None,
    deal_id: str | None = None,
    lead_id: str | None = None,
    tag_ids: list[str] | None = None,
) -> dict:
    """Create an activity on an entity.

    Activity types: 1=Call, 2=Email, 3=Text, 4=In-Person Meeting,
    5=Online Meeting, 6=Quote Sent, 7=NDA Sent, 8=NDA Completed, 9=Note.
    """
    resource = ENTITY_TYPES.get(entity_type.lower().strip(), entity_type)
    client = _client()
    payload: dict[str, Any] = {"type": activity_type, "notes": notes, "peopleIds": people_ids or []}
    if company_id:
        payload["companyId"] = company_id
    if deal_id:
        payload["dealId"] = deal_id
    if lead_id:
        payload["leadId"] = lead_id
    if tag_ids:
        payload["tags"] = tag_ids
    response = client.post(f"{resource}/{entity_id}/activities", json_payload=payload)
    return _ok(response)


@mcp.tool()
def list_activity_types() -> list[dict]:
    """List available activity types."""
    return [{"id": k, "name": v} for k, v in ACTIVITY_TYPES.items()]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@mcp.tool()
def search(
    query: str,
    entity_type: str | None = None,
    filter_by: str | None = None,
    sort_by: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Search across all Dreamhub entities (companies, people, leads, deals)."""
    client = _client()
    payload: dict[str, Any] = {"query": query, "page": page, "pageSize": page_size}
    if entity_type:
        payload["entityTypes"] = [entity_type]
    if filter_by:
        payload["filterBy"] = filter_by
    if sort_by:
        payload["sortBy"] = sort_by
    response = client.post("search/global", json_payload=payload)
    return _ok(response)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@mcp.tool()
def get_history(
    entity_type: str | None = None,
    entity_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """View activity and change history."""
    client = _client()
    params: dict[str, Any] = {"page": page, "pageSize": page_size}
    if entity_type:
        params["entityType"] = entity_type
    if entity_id:
        params["entityId"] = entity_id
    response = client.get("history", params=params)
    return _ok(response)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

REPORT_TYPES = [
    "kpis",
    "sales_pipeline_funnel",
    "conversion_rates",
    "win_rate",
    "average_time_spent",
    "stakeholder_mapping",
    "quota_achievement",
    "leads_analysis",
]


@mcp.tool()
def get_report(report_type: str) -> dict:
    """Fetch a sales report.

    Types: kpis, sales_pipeline_funnel, conversion_rates, win_rate,
    average_time_spent, stakeholder_mapping, quota_achievement, leads_analysis.
    """
    if report_type not in REPORT_TYPES:
        return {"error": True, "detail": f"Unknown report type '{report_type}'. Valid: {', '.join(REPORT_TYPES)}"}
    client = _client()
    response = client.get(f"reports/{report_type}")
    return _ok(response)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@mcp.tool()
def list_settings() -> dict | list:
    """List all account settings."""
    client = _client()
    response = client.get("settings/account/")
    return _ok(response)


@mcp.tool()
def get_setting(key: str) -> dict:
    """Get a specific account setting by key."""
    client = _client()
    response = client.get(f"settings/account/{key}")
    return _ok(response)


@mcp.tool()
def set_setting(key: str, value: str) -> dict:
    """Update an account setting."""
    client = _client()
    response = client.put(f"settings/account/{key}", json_payload={"value": value})
    return _ok(response)
