"""SQLite database setup and operations."""

import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gutagent.db")


def validate_timestamp(occurred_at: str | None) -> str:
    """Validate and return a timestamp string. Raises ValueError for invalid dates."""
    if occurred_at is None:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # This will raise ValueError for impossible dates like Feb 29 in non-leap years
    datetime.fromisoformat(occurred_at)
    return occurred_at


def get_connection():
    """Get a database connection, creating the DB if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            meal_type TEXT,
            description TEXT NOT NULL,
            foods JSON,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS symptoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            symptom TEXT NOT NULL,
            severity INTEGER CHECK(severity BETWEEN 1 AND 10),
            timing TEXT,
            notes TEXT
        );
            
        CREATE TABLE IF NOT EXISTS medication_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TIMESTAMP,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            dose TEXT,
            notes TEXT
        );
            
        CREATE TABLE IF NOT EXISTS vitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vital_type TEXT NOT NULL,
            systolic INTEGER,
            diastolic INTEGER,
            heart_rate INTEGER,
            value REAL,
            unit TEXT,
            occurred_at TIMESTAMP,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        );
            
        CREATE TABLE IF NOT EXISTS labs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_date TEXT NOT NULL,
            test_name TEXT NOT NULL,
            value REAL,
            unit TEXT,
            reference_range TEXT,
            status TEXT,
            notes TEXT,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
            
        CREATE TABLE IF NOT EXISTS sleep (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hours REAL,
            quality TEXT,
            occurred_at TIMESTAMP,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS exercise (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity TEXT NOT NULL,
            duration_minutes INTEGER,
            occurred_at TIMESTAMP,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            occurred_at TIMESTAMP,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

# --- Edit log operations ---

def update_log(table: str, entry_id: int, updates: dict) -> dict:
    """Update fields on an existing log entry."""
    allowed_tables = {"meals", "symptoms", "vitals", "medication_events", "sleep", "exercise", "journal"}
    if table not in allowed_tables:
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
    allowed_tables = {"meals", "symptoms", "vitals", "medication_events", "journal"}
    if table not in allowed_tables:
        return {"error": f"Cannot delete from table: {table}"}

    conn = get_connection()
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "table": table, "id": entry_id}

# --- Meal operations ---

def log_meal(meal_type: str | None, description: str, foods: list[str],
             notes: str | None = None, occurred_at: str | None = None) -> dict:
    """Log a meal entry."""
    timestamp = validate_timestamp(occurred_at)
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO meals (meal_type, description, foods, notes, occurred_at) VALUES (?, ?, ?, ?, ?)",
        (meal_type, description, json.dumps(foods), notes, timestamp)
    )
    conn.commit()
    meal_id = cursor.lastrowid
    conn.close()
    return {"id": meal_id, "status": "logged", "meal_type": meal_type, "foods": foods, "when": timestamp}

def get_recent_meals(days_back: int = 7) -> list[dict]:
    """Get meals from the last N days."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
    rows = conn.execute(
        "SELECT * FROM meals WHERE occurred_at >= ? ORDER BY occurred_at DESC", (cutoff,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def search_meals_by_food(food: str) -> list[dict]:
    """Search meals containing a specific food."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM meals WHERE foods LIKE ? ORDER BY occurred_at DESC",
        (f"%{food}%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Symptom operations ---

def log_symptom(symptom: str, severity: int, timing: str | None = None,
                notes: str | None = None, occurred_at: str | None = None) -> dict:
    """Log a symptom entry."""
    timestamp = validate_timestamp(occurred_at)
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO symptoms (symptom, severity, timing, notes, occurred_at) VALUES (?, ?, ?, ?, ?)",
        (symptom, severity, timing, notes, timestamp)
    )
    conn.commit()
    symptom_id = cursor.lastrowid
    conn.close()
    return {"id": symptom_id, "status": "logged", "symptom": symptom, "severity": severity, "when": timestamp}

def get_recent_symptoms(days_back: int = 7) -> list[dict]:
    """Get symptoms from the last N days."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
    rows = conn.execute(
        "SELECT * FROM symptoms WHERE occurred_at >= ? ORDER BY occurred_at DESC", (cutoff,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def search_symptoms(symptom: str) -> list[dict]:
    """Search for a specific symptom type."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM symptoms WHERE symptom LIKE ? ORDER BY occurred_at DESC",
        (f"%{symptom}%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# -- Medication operations --

def log_medication_event(medication: str, event_type: str,
                         occurred_at: str | None = None, dose: str | None = None,
                         notes: str | None = None) -> dict:
    """Log a medication change."""
    timestamp = validate_timestamp(occurred_at)
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO medication_events (medication, event_type, occurred_at, dose, notes) VALUES (?, ?, ?, ?, ?)",
        (medication, event_type, timestamp, dose, notes)
    )
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return {"id": event_id, "status": "logged", "medication": medication, "event": event_type, "when": timestamp}

def get_recent_meds(days_back: int = 365) -> list:
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM medication_events WHERE occurred_at >= ? ORDER BY occurred_at",
        (cutoff,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# -- Vitals operations --

def log_vital(vital_type: str, occurred_at: str | None = None,
              systolic: int | None = None, diastolic: int | None = None,
              heart_rate: int | None = None, value: float | None = None,
              unit: str | None = None, notes: str | None = None) -> dict:
    """Log a vital sign reading."""
    timestamp = validate_timestamp(occurred_at)
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO vitals
           (vital_type, systolic, diastolic, heart_rate, value, unit, occurred_at, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (vital_type, systolic, diastolic, heart_rate, value, unit, timestamp, notes)
    )
    conn.commit()
    vital_id = cursor.lastrowid
    conn.close()

    result = {"id": vital_id, "status": "logged", "type": vital_type, "when": timestamp}
    if systolic:
        result["reading"] = f"{systolic}/{diastolic} HR:{heart_rate}"
    if value:
        result["reading"] = f"{value} {unit}"
    return result

def get_recent_vitals(days_back: int = 0, vital_type: str | None = None) -> list:
    conn = get_connection()
    query = "SELECT * FROM vitals WHERE 1=1"
    params = []
    if days_back > 0:
        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        query += " AND occurred_at >= ?"
        params.append(cutoff)
    if vital_type:
        query += " AND vital_type = ?"
        params.append(vital_type)
    rows = conn.execute(query + " ORDER BY occurred_at", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# -- Labs operations --

def get_recent_labs(test_date: str | None = None) -> list:
    conn = get_connection()
    if test_date:
        rows = conn.execute(
            "SELECT * FROM labs WHERE test_date = ? ORDER BY status, test_name",
            (test_date,)
        ).fetchall()
    else:
        # Get most recent test date's results
        rows = conn.execute(
            "SELECT * FROM labs WHERE test_date = (SELECT MAX(test_date) FROM labs) ORDER BY status, test_name"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Sleep operations ---

def log_sleep(hours: float | None = None, quality: str | None = None,
              occurred_at: str | None = None, notes: str | None = None) -> dict:
    """Log a sleep entry."""
    timestamp = validate_timestamp(occurred_at)
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO sleep (hours, quality, occurred_at, notes) VALUES (?, ?, ?, ?)",
        (hours, quality, timestamp, notes)
    )
    conn.commit()
    entry_id = cursor.lastrowid
    conn.close()
    result = {"id": entry_id, "status": "logged", "when": timestamp}
    if hours:
        result["hours"] = hours
    if quality:
        result["quality"] = quality
    return result

def get_recent_sleep(days_back: int = 7) -> list[dict]:
    """Get sleep entries from the last N days."""
    conn = get_connection()
    if days_back > 0:
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
        rows = conn.execute(
            "SELECT * FROM sleep WHERE occurred_at >= ? ORDER BY occurred_at DESC", (cutoff,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM sleep ORDER BY occurred_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Exercise operations ---

def log_exercise(activity: str, duration_minutes: int | None = None,
                 occurred_at: str | None = None, notes: str | None = None) -> dict:
    """Log an exercise entry."""
    timestamp = validate_timestamp(occurred_at)
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO exercise (activity, duration_minutes, occurred_at, notes) VALUES (?, ?, ?, ?)",
        (activity, duration_minutes, timestamp, notes)
    )
    conn.commit()
    entry_id = cursor.lastrowid
    conn.close()
    result = {"id": entry_id, "status": "logged", "activity": activity, "when": timestamp}
    if duration_minutes:
        result["duration_minutes"] = duration_minutes
    return result

def get_recent_exercise(days_back: int = 7) -> list[dict]:
    """Get exercise entries from the last N days."""
    conn = get_connection()
    if days_back > 0:
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
        rows = conn.execute(
            "SELECT * FROM exercise WHERE occurred_at >= ? ORDER BY occurred_at DESC", (cutoff,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM exercise ORDER BY occurred_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Journal operations ---

def log_journal_entry(description: str, occurred_at: str | None = None) -> dict:
    """Log a journal entry."""
    timestamp = validate_timestamp(occurred_at)
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO journal (description, occurred_at) VALUES (?, ?)",
        (description, timestamp)
    )
    conn.commit()
    entry_id = cursor.lastrowid
    conn.close()
    return {"id": entry_id, "status": "logged", "description": description, "when": timestamp}

def get_recent_journal(days_back: int = 7) -> list[dict]:
    """Get journal entries from the last N days."""
    conn = get_connection()
    if days_back > 0:
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
        rows = conn.execute(
            "SELECT * FROM journal WHERE occurred_at >= ? ORDER BY occurred_at DESC", (cutoff,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM journal ORDER BY occurred_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

