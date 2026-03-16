"""dh tasks — manage CRM tasks."""

from dreamhubcli.commands._crud import build_crud_app

app = build_crud_app(
    name="tasks",
    resource_path="tasks",
    collection_key="tasks",
    help_text="Manage CRM tasks.",
    display_columns=["id", "title", "assigneeId", "dueDate", "isCompleted", "isHighPriority"],
    status_columns=["isCompleted", "isHighPriority"],
    label_maps={
        "isCompleted": {1: "Completed", 0: "Open"},
        "isHighPriority": {1: "High", 0: "Normal"},
    },
)
