"""SQLite database setup and operations."""

import sqlite3
import json
import os
from datetime import datetime, timedelta

# Database path - can be overridden with GUTAGENT_DB_PATH env var for testing
_default_db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gutagent.db")
DB_PATH = os.getenv("GUTAGENT_DB_PATH", _default_db_path)

# RDA values for nutrition alerts
# target = daily recommended intake
# upper_limit = safe upper limit (None if no concern)
RDA_TARGETS = {
    "fiber": {"target": 25, "unit": "g", "upper_limit": None},
    "vitamin_b12": {"target": 2.4, "unit": "μg", "upper_limit": None},
    "vitamin_d": {"target": 15, "unit": "μg", "upper_limit": 100},
    "folate": {"target": 400, "unit": "μg", "upper_limit": 1000},
    "iron": {"target": 8, "unit": "mg", "upper_limit": 45},
    "zinc": {"target": 11, "unit": "mg", "upper_limit": 40},
    "magnesium": {"target": 400, "unit": "mg", "upper_limit": None},
    "calcium": {"target": 1000, "unit": "mg", "upper_limit": 2500},
    "potassium": {"target": 2600, "unit": "mg", "upper_limit": None},
    "omega_3": {"target": 1.6, "unit": "g", "upper_limit": None},
    "vitamin_a": {"target": 900, "unit": "μg", "upper_limit": 3000},
    "vitamin_c": {"target": 90, "unit": "mg", "upper_limit": None},
}


def validate_timestamp(occurred_at: str | None) -> str:
    """Validate and return a timestamp string. Raises ValueError for invalid dates."""
    if occurred_at is None:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    datetime.fromisoformat(occurred_at)
    return occurred_at


def get_connection():
    """Get a database connection, creating the DB if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TIMESTAMP,
            meal_type TEXT,
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS symptoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TIMESTAMP,
            symptom TEXT NOT NULL,
            severity INTEGER CHECK(severity BETWEEN 1 AND 10),
            timing TEXT,
            notes TEXT
        );
            
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TIMESTAMP,
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
            logged_at TIMESTAMP
        );
            
        CREATE TABLE IF NOT EXISTS sleep (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hours REAL,
            quality TEXT,
            occurred_at TIMESTAMP,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS exercise (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity TEXT NOT NULL,
            duration_minutes INTEGER,
            occurred_at TIMESTAMP,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            logged_at TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            ingredients JSON NOT NULL,
            notes TEXT,
            created_at TIMESTAMP,
            servings REAL DEFAULT 1,
            calories REAL DEFAULT 0,
            protein REAL DEFAULT 0,
            carbs REAL DEFAULT 0,
            fat REAL DEFAULT 0,
            fiber REAL DEFAULT 0,
            vitamin_b12 REAL DEFAULT 0,
            vitamin_d REAL DEFAULT 0,
            folate REAL DEFAULT 0,
            iron REAL DEFAULT 0,
            zinc REAL DEFAULT 0,
            magnesium REAL DEFAULT 0,
            calcium REAL DEFAULT 0,
            potassium REAL DEFAULT 0,
            omega_3 REAL DEFAULT 0,
            vitamin_a REAL DEFAULT 0,
            vitamin_c REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS meal_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER NOT NULL,
            food_name TEXT NOT NULL,
            quantity REAL,
            unit TEXT,
            FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS meal_nutrition (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER NOT NULL UNIQUE,
            calories REAL DEFAULT 0,
            protein REAL DEFAULT 0,
            carbs REAL DEFAULT 0,
            fat REAL DEFAULT 0,
            fiber REAL DEFAULT 0,
            vitamin_b12 REAL DEFAULT 0,
            vitamin_d REAL DEFAULT 0,
            folate REAL DEFAULT 0,
            iron REAL DEFAULT 0,
            zinc REAL DEFAULT 0,
            magnesium REAL DEFAULT 0,
            calcium REAL DEFAULT 0,
            potassium REAL DEFAULT 0,
            omega_3 REAL DEFAULT 0,
            vitamin_a REAL DEFAULT 0,
            vitamin_c REAL DEFAULT 0,
            FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_meal_items_meal ON meal_items(meal_id);
        CREATE INDEX IF NOT EXISTS idx_meal_nutrition_meal ON meal_nutrition(meal_id);
    """)
    conn.commit()
    conn.close()


# --- Edit Log Operations ---

