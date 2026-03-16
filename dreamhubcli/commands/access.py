"""dh access — manage personal access tokens (dev/QA only)."""

from __future__ import annotations

import typer

from dreamhubcli.client import DreamhubClient
from dreamhubcli.errors import handle_response, require_auth
from dreamhubcli.output import console, print_detail, print_json, print_success

app = typer.Typer(name="access", help="Manage personal access tokens (dev/QA only).", no_args_is_help=True)


@app.command(
    name="token",
    epilog="\b\nExamples:\n  dh access token\n  dh access token --json",
)
def get_token(
    ctx: typer.Context,
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Show current user's token metadata."""
    require_auth()
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status("Fetching token info...", spinner="dots"):
            response = client.get("accessenabler/tokens/me")
    except KeyboardInterrupt:
        raise typer.Exit(code=1) from None
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    if use_json:
        print_json(data)
    else:
        print_detail(data, title="Token")


@app.command(
    name="create-token",
    epilog="\b\nExamples:\n  dh access create-token\n  dh access create-token --json",
)
def create_token(
    ctx: typer.Context,
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Create a new personal access token."""
    require_auth()
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status("Creating token...", spinner="dots"):
            response = client.post("accessenabler/tokens")
    except KeyboardInterrupt:
        raise typer.Exit(code=1) from None
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    if use_json:
        print_json(data)
    else:
        print_success("Personal access token created.")
        print_detail(data)


@app.command(
    name="delete-token",
    epilog="\b\nExamples:\n  dh access delete-token pat-abc123\n  dh access delete-token pat-abc123 --force",
)
def delete_token(
    ctx: typer.Context,
    token_id: str = typer.Argument(help="Token ID to delete."),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Delete a personal access token."""
    require_auth()
    if not force:
        confirmed = typer.confirm(f"Delete token {token_id}?")
        if not confirmed:
            raise typer.Abort()
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status(f"Deleting token {token_id}...", spinner="dots"):
            response = client.delete(f"accessenabler/tokens/{token_id}")
    except KeyboardInterrupt:
        raise typer.Exit(code=1) from None
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    print_success(f"Deleted token {token_id}.")
