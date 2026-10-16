"""dh access — manage personal access tokens (dev/QA only)."""

from __future__ import annotations

import typer

from dreamhubcli.client import DreamhubClient
from dreamhubcli.errors import handle_response, require_auth
from dreamhubcli.output import console, print_detail, print_json, print_success, print_table

app = typer.Typer(name="access", help="Manage personal access tokens (dev/QA only).", no_args_is_help=True)


@app.command(
    name="token",
    epilog="\b\nExamples:\n  dh access token\n  dh access token --page 2\n  dh access token --json",
)
def get_token(
    ctx: typer.Context,
    page: int = typer.Option(1, "--page", "-p", min=1, help="Page number."),
    page_size: int = typer.Option(20, "--page-size", "-s", min=1, max=100, help="Results per page."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """List the current user's active tokens under every name (metadata only)."""
    require_auth()
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status("Fetching tokens...", spinner="dots"):
            response = client.get("accessenabler/tokens/", params={"page": page, "pageSize": page_size})
    except KeyboardInterrupt:
        raise typer.Exit(code=1) from None
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    if use_json:
        print_json(data)
    else:
        print_table(
            data.get("tokens", []),
            columns=["id", "name", "createdAt", "expiresAt", "lastUsedAt"],
            title=f"Tokens ({data.get('total', 0)} total)",
        )


@app.command(
    name="create-token",
    epilog=(
        "\b\nExamples:\n  dh access create-token --name nightly-export\n"
        "  dh access create-token --name nightly-export --expires-days 90 --json"
    ),
)
def create_token(
    ctx: typer.Context,
    name: str = typer.Option(
        ..., "--name", "-n", help="Token name. Creating a token replaces your other tokens with the same name."
    ),
    expires_days: int = typer.Option(365, "--expires-days", min=1, max=365, help="Days until the token expires."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Create a personal access token, rotating any existing token with the same name."""
    require_auth()
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status("Creating token...", spinner="dots"):
            response = client.post("accessenabler/tokens/", json_payload={"name": name, "expiresInDays": expires_days})
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
