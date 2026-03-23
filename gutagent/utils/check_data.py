"""Check GutAgent database contents.

Usage:
    python -m gutagent.utils.check_data              # show all
    python -m gutagent.utils.check_data meals        # just meals
    python -m gutagent.utils.check_data meals --days 3   # last 3 days
    python -m gutagent.utils.check_data meals --full     # show items + all nutrition
    python -m gutagent.utils.check_data symptoms vitals  # multiple sections
    python -m gutagent.utils.check_data labs --status low  # filter labs
    python -m gutagent.utils.check_data nutrition    # summary + alerts
    python -m gutagent.utils.check_data recipes      # saved recipes
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta

from gutagent.paths import DB_PATH

SECTIONS = ["meals", "symptoms", "vitals", "labs", "meds", "sleep", "exercise", "journal", "recipes", "nutrition"]


def parse_args():
    args = sys.argv[1:]
    sections = []
    status_filter = None
    days_filter = None
    full_mode = False

    i = 0
    while i < len(args):
        if args[i] == "--status" and i + 1 < len(args):
            status_filter = args[i + 1]
            i += 2
        elif args[i] == "--days" and i + 1 < len(args):
            days_filter = int(args[i + 1])
            i += 2
        elif args[i] == "--full":
            full_mode = True
            i += 1
        else:
            sections.append(args[i])
            i += 1

    if not sections:
        sections = SECTIONS

    return sections, status_filter, days_filter, full_mode


def format_date(ts):
    """Format timestamp for display."""
    if not ts:
        return "—"
    return ts[:16] if len(ts) > 16 else ts


def show_meals(conn, days_filter, full_mode):
    print("\n━━━ Meals ━━━")

    where = ""
    params = []
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        where = "WHERE m.occurred_at >= ?"
        params = [cutoff]

    query = f"""
        SELECT m.id, m.occurred_at, m.meal_type, m.description,
               mn.calories, mn.protein, mn.carbs, mn.fat, mn.fiber,
               mn.vitamin_b12, mn.vitamin_d, mn.folate, mn.iron, mn.zinc,
               mn.magnesium, mn.calcium, mn.potassium, mn.omega_3,
               mn.vitamin_a, mn.vitamin_c
        FROM meals m
        LEFT JOIN meal_nutrition mn ON m.id = mn.meal_id
        {where}
        ORDER BY m.occurred_at DESC
    """

    meals = conn.execute(query, params).fetchall()

    if not meals:
        print("  No meals found.")
        return

    for meal in meals:
        # Basic info line
        meal_type = meal['meal_type'] or 'meal'
        cal = int(meal['calories']) if meal['calories'] else 0
        pro = int(meal['protein']) if meal['protein'] else 0

        print(f"\n[{meal['id']}] {format_date(meal['occurred_at'])} | {meal_type}")
        print(f"    {meal['description']}")

        if cal:
            carbs = int(meal['carbs']) if meal['carbs'] else 0
            fat = int(meal['fat']) if meal['fat'] else 0
            fiber = int(meal['fiber']) if meal['fiber'] else 0
            print(f"    {cal} cal | {pro}g protein | {carbs}g carbs | {fat}g fat | {fiber}g fiber")

        if full_mode:
            # Show meal items
            items = conn.execute(
                "SELECT food_name, quantity, unit FROM meal_items WHERE meal_id = ?",
                (meal['id'],)
            ).fetchall()

            if items:
                print("    Items:")
                for item in items:
                    qty = f"{item['quantity']}" if item['quantity'] else ""
                    unit = item['unit'] or ""
                    print(f"      • {item['food_name']} {qty} {unit}".rstrip())

            # Show micronutrients if present
            if meal['vitamin_b12'] or meal['iron'] or meal['calcium']:
                print("    Micronutrients:")
                micros = []
                if meal['vitamin_b12']: micros.append(f"B12: {meal['vitamin_b12']:.1f}μg")
                if meal['vitamin_d']: micros.append(f"D: {meal['vitamin_d']:.0f}IU")
                if meal['folate']: micros.append(f"Folate: {meal['folate']:.0f}μg")
                if meal['iron']: micros.append(f"Iron: {meal['iron']:.1f}mg")
                if meal['zinc']: micros.append(f"Zinc: {meal['zinc']:.1f}mg")
                if meal['magnesium']: micros.append(f"Mg: {meal['magnesium']:.0f}mg")
                if meal['calcium']: micros.append(f"Ca: {meal['calcium']:.0f}mg")
                if meal['potassium']: micros.append(f"K: {meal['potassium']:.0f}mg")
                if meal['omega_3']: micros.append(f"Ω3: {meal['omega_3']:.1f}g")
                if meal['vitamin_a']: micros.append(f"A: {meal['vitamin_a']:.0f}IU")
                if meal['vitamin_c']: micros.append(f"C: {meal['vitamin_c']:.0f}mg")
                # Print in rows of 4
                for i in range(0, len(micros), 4):
                    print(f"      {' | '.join(micros[i:i+4])}")

    print(f"\n  Total: {len(meals)} meals")


def show_symptoms(conn, days_filter):
    print("\n━━━ Symptoms ━━━")

    where = ""
    params = []
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        where = "WHERE occurred_at >= ?"
        params = [cutoff]

    rows = conn.execute(
        f"SELECT * FROM symptoms {where} ORDER BY occurred_at DESC", params
    ).fetchall()

    if not rows:
        print("  No symptoms found.")
        return

    for row in rows:
        notes = f" — {row['notes']}" if row['notes'] else ""
        print(f"[{row['id']}] {format_date(row['occurred_at'])} | {row['symptom']} (severity {row['severity']}){notes}")

    print(f"\n  Total: {len(rows)} entries")


def show_meds(conn, days_filter):
    print("\n━━━ Medications ━━━")

    where = ""
    params = []
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        where = "WHERE occurred_at >= ?"
        params = [cutoff]

    rows = conn.execute(
        f"SELECT * FROM medications {where} ORDER BY occurred_at DESC", params
    ).fetchall()

    if not rows:
        print("  No medication events found.")
        return

    for row in rows:
        dose = f" ({row['dose']})" if row['dose'] else ""
        notes = f" — {row['notes']}" if row['notes'] else ""
        print(f"[{row['id']}] {format_date(row['occurred_at'])} | {row['medication']}{dose} [{row['event_type']}]{notes}")

    print(f"\n  Total: {len(rows)} events")


def show_vitals(conn, days_filter):
    print("\n━━━ Vitals ━━━")

    where = ""
    params = []
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        where = "WHERE occurred_at >= ?"
        params = [cutoff]

    rows = conn.execute(
        f"SELECT * FROM vitals {where} ORDER BY occurred_at DESC", params
    ).fetchall()

    if not rows:
        print("  No vitals found.")
        return

    for row in rows:
        notes = f" — {row['notes']}" if row['notes'] else ""
        if row['vital_type'] == 'blood_pressure':
            hr = f" HR:{row['heart_rate']}" if row['heart_rate'] else ""
            print(f"[{row['id']}] {format_date(row['occurred_at'])} | BP: {row['systolic']}/{row['diastolic']}{hr}{notes}")
        else:
            unit = row['unit'] or ""
            print(f"[{row['id']}] {format_date(row['occurred_at'])} | {row['vital_type']}: {row['value']} {unit}{notes}")

    print(f"\n  Total: {len(rows)} readings")


def show_labs(conn, status_filter):
    print("\n━━━ Labs ━━━")

    where = ""
    params = []
    if status_filter:
        where = "WHERE status = ?"
        params = [status_filter]

    rows = conn.execute(
        f"SELECT * FROM labs {where} ORDER BY test_date DESC, test_name", params
    ).fetchall()

    if not rows:
        print("  No lab results found.")
        return

    for row in rows:
        val = f"{row['value']} {row['unit']}" if row['value'] else "—"
        ref = f" (ref: {row['reference_range']})" if row['reference_range'] else ""
        status = f" [{row['status']}]" if row['status'] else ""
        notes = f" — {row['notes']}" if row['notes'] else ""
        print(f"[{row['id']}] {row['test_date']} | {row['test_name']}: {val}{ref}{status}{notes}")

    print(f"\n  Total: {len(rows)} results")


def show_sleep(conn, days_filter):
    print("\n━━━ Sleep ━━━")

    where = ""
    params = []
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        where = "WHERE occurred_at >= ?"
        params = [cutoff]

    rows = conn.execute(
        f"SELECT * FROM sleep {where} ORDER BY occurred_at DESC", params
    ).fetchall()

    if not rows:
        print("  No sleep entries found.")
        return

    for row in rows:
        hours = f"{row['hours']} hrs" if row['hours'] else "?"
        quality = f", {row['quality']}" if row['quality'] else ""
        notes = f" — {row['notes']}" if row['notes'] else ""
        print(f"[{row['id']}] {format_date(row['occurred_at'])} | {hours}{quality}{notes}")

    print(f"\n  Total: {len(rows)} entries")


def show_exercise(conn, days_filter):
    print("\n━━━ Exercise ━━━")

    where = ""
    params = []
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        where = "WHERE occurred_at >= ?"
        params = [cutoff]

    rows = conn.execute(
        f"SELECT * FROM exercise {where} ORDER BY occurred_at DESC", params
    ).fetchall()

    if not rows:
        print("  No exercise entries found.")
        return

    for row in rows:
        duration = f" ({row['duration_minutes']} min)" if row['duration_minutes'] else ""
        notes = f" — {row['notes']}" if row['notes'] else ""
        print(f"[{row['id']}] {format_date(row['occurred_at'])} | {row['activity']}{duration}{notes}")

    print(f"\n  Total: {len(rows)} entries")


def show_journal(conn, days_filter):
    print("\n━━━ Journal ━━━")

    where = ""
    params = []
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        where = "WHERE logged_at >= ?"
        params = [cutoff]

    rows = conn.execute(
        f"SELECT * FROM journal {where} ORDER BY logged_at DESC", params
    ).fetchall()

    if not rows:
        print("  No journal entries found.")
        return

    for row in rows:
        desc = row['description'][:100] + "..." if len(row['description']) > 100 else row['description']
        print(f"[{row['id']}] {format_date(row['logged_at'])} | {desc}")

    print(f"\n  Total: {len(rows)} entries")


def show_recipes(conn, days_filter):
    print("\n━━━ Recipes ━━━")

    rows = conn.execute("SELECT * FROM recipes ORDER BY name").fetchall()

    if not rows:
        print("  No recipes saved.")
        return

    for row in rows:
        ingredients = json.loads(row['ingredients'])
        names = [i.get('name', '?') for i in ingredients]
        servings = f" ({row['servings']} servings)" if row['servings'] and row['servings'] != 1 else ""
        cal = int(row['calories']) if row['calories'] else 0
        pro = int(row['protein']) if row['protein'] else 0

        print(f"\n[{row['id']}] {row['name']}{servings}")
        print(f"    Per serving: {cal} cal, {pro}g protein")
        print(f"    Ingredients: {', '.join(names[:6])}{'...' if len(names) > 6 else ''}")

    print(f"\n  Total: {len(rows)} recipes")


def show_nutrition(conn, days_filter):
    print("\n━━━ Nutrition Summary ━━━")
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
        print(f"  No nutrition data in the last {days} days.")
        return

    d = row['days_with_data']
    print(f"Last {days} days ({d} days with data):\n")

    def avg(v):
        return round(v / d, 1) if v and d else 0

    print("Macros (daily avg):")
    print(f"  Calories:  {avg(row['total_cal']):.0f}")
    print(f"  Protein:   {avg(row['total_protein']):.0f}g")
    print(f"  Carbs:     {avg(row['total_carbs']):.0f}g")
    print(f"  Fat:       {avg(row['total_fat']):.0f}g")
    print(f"  Fiber:     {avg(row['total_fiber']):.0f}g (target: 25g)")

    print("\nMicronutrients (daily avg):")
    print(f"  B12:       {avg(row['total_b12']):.1f}μg (target: 2.4μg)")
    print(f"  Vitamin D: {avg(row['total_d']):.0f}IU (target: 600IU)")
    print(f"  Folate:    {avg(row['total_folate']):.0f}μg (target: 400μg)")
    print(f"  Iron:      {avg(row['total_iron']):.1f}mg (target: 8mg)")
    print(f"  Zinc:      {avg(row['total_zinc']):.1f}mg (target: 11mg)")
    print(f"  Magnesium: {avg(row['total_mag']):.0f}mg (target: 400mg)")
    print(f"  Calcium:   {avg(row['total_calcium']):.0f}mg (target: 1000mg)")
    print(f"  Potassium: {avg(row['total_potassium']):.0f}mg (target: 2600mg)")
    print(f"  Omega-3:   {avg(row['total_omega3']):.1f}g (target: 1.6g)")
    print(f"  Vitamin A: {avg(row['total_a']):.0f}IU (target: 3000IU)")
    print(f"  Vitamin C: {avg(row['total_c']):.0f}mg (target: 90mg)")

    # Show alerts
    print("\n━━━ Alerts ━━━")
    from gutagent.db import get_nutrition_alerts
    alerts = get_nutrition_alerts(days)
    if alerts == "No nutrition alerts":
        print("  ✓ No deficiencies or excesses detected.")
    else:
        # Strip header and print each line
        for line in alerts.split("\n"):
            if line and not line.startswith("==="):
                print(f"  ⚠️  {line}")


def main():
    sections, status_filter, days_filter, full_mode = parse_args()

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    for section in sections:
        if section == "meals":
            show_meals(conn, days_filter, full_mode)
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
            print(f"Unknown section: {section}")
            print(f"Options: {', '.join(SECTIONS)}")

    conn.close()


if __name__ == "__main__":
    main()