def update_log(table: str, entry_id: int, updates: dict) -> dict:
    """Update fields on an existing log entry."""
    allowed_tables = {"meals", "symptoms", "vitals", "medications", "sleep", "exercise", "journal"}
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
    allowed_tables = {"meals", "symptoms", "vitals", "medications", "sleep", "exercise", "journal"}
    if table not in allowed_tables:
        return {"error": f"Cannot delete from table: {table}"}

    conn = get_connection()
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "table": table, "id": entry_id}


# --- Meal Operations ---

def log_meal_with_nutrition(meal_type: str | None, description: str, items: list[dict],
                            nutrition: dict, occurred_at: str | None = None) -> dict:
    """Log a meal with itemized foods and calculated nutrition."""
    timestamp = validate_timestamp(occurred_at)
    conn = get_connection()

    # Insert meal
    cursor = conn.execute(
        "INSERT INTO meals (meal_type, description, occurred_at) VALUES (?, ?, ?)",
        (meal_type, description, timestamp)
    )
    meal_id = cursor.lastrowid

    # Insert meal items
    for item in items:
        conn.execute(
            """INSERT INTO meal_items (meal_id, food_name, quantity, unit)
               VALUES (?, ?, ?, ?)""",
            (meal_id, item.get("food_name"), item.get("quantity"), item.get("unit"))
        )

    # Insert nutrition totals
    conn.execute(
        """INSERT INTO meal_nutrition 
           (meal_id, calories, protein, carbs, fat, fiber, 
            vitamin_b12, vitamin_d, folate, iron, zinc, magnesium,
            calcium, potassium, omega_3, vitamin_a, vitamin_c)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (meal_id,
         nutrition.get("calories", 0), nutrition.get("protein", 0),
         nutrition.get("carbs", 0), nutrition.get("fat", 0), nutrition.get("fiber", 0),
         nutrition.get("vitamin_b12", 0), nutrition.get("vitamin_d", 0),
         nutrition.get("folate", 0), nutrition.get("iron", 0),
         nutrition.get("zinc", 0), nutrition.get("magnesium", 0),
         nutrition.get("calcium", 0), nutrition.get("potassium", 0),
         nutrition.get("omega_3", 0), nutrition.get("vitamin_a", 0),
         nutrition.get("vitamin_c", 0))
    )

    conn.commit()
    conn.close()

    # Compact return - just essential info
    cal = int(nutrition.get("calories", 0))
    pro = int(nutrition.get("protein", 0))
    return {
        "id": meal_id,
        "status": "logged",
        "meal_type": meal_type,
        "when": timestamp,
        "summary": f"{description} — {cal} cal, {pro}g protein"
    }


def get_recent_meals(days_back: int = 7) -> list[dict]:
    """Get meals from the last N days with nutrition data."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute("""
        SELECT m.*, mn.calories, mn.protein, mn.carbs, mn.fat, mn.fiber
        FROM meals m
        LEFT JOIN meal_nutrition mn ON m.id = mn.meal_id
        WHERE m.occurred_at >= ? 
        ORDER BY m.occurred_at DESC
    """, (cutoff,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_meals_by_food(food: str) -> list[dict]:
    """Search meals containing a specific food."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM meals WHERE description LIKE ? ORDER BY occurred_at DESC",
        (f"%{food}%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_logs_by_date(table: str, date: str) -> list[dict]:
    """
    Get all entries from a table for a specific date.

    Args:
        table: One of meals, symptoms, vitals, medications, sleep, exercise, journal
        date: Date string in YYYY-MM-DD format

    Returns:
        List of entries with all fields including id
    """
    allowed_tables = {"meals", "symptoms", "vitals", "medications", "sleep", "exercise", "journal"}
    if table not in allowed_tables:
        return []

    # journal uses logged_at, others use occurred_at
    date_column = "logged_at" if table == "journal" else "occurred_at"

    conn = get_connection()
    rows = conn.execute(
        f"SELECT * FROM {table} WHERE DATE({date_column}) = ? ORDER BY {date_column} DESC",
        (date,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Symptom Operations ---

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
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
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


# -- Medication Operations --

def log_medication_event(medication: str, event_type: str,
                         occurred_at: str | None = None, dose: str | None = None,
                         notes: str | None = None) -> dict:
    """Log a medication change."""
    timestamp = validate_timestamp(occurred_at)
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO medications (medication, event_type, occurred_at, dose, notes) VALUES (?, ?, ?, ?, ?)",
        (medication, event_type, timestamp, dose, notes)
    )
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return {"id": event_id, "status": "logged", "medication": medication, "event": event_type, "when": timestamp}


def get_recent_meds(days_back: int = 365) -> list:
    """Get medication events from last N days."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM medications WHERE occurred_at >= ? ORDER BY occurred_at",
        (cutoff,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_current_and_recent_meds(recent_days: int = 30) -> list:
    """
    Get current medications + recent changes.
    Returns: recent events (last N days) + the latest 'started' event for each medication.
    This shows what's currently active plus recent changes.
    """
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=recent_days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT me.*
        FROM medications me
        WHERE me.occurred_at >= ?
           OR (me.event_type = 'started' 
               AND me.id = (SELECT id FROM medications me2 
                            WHERE me2.medication = me.medication 
                            ORDER BY occurred_at DESC LIMIT 1))
        ORDER BY occurred_at DESC
    """, (cutoff,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# -- Vitals Operations --

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


def get_recent_vitals(days_back: int = 0, vital_type: str | None = None) -> str:
    """
    Get vital signs as a compact text summary.
    Returns pre-formatted summary for Claude to analyze without huge JSON.
    """
    conn = get_connection()

    # Determine date range
    if days_back > 0:
        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    else:
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    lines = []

    # --- Blood Pressure ---
    if vital_type is None or vital_type == "blood_pressure":
        bp_rows = conn.execute("""
            SELECT systolic, diastolic, heart_rate, occurred_at, notes
            FROM vitals 
            WHERE vital_type = 'blood_pressure' AND occurred_at >= ?
            ORDER BY occurred_at DESC
        """, (cutoff,)).fetchall()

        if bp_rows:
            lines.append("=== BLOOD PRESSURE ===")
            # Recent readings (last 7)
            lines.append("Recent readings:")
            for row in bp_rows[:7]:
                date = row["occurred_at"][:10]
                note = f" ({row['notes'][:30]})" if row["notes"] else ""
                lines.append(f"  {date}: {row['systolic']}/{row['diastolic']} HR:{row['heart_rate'] or '?'}{note}")

            # Calculate stats for period
            systolics = [r["systolic"] for r in bp_rows if r["systolic"]]
            diastolics = [r["diastolic"] for r in bp_rows if r["diastolic"]]
            if systolics:
                lines.append(f"Period stats ({len(bp_rows)} readings):")
                lines.append(f"  Avg: {sum(systolics)//len(systolics)}/{sum(diastolics)//len(diastolics)}")
                lines.append(f"  Range: {min(systolics)}-{max(systolics)} / {min(diastolics)}-{max(diastolics)}")

        # Historical baseline
        hist_bp = conn.execute("""
            SELECT strftime('%Y', occurred_at) as year,
                   ROUND(AVG(systolic), 0) as avg_sys, ROUND(AVG(diastolic), 0) as avg_dia
            FROM vitals WHERE vital_type = 'blood_pressure' AND occurred_at < ?
            GROUP BY year ORDER BY year DESC LIMIT 3
        """, (cutoff,)).fetchall()
        if hist_bp:
            lines.append("Historical baseline:")
            for h in hist_bp:
                lines.append(f"  {h['year']}: {int(h['avg_sys'])}/{int(h['avg_dia'])}")

    # --- Weight ---
    if vital_type is None or vital_type == "weight":
        wt_rows = conn.execute("""
            SELECT value, unit, occurred_at
            FROM vitals 
            WHERE vital_type = 'weight' AND occurred_at >= ?
            ORDER BY occurred_at DESC
        """, (cutoff,)).fetchall()

        if wt_rows:
            lines.append("\n=== WEIGHT ===")
            lines.append("Recent readings:")
            for row in wt_rows[:5]:
                date = row["occurred_at"][:10]
                lines.append(f"  {date}: {row['value']} {row['unit']}")

            values = [r["value"] for r in wt_rows if r["value"]]
            if values:
                lines.append(f"Period: {min(values)}-{max(values)} {wt_rows[0]['unit']}")

        # Historical
        hist_wt = conn.execute("""
            SELECT strftime('%Y', occurred_at) as year,
                   ROUND(AVG(value), 1) as avg_val, unit
            FROM vitals WHERE vital_type = 'weight' AND occurred_at < ?
            GROUP BY year ORDER BY year DESC LIMIT 3
        """, (cutoff,)).fetchall()
        if hist_wt:
            lines.append("Historical:")
            for h in hist_wt:
                lines.append(f"  {h['year']}: {h['avg_val']} {h['unit']}")

    # --- Other vitals ---
    if vital_type is None:
        other_rows = conn.execute("""
            SELECT vital_type, value, unit, occurred_at, notes
            FROM vitals 
            WHERE vital_type NOT IN ('blood_pressure', 'weight') AND occurred_at >= ?
            ORDER BY vital_type, occurred_at DESC
        """, (cutoff,)).fetchall()

        if other_rows:
            current_type = None
            for row in other_rows:
                if row["vital_type"] != current_type:
                    current_type = row["vital_type"]
                    lines.append(f"\n=== {current_type.upper()} ===")
                date = row["occurred_at"][:10]
                note = f" ({row['notes'][:30]})" if row["notes"] else ""
                lines.append(f"  {date}: {row['value']} {row['unit']}{note}")
    elif vital_type and vital_type not in ("blood_pressure", "weight"):
        other_rows = conn.execute("""
            SELECT value, unit, occurred_at, notes
            FROM vitals WHERE vital_type = ? AND occurred_at >= ?
            ORDER BY occurred_at DESC
        """, (vital_type, cutoff)).fetchall()

        if other_rows:
            lines.append(f"=== {vital_type.upper()} ===")
            for row in other_rows[:10]:
                date = row["occurred_at"][:10]
                note = f" ({row['notes'][:30]})" if row["notes"] else ""
                lines.append(f"  {date}: {row['value']} {row['unit']}{note}")

    conn.close()

    if not lines:
        return "No vitals found for this period."

    return "\n".join(lines)


# -- Labs Operations --

def get_recent_labs(test_date: str | None = None) -> list:
    """Get labs from a specific date or most recent date."""
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


def get_latest_labs_per_test() -> list:
    """Get the most recent value for EACH test type (not just most recent date)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT *
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY test_name ORDER BY test_date DESC) as rn
            FROM labs
        )
        WHERE rn = 1
        ORDER BY test_date DESC, test_name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Sleep Operations ---

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
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT * FROM sleep WHERE occurred_at >= ? ORDER BY occurred_at DESC", (cutoff,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Exercise Operations ---

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
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT * FROM exercise WHERE occurred_at >= ? ORDER BY occurred_at DESC", (cutoff,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Journal Operations ---

def log_journal_entry(description: str) -> dict:
    """Log a journal entry."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO journal (description, logged_at) VALUES (?, ?)",
        (description, timestamp)
    )
    conn.commit()
    entry_id = cursor.lastrowid
    conn.close()
    return {"id": entry_id, "status": "logged", "description": description}


def get_recent_journal(days_back: int = 7) -> list[dict]:
    """Get journal entries from the last N days."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT * FROM journal WHERE logged_at >= ? ORDER BY logged_at DESC", (cutoff,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Recipe Operations ---

def save_recipe(name: str, ingredients: list[dict], notes: str | None = None,
                nutrition: dict | None = None, servings: float = 1) -> dict:
    """
    Save or update a recipe with pre-calculated per-serving nutrition.

    If nutrition is provided from ingredients totals, it will be divided by servings
    to get per-serving values.
    """
    conn = get_connection()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Calculate nutrition from ingredients if not provided
    if nutrition is None:
        nutrition = {
            "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0,
            "vitamin_b12": 0, "vitamin_d": 0, "folate": 0, "iron": 0, "zinc": 0,
            "magnesium": 0, "calcium": 0, "potassium": 0, "omega_3": 0,
            "vitamin_a": 0, "vitamin_c": 0
        }
        for item in ingredients:
            for key in nutrition:
                nutrition[key] += item.get(key, 0)

    # Divide by servings to get per-serving nutrition
    per_serving = {k: v / servings for k, v in nutrition.items()}

    # Check if recipe exists (case-insensitive)
    existing = conn.execute(
        "SELECT id FROM recipes WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE recipes SET ingredients = ?, notes = ?, servings = ?,
               calories = ?, protein = ?, carbs = ?, fat = ?, fiber = ?,
               vitamin_b12 = ?, vitamin_d = ?, folate = ?, iron = ?, zinc = ?,
               magnesium = ?, calcium = ?, potassium = ?, omega_3 = ?,
               vitamin_a = ?, vitamin_c = ?
               WHERE id = ?""",
            (json.dumps(ingredients), notes, servings,
             per_serving.get("calories", 0), per_serving.get("protein", 0),
             per_serving.get("carbs", 0), per_serving.get("fat", 0), per_serving.get("fiber", 0),
             per_serving.get("vitamin_b12", 0), per_serving.get("vitamin_d", 0),
             per_serving.get("folate", 0), per_serving.get("iron", 0), per_serving.get("zinc", 0),
             per_serving.get("magnesium", 0), per_serving.get("calcium", 0),
             per_serving.get("potassium", 0), per_serving.get("omega_3", 0),
             per_serving.get("vitamin_a", 0), per_serving.get("vitamin_c", 0),
             existing["id"])
        )
        recipe_id = existing["id"]
        action = "updated"
    else:
        cursor = conn.execute(
            """INSERT INTO recipes 
               (name, ingredients, notes, created_at, servings,
                calories, protein, carbs, fat, fiber,
                vitamin_b12, vitamin_d, folate, iron, zinc,
                magnesium, calcium, potassium, omega_3, vitamin_a, vitamin_c)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, json.dumps(ingredients), notes, timestamp, servings,
             per_serving.get("calories", 0), per_serving.get("protein", 0),
             per_serving.get("carbs", 0), per_serving.get("fat", 0), per_serving.get("fiber", 0),
             per_serving.get("vitamin_b12", 0), per_serving.get("vitamin_d", 0),
             per_serving.get("folate", 0), per_serving.get("iron", 0), per_serving.get("zinc", 0),
             per_serving.get("magnesium", 0), per_serving.get("calcium", 0),
             per_serving.get("potassium", 0), per_serving.get("omega_3", 0),
             per_serving.get("vitamin_a", 0), per_serving.get("vitamin_c", 0))
        )
        recipe_id = cursor.lastrowid
        action = "created"

    conn.commit()
    conn.close()

    return {
        "id": recipe_id, "status": action, "name": name, "servings": servings,
        "per_serving": {"calories": round(per_serving.get("calories", 0)),
                        "protein": round(per_serving.get("protein", 0))}
    }


def get_recipe(name: str) -> dict | None:
    """Get a recipe by name (case-insensitive), including per-serving nutrition."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM recipes WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "name": row["name"],
            "ingredients": json.loads(row["ingredients"]),
            "notes": row["notes"],
            "created_at": row["created_at"],
            "servings": row["servings"] or 1,
            "nutrition": {
                "calories": row["calories"] or 0,
                "protein": row["protein"] or 0,
                "carbs": row["carbs"] or 0,
                "fat": row["fat"] or 0,
                "fiber": row["fiber"] or 0,
                "vitamin_b12": row["vitamin_b12"] or 0,
                "vitamin_d": row["vitamin_d"] or 0,
                "folate": row["folate"] or 0,
                "iron": row["iron"] or 0,
                "zinc": row["zinc"] or 0,
                "magnesium": row["magnesium"] or 0,
                "calcium": row["calcium"] or 0,
                "potassium": row["potassium"] or 0,
                "omega_3": row["omega_3"] or 0,
                "vitamin_a": row["vitamin_a"] or 0,
                "vitamin_c": row["vitamin_c"] or 0,
            }
        }
    return None


def list_recipes() -> list[dict]:
    """List all saved recipes."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, notes, created_at FROM recipes ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_recipe(name: str) -> dict:
    """Delete a recipe by name."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM recipes WHERE name = ? COLLATE NOCASE", (name,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return {"status": "deleted" if deleted else "not_found", "name": name}


# --- Nutrition Summary Operations ---

def get_nutrition_summary(days: int = 3) -> str:
    """Get nutrition totals and daily averages for the past N days as compact text."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    row = conn.execute("""
        SELECT 
            COUNT(DISTINCT DATE(m.occurred_at)) as days_with_data,
            SUM(mn.calories) as total_calories,
            SUM(mn.protein) as total_protein,
            SUM(mn.carbs) as total_carbs,
            SUM(mn.fat) as total_fat,
            SUM(mn.fiber) as total_fiber,
            SUM(mn.vitamin_b12) as total_b12,
            SUM(mn.vitamin_d) as total_d,
            SUM(mn.folate) as total_folate,
            SUM(mn.iron) as total_iron,
            SUM(mn.zinc) as total_zinc,
            SUM(mn.magnesium) as total_magnesium,
            SUM(mn.calcium) as total_calcium,
            SUM(mn.potassium) as total_potassium,
            SUM(mn.omega_3) as total_omega_3,
            SUM(mn.vitamin_a) as total_vitamin_a,
            SUM(mn.vitamin_c) as total_vitamin_c
        FROM meals m
        JOIN meal_nutrition mn ON m.id = mn.meal_id
        WHERE m.occurred_at >= ?
    """, (cutoff,)).fetchone()

    conn.close()

    if not row or not row["days_with_data"]:
        return f"No nutrition data in last {days} days"

    d = row["days_with_data"]
    def avg(v, decimals=0): return round(v / d, decimals) if v and d else 0

    lines = [f"=== NUTRITION ({d} days with data) ==="]
    lines.append(f"Daily avg: {avg(row['total_calories'])} cal, {avg(row['total_protein'])}g protein, {avg(row['total_carbs'])}g carbs, {avg(row['total_fat'])}g fat, {avg(row['total_fiber'])}g fiber")
    lines.append(f"Micros avg: B12:{avg(row['total_b12'], 1)}μg, D:{avg(row['total_d'])}IU, folate:{avg(row['total_folate'])}μg, iron:{avg(row['total_iron'], 1)}mg, zinc:{avg(row['total_zinc'], 1)}mg")
    lines.append(f"  Mg:{avg(row['total_magnesium'])}mg, Ca:{avg(row['total_calcium'])}mg, K:{avg(row['total_potassium'])}mg, ω3:{avg(row['total_omega_3'], 1)}g, A:{avg(row['total_vitamin_a'])}IU, C:{avg(row['total_vitamin_c'])}mg")
    return "\n".join(lines)


def get_nutrition_alerts(days: int = 3) -> str:
    """Check for nutrient deficiencies based on RDA values. Returns compact text."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    row = conn.execute("""
        SELECT 
            COUNT(DISTINCT DATE(m.occurred_at)) as days_with_data,
            SUM(mn.calories) as total_calories,
            SUM(mn.protein) as total_protein,
            SUM(mn.carbs) as total_carbs,
            SUM(mn.fat) as total_fat,
            SUM(mn.fiber) as total_fiber,
            SUM(mn.vitamin_b12) as total_b12,
            SUM(mn.vitamin_d) as total_d,
            SUM(mn.folate) as total_folate,
            SUM(mn.iron) as total_iron,
            SUM(mn.zinc) as total_zinc,
            SUM(mn.magnesium) as total_magnesium,
            SUM(mn.calcium) as total_calcium,
            SUM(mn.potassium) as total_potassium,
            SUM(mn.omega_3) as total_omega_3,
            SUM(mn.vitamin_a) as total_vitamin_a,
            SUM(mn.vitamin_c) as total_vitamin_c
        FROM meals m
        JOIN meal_nutrition mn ON m.id = mn.meal_id
        WHERE m.occurred_at >= ?
    """, (cutoff,)).fetchone()
    conn.close()

    if not row or not row["days_with_data"]:
        return "No nutrition data to analyze"

    d = row["days_with_data"]

    # Calculate daily averages
    daily_avg = {
        "calories": (row["total_calories"] or 0) / d,
        "protein": (row["total_protein"] or 0) / d,
        "fiber": (row["total_fiber"] or 0) / d,
        "vitamin_b12": (row["total_b12"] or 0) / d,
        "vitamin_d": (row["total_d"] or 0) / d,
        "folate": (row["total_folate"] or 0) / d,
        "iron": (row["total_iron"] or 0) / d,
        "zinc": (row["total_zinc"] or 0) / d,
        "magnesium": (row["total_magnesium"] or 0) / d,
        "calcium": (row["total_calcium"] or 0) / d,
        "potassium": (row["total_potassium"] or 0) / d,
        "omega_3": (row["total_omega_3"] or 0) / d,
        "vitamin_a": (row["total_vitamin_a"] or 0) / d,
        "vitamin_c": (row["total_vitamin_c"] or 0) / d,
    }

    alerts = []
    for nutrient, target_info in RDA_TARGETS.items():
        actual = daily_avg.get(nutrient, 0)
        target = target_info["target"]
        pct = (actual / target) * 100 if target > 0 else 0

        if pct < 70:
            severity = "LOW" if pct >= 50 else "VERY LOW"
            alerts.append(f"{nutrient}: {int(pct)}% of RDA ({severity})")

    if not alerts:
        return "No nutrition alerts"

    return "=== NUTRITION ALERTS ===\n" + "\n".join(alerts)
