"""Nutrition calculations, RDA targets, and alerts."""

from datetime import datetime, timedelta
from .connection import get_connection


# Global RDA targets - set by set_rda_targets()
RDA_TARGETS = {}


def set_rda_targets(profile: dict):
    """Set RDA targets based on profile."""
    gender = 'male'
    age = 30

    if profile:
        personal = profile.get("personal", {})
        sex = personal.get("sex", "").lower()
        dob_age = _calculate_age_from_dob(personal.get("dob", ""))

        if sex in ['f', 'female', 'woman']:
            gender = 'female'
        if dob_age:
            age = dob_age

    new_targets = _calculate_rda_targets(gender, age)
    RDA_TARGETS.clear()
    RDA_TARGETS.update(new_targets)


def _calculate_age_from_dob(dob_string: str) -> int | None:
    """Calculate age from DOB string (YYYY-MM-DD format)."""
    if not dob_string or dob_string == "YYYY-MM-DD":
        return None
    try:
        dob = datetime.strptime(dob_string, "%Y-%m-%d")
        today = datetime.now()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age
    except (ValueError, AttributeError):
        return None


def _calculate_rda_targets(gender: str, age: int) -> dict:
    """Calculate RDA targets based on gender and age.
    target = daily recommended intake
    upper_limit = safe upper limit (None if no concern)
    """
    targets = {
        "fiber": {"target": 38, "unit": "g", "upper_limit": None},
        "vitamin_b12": {"target": 2.4, "unit": "μg", "upper_limit": None},
        "vitamin_d": {"target": 600, "unit": "IU", "upper_limit": 4000},
        "folate": {"target": 400, "unit": "μg", "upper_limit": 1000},
        "iron": {"target": 8, "unit": "mg", "upper_limit": 45},
        "zinc": {"target": 11, "unit": "mg", "upper_limit": 40},
        "magnesium": {"target": 420, "unit": "mg", "upper_limit": None},
        "calcium": {"target": 1000, "unit": "mg", "upper_limit": 2500},
        "potassium": {"target": 3400, "unit": "mg", "upper_limit": None},
        "omega_3": {"target": 1.6, "unit": "g", "upper_limit": None},
        "vitamin_a": {"target": 3000, "unit": "IU", "upper_limit": 10000},
        "vitamin_c": {"target": 90, "unit": "mg", "upper_limit": 2000},
    }

    if gender == "female":
        targets["fiber"]["target"] = 25 if age < 51 else 21
        targets["iron"]["target"] = 18 if age < 51 else 8
        targets["zinc"]["target"] = 8
        targets["magnesium"]["target"] = 310 if age < 31 else 320
        targets["calcium"]["target"] = 1200 if age >= 51 else 1000
        targets["potassium"]["target"] = 2600
        targets["omega_3"]["target"] = 1.1
        targets["vitamin_a"]["target"] = 2333  # 700 μg RAE
        targets["vitamin_c"]["target"] = 75
    else:  # male
        targets["fiber"]["target"] = 38 if age < 51 else 30
        targets["magnesium"]["target"] = 400 if age < 31 else 420
        targets["calcium"]["target"] = 1200 if age >= 71 else 1000

    # Age-specific overrides (both genders)
    if age >= 51:
        targets["calcium"]["upper_limit"] = 2000

    if age >= 71:
        targets["vitamin_d"]["target"] = 800
        targets["calcium"]["target"] = 1200

    return targets


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
        "calories": round((row["total_calories"] or 0) / d),
        "protein": round((row["total_protein"] or 0) / d),
        "fat": round((row["total_fat"] or 0) / d),
        "carbs": round((row["total_carbs"] or 0) / d),
        "fiber": round((row["total_fiber"] or 0) / d),
        "vitamin_b12": round((row["total_b12"] or 0) / d, 1),
        "vitamin_d": round((row["total_d"] or 0) / d),
        "folate": round((row["total_folate"] or 0) / d),
        "iron": round((row["total_iron"] or 0) / d, 1),
        "zinc": round((row["total_zinc"] or 0) / d, 1),
        "magnesium": round((row["total_magnesium"] or 0) / d),
        "calcium": round((row["total_calcium"] or 0) / d),
        "potassium": round((row["total_potassium"] or 0) / d),
        "omega_3": round((row["total_omega_3"] or 0) / d, 1),
        "vitamin_a": round((row["total_vitamin_a"] or 0) / d),
        "vitamin_c": round((row["total_vitamin_c"] or 0) / d),
    }

    alerts = []
    for nutrient, target_info in RDA_TARGETS.items():
        actual = daily_avg.get(nutrient, 0)
        target = target_info["target"]
        pct = (actual / target) * 100 if target > 0 else 0

        if pct < 70:
            severity = "LOW" if pct >= 50 else "VERY LOW"
            unit = target_info["unit"]
            alerts.append(f"{nutrient}: {actual}{unit}/day (target: {target}{unit}) - {int(pct)}% ({severity})")

    if not alerts:
        return "No nutrition alerts"

    return "=== NUTRITION ALERTS ===\n" + "\n".join(alerts)
