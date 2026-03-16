"""dh people — manage contact/person records."""

from dreamhubcli.commands._crud import build_crud_app

app = build_crud_app(
    name="people",
    resource_path="people",
    collection_key="people",
    help_text="Manage contact and person records.",
    singular_name="person",
    display_columns=["id", "firstName", "lastName", "email", "companyId", "title", "status"],
    status_columns=["status"],
    label_maps={
        "status": {
            1: "New",
            2: "Greenfield",
            3: "Engaged in Deal",
            4: "Engaged in Lead",
            5: "Engaged",
            6: "Active Customer",
            7: "Disqualified",
        }
    },
)
