"""dh search — global search across entities."""

from __future__ import annotations

import typer

from dreamhubcli.client import DreamhubClient
from dreamhubcli.errors import handle_response, require_auth
from dreamhubcli.output import console, print_json, print_table

ENTITY_TYPES = ["companies", "people", "leads", "deals"]


def search_command(
    ctx: typer.Context,
    query: str = typer.Argument(help="Search query string."),
    entity_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help=f"Limit to entity type ({', '.join(ENTITY_TYPES)}).",
    ),
    filter_by: str | None = typer.Option(
        None,
        "--filter",
        "-f",
        help="Typesense filter expression (e.g. 'status:=active').",
    ),
    sort_by: str | None = typer.Option(None, "--sort", help="Sort expression (e.g. 'name:asc')."),
    page: int = typer.Option(1, "--page", "-p", help="Page number."),
    page_size: int = typer.Option(20, "--page-size", "-s", help="Results per page."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Search across all Dreamhub entities."""
    require_auth()
    client = DreamhubClient(api_url=api_url)
    payload: dict = {
        "query": query,
        "page": page,
        "pageSize": page_size,
    }
    if entity_type:
        payload["entityTypes"] = [entity_type]
    if filter_by:
        payload["filterBy"] = filter_by
    if sort_by:
        payload["sortBy"] = sort_by
    try:
        with console.status("Searching...", spinner="dots"):
            response = client.post("search/global", json_payload=payload)
    except KeyboardInterrupt:
        raise typer.Exit(code=1) from None
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    if use_json:
        print_json(data)
    else:
        rows = data.get("results", [])
        total = data.get("total", len(rows))
        print_table(rows, columns=["entityType", "id", "name"], title=f"Search: {query}")
        console.print(f"[dim]Page {page} | {len(rows)} of {total} results | {data.get('queryTimeMs', 0)}ms[/dim]")
