"""System prompt construction for GutAgent."""

import json
import sqlite3
import os
from datetime import datetime, timedelta


def get_dynamic_context() -> str:
    """Pull recent data from all tables for the system prompt."""
    db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gutagent.db")

    if not os.path.exists(db_path):
        return "No data logged yet."

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    sections = []

    # Cutoffs in local time
    now = datetime.now()
    cutoff_7_days = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_3_days = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")

    # Medication timeline (all history — important for context)
    meds = conn.execute("""
        SELECT id, medication, event_type, occurred_at, dose, notes
        FROM medication_events
        ORDER BY occurred_at
    """).fetchall()

    if meds:
        lines = []
        for m in meds:
            dose_str = f" ({m['dose']})" if m['dose'] else ""
            notes_str = f" — {m['notes']}" if m['notes'] else ""
            lines.append(f"- [id:{m['id']}] {m['occurred_at']} [{m['event_type']}]: {m['medication']}{dose_str}{notes_str}")
        sections.append("## Medication Timeline\n" + "\n".join(lines))

    # Latest labs
    labs = conn.execute("""
        SELECT test_name, value, unit, reference_range, status, notes
        FROM labs
        WHERE test_date = (SELECT MAX(test_date) FROM labs)
        ORDER BY status, test_name
    """).fetchall()
    if labs:
        lines = []
        for lab in labs:
            val = f"{lab['value']} {lab['unit']}" if lab['value'] else "—"
            ref = f" (ref: {lab['reference_range']})" if lab['reference_range'] else ""
            flag = " ⚠" if lab['status'] in ('high', 'low', 'critical', 'abnormal') else ""
            lines.append(f"- {lab['test_name']}: {val}{ref} [{lab['status']}]{flag}")
        sections.append("## Latest Lab Results\n" + "\n".join(lines))

    # Recent vitals — last 7 days
    vitals = conn.execute("""
        SELECT id, vital_type, systolic, diastolic, heart_rate, value, unit, occurred_at, notes
        FROM vitals
        WHERE occurred_at >= ?
        ORDER BY occurred_at DESC
    """, (cutoff_7_days,)).fetchall()
    if vitals:
        lines = []
        for v in vitals:
            if v['vital_type'] == 'blood_pressure':
                lines.append(f"- [id:{v['id']}] {v['occurred_at']}: BP {v['systolic']}/{v['diastolic']} HR:{v['heart_rate']} | {v['notes'] or ''}")
            else:
                lines.append(f"- [id:{v['id']}] {v['occurred_at']}: {v['vital_type']} {v['value']} {v['unit']} | {v['notes'] or ''}")
        sections.append("## Recent Vitals (Last 7 Days)\n" + "\n".join(lines))

    # Recent meals — last 3 days (with nutrition if available)
    meals = conn.execute("""
        SELECT m.id, m.occurred_at, m.meal_type, m.description, 
               mn.calories, mn.protein, mn.carbs, mn.fat
        FROM meals m
        LEFT JOIN meal_nutrition mn ON m.id = mn.meal_id
        WHERE m.occurred_at >= ?
        ORDER BY m.occurred_at DESC
    """, (cutoff_3_days,)).fetchall()
    if meals:
        lines = []
        for m in meals:
            base = f"- [id:{m['id']}] {m['occurred_at']}: {m['meal_type'] or 'meal'} — {m['description']}"
            if m['calories']:
                base += f" [{int(m['calories'])} cal, {int(m['protein'])}g protein]"
            lines.append(base)
        sections.append("## Recent Meals (Last 3 Days)\n" + "\n".join(lines))

    # Recent symptoms — last 7 days
    symptoms = conn.execute("""
        SELECT id, occurred_at, symptom, severity, notes
        FROM symptoms
        WHERE occurred_at >= ?
        ORDER BY occurred_at DESC
    """, (cutoff_7_days,)).fetchall()
    if symptoms:
        lines = []
        for s in symptoms:
            notes_str = f" — {s['notes']}" if s['notes'] else ""
            lines.append(f"- [id:{s['id']}] {s['occurred_at']}: {s['symptom']} (severity {s['severity']}){notes_str}")
        sections.append("## Recent Symptoms (Last 7 Days)\n" + "\n".join(lines))

    # Recent sleep — last 7 days
    sleep = conn.execute("""
        SELECT id, occurred_at, hours, quality, notes
        FROM sleep
        WHERE occurred_at >= ?
        ORDER BY occurred_at DESC
    """, (cutoff_7_days,)).fetchall()
    if sleep:
        lines = []
        for s in sleep:
            hours_str = f"{s['hours']} hours" if s['hours'] else ""
            quality_str = f", {s['quality']}" if s['quality'] else ""
            notes_str = f" — {s['notes']}" if s['notes'] else ""
            lines.append(f"- [id:{s['id']}] {s['occurred_at']}: {hours_str}{quality_str}{notes_str}")
        sections.append("## Recent Sleep (Last 7 Days)\n" + "\n".join(lines))

    # Recent exercise — last 7 days
    exercise = conn.execute("""
        SELECT id, occurred_at, activity, duration_minutes, notes
        FROM exercise
        WHERE occurred_at >= ?
        ORDER BY occurred_at DESC
    """, (cutoff_7_days,)).fetchall()
    if exercise:
        lines = []
        for e in exercise:
            duration_str = f" ({e['duration_minutes']} min)" if e['duration_minutes'] else ""
            notes_str = f" — {e['notes']}" if e['notes'] else ""
            lines.append(f"- [id:{e['id']}] {e['occurred_at']}: {e['activity']}{duration_str}{notes_str}")
        sections.append("## Recent Exercise (Last 7 Days)\n" + "\n".join(lines))

    # Recent journal — last 7 days
    journal = conn.execute("""
        SELECT id, logged_at, description
        FROM journal
        WHERE logged_at >= ?
        ORDER BY logged_at DESC
    """, (cutoff_7_days,)).fetchall()
    if journal:
        lines = []
        for j in journal:
            lines.append(f"- [id:{j['id']}] {j['logged_at']}: {j['description']}")
        sections.append("## Recent Journal (Last 7 Days)\n" + "\n".join(lines))

    # Saved recipes
    recipes = conn.execute("SELECT name FROM recipes ORDER BY name").fetchall()
    if recipes:
        recipe_names = [r['name'] for r in recipes]
        sections.append("## Saved Recipes\n" + ", ".join(recipe_names))

    conn.close()
    return "\n\n".join(sections) if sections else "No data logged yet."


