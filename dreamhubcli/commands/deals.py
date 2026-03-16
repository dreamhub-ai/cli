"""dh deals — manage deal/opportunity records."""

from dreamhubcli.commands._crud import build_crud_app

app = build_crud_app(
    name="deals",
    resource_path="deals",
    collection_key="deals",
    help_text="Manage deal and opportunity records.",
    display_columns=["id", "name", "companyId", "stage", "value", "status"],
    status_columns=["status", "stage"],
    label_maps={
        "status": {1: "In Progress", 2: "Stuck", 4: "Won", 5: "Lost"},
        "stage": {
            1: "Prospecting",
            2: "Demo",
            3: "Demo to DMs",
            4: "Waiting Data POC",
            5: "POC",
            6: "Pilot",
            7: "Proposal",
            8: "Negotiation",
            9: "Closed Won",
            10: "Closed Lost",
        },
    },
)
