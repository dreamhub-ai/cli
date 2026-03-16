"""dh settings — manage account settings."""

from typing import Any, Optional

import typer

from dreamhubcli.client import DreamhubClient
from dreamhubcli.errors import handle_response, require_auth
from dreamhubcli.output import console, print_detail, print_json, print_success, print_table

app = typer.Typer(name="settings", help="Manage account settings.", no_args_is_help=True)


@app.command(
    name="list",
    epilog="\b\nExamples:\n  dh settings list\n  dh settings list --json",
)
def list_settings(
    ctx: typer.Context,
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """List all account settings."""
    require_auth()
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status("Fetching settings...", spinner="dots"):
            response = client.get("settings/account/")
    except KeyboardInterrupt:
        raise typer.Exit(code=1)
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    if use_json:
        print_json(data)
    else:
        rows = data if isinstance(data, list) else [data]
        print_table(rows, columns=["key", "value", "valueType", "category", "description"], title="Settings")


@app.command(
    name="get",
    epilog="\b\nExamples:\n  dh settings get fiscal_year_start\n  dh settings get account_currency --json",
)
def get_setting(
    ctx: typer.Context,
    key: str = typer.Argument(help="Setting key (e.g. fiscal_year_start, account_currency)."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Get a specific account setting by key."""
    require_auth()
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status(f"Fetching setting {key}...", spinner="dots"):
            response = client.get(f"settings/account/{key}")
    except KeyboardInterrupt:
        raise typer.Exit(code=1)
    handle_response(response, verbose=ctx.obj.get("verbose", False), entity_name=f"setting '{key}'")
    data = response.json()
    if use_json:
        print_json(data)
    else:
        print_detail(data)


@app.command(
    name="set",
    epilog="\b\nExamples:\n  dh settings set account_currency EUR\n"
    "  dh settings set is_arr true\n  dh settings set fiscal_year_start 2025-01-01",
)
def set_setting(
    ctx: typer.Context,
    key: str = typer.Argument(help="Setting key."),
    value: str = typer.Argument(help="New value."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Update an account setting."""
    require_auth()
    client = DreamhubClient(api_url=api_url)
    payload: dict[str, Any] = {"value": value}
    try:
        with console.status(f"Updating {key}...", spinner="dots"):
            response = client.put(f"settings/account/{key}", json_payload=payload)
    except KeyboardInterrupt:
        raise typer.Exit(code=1)
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    if use_json:
        print_json(data)
    else:
        print_success(f"Updated {key}.")
        print_detail(data)
