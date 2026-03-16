"""Output formatting for Dreamhub CLI.

Supports Rich tables for human-readable output and raw JSON for machine consumption.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()
error_console = Console(stderr=True)

_STATUS_COLORS: dict[str, str] = {
    # Green — healthy/active/successful states
    "active": "green",
    "customer": "green",
    "won": "green",
    "qualified": "green",
    "converted": "green",
    "completed": "green",
    "closed_won": "green",
    # Red — negative/closed/failed states
    "churned": "red",
    "lost": "red",
    "inactive": "red",
    "disqualified": "red",
    "expired": "red",
    "failed": "red",
    "closed_lost": "red",
    "high": "red",
    # Yellow — in-progress/transitional states
    "prospect": "yellow",
    "pending": "yellow",
    "in_progress": "yellow",
    "stuck": "yellow",
    "on_hold": "yellow",
    "new": "yellow",
    "prospecting": "yellow",
    # Cyan — neutral/open states
    "open": "cyan",
    "normal": "cyan",
}


def color_status(value: Any) -> str:
    """Wrap a status value in Rich color markup based on its meaning.

    Performs case-insensitive lookup (spaces are normalized to underscores).
    Returns the value unchanged if no color mapping is found.
    Handles non-string values (int, None, etc.) by converting to string first.
    """
    if value is None:
        return ""
    str_value = str(value)
    normalized = str_value.lower().replace(" ", "_")
    color = _STATUS_COLORS.get(normalized)
    if color:
        return f"[{color}]{str_value}[/{color}]"
    return str_value


def print_json(data: Any) -> None:
    """Print raw JSON to stdout."""
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def print_table(
    rows: list[dict[str, Any]],
    columns: list[str] | None = None,
    title: str | None = None,
    status_columns: list[str] | None = None,
    label_maps: dict[str, dict[int, str]] | None = None,
) -> None:
    """Render a list of dicts as a Rich table.

    Column headers are derived from dict keys (converted from camelCase to snake_case for readability).

    Args:
        rows: List of dicts to render.
        columns: Columns to display. If None, all keys from the first row are used.
        title: Optional table title.
        status_columns: Column names whose values should be color-coded via color_status().
        label_maps: Per-column value-to-label mappings (e.g. {\"status\": {1: \"Prospect\"}}).
    """
    if not rows:
        console.print("[dim]No results found.[/dim]")
        return

    if columns is None:
        columns = list(rows[0].keys())

    # Drop columns where every row has an empty/None value
    columns = [col for col in columns if any(row.get(col) not in (None, "", "None") for row in rows)]

    status_set = set(status_columns) if status_columns else set()
    labels = label_maps or {}

    table = Table(title=title, show_lines=False)
    for column_name in columns:
        header = _camel_to_snake(column_name)
        table.add_column(header, overflow="fold")

    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column, "")
            # Apply label mapping if available
            if column in labels and value in labels[column]:
                display = labels[column][value]
            else:
                display = str(value) if value is not None else ""
            if column in status_set:
                display = color_status(display)
            cells.append(display)
        table.add_row(*cells)

    console.print(table)


def print_detail(data: dict[str, Any], title: str | None = None) -> None:
    """Render a single object as a key-value list."""
    if title:
        console.print(f"[bold]{title}[/bold]")

    for key, value in data.items():
        if key == "actions":
            continue
        header = _camel_to_snake(key)
        console.print(f"  [bold]{header}:[/bold] {value}")

    actions = data.get("actions", [])
    if actions:
        console.print("\n  [bold]actions:[/bold]")
        for action in actions:
            console.print(f"    - {action['name']} → {action['method']} {action['uri']}")


def print_error(message: str) -> None:
    error_console.print(f"[red]Error:[/red] {message}")


def print_success(message: str) -> None:
    console.print(f"[green]{message}[/green]")


def print_warning(message: str) -> None:
    error_console.print(f"[yellow]Warning:[/yellow] {message}")


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case for display headers."""
    result: list[str] = []
    for char in name:
        if char.isupper() and result:
            result.append("_")
        result.append(char.lower())
    return "".join(result)
