"""Shared factory for standard CRUD entity commands.

Each entity command module calls `build_crud_app()` to get a Typer sub-app
with list/get/create/update/delete commands wired to the correct API path.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from dreamhubcli.client import DreamhubClient
from dreamhubcli.errors import handle_response, require_auth
from dreamhubcli.output import console, print_detail, print_error, print_json, print_success, print_table


def _resolve_columns(
    all_fields: bool,
    fields: str | None,
    default: list[str] | None,
) -> list[str] | None:
    if all_fields:
        return None
    if fields:
        return [f.strip() for f in fields.split(",")]
    return default


_FILTER_OPERATORS = {
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "nin",
    "not_in",
    "contains",
    "contains_nocase",
    "between",
    "between_or_null",
    "not_null",
}


def _parse_inline_filters(args: list[str]) -> list[dict[str, Any]] | None:
    """Parse positional filter args into {field: {op: value}} dicts.

    Format: FIELD OP VALUE [and FIELD OP VALUE ...]
    Output: [{"name": {"contains_nocase": "Acme"}}, {"status": {"eq": 1}}]

    Examples:
        ["name", "contains_nocase", "Acme"]
        ["status", "eq", "1", "and", "name", "contains_nocase", "Acme"]
        ["email", "not_null"]
    """
    # Split on "and" keyword into groups
    groups: list[list[str]] = []
    current: list[str] = []
    for token in args:
        if token.lower() == "and" and current:
            groups.append(current)
            current = []
        else:
            current.append(token)
    if current:
        groups.append(current)

    conditions: list[dict[str, Any]] = []
    for group in groups:
        if len(group) < 2:
            print_error(f"Expected: FIELD OPERATOR [VALUE], got: {' '.join(group)}")
            return None
        field, operator = group[0], group[1].lower()
        if operator not in _FILTER_OPERATORS:
            print_error(f"Unknown operator '{operator}'. Valid: {', '.join(sorted(_FILTER_OPERATORS))}")
            return None
        if operator == "not_null":
            conditions.append({field: {operator: True}})
        elif len(group) < 3:
            print_error(f"Missing value: {field} {operator} <value>")
            return None
        elif operator in ("in", "nin", "not_in"):
            values = [_coerce_value(v.strip()) for v in " ".join(group[2:]).split(",")]
            conditions.append({field: {operator: values}})
        elif operator in ("between", "between_or_null"):
            parts = [_coerce_value(v.strip()) for v in " ".join(group[2:]).split(",")]
            if len(parts) != 2:
                print_error(f"{operator} requires two comma-separated values: {field} {operator} low,high")
                return None
            conditions.append({field: {operator: parts}})
        else:
            raw_value = " ".join(group[2:])
            value: Any = _coerce_value(raw_value)
            conditions.append({field: {operator: value}})
    return conditions


def _coerce_value(raw: str) -> Any:
    """Coerce a string value to int, float, or bool when appropriate."""
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def build_crud_app(
    *,
    name: str,
    resource_path: str,
    collection_key: str,
    help_text: str,
    display_columns: list[str] | None = None,
    status_columns: list[str] | None = None,
    label_maps: dict[str, dict[int, str]] | None = None,
    singular_name: str | None = None,
) -> typer.Typer:
    """Create a Typer sub-app with standard CRUD commands for an entity.

    Args:
        name: CLI command name (e.g. "companies").
        resource_path: API path segment (e.g. "companies").
        collection_key: Key in the list response JSON that holds the array (e.g. "companies").
        help_text: Help string for the command group.
        display_columns: Columns to show in list output. If None, all columns are shown.
        status_columns: Columns whose values should be color-coded by status.
        singular_name: Override for the singular form (e.g. "person" for "people").
    """
    app = typer.Typer(name=name, help=help_text, no_args_is_help=True)
    singular = singular_name or (name[:-3] + "y" if name.endswith("ies") else name.rstrip("s"))

    @app.command(
        name="list",
        help=f"List all {name} (paginated).",
        epilog=f"\b\nExamples:\n  dh {name} list\n  dh {name} list --page 2 --json",
    )
    def list_entities(
        ctx: typer.Context,
        page: int = typer.Option(1, "--page", "-p", help="Page number."),
        page_size: int = typer.Option(20, "--page-size", "-s", help="Results per page."),
        use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
        all_fields: bool = typer.Option(False, "--all-fields", help="Show all fields in output."),
        fields: str | None = typer.Option(None, "--fields", help="Comma-separated list of fields to show."),
        api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
    ) -> None:
        require_auth()
        if page < 1 or page_size < 1:
            print_error("--page and --page-size must be >= 1")
            raise typer.Exit(code=1)
        if all_fields and fields:
            print_error("--all-fields and --fields are mutually exclusive")
            raise typer.Exit(code=1)
        client = DreamhubClient(api_url=api_url)
        try:
            with console.status(f"Fetching {name}...", spinner="dots"):
                response = client.request(
                    "POST",
                    f"{resource_path}/filter",
                    params={"page": page, "size": page_size},
                    json_payload={"filters": {}},
                )
        except KeyboardInterrupt:
            raise typer.Exit(code=1)
        if response.status_code == 404:
            if use_json:
                print_json({collection_key: [], "total": 0, "page": page, "pageSize": page_size})
            else:
                console.print(f"[dim]No {name} found.[/dim]")
            return
        handle_response(response, verbose=ctx.obj.get("verbose", False))
        data = response.json()
        if use_json:
            print_json(data)
        else:
            rows = data.get(collection_key, [])
            total = data.get("total", len(rows))
            current_page = data.get("page", page)
            columns_override = _resolve_columns(all_fields, fields, display_columns)
            print_table(
                rows,
                columns=columns_override,
                title=name.title(),
                status_columns=status_columns,
                label_maps=label_maps,
            )
            console.print(f"[dim]Page {current_page} | {len(rows)} of {total} results[/dim]")

    @app.command(
        name="get",
        help=f"Get a single {singular} by ID.",
        epilog=f"\b\nExamples:\n  dh {name} get <ID>\n  dh {name} get <ID> --json",
    )
    def get_entity(
        ctx: typer.Context,
        entity_id: str = typer.Argument(help=f"{singular.title()} ID."),
        use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
        api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
    ) -> None:
        require_auth()
        client = DreamhubClient(api_url=api_url)
        try:
            with console.status(f"Fetching {singular} {entity_id}...", spinner="dots"):
                response = client.get(f"{resource_path}/{entity_id}")
                handle_response(
                    response,
                    verbose=ctx.obj.get("verbose", False),
                    entity_name=f"{singular} '{entity_id}'",
                )
        except KeyboardInterrupt:
            raise typer.Exit(code=1)
        data = response.json()
        if use_json:
            print_json(data)
        else:
            print_detail(data)

    @app.command(
        name="create",
        help=f"Create a new {singular}.",
        epilog=f'\b\nExamples:\n  dh {name} create \'{{"name": "Example"}}\'',
    )
    def create_entity(
        ctx: typer.Context,
        payload: str = typer.Argument(help="JSON payload for creation."),
        use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
        api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
    ) -> None:
        require_auth()
        client = DreamhubClient(api_url=api_url)
        try:
            parsed_payload: dict[str, Any] = json.loads(payload)
        except json.JSONDecodeError as e:
            print_error(f"Invalid JSON: {e}")
            raise typer.Exit(code=1)
        try:
            with console.status(f"Creating {singular}...", spinner="dots"):
                response = client.post(resource_path, json_payload=parsed_payload)
                handle_response(response, verbose=ctx.obj.get("verbose", False))
        except KeyboardInterrupt:
            raise typer.Exit(code=1)
        data = response.json()
        if use_json:
            print_json(data)
        else:
            print_success(f"Created {singular} successfully.")
            print_detail(data)
            entity_id = data.get("id", "")
            if entity_id:
                console.print(f"[dim]Next: dh {name} get {entity_id}[/dim]")

    @app.command(
        name="update",
        help=f"Update an existing {singular}.",
        epilog=f'\b\nExamples:\n  dh {name} update <ID> \'{{"name": "Updated"}}\'',
    )
    def update_entity(
        ctx: typer.Context,
        entity_id: str = typer.Argument(help=f"{singular.title()} ID."),
        payload: str = typer.Argument(help="JSON payload for update."),
        use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
        api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
    ) -> None:
        require_auth()
        client = DreamhubClient(api_url=api_url)
        try:
            parsed_payload: dict[str, Any] = json.loads(payload)
        except json.JSONDecodeError as e:
            print_error(f"Invalid JSON: {e}")
            raise typer.Exit(code=1)
        try:
            with console.status(f"Updating {singular} {entity_id}...", spinner="dots"):
                response = client.put(f"{resource_path}/{entity_id}", json_payload=parsed_payload)
                handle_response(response, verbose=ctx.obj.get("verbose", False))
        except KeyboardInterrupt:
            raise typer.Exit(code=1)
        data = response.json()
        if use_json:
            print_json(data)
        else:
            print_success(f"Updated {singular} successfully.")
            print_detail(data)
            console.print(f"[dim]Next: dh {name} get {entity_id}[/dim]")

    @app.command(
        name="delete",
        help=f"Delete a {singular} by ID.",
        epilog=f"\b\nExamples:\n  dh {name} delete <ID>\n  dh {name} delete <ID> --force",
    )
    def delete_entity(
        ctx: typer.Context,
        entity_id: str = typer.Argument(help=f"{singular.title()} ID."),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation."),
        api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
    ) -> None:
        require_auth()
        if not force:
            confirmed = typer.confirm(f"Delete {singular} {entity_id}?")
            if not confirmed:
                raise typer.Abort()
        client = DreamhubClient(api_url=api_url)
        try:
            with console.status(f"Deleting {singular} {entity_id}...", spinner="dots"):
                response = client.delete(f"{resource_path}/{entity_id}")
                handle_response(
                    response,
                    verbose=ctx.obj.get("verbose", False),
                    entity_name=f"{singular} '{entity_id}'",
                )
        except KeyboardInterrupt:
            raise typer.Exit(code=1)
        print_success(f"Deleted {singular} {entity_id}.")

    _filter_epilog = "\b\n" + "\n".join(
        [
            "Examples:",
            f"  dh {name} filter name contains_nocase Acme",
            f"  dh {name} filter status eq 1",
            f"  dh {name} filter status eq 1 and name contains_nocase Acme",
            f"  dh {name} filter --from filter.json",
            "",
            "Operators: eq ne gt gte lt lte in nin not_in contains contains_nocase between between_or_null not_null",
        ]
    )

    @app.command(
        name="filter",
        help=f"Filter {name} by field conditions.",
        epilog=_filter_epilog,
        context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
    )
    def filter_entities(
        ctx: typer.Context,
        from_file: str | None = typer.Option(None, "--from", help="Read filter from JSON file."),
        page: int = typer.Option(1, "--page", "-p", help="Page number."),
        page_size: int = typer.Option(20, "--page-size", "-s", help="Results per page."),
        use_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
        all_fields: bool = typer.Option(False, "--all-fields", help="Show all fields in output."),
        fields: str | None = typer.Option(None, "--fields", help="Comma-separated list of fields to show."),
        api_url: str | None = typer.Option(None, "--api-url", help="Override API base URL."),
    ) -> None:
        require_auth()
        if page < 1 or page_size < 1:
            print_error("--page and --page-size must be >= 1")
            raise typer.Exit(code=1)
        if all_fields and fields:
            print_error("--all-fields and --fields are mutually exclusive")
            raise typer.Exit(code=1)
        parsed_payload: dict[str, Any]
        extra_args = ctx.args
        if from_file:
            try:
                with open(from_file) as f:
                    parsed_payload = json.load(f)
            except FileNotFoundError:
                print_error(f"File not found: {from_file}")
                raise typer.Exit(code=1)
            except json.JSONDecodeError as e:
                print_error(f"Invalid JSON in {from_file}: {e}")
                raise typer.Exit(code=1)
        elif extra_args:
            conditions = _parse_inline_filters(extra_args)
            if conditions is None:
                raise typer.Exit(code=1)
            if len(conditions) == 1:
                parsed_payload = {"filters": conditions[0]}
            else:
                parsed_payload = {"filters": {"$and": conditions}}
        else:
            parsed_payload = {"filters": {}}
        client = DreamhubClient(api_url=api_url)
        try:
            with console.status(f"Filtering {name}...", spinner="dots"):
                response = client.request(
                    "POST",
                    f"{resource_path}/filter",
                    params={"page": page, "size": page_size},
                    json_payload=parsed_payload,
                )
        except KeyboardInterrupt:
            raise typer.Exit(code=1)
        # 404 means no results for filter — not an error
        if response.status_code == 404:
            if use_json:
                print_json({collection_key: [], "total": 0, "page": page, "pageSize": page_size})
            else:
                console.print(f"[dim]No {name} found matching the filter.[/dim]")
            return
        handle_response(response, verbose=ctx.obj.get("verbose", False))
        data = response.json()
        if use_json:
            print_json(data)
        else:
            rows = data.get(collection_key, [])
            total = data.get("total", len(rows))
            current_page = data.get("page", page)
            columns_override = _resolve_columns(all_fields, fields, display_columns)
            print_table(
                rows,
                columns=columns_override,
                title=name.title(),
                status_columns=status_columns,
                label_maps=label_maps,
            )
            console.print(f"[dim]Page {current_page} | {len(rows)} of {total} results[/dim]")

    return app
