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
    """Save updated profile."""
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)

def update_profile(section: str, action: str, value: str) -> dict:
    """
    Update a section of the profile.

    section: dot-notation path like 'conditions.chronic' or 'lifestyle.notes'
    action: 'append', 'set', or 'remove'
    value: the value to add/set/remove
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

    else:
        return {"error": f"Unknown action: {action}"}

    save_profile(profile)
    return {"status": "updated", "section": section, "action": action, "value": value}

