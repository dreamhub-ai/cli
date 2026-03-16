"""Dreamhub CLI — unified command-line interface for all Dreamhub APIs.

Usage:
    dh <command> <subcommand> [options]

Examples:
    dh auth login --token pat_xxx --tenant-id my-tenant
    dh companies list --json
    dh deals get D-AB-1234
    dh search "Acme Corp"
"""

from __future__ import annotations

from typing import Optional

import typer

from dreamhubcli import __version__
from dreamhubcli.commands import (
    access,
    activities,
    auth,
    companies,
    deals,
    enrichment,
    history,
    leads,
    people,
    reporting,
    search,
    settings,
    tasks,
    users,
)
from dreamhubcli.config import is_dev_environment

app = typer.Typer(
    name="dh",
    help="Dreamhub CLI — unified command-line interface for all Dreamhub APIs.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
    epilog="Run 'dh COMMAND --help' for command-specific examples.",
)


def _version_callback(value: bool) -> None:
    if value:
        from dreamhubcli.output import console

        console.print(f"[bold]Dreamhub CLI[/bold] v{__version__}")
        console.print(f"[dim]https://github.com/dreamhub-ai/cli[/dim]")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed error output."),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    """Dreamhub CLI — unified command-line interface for all Dreamhub APIs."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    if ctx.invoked_subcommand is None:
        pass


app.add_typer(activities.app)
app.add_typer(auth.app)
app.add_typer(companies.app)
app.add_typer(deals.app)
app.add_typer(leads.app)
app.add_typer(people.app)
app.add_typer(users.app)
app.add_typer(settings.app)
app.command(
    name="history",
    help="View activity and change history.",
    epilog="\b\nExamples:\n  dh history\n  dh history --entity-type company --entity-id CO-AB-1",
)(history.history_command)
app.add_typer(tasks.app)
app.command(
    name="search",
    help="Search across all Dreamhub entities.",
    epilog='\b\nExamples:\n  dh search "Acme Corp"\n  dh search "Acme" --type companies --json',
)(search.search_command)
app.add_typer(reporting.app)

# Dev/QA only commands — hidden in production
if is_dev_environment():
    app.add_typer(enrichment.app)
    app.add_typer(access.app)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
