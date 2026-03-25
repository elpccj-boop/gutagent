"""Logging operations for all health data: meals, symptoms, vitals, labs, meds, sleep, exercise, journal."""

from datetime import datetime, timedelta
from .connection import get_connection, validate_timestamp
from .common import round_nutrition


# =============================================================================
# MEALS
# =============================================================================

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

    # Round nutrition values before storing
    nutrition = round_nutrition(nutrition)

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

    # Compact return
    cal = int(nutrition.get("calories", 0))
    pro = int(nutrition.get("protein", 0))
    fat = int(nutrition.get("fat", 0))
    carb = int(nutrition.get("carbs", 0))
    fiber = int(nutrition.get("fiber", 0))

    return {
        "id": meal_id,
        "status": "logged",
        "meal_type": meal_type,
        "when": timestamp,
        "summary": f"{description} — {cal} cal, {carb}g carb, {fiber}g fiber, {pro}g p, {fat}g f"
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


# =============================================================================
# SYMPTOMS
# =============================================================================

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


# =============================================================================
# MEDICATIONS
# =============================================================================

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


def get_current_and_recent_meds(days_back: int = 30) -> list:
    """
    Get current medications + recent changes.
    Returns: recent events (last N days) + the latest 'started' event for each medication.
    """
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
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


def get_meds_summary(days_back: int = 0) -> str:
    """
    Get medication history as a compact text summary.
    Returns pre-formatted summary for Claude to analyze.
    """
    conn = get_connection()
    lines = []
    # Current medications (started but not stopped)
    current = conn.execute("""
        SELECT m1.medication, m1.dose, m1.occurred_at as started_at, m1.notes
        FROM medications m1
        WHERE m1.event_type = 'started'
          AND NOT EXISTS (
              SELECT 1 FROM medications m2 
              WHERE m2.medication = m1.medication 
                AND m2.event_type = 'stopped'
                AND m2.occurred_at > m1.occurred_at
          )
        ORDER BY m1.occurred_at DESC
    """).fetchall()

    if current:
        lines.append("=== CURRENT MEDICATIONS ===")
        for med in current:
            dose = f" ({med['dose']})" if med['dose'] else ""
            started = med['started_at'][:10]
            lines.append(f"  {med['medication']}{dose} — since {started}")

    # Recent changes
    if days_back > 0:
        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        changes = conn.execute("""
            SELECT * FROM medications 
            WHERE occurred_at >= ? 
            ORDER BY occurred_at DESC
        """, (cutoff,)).fetchall()
    else:
        changes = conn.execute("""
            SELECT * FROM medications ORDER BY occurred_at DESC
        """).fetchall()

    # Group by event type
    started = [m for m in changes if m['event_type'] == 'started']
    stopped = [m for m in changes if m['event_type'] == 'stopped']
    dose_changed = [m for m in changes if m['event_type'] == 'dose_changed']

    period = f"last {days_back}d" if days_back > 0 else "all time"

    if started or stopped or dose_changed:
        lines.append(f"\n=== MEDICATION HISTORY ({period}) ===")

        if started:
            lines.append(f"Started ({len(started)}):")
            for m in started[:10]:  # Limit to 10
                dose = f" ({m['dose']})" if m['dose'] else ""
                lines.append(f"  {m['occurred_at'][:10]}: {m['medication']}{dose}")

        if stopped:
            lines.append(f"Stopped ({len(stopped)}):")
            for m in stopped[:10]:
                lines.append(f"  {m['occurred_at'][:10]}: {m['medication']}")

        if dose_changed:
            lines.append(f"Dose changes ({len(dose_changed)}):")
            for m in dose_changed[:10]:
                dose = f" → {m['dose']}" if m['dose'] else ""
                lines.append(f"  {m['occurred_at'][:10]}: {m['medication']}{dose}")

        lines.append(f"\nTotal events: {len(changes)}")

    conn.close()

    if not lines:
        return "No medication history found."

    return "\n".join(lines)


# =============================================================================
# VITALS
# =============================================================================

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


def get_recent_vitals(days_back: int = 7, vital_type: str | None = None) -> list:
    """Get vital signs from last N days as a list of dicts."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    if vital_type:
        rows = conn.execute(
            "SELECT * FROM vitals WHERE vital_type = ? AND occurred_at >= ? ORDER BY occurred_at DESC",
            (vital_type, cutoff)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM vitals WHERE occurred_at >= ? ORDER BY occurred_at DESC",
            (cutoff,)
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def get_vitals_summary(days_back: int = 0, vital_type: str | None = None) -> str:
    """
    Get vital signs as a compact text summary.
    Returns pre-formatted summary for Claude to analyze.
    """
    conn = get_connection()

    if days_back > 0:
        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    else:
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    lines = []

    # Blood Pressure
    if vital_type is None or vital_type == "blood_pressure":
        bp_rows = conn.execute("""
            SELECT systolic, diastolic, heart_rate, occurred_at, notes
            FROM vitals 
            WHERE vital_type = 'blood_pressure' AND occurred_at >= ?
            ORDER BY occurred_at DESC
        """, (cutoff,)).fetchall()

        if bp_rows:
            lines.append("=== BLOOD PRESSURE ===")
            lines.append("Recent readings:")
            for row in bp_rows[:7]:
                date = row["occurred_at"][:10]
                note = f" ({row['notes'][:30]})" if row["notes"] else ""
                lines.append(f"  {date}: {row['systolic']}/{row['diastolic']} HR:{row['heart_rate'] or '?'}{note}")

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

    # Weight
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

    # Other vitals
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


# =============================================================================
# LABS
# =============================================================================

def log_lab(test_name: str, test_date: str | None = None, value: float | None = None,
            unit: str | None = None, reference_range: str | None = None,
            status: str | None = None, notes: str | None = None) -> dict:
    """Log a lab test result."""
    validated_test_date = validate_timestamp(test_date)
    test_date_str = validated_test_date.split()[0]
    logged_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO labs (test_name, test_date, value, unit, reference_range, status, notes, logged_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (test_name, test_date_str, value, unit, reference_range, status, notes, logged_at)
    )
    conn.commit()
    lab_id = cursor.lastrowid
    conn.close()

    summary_parts = [test_name]
    if value is not None:
        summary_parts.append(f"{value}")
    if unit:
        summary_parts.append(unit)
    if status:
        summary_parts.append(f"({status})")

    return {"id": lab_id, "status": "logged", "test_name": test_name,
            "test_date": test_date_str, "summary": " ".join(summary_parts)}


def get_labs_by_date(test_date: str | None = None) -> list:
    """Get labs from a specific date or most recent date."""
    conn = get_connection()
    if test_date:
        rows = conn.execute(
            "SELECT * FROM labs WHERE test_date = ? ORDER BY status, test_name",
            (test_date,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM labs WHERE test_date = (SELECT MAX(test_date) FROM labs) ORDER BY status, test_name"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_labs_per_test() -> list:
    """Get the most recent value for EACH test type."""
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


def search_labs_by_test(test_name: str) -> list:
    """Get all results for a specific test (e.g., CRP history)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM labs WHERE LOWER(test_name) LIKE LOWER(?) ORDER BY test_date DESC",
        (f"%{test_name}%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# =============================================================================
# SLEEP
# =============================================================================

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


# =============================================================================
# EXERCISE
# =============================================================================

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


# =============================================================================
# JOURNAL
# =============================================================================

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
