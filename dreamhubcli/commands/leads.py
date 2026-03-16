"""dh leads — manage lead records."""

from dreamhubcli.commands._crud import build_crud_app

app = build_crud_app(
    name="leads",
    resource_path="leads",
    collection_key="leads",
    help_text="Manage lead records.",
    display_columns=["id", "firstName", "lastName", "email", "companyName", "status"],
    status_columns=["status"],
    label_maps={"status": {1: "Disqualified", 2: "Qualified", 3: "Converted", 4: "Stuck", 5: "New", 6: "In Progress"}},
)
