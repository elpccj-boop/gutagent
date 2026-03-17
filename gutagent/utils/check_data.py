"""Check GutAgent database contents.

Usage:
    python -m gutagent.utils.check_data              # show all
    python -m gutagent.utils.check_data meals        # just meals
    python -m gutagent.utils.check_data symptoms vitals  # symptoms and vitals
    python -m gutagent.utils.check_data labs --status abnormal  # filter labs by status
    python -m gutagent.utils.check_data vitals --days 7  # last 7 days only
    python -m gutagent.utils.check_data nutrition    # nutrition summary + alerts
    python -m gutagent.utils.check_data recipes      # saved recipes
"""

import sqlite3
import os
import sys
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "../..", "data", "gutagent.db")

SECTIONS = ["meals", "symptoms", "meds", "vitals", "labs", "sleep", "exercise", "journal", "recipes", "nutrition"]


def parse_args():
    args = sys.argv[1:]
    sections = []
    status_filter = None
    days_filter = None

    i = 0
    while i < len(args):
        if args[i] == "--status" and i + 1 < len(args):
            status_filter = args[i + 1]
            i += 2
        elif args[i] == "--days" and i + 1 < len(args):
            days_filter = int(args[i + 1])
            i += 2
        else:
            sections.append(args[i])
            i += 1

    if not sections:
        sections = SECTIONS

    return sections, status_filter, days_filter


def show_meals(conn, days_filter):
    print("\n--- Meals ---")
    query = """
        SELECT m.*, mn.calories, mn.protein, mn.carbs, mn.fat, mn.fiber
        FROM meals m
        LEFT JOIN meal_nutrition mn ON m.id = mn.meal_id
        ORDER BY m.occurred_at
    """
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        query = f"""
            SELECT m.*, mn.calories, mn.protein, mn.carbs, mn.fat, mn.fiber
            FROM meals m
            LEFT JOIN meal_nutrition mn ON m.id = mn.meal_id
            WHERE m.occurred_at >= '{cutoff}'
            ORDER BY m.occurred_at
        """
    for row in conn.execute(query):
        nutrition = ""
        if row['calories']:
            nutrition = f" [{int(row['calories'])} cal, {int(row['protein'])}g protein]"
        print(f"{row['id']}: {row['occurred_at']} | {row['meal_type']} | {row['description']}{nutrition}")


def show_symptoms(conn, days_filter):
    print("\n--- Symptoms ---")
    query = "SELECT * FROM symptoms ORDER BY occurred_at"
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        query = f"SELECT * FROM symptoms WHERE occurred_at >= '{cutoff}' ORDER BY occurred_at"
    for row in conn.execute(query):
        print(f"{row['id']}: {row['occurred_at']} | {row['symptom']} | severity: {row['severity']} | {row['notes'] or ''}")


def show_meds(conn, days_filter):
    print("\n--- Medication Events ---")
    query = "SELECT * FROM medications ORDER BY occurred_at"
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        query = f"SELECT * FROM medications WHERE occurred_at >= '{cutoff}' ORDER BY occurred_at"
    for row in conn.execute(query):
        print(f"{row['id']}: {row['occurred_at']} | {row['medication']} | {row['event_type']} | {row['dose'] or ''} | {row['notes'] or ''}")


def show_vitals(conn, days_filter):
    print("\n--- Vitals ---")
    query = "SELECT * FROM vitals ORDER BY occurred_at"
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        query = f"SELECT * FROM vitals WHERE occurred_at >= '{cutoff}' ORDER BY occurred_at"
    for row in conn.execute(query):
        if row['vital_type'] == 'blood_pressure':
            print(f"{row['id']}: {row['occurred_at']} | BP: {row['systolic']}/{row['diastolic']} HR:{row['heart_rate']} | {row['notes'] or ''}")
        else:
            print(f"{row['id']}: {row['occurred_at']} | {row['vital_type']}: {row['value']} {row['unit']} | {row['notes'] or ''}")


def show_labs(conn, status_filter):
    print("\n--- Labs ---")
    query = "SELECT * FROM labs ORDER BY test_date, status"
    if status_filter:
        query = f"SELECT * FROM labs WHERE status = '{status_filter}' ORDER BY test_date, test_name"
    for row in conn.execute(query):
        val = f"{row['value']} {row['unit']}" if row['value'] else "—"
        ref = f"(ref: {row['reference_range']})" if row['reference_range'] else ""
        notes = f"| {row['notes']}" if row['notes'] else ""
        print(f"{row['test_date']} | {row['test_name']}: {val} {ref} [{row['status']}] {notes}")


def show_sleep(conn, days_filter):
    print("\n--- Sleep ---")
    query = "SELECT * FROM sleep ORDER BY occurred_at"
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        query = f"SELECT * FROM sleep WHERE occurred_at >= '{cutoff}' ORDER BY occurred_at"
    for row in conn.execute(query):
        hours = f"{row['hours']} hrs" if row['hours'] else ""
        quality = row['quality'] or ""
        print(f"{row['id']}: {row['occurred_at']} | {hours} {quality} | {row['notes'] or ''}")


def show_exercise(conn, days_filter):
    print("\n--- Exercise ---")
    query = "SELECT * FROM exercise ORDER BY occurred_at"
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        query = f"SELECT * FROM exercise WHERE occurred_at >= '{cutoff}' ORDER BY occurred_at"
    for row in conn.execute(query):
        duration = f"({row['duration_minutes']} min)" if row['duration_minutes'] else ""
        print(f"{row['id']}: {row['occurred_at']} | {row['activity']} {duration} | {row['notes'] or ''}")


