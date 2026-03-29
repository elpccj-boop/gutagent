#!/usr/bin/env python3
"""Export GutAgent data to JSON for mobile import.

Usage:
    # Export from default data/gutagent.db
    python -m gutagent.utils.export_data --pretty -o export.json

    # Export from specific database (e.g., Claude's db)
    python -m gutagent.utils.export_data --db data/claude/gutagent.db --profile data/claude/profile.json -o export.json
    
    # Export from Gemini's db
    python -m gutagent.utils.export_data --db data/gemini/gutagent.db --profile data/gemini/profile.json -o export.json
"""

import json
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add gutagent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import sqlite3


def export_all(db_path: Path, profile_path: Path) -> dict:
    """Export all data as a dict."""
    
    # Load profile
    profile = {}
    if profile_path.exists():
        with open(profile_path) as f:
            profile = json.load(f)
        print(f"  Profile: {profile_path}", file=sys.stderr)
    else:
        print(f"  Profile not found: {profile_path}", file=sys.stderr)
    
    # Connect to database
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"  Database: {db_path}", file=sys.stderr)
    
    conn = sqlite3.connect(str(db_path))
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
                        try:
                            row_dict["ingredients"] = json.loads(row_dict["ingredients"])
                        except json.JSONDecodeError:
                            pass
                rows.append(row_dict)
            return rows
        except sqlite3.OperationalError as e:
            print(f"  Warning: Could not fetch {table}: {e}", file=sys.stderr)
            return []
    
    # Export each table
    data = {
        "export_version": 1,
        "export_date": datetime.now().isoformat(),
        "source_db": str(db_path),
        "source_profile": str(profile_path),
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
    parser = argparse.ArgumentParser(
        description="Export GutAgent data to JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export from default location
  python -m gutagent.utils.export_data --pretty -o export.json

  # Export from Claude's db
  python -m gutagent.utils.export_data \\
      --db data/claude/gutagent.db \\
      --profile data/claude/profile.json \\
      -o claude_export.json

  # Export from Gemini's db  
  python -m gutagent.utils.export_data \\
      --db data/gemini/gutagent.db \\
      --profile data/gemini/profile.json \\
      -o gemini_export.json
"""
    )
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    parser.add_argument(
        "--db", 
        type=Path,
        help="Database path (default: data/gutagent.db or GUTAGENT_DB_PATH)"
    )
    parser.add_argument(
        "--profile",
        type=Path, 
        help="Profile path (default: data/profile.json or GUTAGENT_PROFILE_PATH)"
    )
    args = parser.parse_args()
    
    # Determine paths
    if args.db:
        db_path = args.db
    else:
        from gutagent.paths import DB_PATH
        db_path = DB_PATH
        
    if args.profile:
        profile_path = args.profile
    else:
        from gutagent.paths import PROFILE_PATH
        profile_path = PROFILE_PATH
    
    print(f"\nExporting GutAgent data...", file=sys.stderr)
    data = export_all(db_path, profile_path)
    
    indent = 2 if args.pretty else None
    json_str = json.dumps(data, indent=indent, default=str)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(json_str)
        print(f"\n✓ Exported to {args.output}", file=sys.stderr)
    else:
        print(json_str)
    
    # Print summary
    print(f"\nSummary:", file=sys.stderr)
    print(f"  Profile: {len(data['profile'])} sections", file=sys.stderr)
    for table, rows in data["tables"].items():
        if rows:
            print(f"  {table}: {len(rows)} rows", file=sys.stderr)


if __name__ == "__main__":
    main()
