"""dh enrichment — trigger entity enrichment (dev/QA only).

Uses the /integrations/enrichment/ gateway path which is only available
in non-production environments.
"""

from __future__ import annotations

import typer

from dreamhubcli.client import DreamhubClient
from dreamhubcli.errors import handle_response, require_auth
from dreamhubcli.output import console, print_error, print_json, print_success

app = typer.Typer(name="enrichment", help="Trigger entity enrichment (dev/QA only).", no_args_is_help=True)

ENTITY_TYPES = ["people", "companies"]


@app.command(
    name="trigger",
    epilog="\b\nExamples:\n  dh enrichment trigger people\n  dh enrichment trigger companies --json",
)
def trigger_enrichment(
    ctx: typer.Context,
    entity_type: str = typer.Argument(help=f"Entity type to enrich ({', '.join(ENTITY_TYPES)})."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Trigger enrichment for an entity type."""
    require_auth()
    if entity_type not in ENTITY_TYPES:
        print_error(f"Unknown entity type '{entity_type}'. Choose from: {', '.join(ENTITY_TYPES)}")
        raise typer.Exit(code=1)
    client = DreamhubClient(api_url=api_url)
    url = f"{client.origin}/integrations/enrichment/trigger/{entity_type}"
    try:
        with console.status(f"Triggering {entity_type} enrichment...", spinner="dots"):
            response = client.request("POST", url, json_payload={})
    except KeyboardInterrupt:
        raise typer.Exit(code=1) from None
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    if use_json:
        print_json(response.json() if response.content else {})
    else:
        print_success(f"Enrichment triggered for {entity_type}.")
