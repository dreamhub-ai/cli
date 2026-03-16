"""dh history — view activity and change history."""

from typing import Optional

import typer

from dreamhubcli.client import DreamhubClient
from dreamhubcli.errors import handle_response, require_auth
from dreamhubcli.output import console, print_json, print_table


def history_command(
    ctx: typer.Context,
    entity_type: Optional[str] = typer.Option(None, "--entity-type", help="Filter by entity type."),
    entity_id: Optional[str] = typer.Option(None, "--entity-id", help="Filter by entity ID."),
    page: int = typer.Option(1, "--page", "-p", help="Page number."),
    page_size: int = typer.Option(20, "--page-size", "-s", help="Page size."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """View activity and change history."""
    require_auth()
    client = DreamhubClient(api_url=api_url)
    params: dict[str, str | int] = {"page": page, "pageSize": page_size}
    if entity_type:
        params["entityType"] = entity_type
    if entity_id:
        params["entityId"] = entity_id
    try:
        with console.status("Fetching history...", spinner="dots"):
            response = client.get("history", params=params)
    except KeyboardInterrupt:
        raise typer.Exit(code=1)
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    if use_json:
        print_json(data)
    else:
        rows = data.get("history", [])
        print_table(rows, columns=["id", "entityType", "entityId", "action", "userId", "createdAt"], title="History")
