"""dh activities — manage activities across entities."""

from __future__ import annotations

import json
from typing import Any

import typer

from dreamhubcli.client import DreamhubClient
from dreamhubcli.errors import handle_response, require_auth
from dreamhubcli.output import console, print_detail, print_error, print_json, print_success, print_table

app = typer.Typer(name="activities", help="Manage activities (calls, emails, meetings, notes).", no_args_is_help=True)

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

ACTIVITY_TYPE_NAMES = {v.lower().replace(" ", "-").replace("_", "-"): k for k, v in ACTIVITY_TYPES.items()}


def _resolve_entity_path(entity_type: str) -> str:
    """Map entity type input to API resource path."""
    normalized = entity_type.lower().strip()
    if normalized not in ENTITY_TYPES:
        print_error(f"Unknown entity type '{entity_type}'. Valid: {', '.join(sorted(set(ENTITY_TYPES.values())))}")
        raise typer.Exit(code=1)
    return ENTITY_TYPES[normalized]


def _resolve_activity_type(value: str) -> int:
    """Resolve activity type from name or numeric ID."""
    try:
        type_id = int(value)
        if type_id in ACTIVITY_TYPES:
            return type_id
    except ValueError:
        pass
    normalized = value.lower().strip().replace(" ", "-").replace("_", "-")
    if normalized in ACTIVITY_TYPE_NAMES:
        return ACTIVITY_TYPE_NAMES[normalized]
    print_error(f"Unknown activity type '{value}'.")
    console.print(f"[dim]Valid types: {', '.join(f'{k}={v}' for k, v in ACTIVITY_TYPES.items())}[/dim]")
    raise typer.Exit(code=1)


