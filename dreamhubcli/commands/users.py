"""dh users — manage user accounts."""

from dreamhubcli.commands._crud import build_crud_app

app = build_crud_app(
    name="users",
    resource_path="users",
    collection_key="users",
    help_text="Manage user accounts.",
    display_columns=["id", "email", "firstName", "lastName", "role", "status"],
    status_columns=["status"],
    label_maps={"status": {1: "Active", 2: "Inactive", 3: "Pending", 4: "Expired"}},
)
