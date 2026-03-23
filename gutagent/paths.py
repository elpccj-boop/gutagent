"""Centralized path management for GutAgent.

All paths are configurable via environment variables:
- GUTAGENT_DATA_DIR: Base directory for data files (default: ./data)
- GUTAGENT_DB_PATH: Database file path (default: $GUTAGENT_DATA_DIR/gutagent.db)
- GUTAGENT_PROFILE_PATH: Profile file path (default: $GUTAGENT_DATA_DIR/profile.json)
"""

import os
from pathlib import Path

# Project root (directory containing gutagent package)
PROJECT_ROOT = Path(__file__).parent.parent

# Package root (gutagent directory)
PACKAGE_ROOT = Path(__file__).parent

# Data directory - can be overridden with GUTAGENT_DATA_DIR
_default_data_dir = PROJECT_ROOT / "data"
DATA_DIR = Path(os.getenv("GUTAGENT_DATA_DIR", _default_data_dir))

# Database path - can be overridden with GUTAGENT_DB_PATH
_default_db_path = DATA_DIR / "gutagent.db"
DB_PATH = Path(os.getenv("GUTAGENT_DB_PATH", _default_db_path))

# Profile path - can be overridden with GUTAGENT_PROFILE_PATH
_default_profile_path = DATA_DIR / "profile.json"
PROFILE_PATH = Path(os.getenv("GUTAGENT_PROFILE_PATH", _default_profile_path))

# Profile template (ships with package, not in data/)
PROFILE_TEMPLATE_PATH = PACKAGE_ROOT / "profile_template.json"

# Web UI directory
WEB_DIR = PACKAGE_ROOT / "web"


def ensure_data_dir():
    """Create data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_db_path() -> str:
    """Get database path as string (for sqlite3 compatibility)."""
    ensure_data_dir()
    return str(DB_PATH)


def get_profile_path() -> str:
    """Get profile path as string."""
    return str(PROFILE_PATH)
