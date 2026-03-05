"""
Fix or correct data in the GutAgent database.

Usage:
    python utils/fix_data.py

Edit this script as needed for one-off corrections. Examples:

    # Update a symptom severity
    conn.execute("UPDATE symptoms SET severity = 3 WHERE id = 6")

    # Delete a duplicate entry
    conn.execute("DELETE FROM symptoms WHERE id = 7")

    # Fix a timestamp
    conn.execute("UPDATE meals SET occurred_at = '2026-03-02 13:30:00' WHERE id = 5")

    # Always commit after changes
    conn.commit()
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gutagent.db")

conn = sqlite3.connect(DB_PATH)

# --- Add your fixes below ---

# --- End fixes ---

conn.commit()
conn.close()
print("Fixes applied.")