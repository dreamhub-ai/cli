"""dh companies — manage company records."""

from dreamhubcli.commands._crud import build_crud_app

app = build_crud_app(
    name="companies",
    resource_path="companies",
    collection_key="companies",
    help_text="Manage company records.",
    display_columns=["id", "name", "domain", "industry", "status"],
    status_columns=["status"],
    label_maps={"status": {1: "Prospect", 2: "Customer", 3: "Churned", 4: "On Hold", 5: "Disqualified"}},
)
