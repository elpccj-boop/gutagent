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
