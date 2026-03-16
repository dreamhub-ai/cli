"""Tests for dreamhubcli.output module."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from dreamhubcli.output import _camel_to_snake, color_status, print_json, print_table


class TestCamelToSnake:
    def test_simple(self) -> None:
        assert _camel_to_snake("firstName") == "first_name"

    def test_already_snake(self) -> None:
        assert _camel_to_snake("first_name") == "first_name"

    def test_single_word(self) -> None:
        assert _camel_to_snake("name") == "name"

    def test_multiple_capitals(self) -> None:
        assert _camel_to_snake("createdAt") == "created_at"

    def test_id_field(self) -> None:
        assert _camel_to_snake("companyId") == "company_id"


class TestPrintJson:
    def test_outputs_valid_json(self) -> None:
        output = StringIO()
        with patch("sys.stdout", output):
            print_json({"name": "Acme", "id": "CO-AB-1"})
        result = json.loads(output.getvalue())
        assert result["name"] == "Acme"
        assert result["id"] == "CO-AB-1"

    def test_outputs_list(self) -> None:
        output = StringIO()
        with patch("sys.stdout", output):
            print_json([1, 2, 3])
        result = json.loads(output.getvalue())
        assert result == [1, 2, 3]


class TestPrintTable:
    def test_empty_rows(self, capsys) -> None:
        print_table([])
        captured = capsys.readouterr()
        assert "No results" in captured.out

    def test_renders_rows(self, capsys) -> None:
        rows = [
            {"id": "CO-AB-1", "name": "Acme"},
            {"id": "CO-AB-2", "name": "Globex"},
        ]
        print_table(rows)
        captured = capsys.readouterr()
        assert "Acme" in captured.out
        assert "Globex" in captured.out


class TestColorStatus:
    def test_active_is_green(self) -> None:
        assert color_status("active") == "[green]active[/green]"

    def test_churned_is_red(self) -> None:
        assert color_status("Churned") == "[red]Churned[/red]"

    def test_pending_is_yellow(self) -> None:
        assert color_status("pending") == "[yellow]pending[/yellow]"

    def test_unknown_passthrough(self) -> None:
        assert color_status("unknown_value") == "unknown_value"

    def test_case_insensitive_in_progress(self) -> None:
        assert color_status("In Progress") == "[yellow]In Progress[/yellow]"

    def test_won_is_green(self) -> None:
        assert color_status("won") == "[green]won[/green]"

    def test_lost_is_red(self) -> None:
        assert color_status("lost") == "[red]lost[/red]"

    def test_disqualified_is_red(self) -> None:
        assert color_status("Disqualified") == "[red]Disqualified[/red]"


class TestPrintTableStatusColumns:
    def test_status_column_color_coded(self, capsys) -> None:
        rows = [{"name": "Acme", "status": "active"}]
        print_table(rows, status_columns=["status"])
        captured = capsys.readouterr()
        assert "Acme" in captured.out

    def test_no_status_columns_backward_compatible(self, capsys) -> None:
        rows = [{"id": "1", "name": "Acme"}]
        print_table(rows)
        captured = capsys.readouterr()
        assert "Acme" in captured.out
