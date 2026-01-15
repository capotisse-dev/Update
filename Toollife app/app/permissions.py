# Levels: none, view, edit, override
PERMISSIONS = {
    "Top (Super User)": {
        "view_data": "edit",
        "edit_any": "override",
        "manage_tools": "edit",
        "manage_users": "none",  # Top can’t manage users unless you want it
        "export": "edit",
    },
    "Admin": {
        "view_data": "edit",
        "edit_any": "edit",
        "manage_tools": "edit",
        "manage_users": "edit",
        "export": "edit",
    }
}

def can(role: str, key: str, at_least="view"):
    order = {"none": 0, "view": 1, "edit": 2, "override": 3}
    have = PERMISSIONS.get(role, {}).get(key, "none")
    return order.get(have, 0) >= order.get(at_least, 1)
