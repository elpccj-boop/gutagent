"""Medical profile management."""

import json
import os

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "profile.json")

def load_profile() -> dict:
    """Load the medical profile from JSON."""
    if not os.path.exists(PROFILE_PATH):
        return {"error": "Profile not found. Create data/profile.json with your medical data."}
    with open(PROFILE_PATH, "r") as f:
        return json.load(f)


def save_profile(profile: dict):
    """Save updated profile and refresh RDA targets if needed."""
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)

    # Refresh RDA targets with the profile we just saved
    from gutagent.db.models import set_rda_targets
    set_rda_targets(profile)  # No re-reading needed!


def update_profile(section: str, action: str, value: str) -> dict:
    """
    Update a section of the profile.

    section: dot-notation path like 'conditions.chronic' or 'upcoming_appointments.elf_test'
    action: 'append', 'set', 'remove', or 'delete'
    value: the value to add/set/remove (not used for 'delete')
    """
    profile = load_profile()

    # Navigate to the parent and get the key
    keys = section.split(".")
    parent = profile
    for key in keys[:-1]:
        if key not in parent:
            parent[key] = {}
        parent = parent[key]

    final_key = keys[-1]
    current = parent.get(final_key)

    if action == "append":
        if current is None:
            parent[final_key] = [value]
        elif isinstance(current, list):
            parent[final_key].append(value)
        else:
            return {"error": f"Cannot append to {section} — it's not a list"}

    elif action == "set":
        parent[final_key] = value

    elif action == "remove":
        if not isinstance(current, list):
            return {"error": f"Cannot remove from {section} — it's not a list"}
        # Find and remove by substring match
        original_len = len(current)
        parent[final_key] = [item for item in current if value.lower() not in item.lower()]
        removed = original_len - len(parent[final_key])
        if removed == 0:
            return {"error": f"No item matching '{value}' found in {section}"}
        save_profile(profile)
        return {"status": "removed", "section": section, "matched": value, "items_removed": removed}

    elif action == "delete":
        # Delete a dictionary key entirely
        if final_key in parent:
            del parent[final_key]
            save_profile(profile)
            return {"status": "deleted", "section": section, "key": final_key}
        else:
            return {"error": f"Key '{final_key}' not found in {'.'.join(keys[:-1])}"}

    else:
        return {"error": f"Unknown action: {action}"}

    save_profile(profile)
    return {"status": "updated", "section": section, "action": action, "value": value}

