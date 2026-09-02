"""dh contracts — manage contract records."""

from dreamhubcli.commands._crud import build_crud_app

# The MCP surface renders the same records from its own copy in mcp_server.py, so a
# test pins the two together — they drifted on renewalType once already.
CONTRACT_LABEL_MAPS = {
    "status": {
        1: "Active",
        2: "Upcoming",
        3: "Expired",
        4: "No Services Configured",
        5: "One-Time Services Only",
        6: "Draft",
    },
    # Value 3 is HYBRID in the backend enum but reads as "Mixed" everywhere a
    # Dreamhub user sees it.
    "renewalType": {1: "Auto Renewal", 2: "Manual Renewal", 3: "Mixed"},
}

app = build_crud_app(
    name="contracts",
    resource_path="contracts",
    collection_key="contracts",
    help_text="Manage contract records.",
    display_columns=["id", "name", "companyId", "status", "renewalType", "startDate", "endDate", "arr"],
    status_columns=["status", "renewalType"],
    label_maps=CONTRACT_LABEL_MAPS,
)
