"""dh reporting — fetch sales reports."""

from __future__ import annotations

import typer

from dreamhubcli.client import DreamhubClient
from dreamhubcli.errors import handle_response, require_auth
from dreamhubcli.output import console, print_error, print_json, print_table

app = typer.Typer(name="reporting", help="Fetch sales reports.", no_args_is_help=True)

REPORT_TYPES = [
    "kpis",
    "sales_pipeline_funnel",
    "conversion_rates",
    "win_rate",
    "average_time_spent",
    "stakeholder_mapping",
    "quota_achievement",
    "leads_analysis",
]


@app.command(
    name="get",
    epilog="\b\nExamples:\n  dh reporting get kpis\n  dh reporting get sales_pipeline_funnel --json\n\n"
    "Available reports:\n  " + ", ".join(REPORT_TYPES),
)
def get_report(
    ctx: typer.Context,
    report_type: str = typer.Argument(help=f"Report type ({', '.join(REPORT_TYPES)})."),
    use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
) -> None:
    """Fetch a report by type."""
    require_auth()
    if report_type not in REPORT_TYPES:
        print_error(f"Unknown report type '{report_type}'.")
        console.print(f"[dim]Available: {', '.join(REPORT_TYPES)}[/dim]")
        raise typer.Exit(code=1)
    client = DreamhubClient(api_url=api_url)
    try:
        with console.status(f"Fetching {report_type} report...", spinner="dots"):
            response = client.get(f"reports/{report_type}")
    except KeyboardInterrupt:
        raise typer.Exit(code=1) from None
    handle_response(response, verbose=ctx.obj.get("verbose", False))
    data = response.json()
    if use_json:
        print_json(data)
    else:
        _render_report(report_type, data)


@app.command(
    name="list",
    epilog="\b\nExamples:\n  dh reporting list",
)
def list_reports() -> None:
    """List available report types."""
    table_rows = [{"type": rt} for rt in REPORT_TYPES]
    print_table(table_rows, columns=["type"], title="Available Reports")


def _render_report(report_type: str, data: dict) -> None:
    """Render report data as a table, falling back to raw key-value output."""
    report_data = data.get(report_type) or data.get(_to_camel(report_type)) or data
    if isinstance(report_data, list):
        print_table(report_data, title=report_type.replace("_", " ").title())
    elif isinstance(report_data, dict):
        for key, value in report_data.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                print_table(value, title=key.replace("_", " ").title())
            else:
                console.print(f"  [bold]{key}:[/bold] {value}")
    else:
        console.print(str(report_data))


def _to_camel(snake: str) -> str:
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
