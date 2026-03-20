"""dh auth — login, logout, and credential status."""

from typing import Optional

import typer
from rich.panel import Panel

from dreamhubcli import __version__
from dreamhubcli.auth import (
    create_cli_pat,
    delete_cli_pat,
    is_authenticated,
    login_with_browser,
    login_with_token,
    logout,
)
from dreamhubcli.client import DreamhubClient
from dreamhubcli.errors import handle_response
from dreamhubcli.output import console, print_error, print_success

app = typer.Typer(name="auth", help="Manage authentication credentials.", no_args_is_help=True)


@app.command(
    epilog=(
        "\b\nExamples:\n"
        "  dh auth login                          # Opens browser for OAuth login\n"
        "  dh auth login --token pat_xxx          # Login with a Personal Access Token\n"
        "  dh auth login --token pat_xxx --tenant-id my-tenant\n"
        "\n"
        "Personal Access Tokens (PATs):\n"
        "  PATs are long-lived API keys for use in CI/CD, scripts, or headless servers.\n"
        "  Create one at: Settings > API Keys in the Dreamhub web app.\n"
        "  Pass it with --token or set the DH_TOKEN environment variable."
    ),
)
def login(
    token: Optional[str] = typer.Option(
        None,
        "--token",
        "-t",
        help="Personal access token (PAT). Create one at Settings > API Keys in the web app.",
    ),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id", help="Tenant ID for x-tenant-id header."),
) -> None:
    """Authenticate with Dreamhub. Pass --token for PAT login, or omit to open the browser."""
    if token:
        login_with_token(token, tenant_id=tenant_id)
        print_success("Logged in successfully with PAT.")
        console.print("[dim]Tip: Run 'dh --install-completion' to enable tab completion in your shell.[/dim]")
    else:
        config = login_with_browser()
        create_cli_pat(config)
        print_success("Logged in successfully via browser.")
        console.print("[dim]Tip: Run 'dh --install-completion' to enable tab completion in your shell.[/dim]")


def _print_status_panel(*, email: str | None = None, tenant: str | None = None) -> None:
    """Render the branded status panel."""
    from dreamhubcli.config import DEFAULT_API_URL

    lines: list[str] = []
    if email:
        lines.append(f"  [bold]User:[/bold]    {email}")
    if tenant:
        lines.append(f"  [bold]Tenant:[/bold]  {tenant}")
    lines.append(f"  [bold]API:[/bold]     {DEFAULT_API_URL}")
    lines.append(f"  [bold]Version:[/bold] {__version__}")
    lines.append("  [bold]Status:[/bold]  [green]Authenticated[/green]")

    panel = Panel("\n".join(lines), border_style="dim", padding=(0, 1))
    console.print(panel)


@app.command(
    epilog="\b\nExamples:\n  dh auth status",
)
def status() -> None:
    """Show current authentication status by verifying the token against the API."""
    if not is_authenticated():
        print_error("Not logged in. Run: dh auth login")
        raise typer.Exit(code=1)

    client = DreamhubClient()
    response = client.get("me")

    if response.status_code == 200:
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            _print_status_panel()
            return
        data = response.json()
        email = data.get("email")
        tenant = data.get("tenantName", data.get("tenant_name"))
        _print_status_panel(email=email, tenant=tenant)
        return

    if response.status_code == 401:
        logout()
        print_error("Token expired. Run: dh auth login")
        raise typer.Exit(code=1)

    if response.status_code == 404:
        # /users/me may not exist for PAT-based auth; token is still valid
        _print_status_panel()
        return

    handle_response(response)


@app.command(
    name="logout",
    epilog="\b\nExamples:\n  dh auth logout",
)
def do_logout() -> None:
    """Clear stored credentials."""
    from dreamhubcli.config import load_config

    config = load_config()
    delete_cli_pat(config)
    logout()
    print_success("Logged out.")
