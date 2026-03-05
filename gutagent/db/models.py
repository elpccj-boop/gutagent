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

        CREATE TABLE IF NOT EXISTS correlations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food TEXT NOT NULL,
            symptom TEXT NOT NULL,
            occurrences INTEGER DEFAULT 1,
            avg_severity REAL,
            avg_hours_after REAL,
            confidence TEXT DEFAULT 'low',
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
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
    """)
    conn.commit()
    conn.close()

def update_entry(table: str, entry_id: int, updates: dict) -> dict:
    """Update fields on an existing entry."""
    allowed_tables = {"meals", "symptoms", "vitals", "medication_events"}
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

def delete_entry(table: str, entry_id: int) -> dict:
    """Delete an entry by id."""
    allowed_tables = {"meals", "symptoms", "vitals", "medication_events"}
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

# --- Pattern analysis ---

def analyze_food_symptom_patterns(
    days_back: int = 30,
    symptom_focus: str | None = None,
    food_focus: str | None = None
) -> dict:
    """
    Analyze correlations between meals and symptoms.
    Looks for symptoms that occur within 0.5-8 hours of eating specific foods.

    Tracks both positive evidence (food followed by symptom) and negative evidence
    (food eaten with no symptom) to compute a symptom rate. Also detects foods that
    always co-occur so the user knows when triggers can't be isolated.
    """
    from bisect import bisect_left, bisect_right
    from collections import Counter

    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

    meals = conn.execute(
        "SELECT * FROM meals WHERE occurred_at >= ? ORDER BY occurred_at", (cutoff,)
    ).fetchall()

    symptoms_query = "SELECT * FROM symptoms WHERE occurred_at >= ?"
    params = [cutoff]
    if symptom_focus:
        symptoms_query += " AND symptom LIKE ?"
        params.append(f"%{symptom_focus}%")

    symptom_rows = conn.execute(
        symptoms_query + " ORDER BY occurred_at", params
    ).fetchall()
    conn.close()

    if not meals or not symptom_rows:
        return {
            "status": "insufficient_data",
            "meals_count": len(meals),
            "symptoms_count": len(symptom_rows),
            "message": "Need more logged meals and symptoms to find patterns. Keep logging!"
        }

    # Parse meal data: times, per-meal food lists, and total food frequency
    meal_times = []
    meal_foods = []
    food_total_count = Counter()  # how many meals contain each food
    food_co_occurs = {}  # food -> Counter of other foods eaten in the same meal

    for meal in meals:
        mt = datetime.fromisoformat(meal["occurred_at"])
        foods = json.loads(meal["foods"]) if meal["foods"] else []
        if food_focus:
            foods = [f for f in foods if food_focus.lower() in f.lower()]
        foods_lower = [f.lower() for f in foods]

        meal_times.append(mt)
        meal_foods.append(foods)

        for fl in foods_lower:
            food_total_count[fl] += 1
            if fl not in food_co_occurs:
                food_co_occurs[fl] = Counter()
            for other in foods_lower:
                if other != fl:
                    food_co_occurs[fl][other] += 1

    # Sort symptom times for efficient lookup (already sorted from SQL, but parse them)
    sx_times = [datetime.fromisoformat(s["occurred_at"]) for s in symptom_rows]

    # For each meal, find symptoms in the 0.5-8 hour window using bisect
    # Track both hits (food + symptom) and misses (food + no symptom)
    correlations = {}
    food_no_symptom_count = Counter()  # meals where food had NO symptom follow

    for i, (mt, foods) in enumerate(zip(meal_times, meal_foods)):
        window_start = mt + timedelta(hours=0.5)
        window_end = mt + timedelta(hours=8)

        # Find symptoms in this meal's window via bisect
        lo = bisect_left(sx_times, window_start)
        hi = bisect_right(sx_times, window_end)
        window_symptoms = symptom_rows[lo:hi]

        foods_lower = [f.lower() for f in foods]

        if not window_symptoms:
            # Negative evidence: this meal had no symptoms in the window
            for fl in foods_lower:
                food_no_symptom_count[fl] += 1
            continue

        for sx_idx in range(lo, hi):
            symptom_row = symptom_rows[sx_idx]
            hours_diff = (sx_times[sx_idx] - mt).total_seconds() / 3600

            for food, fl in zip(foods, foods_lower):
                key = f"{fl}|{symptom_row['symptom']}"
                if key not in correlations:
                    correlations[key] = {
                        "food": food,
                        "symptom": symptom_row["symptom"],
                        "occurrences": 0,
                        "total_severity": 0,
                        "total_hours": 0,
                        "instances": []
                    }
                c = correlations[key]
                c["occurrences"] += 1
                c["total_severity"] += symptom_row["severity"]
                c["total_hours"] += hours_diff
                c["instances"].append({
                    "meal_time": meals[i]["occurred_at"],
                    "symptom_time": symptom_row["occurred_at"],
                    "hours_after": round(hours_diff, 1),
                    "severity": symptom_row["severity"]
                })

        # Foods in this meal that had at least one symptom are NOT counted as misses.
        # Foods with no matching symptom type still get negative evidence for those types,
        # but that's handled implicitly by total_count - occurrences below.

    # Score correlations using symptom rate (not just raw count)
    results = []
    for key, c in correlations.items():
        fl = c["food"].lower()
        n = c["occurrences"]
        total_meals_with_food = food_total_count[fl]
        meals_without_symptom = food_no_symptom_count.get(fl, 0)
        symptom_rate = n / total_meals_with_food if total_meals_with_food > 0 else 0

        avg_severity = c["total_severity"] / n
        avg_hours = c["total_hours"] / n

        # Confidence: requires both sufficient data AND a meaningful symptom rate
        if total_meals_with_food < 3:
            confidence = "low"
        elif symptom_rate >= 0.5 and n >= 3:
            confidence = "high"
        elif symptom_rate >= 0.3 and n >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        # Score: symptom_rate * avg_severity gives a balanced ranking
        # A food eaten 20 times with 2 symptoms scores lower than one eaten 5 times with 4 symptoms
        score = symptom_rate * avg_severity

        # Detect co-occurring foods that always appear together
        co_occurs = food_co_occurs.get(fl, Counter())
        always_together = [
            food for food, count in co_occurs.items()
            if count == total_meals_with_food and total_meals_with_food >= 2
        ]

        result = {
            "food": c["food"],
            "symptom": c["symptom"],
            "occurrences": n,
            "times_eaten": total_meals_with_food,
            "times_no_symptom": meals_without_symptom,
            "symptom_rate": round(symptom_rate, 2),
            "avg_severity": round(avg_severity, 1),
            "avg_hours_after": round(avg_hours, 1),
            "confidence": confidence,
            "score": round(score, 2),
            "instances": c["instances"]
        }
        if always_together:
            result["always_eaten_with"] = always_together

        results.append(result)

    results.sort(key=lambda x: x["score"], reverse=True)

    # Identify safe foods: eaten 3+ times with no symptoms at all
    foods_with_symptoms = {c["food"].lower() for c in correlations.values()}
    safe_foods = [
        {"food": food, "times_eaten": count}
        for food, count in food_total_count.items()
        if food not in foods_with_symptoms and count >= 3
    ]
    safe_foods.sort(key=lambda x: x["times_eaten"], reverse=True)

    return {
        "status": "ok",
        "days_analyzed": days_back,
        "meals_count": len(meals),
        "symptoms_count": len(symptom_rows),
        "correlations": results[:10],
        "safe_foods": safe_foods[:10],
        "message": f"Analyzed {len(meals)} meals and {len(symptom_rows)} symptoms over {days_back} days."
    }
