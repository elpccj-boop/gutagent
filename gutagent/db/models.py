"""SQLite database setup and operations."""

import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gutagent.db")

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
            description TEXT NOT NULL,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS symptoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TIMESTAMP,
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
            created_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS meal_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER NOT NULL,
            food_name TEXT NOT NULL,
            quantity REAL,
            unit TEXT,
            is_spice BOOLEAN DEFAULT 0,
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
    allowed_tables = {"meals", "symptoms", "vitals", "medication_events", "journal", "sleep", "exercise"}
    if table not in allowed_tables:
        return {"error": f"Cannot delete from table: {table}"}

    conn = get_connection()
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "table": table, "id": entry_id}


# --- Meal Operations ---

def log_meal(meal_type: str | None, description: str,
             notes: str | None = None, occurred_at: str | None = None) -> dict:
    """Log a meal entry (basic, without nutrition)."""
    timestamp = validate_timestamp(occurred_at)
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO meals (meal_type, description, notes, occurred_at) VALUES (?, ?, ?, ?)",
        (meal_type, description, notes, timestamp)
    )
    conn.commit()
    meal_id = cursor.lastrowid
    conn.close()
    return {"id": meal_id, "status": "logged", "meal_type": meal_type, "description": description, "when": timestamp}


def log_meal_with_nutrition(meal_type: str | None, description: str, items: list[dict],
                            nutrition: dict, notes: str | None = None,
                            occurred_at: str | None = None) -> dict:
    """Log a meal with itemized foods and calculated nutrition."""
    timestamp = validate_timestamp(occurred_at)
    conn = get_connection()

    # Insert meal
    cursor = conn.execute(
        "INSERT INTO meals (meal_type, description, notes, occurred_at) VALUES (?, ?, ?, ?)",
        (meal_type, description, notes, timestamp)
    )
    meal_id = cursor.lastrowid

    # Insert meal items
    for item in items:
        conn.execute(
            """INSERT INTO meal_items (meal_id, food_name, quantity, unit, is_spice)
               VALUES (?, ?, ?, ?, ?)""",
            (meal_id, item.get("food_name"), item.get("quantity"),
             item.get("unit"), item.get("is_spice", False))
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

    return {
        "id": meal_id,
        "status": "logged",
        "meal_type": meal_type,
        "description": description,
        "when": timestamp,
        "items_count": len(items),
        "nutrition": nutrition
    }


def get_recent_meals(days_back: int = 7) -> list[dict]:
    """Get meals from the last N days."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT * FROM meals WHERE occurred_at >= ? ORDER BY occurred_at DESC", (cutoff,)
    ).fetchall()
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
        table: One of meals, symptoms, vitals, medication_events, sleep, exercise, journal
        date: Date string in YYYY-MM-DD format

    Returns:
        List of entries with all fields including id
    """
    allowed_tables = {"meals", "symptoms", "vitals", "medication_events", "sleep", "exercise", "journal"}
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


# -- Labs Operations --

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

def save_recipe(name: str, ingredients: list[dict], notes: str | None = None) -> dict:
    """Save or update a recipe."""
    conn = get_connection()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Check if recipe exists (case-insensitive)
    existing = conn.execute(
        "SELECT id FROM recipes WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE recipes SET ingredients = ?, notes = ? WHERE id = ?",
            (json.dumps(ingredients), notes, existing["id"])
        )
        recipe_id = existing["id"]
        action = "updated"
    else:
        cursor = conn.execute(
            "INSERT INTO recipes (name, ingredients, notes, created_at) VALUES (?, ?, ?, ?)",
            (name, json.dumps(ingredients), notes, timestamp)
        )
        recipe_id = cursor.lastrowid
        action = "created"

    conn.commit()
    conn.close()

    return {"id": recipe_id, "status": action, "name": name, "ingredients_count": len(ingredients)}


def get_recipe(name: str) -> dict | None:
    """Get a recipe by name (case-insensitive)."""
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
            "created_at": row["created_at"]
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

def get_nutrition_summary(days: int = 3) -> dict:
    """Get nutrition totals and daily averages for the past N days."""
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
        return {"days_with_data": 0, "message": "No nutrition data in this period"}

    days_with_data = row["days_with_data"]

    def safe_val(v):
        return round(v, 1) if v else 0

    def safe_avg(v):
        return round(safe_val(v) / days_with_data, 1) if days_with_data else 0

    return {
        "period_days": days,
        "days_with_data": days_with_data,
        "totals": {
            "calories": safe_val(row["total_calories"]),
            "protein": safe_val(row["total_protein"]),
            "carbs": safe_val(row["total_carbs"]),
            "fat": safe_val(row["total_fat"]),
            "fiber": safe_val(row["total_fiber"]),
            "vitamin_b12": safe_val(row["total_b12"]),
            "vitamin_d": safe_val(row["total_d"]),
            "folate": safe_val(row["total_folate"]),
            "iron": safe_val(row["total_iron"]),
            "zinc": safe_val(row["total_zinc"]),
            "magnesium": safe_val(row["total_magnesium"]),
            "calcium": safe_val(row["total_calcium"]),
            "potassium": safe_val(row["total_potassium"]),
            "omega_3": safe_val(row["total_omega_3"]),
            "vitamin_a": safe_val(row["total_vitamin_a"]),
            "vitamin_c": safe_val(row["total_vitamin_c"]),
        },
        "daily_averages": {
            "calories": safe_avg(row["total_calories"]),
            "protein": safe_avg(row["total_protein"]),
            "carbs": safe_avg(row["total_carbs"]),
            "fat": safe_avg(row["total_fat"]),
            "fiber": safe_avg(row["total_fiber"]),
            "vitamin_b12": safe_avg(row["total_b12"]),
            "vitamin_d": safe_avg(row["total_d"]),
            "folate": safe_avg(row["total_folate"]),
            "iron": safe_avg(row["total_iron"]),
            "zinc": safe_avg(row["total_zinc"]),
            "magnesium": safe_avg(row["total_magnesium"]),
            "calcium": safe_avg(row["total_calcium"]),
            "potassium": safe_avg(row["total_potassium"]),
            "omega_3": safe_avg(row["total_omega_3"]),
            "vitamin_a": safe_avg(row["total_vitamin_a"]),
            "vitamin_c": safe_avg(row["total_vitamin_c"]),
        }
    }


def get_nutrition_alerts(days: int = 3) -> list[dict]:
    """Check for nutrient deficiencies and excesses based on RDA values."""
    summary = get_nutrition_summary(days)

    if summary.get("days_with_data", 0) == 0:
        return []

    alerts = []
    daily_avg = summary["daily_averages"]

    for nutrient, target_info in RDA_TARGETS.items():
        actual = daily_avg.get(nutrient, 0)
        target = target_info["target"]
        upper_limit = target_info.get("upper_limit")
        pct = (actual / target) * 100 if target > 0 else 0

        # Check for deficiency
        if pct < 70:
            alerts.append({
                "nutrient": nutrient,
                "daily_average": actual,
                "target": target,
                "unit": target_info["unit"],
                "percent_of_rda": round(pct, 1),
                "severity": "low" if pct >= 50 else "very_low",
                "type": "deficiency"
            })

        # Check for excess (only for nutrients with upper limits)
        if upper_limit and actual > upper_limit:
            pct_of_limit = (actual / upper_limit) * 100
            alerts.append({
                "nutrient": nutrient,
                "daily_average": actual,
                "upper_limit": upper_limit,
                "unit": target_info["unit"],
                "percent_of_upper_limit": round(pct_of_limit, 1),
                "severity": "high" if pct_of_limit < 150 else "very_high",
                "type": "excess"
            })

    # Sort: excesses first (more urgent), then deficiencies by percent
    return sorted(alerts, key=lambda x: (x["type"] == "deficiency", x.get("percent_of_rda", 0)))