def get_nutrition_alerts_text() -> str:
    """Get formatted nutrition alerts for the system prompt."""
    from gutagent.db.models import get_nutrition_alerts

    try:
        alerts = get_nutrition_alerts(days=3)
    except Exception:
        return ""

    if not alerts:
        return ""

    lines = ["## Nutrition Alerts (Last 3 Days)"]
    for alert in alerts:
        nutrient_name = alert["nutrient"].replace("_", " ").title()

        if alert["type"] == "deficiency":
            severity_marker = "⚠️" if alert["severity"] == "low" else "🔴"
            lines.append(
                f"{severity_marker} Low {nutrient_name}: {alert['daily_average']}{alert['unit']}/day "
                f"({alert['percent_of_rda']}% of {alert['target']}{alert['unit']} target)"
            )
        else:  # excess
            severity_marker = "⚠️" if alert["severity"] == "high" else "🔴"
            lines.append(
                f"{severity_marker} High {nutrient_name}: {alert['daily_average']}{alert['unit']}/day "
                f"(exceeds {alert['upper_limit']}{alert['unit']} safe limit)"
            )

    return "\n".join(lines)


def build_static_system_prompt(profile: dict) -> str:
    """
    Build the STATIC portion of the system prompt.
    This part is cached and should not change between calls.
    """
    profile_text = json.dumps(profile, indent=2)

    return f"""You are GutAgent, a personalized dietary assistant for a patient with 
inflammatory bowel disease. You are warm, practical, and evidence-informed — like a 
knowledgeable friend who happens to understand IBD nutrition deeply.

## Patient's Medical Profile
{profile_text}

## Core Behavior

PROACTIVE LOGGING:
- When the user mentions eating ANYTHING, call log_meal immediately — even casual mentions
- Parse meals into individual food items with estimated nutrition (calories, protein, carbs, fat, fiber, and micronutrients)
- Use your knowledge to estimate nutrition for any food, including Indian cuisine
- Check for saved recipes first; if a dish matches a saved recipe, use recipe_name parameter
- When the user mentions ANY physical or mental symptom, call log_symptom immediately
- When the user mentions ANY medication change, call log_medication_event immediately
- When the user mentions ANY vital reading, call log_vital immediately
- When the user mentions sleep (hours or quality), call log_sleep
- When the user mentions exercise or physical activity, call log_exercise
- You don't need to ask permission to log. Just do it and confirm briefly.
- Journal entries are only logged when the user explicitly wants to note something

NUTRITION TRACKING:
- Estimate nutrition directly using your knowledge — no external lookup needed
- Track both macros (calories, protein, carbs, fat, fiber) and micronutrients (B12, D, folate, iron, zinc, magnesium, calcium, potassium, omega-3, vitamin A, vitamin C)
- Provide reasonable estimates even for regional/ethnic foods
- Example: "2 rotis with dal" → roti (120 cal, 3g protein, 2mg iron each), dal (150 cal, 10g protein, 3mg iron per cup)
- Include brief nutrition summary when logging meals (e.g., "~450 cal, 32g protein")
- When discussing nutrition, proactively mention any alerts if relevant
- Offer to save recipes when the user describes dishes they eat often

SEVERITY — ALWAYS ASK:
- Never guess symptom severity. Always ask the patient to rate 1-10.

SEPARATE CONCERNS:
- If the user mentions a meal AND a symptom in the same message, make separate tool calls for each.
- If the user mentions a medication change AND a symptom, make separate tool calls for each.

DIETARY GUIDANCE:
- Read the patient's profile carefully — respect their known triggers, safe foods, and preferences
- Base all meal suggestions on their safe foods list and preferred cooking style
- Never suggest foods from their known triggers lists
- Keep suggestions practical and simple

COMMUNICATION STYLE:
- Concise and practical, not lecturing
- Honest about uncertainty — "based on your pattern" not "definitely"
- Don't repeat the patient's full medical history back to them
- When logging meals/symptoms, confirm briefly and move on
- Include brief nutrition summary when logging meals (e.g., "~450 cal, 32g protein")

PATTERN AWARENESS:
- If the patient reports a symptom, check recent meals using query_logs
- Note correlations between medication changes and symptoms/vitals
- Flag potential new triggers or confirm known ones
- Consider nutrition gaps when interpreting symptoms (fatigue + low B12, etc.)

ANALYZING TRENDS — ALWAYS CHECK BASELINE:
- When analyzing ANY trend (BP, symptoms, weight, sleep, etc.), don't just show recent data — establish what "normal" looks like for this patient
- Use query_logs to pull historical data to find the baseline pattern
- If the patient corrects your analysis, acknowledge specifically what you missed and why

NEVER FABRICATE PATIENT DATA:
- Never invent or assume medications, diagnoses, lab results, or any details about THIS patient.
- Only state what is explicitly in the patient's profile or database records.
- If unsure whether the patient is on a medication or has a condition, ask — don't assume.
- You CAN and SHOULD use your general medical knowledge to explain conditions, suggest questions for doctors, interpret patterns, and provide dietary guidance.

CORRECTIONS:
- Entry IDs are shown in square brackets like [id:47] in the recent data below.
- If the user asks to correct or delete an entry, use correct_log with the correct entry_id.
- Never guess IDs — only use IDs you can see in the recent data.
- For entries older than the recent data window, use query_logs with query_type="date_search", the specific date (YYYY-MM-DD), and table (meals, symptoms, vitals, etc.) to find the entry and its ID.
- Example: "correct my lunch from March 5th" → first call query_logs with query_type="date_search", date="2026-03-05", table="meals" to get the entry ID, then use correct_log.
- Never create a new entry when a correction is needed.

SAVING SUGGESTIONS:
- When you suggest medical tests, deficiency checks, or important items to discuss with a doctor, offer to save them if the user seems interested.
- If the user says "save that", "remember that", or "add that to my list", use update_profile to save to suggestions.tests_to_request or suggestions.to_discuss_with_doctor.
- Don't offer to save routine food suggestions — only clinically relevant recommendations.

RECIPES:
- When the user describes a dish they make often, offer to save it as a recipe
- Saved recipes enable accurate nutrition and spice tracking for repeated meals
- When logging a meal that matches a saved recipe name, use the recipe_name parameter
- Check for saved recipes when logging meals that match recipe names
"""


def build_dynamic_context() -> str:
    """
    Build the DYNAMIC portion of the system prompt.
    This changes between calls and is NOT cached.
    """
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    dynamic_context = get_dynamic_context()
    nutrition_alerts = get_nutrition_alerts_text()

    return f"""## Current Date and Time
{today}

## Current Data from Patient's Records
{dynamic_context}

{nutrition_alerts}"""


def build_system_prompt(profile: dict) -> str:
    """
    Build the complete system prompt (for backward compatibility).
    Prefer using build_static_system_prompt() + build_dynamic_context() separately
    for prompt caching.
    """
    return build_static_system_prompt(profile) + "\n\n" + build_dynamic_context()
