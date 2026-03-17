"""dh mcp — MCP server for Claude Desktop integration."""

from __future__ import annotations

import json
import platform
import shutil
from pathlib import Path

import typer

from dreamhubcli.output import console, print_error, print_success

app = typer.Typer(name="mcp", help="Claude Desktop MCP integration.", no_args_is_help=True)


def _claude_desktop_config_path() -> Path:
    """Return the Claude Desktop config file path for the current OS."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if system == "Linux":
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    if system == "Windows":
        import os

        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".claude" / "claude_desktop_config.json"


def _find_dh_binary() -> str:
    """Resolve the absolute path to the dh binary."""
    path = shutil.which("dh")
    if path:
        return path
    return "dh"


@app.command(
    name="serve",
    epilog="\b\nExamples:\n  dh mcp serve",
)
def serve() -> None:
    """Start the MCP server over stdio (used by Claude Desktop)."""
    from dreamhubcli.mcp_server import mcp

    mcp.run(transport="stdio")


@app.command(
    name="install",
    epilog="\b\nExamples:\n  dh mcp install\n  dh mcp install --dry-run",
)
def install(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print config without writing."),
) -> None:
    """Configure Claude Desktop to use Dreamhub as an MCP tool provider."""
    dh_path = _find_dh_binary()
    server_config = {
        "command": dh_path,
        "args": ["mcp", "serve"],
    }

    config_path = _claude_desktop_config_path()

    if dry_run:
        console.print(f"[bold]Config path:[/bold] {config_path}")
        console.print("[bold]Server block:[/bold]")
        console.print_json(json.dumps({"mcpServers": {"dreamhub": server_config}}))
        return

    # Read existing config or start fresh
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}
    else:
        existing = {}

    # Merge our server into mcpServers
    servers = existing.setdefault("mcpServers", {})
    servers["dreamhub"] = server_config

    # Write back
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(existing, indent=2) + "\n")

    print_success("Dreamhub MCP server installed.")
    console.print(f"[dim]Config: {config_path}[/dim]")
    console.print(f"[dim]Binary: {dh_path}[/dim]")
    console.print("[dim]Restart Claude Desktop to activate.[/dim]")


@app.command(
    name="uninstall",
    epilog="\b\nExamples:\n  dh mcp uninstall",
)
def uninstall() -> None:
    """Remove Dreamhub from Claude Desktop configuration."""
    config_path = _claude_desktop_config_path()
    if not config_path.exists():
        print_error("Claude Desktop config not found.")
        raise typer.Exit(code=1)
    try:
        existing = json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        print_error("Could not read Claude Desktop config.")
        raise typer.Exit(code=1)

    servers = existing.get("mcpServers", {})
    if "dreamhub" not in servers:
        console.print("[dim]Dreamhub not found in Claude Desktop config.[/dim]")
        return

    del servers["dreamhub"]
    config_path.write_text(json.dumps(existing, indent=2) + "\n")
    print_success("Dreamhub MCP server removed.")
    console.print("[dim]Restart Claude Desktop to apply.[/dim]")
