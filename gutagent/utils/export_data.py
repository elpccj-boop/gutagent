#!/usr/bin/env python3
"""Export GutAgent data to JSON for mobile import.

Usage:
    python export_data.py > gutagent_export.json
    python export_data.py -o gutagent_export.json
"""

import json
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add gutagent to path
sys.path.insert(0, str(Path(__file__).parent))

from gutagent.paths import DB_PATH, PROFILE_PATH
import sqlite3


def export_all() -> dict:
    """Export all data as a dict."""
    
    # Load profile
    profile = {}
    if PROFILE_PATH.exists():
        with open(PROFILE_PATH) as f:
            profile = json.load(f)
    
    # Connect to database
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    def fetch_all(table: str, order_by: str = "id") -> list:
        """Fetch all rows from a table as list of dicts."""
        try:
            cursor = conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}")
            columns = [desc[0] for desc in cursor.description]
            rows = []
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                # Handle JSON fields
                if table == "recipes" and "ingredients" in row_dict:
                    if isinstance(row_dict["ingredients"], str):
                        row_dict["ingredients"] = json.loads(row_dict["ingredients"])
                rows.append(row_dict)
            return rows
        except sqlite3.OperationalError as e:
            print(f"Warning: Could not fetch {table}: {e}", file=sys.stderr)
            return []
    
    # Export each table
    data = {
        "export_version": 1,
        "export_date": datetime.now().isoformat(),
        "profile": profile,
        "tables": {
            "meals": fetch_all("meals", "occurred_at"),
            "meal_items": fetch_all("meal_items", "meal_id"),
            "meal_nutrition": fetch_all("meal_nutrition", "meal_id"),
            "symptoms": fetch_all("symptoms", "occurred_at"),
            "vitals": fetch_all("vitals", "occurred_at"),
            "labs": fetch_all("labs", "test_date"),
            "sleep": fetch_all("sleep", "occurred_at"),
            "exercise": fetch_all("exercise", "occurred_at"),
            "journal": fetch_all("journal", "logged_at"),
            "medications": fetch_all("medications", "occurred_at"),
            "recipes": fetch_all("recipes", "name"),
        }
    }
    
    conn.close()
    return data


def main():
    parser = argparse.ArgumentParser(description="Export GutAgent data to JSON")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    args = parser.parse_args()
    
    data = export_all()
    
    indent = 2 if args.pretty else None
    json_str = json.dumps(data, indent=indent, default=str)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(json_str)
        print(f"Exported to {args.output}", file=sys.stderr)
        print(f"  Profile: {len(data['profile'])} sections", file=sys.stderr)
        for table, rows in data["tables"].items():
            print(f"  {table}: {len(rows)} rows", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