def show_journal(conn, days_filter):
    print("\n--- Journal ---")
    query = "SELECT * FROM journal ORDER BY logged_at"
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        query = f"SELECT * FROM journal WHERE logged_at >= '{cutoff}' ORDER BY logged_at"
    for row in conn.execute(query):
        desc = row['description'][:80] + "..." if len(row['description']) > 80 else row['description']
        print(f"{row['id']}: {row['logged_at']} | {desc}")


def show_recipes(conn, days_filter):
    print("\n--- Recipes ---")
    query = "SELECT * FROM recipes ORDER BY name"
    for row in conn.execute(query):
        import json
        ingredients = json.loads(row['ingredients'])
        ingredient_names = [i.get('name', '?') for i in ingredients]
        print(f"{row['id']}: {row['name']} | {len(ingredients)} ingredients: {', '.join(ingredient_names[:5])}{'...' if len(ingredient_names) > 5 else ''}")


def show_nutrition(conn, days_filter):
    print("\n--- Nutrition Summary ---")
    days = days_filter or 3
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    row = conn.execute("""
        SELECT 
            COUNT(DISTINCT DATE(m.occurred_at)) as days_with_data,
            SUM(mn.calories) as total_cal,
            SUM(mn.protein) as total_protein,
            SUM(mn.carbs) as total_carbs,
            SUM(mn.fat) as total_fat,
            SUM(mn.fiber) as total_fiber,
            SUM(mn.vitamin_b12) as total_b12,
            SUM(mn.vitamin_d) as total_d,
            SUM(mn.folate) as total_folate,
            SUM(mn.iron) as total_iron,
            SUM(mn.zinc) as total_zinc,
            SUM(mn.magnesium) as total_mag,
            SUM(mn.calcium) as total_calcium,
            SUM(mn.potassium) as total_potassium,
            SUM(mn.omega_3) as total_omega3,
            SUM(mn.vitamin_a) as total_a,
            SUM(mn.vitamin_c) as total_c
        FROM meals m
        JOIN meal_nutrition mn ON m.id = mn.meal_id
        WHERE m.occurred_at >= ?
    """, (cutoff,)).fetchone()

    if not row or not row['days_with_data']:
        print(f"No nutrition data in the last {days} days.")
        return

    d = row['days_with_data']
    print(f"Last {days} days ({d} days with data):\n")

    def avg(v):
        return round(v / d, 1) if v and d else 0

    print("Macros:")
    print(f"  Calories:   {avg(row['total_cal'])} / day")
    print(f"  Protein:    {avg(row['total_protein'])}g / day")
    print(f"  Carbs:      {avg(row['total_carbs'])}g / day")
    print(f"  Fat:        {avg(row['total_fat'])}g / day")
    print(f"  Fiber:      {avg(row['total_fiber'])}g / day (target: 25g)")
    print()
    print("Micronutrients:")
    print(f"  Vitamin B12: {avg(row['total_b12'])}μg / day (target: 2.4μg)")
    print(f"  Vitamin D:   {avg(row['total_d'])}μg / day (target: 15μg)")
    print(f"  Folate:      {avg(row['total_folate'])}μg / day (target: 400μg)")
    print(f"  Iron:        {avg(row['total_iron'])}mg / day (target: 8mg)")
    print(f"  Zinc:        {avg(row['total_zinc'])}mg / day (target: 11mg)")
    print(f"  Magnesium:   {avg(row['total_mag'])}mg / day (target: 400mg)")
    print(f"  Calcium:     {avg(row['total_calcium'])}mg / day (target: 1000mg)")
    print(f"  Potassium:   {avg(row['total_potassium'])}mg / day (target: 2600mg)")
    print(f"  Omega-3:     {avg(row['total_omega3'])}g / day (target: 1.6g)")
    print(f"  Vitamin A:   {avg(row['total_a'])}μg / day (target: 900μg)")
    print(f"  Vitamin C:   {avg(row['total_c'])}mg / day (target: 90mg)")

    # Show alerts
    print("\n--- Nutrition Alerts ---")
    from gutagent.db.models import get_nutrition_alerts
    alerts = get_nutrition_alerts(days)
    if not alerts:
        print("  No deficiencies or excesses detected.")
    else:
        for a in alerts:
            name = a['nutrient'].replace('_', ' ').title()
            if a['type'] == 'deficiency':
                severity = "⚠️" if a['severity'] == 'low' else "🔴"
                print(f"  {severity} Low {name}: {a['daily_average']}{a['unit']}/day ({a['percent_of_rda']}% of {a['target']}{a['unit']} target)")
            else:  # excess
                severity = "⚠️" if a['severity'] == 'high' else "🔴"
                print(f"  {severity} High {name}: {a['daily_average']}{a['unit']}/day (exceeds {a['upper_limit']}{a['unit']} safe limit)")


def main():
    sections, status_filter, days_filter = parse_args()

    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    for section in sections:
        if section == "meals":
            show_meals(conn, days_filter)
        elif section == "symptoms":
            show_symptoms(conn, days_filter)
        elif section == "meds":
            show_meds(conn, days_filter)
        elif section == "vitals":
            show_vitals(conn, days_filter)
        elif section == "labs":
            show_labs(conn, status_filter)
        elif section == "sleep":
            show_sleep(conn, days_filter)
        elif section == "exercise":
            show_exercise(conn, days_filter)
        elif section == "journal":
            show_journal(conn, days_filter)
        elif section == "recipes":
            show_recipes(conn, days_filter)
        elif section == "nutrition":
            show_nutrition(conn, days_filter)
        else:
            print(f"Unknown section: {section}. Options: {', '.join(SECTIONS)}")

    conn.close()


if __name__ == "__main__":
    main()
