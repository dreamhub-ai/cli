"""dh auth — login, logout, and credential status."""

from typing import Optional

import typer

from dreamhubcli.auth import is_authenticated, login_with_browser, login_with_token, logout
from dreamhubcli.client import DreamhubClient
from dreamhubcli.config import load_config
from dreamhubcli.errors import handle_response
from dreamhubcli.output import console, print_error, print_success

app = typer.Typer(name="auth", help="Manage authentication credentials.", no_args_is_help=True)


@app.command(
    epilog="\b\nExamples:\n  dh auth login --token pat_xxx --tenant-id my-tenant\n  dh auth login",
)
def login(
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Personal access token (PAT)."),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id", help="Tenant ID for x-tenant-id header."),
) -> None:
    """Authenticate with Dreamhub. Pass --token for PAT login, or omit to open the browser."""
    if token:
        login_with_token(token, tenant_id=tenant_id)
        print_success("Logged in successfully with PAT.")
        console.print("[dim]Tip: Run 'dh --install-completion' to enable tab completion in your shell.[/dim]")
    else:
        login_with_browser()
        print_success("Logged in successfully via browser.")
        console.print("[dim]Tip: Run 'dh --install-completion' to enable tab completion in your shell.[/dim]")


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
            # /me resolved to frontend HTML, not an API endpoint
            console.print("Logged in (token set)")
            return
        data = response.json()
        email = data.get("email", "unknown")
        tenant = data.get("tenantName", data.get("tenant_name", "unknown"))
        console.print(f"Logged in as {email} ({tenant})")
        return

    if response.status_code == 401:
        logout()
        print_error("Token expired. Run: dh auth login")
        raise typer.Exit(code=1)

    if response.status_code == 404:
        # /users/me may not exist for PAT-based auth; token is still valid
        console.print("Logged in (token set)")
        return

    handle_response(response)


@app.command(
    epilog="\b\nExamples:\n  dh auth set-tenant my-tenant-id",
)
def set_tenant(
    tenant_id: str = typer.Argument(help="The tenant ID to set."),
) -> None:
    """Set or update the tenant ID without changing the token."""
    config = load_config()
    if not config.token:
        print_error("Not logged in. Run: dh auth login")
        raise typer.Exit(code=1)
    login_with_token(config.token, tenant_id=tenant_id)
    print_success(f"Tenant ID set to: {tenant_id}")


@app.command(
    epilog="\b\nExamples:\n  dh auth set-url https://crm.dreamhub.ai/api/v1",
)
def set_url(
    api_url: str = typer.Argument(help="The API base URL."),
) -> None:
    """Override the API base URL."""
    from dreamhubcli.config import save_config

    config = load_config()
    config.api_url = api_url
    save_config(config)
    print_success(f"API URL set to: {api_url}")


ENVIRONMENTS = {
    "prod": {
        "api_url": "https://crm.dreamhub.ai/api/v1",
        "auth_url": "https://crm-auth.dreamhub.ai",
        "client_id": "bc32f08d-8c43-4360-bd68-fa1f320c0560",
    },
}


@app.command(
    epilog="\b\nExamples:\n  dh auth set-env prod",
)
def set_env(
    env: str = typer.Argument(help="Environment name (e.g. prod)."),
) -> None:
    """Switch API and auth URLs to a named environment."""
    from dreamhubcli.config import save_config

    if env not in ENVIRONMENTS:
        print_error(f"Unknown environment '{env}'. Choose from: {', '.join(ENVIRONMENTS)}")
        raise typer.Exit(code=1)

    env_config = ENVIRONMENTS[env]
    config = load_config()
    config.api_url = env_config["api_url"]
    config.auth_url = env_config["auth_url"]
    config.client_id = env_config["client_id"]
    save_config(config)
    print_success(f"Switched to {env}: {env_config['api_url']}")


@app.command(
    name="logout",
    epilog="\b\nExamples:\n  dh auth logout",
)
def do_logout() -> None:
    """Clear stored credentials."""
    logout()
    print_success("Logged out.")