@app.command(
    name="list",
    epilog="\b\nExamples:\n  dh activities list deals d-acm-1a2b3c4d\n"
    "  dh activities list companies c-acm-1a2b3c4d --type email\n"
    "  dh activities list people p-johd-1a2b3c4d --from 2026-01-01 --to 2026-03-01 --json",
)
def list_activities(
    ctx: typer.Context,
    entity_type: str = typer.Argument(help="Entity type (companies, deals, leads, people, tasks)."),
    entity_id: str = typer.Argument(help="Entity ID."),
    activity_type: str | None = typer.Option(None, "--type", "-t", help="Filter by activity type (name or ID)."),
    from_date: str | None = typer.Option(None, "--from", help="Start date (ISO 8601)."),
    to_date: str | None = typer.Option(None, "--to", help="End date (ISO 8601)."),
    size: int = typer.Option(20, "--size", "-s", help="Max results."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """List activities for an entity."""
    require_auth()
    resource_path = _resolve_entity_path(entity_type)
    client = DreamhubClient(api_url=api_url)
    payload: dict[str, Any] = {"size": size}
    if activity_type:
        payload["activityTypes"] = [_resolve_activity_type(activity_type)]
    if from_date:
        payload["fromDatetime"] = from_date
    if to_date:
        payload["toDatetime"] = to_date
    try:
        with console.status("Fetching activities...", spinner="dots"):
            response = client.post(f"{resource_path}/{entity_id}/activities/fetch", json_payload=payload)
    except KeyboardInterrupt:
        raise typer.Exit(code=1)
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    if use_json:
        print_json(data)
    else:
        rows = data.get("activities", [])
        total = data.get("total", len(rows))
        for row in rows:
            type_id = row.get("type")
            if type_id in ACTIVITY_TYPES:
                row["typeName"] = ACTIVITY_TYPES[type_id]
            notes = row.get("notes") or {}
            row["subject"] = notes.get("subject", notes.get("date", ""))
        print_table(
            rows,
            columns=["id", "typeName", "subject", "createdAt"],
            title=f"Activities for {entity_id}",
        )
        count_per_type = data.get("countPerType", {})
        if isinstance(count_per_type, dict) and count_per_type:
            parts = [
                f"{ACTIVITY_TYPES.get(int(k), k)}: {v}"
                for k, v in count_per_type.items()
                if str(v).isdigit() and int(v) > 0
            ]
            if parts:
                console.print(f"[dim]{' | '.join(parts)} | Total: {total}[/dim]")
        else:
            console.print(f"[dim]{len(rows)} of {total} activities[/dim]")


@app.command(
    name="get",
    epilog="\b\nExamples:\n  dh activities get deals d-acm-1a2b3c4d act-d-acm-1a2b09-5e6f7a8b\n"
    "  dh activities get people p-johd-1a2b3c4d act-p-johd-1a2b09-5e6f7a8b --json",
)
def get_activity(
    ctx: typer.Context,
    entity_type: str = typer.Argument(help="Entity type (companies, deals, leads, people, tasks)."),
    entity_id: str = typer.Argument(help="Entity ID."),
    activity_id: str = typer.Argument(help="Activity ID."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Get a single activity by ID (fetches from the entity's activity list)."""
    require_auth()
    resource_path = _resolve_entity_path(entity_type)
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status("Fetching activity...", spinner="dots"):
            response = client.post(f"{resource_path}/{entity_id}/activities/fetch", json_payload={"size": 100})
    except KeyboardInterrupt:
        raise typer.Exit(code=1)
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    activities = data.get("activities", [])
    match = next((a for a in activities if a.get("id") == activity_id), None)
    if match is None:
        print_error(f"Activity '{activity_id}' not found on {entity_id}.")
        raise typer.Exit(code=1)
    if use_json:
        print_json(match)
    else:
        type_id = match.get("type")
        if type_id in ACTIVITY_TYPES:
            match["typeName"] = ACTIVITY_TYPES[type_id]
        print_detail(match)


@app.command(
    name="create",
    epilog="\b\nExamples:\n"
    '  dh activities create deals d-acm-1a2b3c4d note \'{"date": "2026-03-16", "summary": "Follow-up"}\''
    " --people p-johd-5e6f7a8b --company c-acm-1a2b3c4d\n"
    '  dh activities create leads l-acm-1a2b3c4d call \'{"date": "2026-03-16", "subject": "Discovery"}\''
    " --people p-johd-5e6f7a8b --company c-acm-1a2b3c4d",
)
def create_activity(
    ctx: typer.Context,
    entity_type: str = typer.Argument(help="Entity type (companies, deals, leads, people, tasks)."),
    entity_id: str = typer.Argument(help="Entity ID."),
    activity_type: str = typer.Argument(help="Activity type (call, email, note, online-meeting, etc.)."),
    notes_json: str = typer.Argument(help="Activity notes as JSON."),
    people: list[str] = typer.Option([], "--people", "-p", help="Person ID(s) to associate."),
    company: str | None = typer.Option(None, "--company", "-c", help="Company ID to associate."),
    deal: str | None = typer.Option(None, "--deal", "-d", help="Deal ID to associate."),
    lead: str | None = typer.Option(None, "--lead", "-l", help="Lead ID to associate."),
    tags: list[str] = typer.Option([], "--tag", help="Activity tag ID(s)."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Create an activity on an entity."""
    require_auth()
    resource_path = _resolve_entity_path(entity_type)
    type_id = _resolve_activity_type(activity_type)
    try:
        notes = json.loads(notes_json)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON for notes: {e}")
        raise typer.Exit(code=1)
    payload: dict[str, Any] = {
        "type": type_id,
        "notes": notes,
        "peopleIds": people,
    }
    if company:
        payload["companyId"] = company
    if deal:
        payload["dealId"] = deal
    if lead:
        payload["leadId"] = lead
    if tags:
        payload["tags"] = tags
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status("Creating activity...", spinner="dots"):
            response = client.post(f"{resource_path}/{entity_id}/activities", json_payload=payload)
    except KeyboardInterrupt:
        raise typer.Exit(code=1)
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    if use_json:
        print_json(data)
    else:
        print_success(f"Created {ACTIVITY_TYPES.get(type_id, 'activity')} on {entity_id}.")
        print_detail(data)


@app.command(
    name="update",
    epilog="\b\nExamples:\n"
    '  dh activities update deals d-acm-1a2b3c4d act-d-acm-1a2b09-5e6f7a8b \'{"notes": {"subject": "Updated"}}\'',
)
def update_activity(
    ctx: typer.Context,
    entity_type: str = typer.Argument(help="Entity type."),
    entity_id: str = typer.Argument(help="Entity ID."),
    activity_id: str = typer.Argument(help="Activity ID."),
    payload: str = typer.Argument(help="JSON payload for update."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Update an activity."""
    require_auth()
    resource_path = _resolve_entity_path(entity_type)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        raise typer.Exit(code=1)
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status("Updating activity...", spinner="dots"):
            response = client.put(f"{resource_path}/{entity_id}/activities/{activity_id}", json_payload=parsed)
    except KeyboardInterrupt:
        raise typer.Exit(code=1)
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    if use_json:
        print_json(data)
    else:
        print_success(f"Updated activity {activity_id}.")
        print_detail(data)


@app.command(
    name="delete",
    epilog="\b\nExamples:\n  dh activities delete deals d-acm-1a2b3c4d act-d-acm-1a2b09-5e6f7a8b",
)
def delete_activity(
    ctx: typer.Context,
    entity_type: str = typer.Argument(help="Entity type."),
    entity_id: str = typer.Argument(help="Entity ID."),
    activity_id: str = typer.Argument(help="Activity ID."),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Delete an activity."""
    require_auth()
    resource_path = _resolve_entity_path(entity_type)
    if not force:
        confirmed = typer.confirm(f"Delete activity {activity_id}?")
        if not confirmed:
            raise typer.Abort()
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status("Deleting activity...", spinner="dots"):
            response = client.delete(f"{resource_path}/{entity_id}/activities/{activity_id}")
    except KeyboardInterrupt:
        raise typer.Exit(code=1)
    handle_response(
        response,
        verbose=ctx.obj.get("verbose", False),
        entity_name=f"activity '{activity_id}'",
    )
    print_success(f"Deleted activity {activity_id}.")


@app.command(
    name="types",
    epilog="\b\nExamples:\n  dh activities types\n  dh activities types --json",
)
def list_types(
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
) -> None:
    """List available activity types."""
    rows = [{"id": k, "name": v} for k, v in ACTIVITY_TYPES.items()]
    if use_json:
        print_json(rows)
    else:
        print_table(rows, columns=["id", "name"], title="Activity Types")
