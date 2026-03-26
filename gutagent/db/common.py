"""Common database utilities and generic log operations."""

from .connection import get_connection

# Allowed tables for generic operations
ALLOWED_TABLES = {"meals", "symptoms", "vitals", "labs", "medications", "sleep", "exercise", "journal"}


def update_log(table: str, entry_id: int, updates: dict) -> dict:
    """Update fields on an existing log entry."""
    if table not in ALLOWED_TABLES:
        return {"error": f"Cannot update table: {table}"}

    conn = get_connection()
    set_clauses = []
    values = []
    for key, val in updates.items():
        set_clauses.append(f"{key} = ?")
        values.append(val)
    values.append(entry_id)

    conn.execute(
        f"UPDATE {table} SET {', '.join(set_clauses)} WHERE id = ?",
        values
    )
    conn.commit()
    conn.close()
    return {"status": "updated", "table": table, "id": entry_id, "changes": updates}


def delete_log(table: str, entry_id: int) -> dict:
    """Delete a log entry by id."""
    if table not in ALLOWED_TABLES:
        return {"error": f"Cannot delete from table: {table}"}

    conn = get_connection()
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "table": table, "id": entry_id}


def get_logs_by_date(table: str, date: str) -> list[dict]:
    """
    Get all entries from a table for a specific date.

    Args:
        table: One of meals, symptoms, vitals, labs, medications, sleep, exercise, journal
        date: Date string in YYYY-MM-DD format

    Returns:
        List of entries with all fields including id
    """
    if table not in ALLOWED_TABLES:
        return []

    # journal uses logged_at, labs uses test_date, others use occurred_at
    if table == "journal":
        date_column = "logged_at"
    elif table == "labs":
        date_column = "test_date"
    else:
        date_column = "occurred_at"

    conn = get_connection()
    rows = conn.execute(
        f"SELECT * FROM {table} WHERE DATE({date_column}) = ? ORDER BY {date_column} DESC",
        (date,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def round_nutrition(nutrition: dict) -> dict:
    """Round nutrition values appropriately based on typical precision."""
    rounded = {}

    # 1 decimal place: B12, iron, zinc, omega-3
    one_decimal = {'vitamin_b12', 'iron', 'zinc', 'omega_3'}

    for nutrient, value in nutrition.items():
        if nutrient in one_decimal:
            rounded[nutrient] = round(value, 1)
        else:
            # Integer: everything else
            rounded[nutrient] = int(round(value))

    return rounded
